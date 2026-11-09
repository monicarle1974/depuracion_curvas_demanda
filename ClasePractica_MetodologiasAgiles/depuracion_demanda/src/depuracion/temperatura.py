"""H2 — Temperatura desde la base INIA (SQLite) (RF-006..RF-008).

Esquema real de ``inia.sqlite`` (inspeccionado en T010):

* ``Estaciones(Id, Nombre, Coord_x, Coord_y)``
* ``Medidores(Id, Id_estacion, Nombre, Tipo, ...)`` — termómetros: ``Tipo LIKE 'Term%'``,
  nombres ``t1``, ``t2``, ``t3``.
* ``Medidas(Id_medidor, Fecha_hora, Valor)`` — ``Fecha_hora`` en segundos epoch (UTC),
  resolución de 10 minutos.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

TABLAS_REQUERIDAS = {"Estaciones", "Medidores", "Medidas"}


class FuenteTemperaturaNoDisponible(RuntimeError):
    """La base de temperaturas no existe, no se puede abrir o no tiene el esquema esperado."""


class EstacionInexistente(LookupError):
    """La estación INIA no existe o no tiene termómetros."""


def abrir_inia(ruta: Path | str | None) -> sqlite3.Connection:
    """Abre ``inia.sqlite`` en modo solo lectura (RNF-006) y valida su esquema (H2.4)."""
    if ruta is None or not Path(ruta).is_file():
        raise FuenteTemperaturaNoDisponible(f"No se encuentra la base de temperaturas: {ruta}")
    uri = Path(ruta).resolve().as_uri() + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        con.text_factory = lambda b: b.decode("utf-8", errors="replace")
        tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error as exc:
        raise FuenteTemperaturaNoDisponible(f"No se puede abrir la base de temperaturas: {exc}") from exc
    faltan = TABLAS_REQUERIDAS - tablas
    if faltan:
        con.close()
        raise FuenteTemperaturaNoDisponible(f"La base de temperaturas no tiene las tablas: {', '.join(sorted(faltan))}")
    return con


def distancia_km(lat1, lon1, lat2, lon2) -> float:
    """Distancia de gran círculo (haversine) en km."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat, dlon = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return float(6371.0 * 2 * np.arcsin(np.sqrt(a)))


def inia_cercanas(con: sqlite3.Connection, lat: float, lon: float, cfg: dict) -> list[tuple[str, float]]:
    """Estaciones INIA con termómetro ordenadas por distancia: [(nombre, km)] (C4).

    En ``inia.sqlite``, ``Coord_x`` es la longitud y ``Coord_y`` la latitud.
    """
    filas = con.execute(
        "SELECT e.Nombre, e.Coord_y, e.Coord_x FROM Estaciones e WHERE e.Coord_x IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM Medidores m WHERE m.Id_estacion = e.Id AND m.Tipo LIKE ?)",
        (cfg["inia"]["tipo_medidor"],),
    ).fetchall()
    return sorted(((n, distancia_km(lat, lon, la, lo)) for n, la, lo in filas), key=lambda x: (x[1], x[0]))


def _termometros(con: sqlite3.Connection, estacion_inia: str, cfg: dict) -> list[tuple[int, str]]:
    filas = con.execute(
        "SELECT m.Id, m.Nombre FROM Medidores m JOIN Estaciones e ON e.Id = m.Id_estacion "
        "WHERE e.Nombre = ? AND m.Tipo LIKE ?",
        (estacion_inia, cfg["inia"]["tipo_medidor"]),
    ).fetchall()
    if not filas:
        raise EstacionInexistente(f"La estación INIA '{estacion_inia}' no existe o no tiene termómetros")
    preferidos = cfg["inia"]["medidores_preferidos"]
    orden = {n: i for i, n in enumerate(preferidos)}
    return sorted(filas, key=lambda f: (orden.get(f[1], len(orden)), f[1]))


def leer_temperatura(con: sqlite3.Connection, estacion_inia: str, inicio: pd.Timestamp, fin: pd.Timestamp,
                     cfg: dict) -> pd.Series:
    """Temperatura cruda de la estación INIA en [inicio, fin].

    Se toma el termómetro preferido (``t1``) y sus faltantes se completan con los
    demás termómetros de la misma estación. Los valores fuera de ``rango_valido``
    se descartan.
    """
    medidores = _termometros(con, estacion_inia, cfg)
    margen = pd.Timedelta("1D")
    desde = int((inicio - margen).tz_convert("UTC").timestamp())
    hasta = int((fin + margen).tz_convert("UTC").timestamp())
    lo, hi = cfg["inia"]["rango_valido"]
    combinada: pd.Series | None = None
    for id_medidor, _nombre in medidores:
        filas = con.execute(
            "SELECT Fecha_hora, Valor FROM Medidas WHERE Id_medidor = ? AND Fecha_hora BETWEEN ? AND ? ORDER BY Fecha_hora",
            (id_medidor, desde, hasta),
        ).fetchall()
        if not filas:
            continue
        datos = np.array(filas, dtype=float)
        indice = pd.to_datetime(datos[:, 0], unit="s").tz_localize(cfg["inia"]["zona_horaria_origen"])
        serie = pd.Series(datos[:, 1], index=indice.tz_convert(cfg["zona_horaria"]))
        serie = serie[~serie.index.duplicated()].where(lambda s: s.between(lo, hi))
        combinada = serie if combinada is None else combinada.combine_first(serie)
    if combinada is None:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([], tz=cfg["zona_horaria"]))
    return combinada.sort_index().rename("temperatura")


