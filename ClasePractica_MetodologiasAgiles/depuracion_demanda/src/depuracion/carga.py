"""H1 — Carga y validación de archivos de demanda (RF-001..RF-004)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

EXTENSIONES = {".csv", ".xlsx", ".xls"}
EXTENSIONES_SQLITE = {".sqlite", ".sqlite3", ".db"}
TABLAS_CURVAS = {"ESTACIONES", "POTENCIA_ESTACION"}


class ErrorArchivo(ValueError):
    """Archivo de demanda inválido."""


class FuenteDemandaNoDisponible(RuntimeError):
    """La base de curvas de demanda no existe o no tiene el esquema esperado."""


@dataclass
class ArchivoOrigen:
    """Datos para reescribir la salida con el mismo formato que la entrada."""

    ruta: Path
    columnas: list[str]
    estaciones: list[str]
    inicio: pd.Timestamp
    fin: pd.Timestamp
    fechas_con_zona: bool
    extras: pd.DataFrame | None = None  # columnas adicionales, indexadas por (estacion, fecha_hora)


@dataclass
class ResultadoCarga:
    series: dict[str, pd.DataFrame] = field(default_factory=dict)
    rechazados: list[tuple[str, str]] = field(default_factory=list)
    archivos: list[ArchivoOrigen] = field(default_factory=list)
    resumen: pd.DataFrame = field(default_factory=pd.DataFrame)
    fuente: str = "archivos"  # "archivos" | "sqlite"
    coordenadas: dict[str, tuple[float, float]] = field(default_factory=dict)  # (lat, lon)


def _leer_crudo(ruta: Path) -> pd.DataFrame:
    if ruta.suffix.lower() == ".csv":
        return pd.read_csv(ruta, sep=None, engine="python", dtype=str, keep_default_na=False)
    return pd.read_excel(ruta, dtype=str, keep_default_na=False)


def _normalizar_zona(fechas: pd.Series, zona: str) -> tuple[pd.Series, bool]:
    """Convierte a la zona del proceso. Las horas ambiguas por cambio de horario se infieren."""
    texto = fechas.astype(str).str.strip()
    con_zona = texto.str.contains(r"(?:[+-]\d{2}:?\d{2}|Z)$", regex=True).all()
    if con_zona:
        return pd.to_datetime(texto, utc=True, format="ISO8601").dt.tz_convert(zona), True
    ingenuas = pd.to_datetime(texto, format="mixed", dayfirst=False)
    try:
        locales = ingenuas.dt.tz_localize(zona, ambiguous="infer", nonexistent="shift_forward")
    except Exception:  # noqa: BLE001 - horas ambiguas no inferibles: se toma la primera ocurrencia
        locales = ingenuas.dt.tz_localize(zona, ambiguous=np.ones(len(ingenuas), dtype=bool), nonexistent="shift_forward")
    return locales, False


def leer_archivo(ruta: Path, cfg: dict) -> tuple[pd.DataFrame, ArchivoOrigen]:
    """Lee y valida un archivo. Devuelve filas normalizadas (estacion, fecha_hora, demanda)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() not in EXTENSIONES:
        raise ErrorArchivo(f"extensión no soportada '{ruta.suffix}'")
    try:
        crudo = _leer_crudo(ruta)
    except Exception as exc:  # noqa: BLE001
        raise ErrorArchivo(f"no se pudo leer: {exc}") from exc

    col = cfg["columnas"]
    faltan = [c for c in (col["estacion"], col["fecha_hora"], col["demanda"]) if c not in crudo.columns]
    if faltan:
        raise ErrorArchivo(f"faltan columnas obligatorias: {', '.join(faltan)}")
    if crudo.empty:
        raise ErrorArchivo("el archivo no contiene registros")

    df = pd.DataFrame({
        "estacion": crudo[col["estacion"]].astype(str).str.strip(),
        "fecha_hora": crudo[col["fecha_hora"]],
        "demanda": crudo[col["demanda"]].astype(str).str.strip().str.replace(",", ".", regex=False),
    })
    try:
        df["fecha_hora"], con_zona = _normalizar_zona(df["fecha_hora"], cfg["zona_horaria"])
    except (ValueError, TypeError) as exc:
        raise ErrorArchivo(f"columna '{col['fecha_hora']}' con fechas inválidas") from exc

    vacias = df["demanda"].isin(["", "nan", "NaN", "NA"])
    numerica = pd.to_numeric(df["demanda"].where(~vacias), errors="coerce")
    no_numericas = numerica.isna() & ~vacias
    if no_numericas.any():
        ejemplo = df.loc[no_numericas, "demanda"].iloc[0]
        raise ErrorArchivo(f"columna '{col['demanda']}' con valores no numéricos (p. ej. {ejemplo!r})")
    df["demanda"] = numerica.astype(float)

    otras = [c for c in crudo.columns if c not in (col["estacion"], col["fecha_hora"], col["demanda"])]
    extras = None
    if otras:
        extras = crudo[otras].copy()
        extras.index = pd.MultiIndex.from_arrays([df["estacion"], df["fecha_hora"]])
        extras = extras[~extras.index.duplicated()]

    origen = ArchivoOrigen(
        extras=extras,
        ruta=ruta,
        columnas=list(crudo.columns),
        estaciones=sorted(df["estacion"].unique()),
        inicio=df["fecha_hora"].min(),
        fin=df["fecha_hora"].max(),
        fechas_con_zona=con_zona,
    )
    return df, origen


