"""Carga y validación de la configuración (RNF-002).

Todos los parámetros del proceso viven en ``config.yaml``; el código no tiene
valores de negocio fijos.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class ErrorConfiguracion(ValueError):
    """La configuración es inválida o está incompleta."""


DEFAULTS: dict[str, Any] = {
    "estaciones": [],                       # vacío = todas las de la entrada
    "periodo": {"desde": None, "hasta": None},
    "columnas": {"estacion": "estacion", "fecha_hora": "fecha_hora", "demanda": "demanda"},
    # Entrada SQLite (BD_CurvasDemanda): Fecha_hora es la hora de reloj local guardada como epoch.
    "fuente_sqlite": {"desfase_utc_horas": -3, "desfase_cambio_horario_horas": -2},
    "mapeo_automatico": True,               # estación INIA más cercana por coordenadas (C4)
    "frecuencia": "1h",
    "zona_horaria": "America/Montevideo",
    "hemisferio": "sur",
    "criterio_estacion": "meteorologico",
    "duplicados": "promedio",
    "inia": {
        "ruta": None,
        "tipo_medidor": "Term%",
        "medidores_preferidos": ["t1", "t2", "t3"],
        "zona_horaria_origen": "UTC",
        "rango_valido": [-30.0, 50.0],
    },
    "alineacion": "auto",
    "max_hueco_temp": "6h",
    "temperatura_confort": {"hdd_base": 18.0, "cdd_base": 22.0},
    "deteccion": {"k": 4.0, "max_iter": 3},
    "metodo": "lineal",
    "max_duracion_relleno": "7D",
    "min_registros_entrenamiento": 2160,
    "graficos": False,
    "seed": 42,
    "aceptacion": {"muestra_outliers_por_estacion": 20, "min_outliers_confirmados": 0.80},
    "mapeo_estaciones": {},
}

DEFAULTS_ESTACION = {"inia": None, "inia_respaldo": None, "capacidad_max_mw": None, "permite_cero": False}

OBLIGATORIOS = ["entrada", "salida", "feriados", "inia.ruta"]
RUTAS = ["entrada", "salida", "feriados", "inia.ruta"]

PERMITIDOS = {
    "hemisferio": {"sur", "norte"},
    "criterio_estacion": {"meteorologico", "astronomico"},
    "duplicados": {"primero", "ultimo", "promedio"},
    "alineacion": {"auto", "igual", "interpolar", "media_intervalo", "media_diaria"},
    "metodo": {"lineal", "ia", "auto"},
}


def _fusionar(base: dict, extra: dict) -> dict:
    res = copy.deepcopy(base)
    for clave, valor in (extra or {}).items():
        if isinstance(valor, dict) and isinstance(res.get(clave), dict):
            res[clave] = _fusionar(res[clave], valor)
        else:
            res[clave] = valor
    return res


def _obtener(cfg: dict, ruta: str):
    actual: Any = cfg
    for parte in ruta.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return None
        actual = actual[parte]
    return actual


def _fijar(cfg: dict, ruta: str, valor) -> None:
    partes = ruta.split(".")
    for parte in partes[:-1]:
        cfg = cfg[parte]
    cfg[partes[-1]] = valor


def _numero(cfg, ruta, minimo=None, maximo=None, incl_min=True, entero=False):
    valor = _obtener(cfg, ruta)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorConfiguracion(f"'{ruta}' debe ser numérico (valor: {valor!r})")
    if entero and int(valor) != valor:
        raise ErrorConfiguracion(f"'{ruta}' debe ser entero (valor: {valor!r})")
    if minimo is not None and (valor < minimo or (not incl_min and valor == minimo)):
        raise ErrorConfiguracion(f"'{ruta}' fuera de rango (valor: {valor!r})")
    if maximo is not None and valor > maximo:
        raise ErrorConfiguracion(f"'{ruta}' fuera de rango (valor: {valor!r})")


def _duracion(cfg, ruta):
    try:
        td = pd.Timedelta(_obtener(cfg, ruta))
    except (ValueError, TypeError) as exc:
        raise ErrorConfiguracion(f"'{ruta}' no es una duración válida") from exc
    if td <= pd.Timedelta(0):
        raise ErrorConfiguracion(f"'{ruta}' debe ser positiva")


def validar(cfg: dict) -> dict:
    for ruta in OBLIGATORIOS:
        if _obtener(cfg, ruta) in (None, "", {}):
            raise ErrorConfiguracion(f"Falta el campo obligatorio '{ruta}'")

    for clave, opciones in PERMITIDOS.items():
        if cfg[clave] not in opciones:
            raise ErrorConfiguracion(f"'{clave}' debe ser uno de {sorted(opciones)} (valor: {cfg[clave]!r})")

    _numero(cfg, "deteccion.k", minimo=0, incl_min=False)
    _numero(cfg, "deteccion.max_iter", minimo=1, entero=True)
    _numero(cfg, "min_registros_entrenamiento", minimo=1, entero=True)
    _numero(cfg, "seed", minimo=0, entero=True)
    _numero(cfg, "aceptacion.muestra_outliers_por_estacion", minimo=1, entero=True)
    _numero(cfg, "aceptacion.min_outliers_confirmados", minimo=0, maximo=1, incl_min=False)
    _numero(cfg, "temperatura_confort.hdd_base")
    _numero(cfg, "temperatura_confort.cdd_base")
    for ruta in ("frecuencia", "max_hueco_temp", "max_duracion_relleno"):
        _duracion(cfg, ruta)

    try:
        pd.Timestamp("2026-01-01").tz_localize(cfg["zona_horaria"])
    except Exception as exc:  # noqa: BLE001 - cualquier error de zona horaria es de configuración
        raise ErrorConfiguracion(f"'zona_horaria' inválida: {cfg['zona_horaria']!r}") from exc

    if cfg["mapeo_estaciones"] is None:
        cfg["mapeo_estaciones"] = {}
    if not isinstance(cfg["mapeo_estaciones"], dict):
        raise ErrorConfiguracion("'mapeo_estaciones' debe ser un diccionario")
    if not cfg["mapeo_estaciones"] and not cfg["mapeo_automatico"]:
        raise ErrorConfiguracion("Falta 'mapeo_estaciones' (o activar 'mapeo_automatico')")
    if not isinstance(cfg["estaciones"], list):
        raise ErrorConfiguracion("'estaciones' debe ser una lista")
    cfg["estaciones"] = [str(e) for e in cfg["estaciones"]]

    fechas = {}
    for clave in ("desde", "hasta"):
        valor = cfg["periodo"].get(clave)
        if valor not in (None, ""):
            try:
                fechas[clave] = pd.Timestamp(str(valor))
            except ValueError as exc:
                raise ErrorConfiguracion(f"'periodo.{clave}' no es una fecha válida: {valor!r}") from exc
            cfg["periodo"][clave] = str(valor)
    if len(fechas) == 2 and fechas["desde"] > fechas["hasta"]:
        raise ErrorConfiguracion("'periodo.desde' debe ser anterior a 'periodo.hasta'")
    for est, datos in cfg["mapeo_estaciones"].items():
        datos = _fusionar(DEFAULTS_ESTACION, datos or {})
        if not datos["inia"]:
            raise ErrorConfiguracion(f"'mapeo_estaciones.{est}.inia' es obligatorio")
        cap = datos["capacidad_max_mw"]
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap <= 0):
            raise ErrorConfiguracion(f"'mapeo_estaciones.{est}.capacidad_max_mw' debe ser > 0")
        cfg["mapeo_estaciones"][est] = datos

    entrada, salida = Path(cfg["entrada"]).resolve(), Path(cfg["salida"]).resolve()
    if salida == entrada or entrada in salida.parents:
        raise ErrorConfiguracion("'salida' no puede ser ni estar dentro de 'entrada' (RNF-004)")
    return cfg


def config_desde_dict(datos: dict, base: Path | None = None) -> dict:
    """Fusiona ``datos`` con los valores por defecto, resuelve rutas y valida."""
    cfg = _fusionar(DEFAULTS, datos)
    for ruta in RUTAS:
        valor = _obtener(cfg, ruta)
        if valor not in (None, ""):
            p = Path(valor)
            if not p.is_absolute() and base is not None:
                p = base / p
            _fijar(cfg, ruta, p.resolve())
    return validar(cfg)


def cargar_config(ruta: str | Path) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorConfiguracion(f"El archivo de configuración no existe: {ruta}")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ErrorConfiguracion(f"YAML inválido en {ruta}: {exc}") from exc
    return config_desde_dict(datos, base=ruta.parent.resolve())


def config_serializable(cfg: dict) -> dict:
    """Copia de la configuración apta para volcar a YAML (rutas como texto)."""

    def conv(v):
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        if isinstance(v, Path):
            return str(v)
        return v

    return conv(cfg)
