"""Orquestación del proceso en el orden de RN-00 (RF-004, RF-022)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .calendario import ErrorFeriados, agregar_calendario, cargar_feriados
from .carga import FuenteDemandaNoDisponible, ResultadoCarga, cargar_entrada
from .config import DEFAULTS_ESTACION
from .deteccion import detectar_outliers
from .salida import escribir_salidas
from .sustitucion import InfoSustitucion, error_validacion, sustituir
from .temperatura import FuenteTemperaturaNoDisponible, abrir_inia, agregar_temperatura, inia_cercanas

EXITO, ERROR, PARCIAL = 0, 1, 2


@dataclass
class ResultadoEstacion:
    estacion: str
    df: pd.DataFrame
    info: InfoSustitucion
    validacion: dict = field(default_factory=dict)


@dataclass
class ResultadoEjecucion:
    codigo: int = EXITO
    ruta_salida: Path | None = None
    estaciones: dict[str, ResultadoEstacion] = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)
    errores_feriados: list[str] = field(default_factory=list)
    carga: ResultadoCarga = field(default_factory=ResultadoCarga)


def resolver_mapeo(cfg: dict, estacion: str, coordenadas: dict, con: sqlite3.Connection) -> bool:
    """Asegura que ``estacion`` tenga estación INIA asignada (C4).

    Si no está en ``mapeo_estaciones`` y ``mapeo_automatico`` está activo, asigna la
    estación INIA con termómetro más cercana y como respaldo la segunda. El mapeo
    resultante queda en la configuración (y en ``config_usada.yaml``) para trazabilidad.
    """
    if estacion in cfg["mapeo_estaciones"]:
        return True
    if not cfg["mapeo_automatico"] or estacion not in coordenadas:
        return False
    cercanas = inia_cercanas(con, *coordenadas[estacion], cfg)
    if not cercanas:
        return False
    cfg["mapeo_estaciones"][estacion] = {
        **DEFAULTS_ESTACION,
        "inia": cercanas[0][0],
        "inia_respaldo": cercanas[1][0] if len(cercanas) > 1 else None,
        "distancia_inia_km": round(cercanas[0][1], 1),
        "mapeo": "automatico",
    }
    return True


def procesar_estacion(serie: pd.DataFrame, estacion: str, cfg: dict, con: sqlite3.Connection,
                      feriados: pd.DataFrame, metodo: str | None = None) -> ResultadoEstacion:
    """Pipeline de una estación: calendario → temperatura → detección → sustitución (RN-00)."""
    est_cfg = cfg["mapeo_estaciones"][estacion]
    metodo = metodo or cfg["metodo"]
    df = agregar_calendario(serie, estacion, feriados, cfg)
    df = agregar_temperatura(df, estacion, con, cfg)
    df = detectar_outliers(df, cfg, est_cfg, metodo="lineal" if metodo == "auto" else metodo)
    df, info = sustituir(df, cfg, est_cfg, metodo)
    validacion = error_validacion(df, cfg, info.metodo) if info.metodo else {}
    return ResultadoEstacion(estacion, df, info, validacion)


def ejecutar(cfg: dict, estaciones: list[str] | None = None, metodo: str | None = None,
             dry_run: bool = False, nombre_ejecucion: str | None = None) -> ResultadoEjecucion:
    res = ResultadoEjecucion()
    # Fuentes obligatorias: si faltan, se aborta antes de procesar y sin salidas (H2.4).
    try:
        feriados, res.errores_feriados = cargar_feriados(cfg["feriados"])
        con = abrir_inia(cfg["inia"]["ruta"])
    except (ErrorFeriados, FuenteTemperaturaNoDisponible) as exc:
        res.codigo = ERROR
        res.errores.append(str(exc))
        return res

    try:
        try:
            res.carga = cargar_entrada(cfg, estaciones)
        except FuenteDemandaNoDisponible as exc:
            res.codigo = ERROR
            res.errores.append(str(exc))
            return res
        res.errores += [f"entrada {nombre}: {motivo}" for nombre, motivo in res.carga.rechazados]
        for estacion, serie in res.carga.series.items():
            if not resolver_mapeo(cfg, estacion, res.carga.coordenadas, con):
                res.errores.append(f"estación {estacion}: sin correspondencia en mapeo_estaciones")
                continue
            try:  # RF-004: un error en una estación no detiene las demás
                res.estaciones[estacion] = procesar_estacion(serie, estacion, cfg, con, feriados, metodo)
            except Exception as exc:  # noqa: BLE001
                res.errores.append(f"estación {estacion}: {type(exc).__name__}: {exc}")
    finally:
        con.close()

    if not res.estaciones:
        res.codigo = ERROR
        if not res.errores:
            res.errores.append("no hay estaciones para procesar")
        return res
    if not dry_run:
        res.ruta_salida = escribir_salidas(res, cfg, nombre_ejecucion)
    res.codigo = PARCIAL if res.errores else EXITO
    return res