def _resolucion(serie: pd.Series) -> pd.Timedelta | None:
    if len(serie) < 2:
        return None
    return pd.Series(serie.index).diff().dropna().median()


def alinear(temp: pd.Series, indice: pd.DatetimeIndex, frecuencia: str, modo: str) -> pd.Series:
    """Alinea la temperatura con el índice de la demanda (RF-008, H2.2).

    * ``igual``: unión exacta por marca de tiempo.
    * ``media_intervalo``: media de las lecturas dentro de cada intervalo de demanda.
    * ``interpolar``: interpolación temporal lineal.
    * ``media_diaria``: media del día, repetida en cada intervalo.
    * ``auto``: ``media_intervalo`` si la temperatura es más fina o igual que la demanda;
      ``interpolar`` si es más gruesa.
    """
    temp = temp.dropna()
    if temp.empty:
        return pd.Series(np.nan, index=indice, name="temperatura")
    freq = pd.Timedelta(frecuencia)
    if modo == "auto":
        res = _resolucion(temp)
        modo = "media_intervalo" if res is not None and res <= freq else "interpolar"

    if modo == "igual":
        out = temp.reindex(indice)
    elif modo == "media_intervalo":
        utc = temp.tz_convert("UTC")
        medias = utc.groupby(utc.index.floor(freq)).mean()
        out = medias.reindex(indice.tz_convert("UTC"))
        out.index = indice
    elif modo == "interpolar":
        union = temp.index.union(indice)
        out = temp.reindex(union).interpolate(method="time", limit_area="inside").reindex(indice)
    elif modo == "media_diaria":
        dias = temp.groupby(temp.index.date).mean()
        out = pd.Series(dias.reindex(indice.date).to_numpy(), index=indice)
    else:
        raise ValueError(f"modo de alineación desconocido: {modo}")
    return out.rename("temperatura")


def completar_faltantes(temp: pd.Series, respaldo: pd.Series | None, max_hueco: str,
                        frecuencia: str) -> tuple[pd.Series, pd.Series]:
    """Completa la temperatura faltante (H2.3).

    1) interpola huecos de hasta ``max_hueco``; 2) usa la estación de respaldo;
    3) lo que quede se marca como faltante. Devuelve (temperatura, origen_temperatura).
    """
    origen = pd.Series(np.where(temp.notna(), "inia", "faltante"), index=temp.index, dtype=object)
    limite = max(int(pd.Timedelta(max_hueco) / pd.Timedelta(frecuencia)), 0)
    if limite > 0 and temp.isna().any():
        faltante = temp.isna()
        grupo = (faltante != faltante.shift()).cumsum()
        largo = faltante.groupby(grupo).transform("sum")
        interp = temp.interpolate(method="time", limit_area="inside")
        usar = faltante & (largo <= limite) & interp.notna()
        temp = temp.where(~usar, interp)
        origen[usar] = "interpolada"
    if respaldo is not None and temp.isna().any():
        usar = temp.isna() & respaldo.reindex(temp.index).notna()
        temp = temp.where(~usar, respaldo.reindex(temp.index))
        origen[usar] = "respaldo"
    return temp, origen


def agregar_temperatura(df: pd.DataFrame, estacion: str, con: sqlite3.Connection, cfg: dict) -> pd.DataFrame:
    """Agrega ``temperatura``, ``origen_temperatura`` y ``temp_faltante`` (RF-006, RF-007)."""
    est_cfg = cfg["mapeo_estaciones"][estacion]
    inicio, fin = df.index.min(), df.index.max()

    def obtener(nombre_inia):
        cruda = leer_temperatura(con, nombre_inia, inicio, fin, cfg)
        return alinear(cruda, df.index, cfg["frecuencia"], cfg["alineacion"])

    principal = obtener(est_cfg["inia"])
    respaldo = obtener(est_cfg["inia_respaldo"]) if est_cfg.get("inia_respaldo") else None
    temp, origen = completar_faltantes(principal, respaldo, cfg["max_hueco_temp"], cfg["frecuencia"])

    df = df.copy()
    df["temperatura"] = temp.to_numpy()
    df["origen_temperatura"] = origen.to_numpy()
    df["temp_faltante"] = df["temperatura"].isna()
    return df