def resolver_duplicados(df: pd.DataFrame, politica: str) -> tuple[pd.DataFrame, int]:
    """Aplica la política de duplicados por marca de tiempo (H1.3)."""
    n_dup = int(df["fecha_hora"].duplicated(keep=False).sum())
    if n_dup == 0:
        return df.set_index("fecha_hora").sort_index(), 0
    agrupado = df.groupby("fecha_hora", sort=True)["demanda"]
    demanda = {"primero": agrupado.first, "ultimo": agrupado.last, "promedio": agrupado.mean}[politica]()
    return demanda.to_frame("demanda"), n_dup


def regularizar(serie: pd.DataFrame, frecuencia: str) -> pd.DataFrame:
    """Reindexa a frecuencia fija y marca los huecos (H1.4)."""
    freq = pd.Timedelta(frecuencia)
    indice_utc = serie.index.tz_convert("UTC")
    completo = pd.date_range(indice_utc.min().floor(freq), indice_utc.max().ceil(freq), freq=freq)
    completo = completo.tz_convert(serie.index.tz)
    serie = serie.copy()
    serie.index = indice_utc.tz_convert(serie.index.tz)
    serie = serie[~serie.index.duplicated()]
    res = serie.reindex(completo)
    res.index.name = "fecha_hora"
    res["es_hueco"] = res["demanda"].isna()
    return res


