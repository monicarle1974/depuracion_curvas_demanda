"""Matriz de variables explicativas (RES-03).

Las cuatro variables mínimas son día de la semana, hora del día, estación del año
y temperatura. La temperatura entra como grados de calefacción (HDD) y de
refrigeración (CDD), que capturan la forma en "U" de la demanda frente a la
temperatura.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .calendario import ESTACIONES_ANIO, TIPOS_DIA

COLUMNAS_REQUERIDAS = ["dia_semana", "hora", "estacion_anio", "tipo_dia"]


class ErrorOrdenProceso(RuntimeError):
    """Se intentó modelar sin las variables que exige RN-00 (calendario + temperatura)."""


def verificar_enriquecido(df: pd.DataFrame, usar_temperatura: bool = True) -> None:
    requeridas = COLUMNAS_REQUERIDAS + (["temperatura"] if usar_temperatura else [])
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise ErrorOrdenProceso(
            "RN-00: la detección y la sustitución requieren los datos enriquecidos con calendario y "
            f"temperatura de inia; faltan columnas: {', '.join(faltan)}"
        )


def _one_hot(valores: pd.Series, categorias, prefijo: str) -> pd.DataFrame:
    cat = pd.Categorical(valores, categories=categorias)
    return pd.get_dummies(cat, prefix=prefijo, dtype=float).set_axis(valores.index)


def grados_dia(temp: pd.Series, cfg: dict) -> tuple[pd.Series, pd.Series]:
    conf = cfg["temperatura_confort"]
    hdd = (conf["hdd_base"] - temp).clip(lower=0)
    cdd = (temp - conf["cdd_base"]).clip(lower=0)
    return hdd, cdd


def construir_X(df: pd.DataFrame, cfg: dict, metodo: str = "lineal", usar_temperatura: bool = True) -> pd.DataFrame:
    """Construye la matriz X con columnas fijas (iguales al entrenar y al predecir)."""
    verificar_enriquecido(df, usar_temperatura)
    partes: list[pd.DataFrame] = []
    if metodo == "lineal":
        partes.append(_one_hot(df["tipo_dia"], TIPOS_DIA, "td"))
        partes.append(_one_hot(df["dia_semana"], range(7), "dow"))
        partes.append(_one_hot(df["estacion_anio"], ESTACIONES_ANIO, "est"))
        horas = _one_hot(df["hora"], range(24), "h")
        partes.append(horas)
        # Interacción hora × fin de semana/feriado: la forma diaria cambia.
        no_laborable = (df["tipo_dia"] != "laborable").astype(float).to_numpy()[:, None]
        partes.append(pd.DataFrame(horas.to_numpy() * no_laborable, index=df.index,
                                   columns=[f"hnl_{h}" for h in range(24)]))
    else:
        partes.append(pd.DataFrame({
            "hora": df["hora"].astype(float),
            "dia_semana": df["dia_semana"].astype(float),
            "tipo_dia": pd.Categorical(df["tipo_dia"], categories=TIPOS_DIA).codes.astype(float),
            "estacion_anio": pd.Categorical(df["estacion_anio"], categories=ESTACIONES_ANIO).codes.astype(float),
        }, index=df.index))
    if usar_temperatura:
        hdd, cdd = grados_dia(df["temperatura"].astype(float), cfg)
        temp = pd.DataFrame({"hdd": hdd, "cdd": cdd}, index=df.index)
        if metodo != "lineal":
            temp["temperatura"] = df["temperatura"].astype(float)
        partes.append(temp)
    X = pd.concat(partes, axis=1)
    return X.astype(float).replace([np.inf, -np.inf], np.nan)
