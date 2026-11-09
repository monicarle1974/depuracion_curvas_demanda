"""Variables de calendario y feriados (RF-005, RN-04, C8)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ESTACIONES_ANIO = ["verano", "otono", "invierno", "primavera"]
TIPOS_DIA = ["laborable", "sabado", "domingo_feriado"]

# Estación del año en el hemisferio NORTE; en el sur se desplaza dos posiciones.
_METEOROLOGICA_NORTE = {12: 3, 1: 3, 2: 3, 3: 0, 4: 0, 5: 0, 6: 1, 7: 1, 8: 1, 9: 2, 10: 2, 11: 2}
# 0=primavera 1=verano 2=otoño 3=invierno (norte)
_NOMBRES_NORTE = ["primavera", "verano", "otono", "invierno"]
_OPUESTA = {"primavera": "otono", "verano": "invierno", "otono": "primavera", "invierno": "verano"}


class ErrorFeriados(ValueError):
    """El archivo de feriados no existe o no se puede leer."""


def estacion_del_anio(fechas: pd.DatetimeIndex, hemisferio: str = "sur", criterio: str = "meteorologico") -> np.ndarray:
    """Devuelve la estación del año para cada fecha (RN-04)."""
    fechas = pd.DatetimeIndex(fechas)
    if criterio == "meteorologico":
        idx = np.array([_METEOROLOGICA_NORTE[m] for m in fechas.month])
    else:  # astronómico aproximado: 21/3, 21/6, 23/9, 21/12
        md = fechas.month * 100 + fechas.day
        idx = np.select([(md >= 321) & (md < 621), (md >= 621) & (md < 923), (md >= 923) & (md < 1221)], [0, 1, 2], default=3)
    nombres = np.array(_NOMBRES_NORTE)[idx]
    if hemisferio == "sur":
        nombres = np.array([_OPUESTA[n] for n in nombres])
    return nombres


def _es_formato_tipos_dia(ruta: Path) -> bool:
    with open(ruta, encoding="latin-1") as f:
        for linea in f:
            linea = linea.split("//", 1)[0].strip()
            if linea:
                return linea.upper().startswith("TIPOS_DIA_SEMANA")
    return False


def cargar_tipos_dia(ruta: Path | str, margen_anios: int = 10) -> tuple[pd.DataFrame, list[str]]:
    """Lee el archivo de feriados del negocio en formato ``tiposDeDia.txt``.

    * ``//`` inicia un comentario (también al final de una línea).
    * ``TIPOS_DIA_SEMANA``: códigos de DO..SA (informativo).
    * ``FERIADOS_COMUNES CANTIDAD n`` seguido de ``n`` líneas ``mes día``: feriados fijos,
      que se expanden a todos los años desde ``(primer año del archivo − margen)`` hasta el último.
    * ``año mes día descripción``: días especiales (Carnaval, Turismo, …).
    """
    errores: list[str] = []
    fijos: list[tuple[int, int, int]] = []
    especiales: list[tuple[pd.Timestamp, str]] = []
    pendientes_fijos = 0
    with open(ruta, encoding="utf-8", errors="replace") as f:
        lineas = f.read().replace("�", "").splitlines()
    for n, cruda in enumerate(lineas, start=1):
        linea = cruda.split("//", 1)[0].strip()
        if not linea:
            continue
        partes = linea.split()
        clave = partes[0].upper()
        if clave == "TIPOS_DIA_SEMANA":
            continue
        if clave == "FERIADOS_COMUNES":
            try:
                pendientes_fijos = int(partes[-1])
            except ValueError:
                errores.append(f"línea {n}: cantidad de feriados comunes inválida")
            continue
        try:
            numeros = [int(p) for p in partes[:3] if p.lstrip("-").isdigit()]
            if pendientes_fijos > 0:
                mes, dia = numeros[0], numeros[1]
                pd.Timestamp(year=2000, month=mes, day=dia)  # valida (2000 es bisiesto)
                fijos.append((mes, dia, n))
                pendientes_fijos -= 1
            else:
                anio, mes, dia = numeros[0], numeros[1], numeros[2]
                descripcion = " ".join(partes[3:]) or "dia especial"
                especiales.append((pd.Timestamp(year=anio, month=mes, day=dia), descripcion))
        except (IndexError, ValueError):
            errores.append(f"línea {n}: no se reconoce {cruda.strip()!r}")
    if pendientes_fijos > 0:
        errores.append(f"faltan {pendientes_fijos} feriados comunes respecto de la CANTIDAD declarada")

    anios = [t.year for t, _ in especiales] or [pd.Timestamp.now().year]
    filas, vistos = [], set()
    for anio in range(min(anios) - margen_anios, max(anios) + 1):
        for mes, dia, _ in fijos:
            try:
                fecha = pd.Timestamp(year=anio, month=mes, day=dia).date()
            except ValueError:
                continue
            filas.append({"fecha": fecha, "descripcion": f"feriado fijo {dia:02d}/{mes:02d}", "estacion": ""})
            vistos.add(fecha)
    for fecha, descripcion in especiales:
        if fecha.date() in vistos:
            errores.append(f"{fecha.date()}: día especial duplicado")
            continue
        vistos.add(fecha.date())
        filas.append({"fecha": fecha.date(), "descripcion": descripcion, "estacion": ""})
    df = pd.DataFrame(filas, columns=["fecha", "descripcion", "estacion"])
    return df.sort_values("fecha").reset_index(drop=True), errores


def cargar_feriados(ruta: Path | str | None) -> tuple[pd.DataFrame, list[str]]:
    """Lee el archivo de feriados proporcionado por el negocio.

    Acepta dos formatos:

    * ``tiposDeDia.txt`` del negocio (ver :func:`cargar_tipos_dia`).
    * CSV con columnas ``fecha`` (AAAA-MM-DD), ``descripcion`` y ``estacion`` (opcional).

    Devuelve los feriados válidos y la lista de errores de filas omitidas.
    """
    if ruta is None or not Path(ruta).is_file():
        raise ErrorFeriados(f"No se encuentra el archivo de feriados: {ruta}")
    if _es_formato_tipos_dia(Path(ruta)):
        return cargar_tipos_dia(ruta)
    try:
        crudo = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001
        raise ErrorFeriados(f"No se pudo leer el archivo de feriados: {exc}") from exc

    faltan = {"fecha", "descripcion"} - set(crudo.columns)
    if faltan:
        raise ErrorFeriados(f"Al archivo de feriados le faltan columnas: {', '.join(sorted(faltan))}")
    if "estacion" not in crudo.columns:
        crudo["estacion"] = ""

    errores: list[str] = []
    validos = []
    vistos: set[tuple[str, str]] = set()
    for n, fila in enumerate(crudo.itertuples(index=False), start=2):
        fecha = pd.to_datetime(fila.fecha.strip(), format="%Y-%m-%d", errors="coerce")
        if pd.isna(fecha):
            errores.append(f"línea {n}: fecha inválida {fila.fecha!r}")
            continue
        if not fila.descripcion.strip():
            errores.append(f"línea {n}: falta la descripción")
            continue
        clave = (fecha.strftime("%Y-%m-%d"), fila.estacion.strip())
        if clave in vistos:
            errores.append(f"línea {n}: feriado duplicado {clave[0]}")
            continue
        vistos.add(clave)
        validos.append({"fecha": fecha.date(), "descripcion": fila.descripcion.strip(), "estacion": fila.estacion.strip()})
    return pd.DataFrame(validos, columns=["fecha", "descripcion", "estacion"]), errores


def fechas_feriado(feriados: pd.DataFrame, estacion: str) -> set:
    if feriados is None or feriados.empty:
        return set()
    aplica = (feriados["estacion"] == "") | (feriados["estacion"] == estacion)
    return set(feriados.loc[aplica, "fecha"])


def agregar_calendario(df: pd.DataFrame, estacion: str, feriados: pd.DataFrame | None, cfg: dict) -> pd.DataFrame:
    """Agrega dia_semana, hora, estacion_anio, es_feriado y tipo_dia (RF-005)."""
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    df["dia_semana"] = idx.day_of_week
    df["hora"] = idx.hour
    df["estacion_anio"] = estacion_del_anio(idx, cfg["hemisferio"], cfg["criterio_estacion"])
    feriados_est = fechas_feriado(feriados, estacion)
    df["es_feriado"] = np.array([d in feriados_est for d in idx.date], dtype=bool)
    df["tipo_dia"] = np.where(
        df["es_feriado"] | (df["dia_semana"] == 6), "domingo_feriado",
        np.where(df["dia_semana"] == 5, "sabado", "laborable"),
    )
    return df