def _filtrar_periodo(serie: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    periodo = cfg.get("periodo") or {}
    zona = cfg["zona_horaria"]
    if periodo.get("desde"):
        serie = serie[serie["fecha_hora"] >= pd.Timestamp(periodo["desde"]).tz_localize(zona)]
    if periodo.get("hasta"):
        fin = pd.Timestamp(periodo["hasta"]).tz_localize(zona) + pd.Timedelta("1D")
        serie = serie[serie["fecha_hora"] < fin]
    return serie


def _construir_series(res: ResultadoCarga, partes: list[pd.DataFrame], cfg: dict) -> ResultadoCarga:
    if not partes:
        return res
    todo = pd.concat(partes, ignore_index=True)
    filas = []
    for estacion, grupo in todo.groupby("estacion", sort=True):
        if grupo.empty:
            continue
        serie, n_dup = resolver_duplicados(grupo[["fecha_hora", "demanda"]], cfg["duplicados"])
        serie = regularizar(serie, cfg["frecuencia"])
        serie.insert(0, "estacion", estacion)
        res.series[estacion] = serie
        filas.append({
            "estacion": estacion,
            "inicio": serie.index.min(),
            "fin": serie.index.max(),
            "registros": len(serie),
            "duplicados": n_dup,
            "huecos": int(serie["es_hueco"].sum()),
        })
    res.resumen = pd.DataFrame(filas)
    return res


def epoch_reloj_a_local(epoch: np.ndarray, cambio: np.ndarray, cfg: dict) -> pd.DatetimeIndex:
    """Convierte ``Fecha_hora`` de BD_CurvasDemanda (hora de reloj local como epoch) a hora local real.

    El desfase respecto a UTC es ``desfase_utc_horas`` (−3 en Uruguay) o, si
    ``Cambio_horario`` ≠ 0, ``desfase_cambio_horario_horas`` (−2, horario de verano).
    """
    fs = cfg["fuente_sqlite"]
    desfase = np.where(np.asarray(cambio) != 0, fs["desfase_cambio_horario_horas"], fs["desfase_utc_horas"])
    utc = pd.to_datetime(np.asarray(epoch, dtype=np.int64) - desfase.astype(np.int64) * 3600, unit="s", utc=True)
    return pd.DatetimeIndex(utc).tz_convert(cfg["zona_horaria"])


def local_a_epoch_reloj(indice: pd.DatetimeIndex, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Inversa de :func:`epoch_reloj_a_local`: devuelve (Fecha_hora, Cambio_horario)."""
    fs = cfg["fuente_sqlite"]
    desfase_h = np.array([t.utcoffset().total_seconds() / 3600 for t in indice])
    cambio = (desfase_h == fs["desfase_cambio_horario_horas"]).astype(int)
    epoch_utc = (indice.tz_convert("UTC") - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")
    return (np.asarray(epoch_utc) + (desfase_h * 3600).astype(np.int64)), cambio


def cargar_sqlite(ruta: Path, cfg: dict, estaciones: list[str] | None = None) -> ResultadoCarga:
    """Carga las curvas de demanda desde BD_CurvasDemanda.sqlite (solo lectura)."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FuenteDemandaNoDisponible(f"No se encuentra la base de curvas de demanda: {ruta}")
    try:
        con = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)
        tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error as exc:
        raise FuenteDemandaNoDisponible(f"No se puede abrir la base de curvas de demanda: {exc}") from exc
    try:
        if not TABLAS_CURVAS <= tablas:
            raise FuenteDemandaNoDisponible(
                f"La base de curvas de demanda no tiene las tablas: {', '.join(sorted(TABLAS_CURVAS - tablas))}")
        res = ResultadoCarga(fuente="sqlite")
        catalogo = con.execute(
            "SELECT Id_estacion, Codigo_estacion, Coord_latitud, Coord_longitud FROM ESTACIONES ORDER BY Codigo_estacion"
        ).fetchall()
        pedidas = set(estaciones or [])
        desconocidas = pedidas - {c for _, c, _, _ in catalogo}
        res.rechazados += [(e, "estación inexistente en la base de curvas de demanda") for e in sorted(desconocidas)]

        periodo = cfg.get("periodo") or {}
        # Margen de ±1 día en epoch de reloj; el filtro exacto se hace en hora local.
        desde = int(pd.Timestamp(periodo["desde"]).timestamp()) - 86400 if periodo.get("desde") else -(2**62)
        hasta = int(pd.Timestamp(periodo["hasta"]).timestamp()) + 2 * 86400 if periodo.get("hasta") else 2**62

        partes = []
        for id_est, codigo, lat, lon in catalogo:
            if pedidas and codigo not in pedidas:
                continue
            filas = con.execute(
                "SELECT Fecha_hora, Valor, Cambio_horario FROM POTENCIA_ESTACION "
                "WHERE Id_estacion = ? AND Fecha_hora BETWEEN ? AND ? ORDER BY Fecha_hora",
                (id_est, desde, hasta),
            ).fetchall()
            if not filas:
                res.rechazados.append((codigo, "sin datos en el periodo"))
                continue
            datos = np.array(filas, dtype=float)
            df = pd.DataFrame({
                "estacion": codigo,
                "fecha_hora": epoch_reloj_a_local(datos[:, 0], np.nan_to_num(datos[:, 2]), cfg),
                "demanda": datos[:, 1],
            })
            df = _filtrar_periodo(df, cfg)
            if df.empty:
                res.rechazados.append((codigo, "sin datos en el periodo"))
                continue
            partes.append(df)
            if lat is not None and lon is not None:
                res.coordenadas[codigo] = (float(lat), float(lon))
    finally:
        con.close()
    return _construir_series(res, partes, cfg)


def cargar_entrada(cfg: dict, estaciones: list[str] | None = None) -> ResultadoCarga:
    """Carga la demanda desde un directorio de archivos o desde una base SQLite (según ``entrada``)."""
    estaciones = estaciones or cfg.get("estaciones") or None
    entrada = Path(cfg["entrada"])
    if entrada.suffix.lower() in EXTENSIONES_SQLITE:
        return cargar_sqlite(entrada, cfg, estaciones)
    res = cargar_directorio(entrada, cfg)
    if estaciones:
        res.series = {k: v for k, v in res.series.items() if k in estaciones}
        if not res.resumen.empty:
            res.resumen = res.resumen[res.resumen["estacion"].isin(estaciones)].reset_index(drop=True)
    return res


def cargar_directorio(directorio: Path, cfg: dict) -> ResultadoCarga:
    """Carga todos los archivos de demanda del directorio (H1.1, H1.2)."""
    directorio = Path(directorio)
    res = ResultadoCarga()
    if not directorio.is_dir():
        res.rechazados.append((str(directorio), "el directorio de entrada no existe"))
        return res

    partes: list[pd.DataFrame] = []
    for ruta in sorted(p for p in directorio.iterdir() if p.is_file()):
        if ruta.name.startswith((".", "~$")):
            continue
        try:
            df, origen = leer_archivo(ruta, cfg)
        except ErrorArchivo as exc:
            res.rechazados.append((ruta.name, str(exc)))
            continue
        partes.append(_filtrar_periodo(df, cfg))
        res.archivos.append(origen)
    return _construir_series(res, partes, cfg)
