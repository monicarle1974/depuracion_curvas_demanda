"""H4 — Sustitución de outliers y huecos por pronóstico (RF-013, RF-016, RF-017)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import verificar_enriquecido
from .modelos import elegir_metodo, entrenar, evaluar_metodos, metricas

ORIGENES = ("original", "estimado", "no_rellenado")


@dataclass
class InfoSustitucion:
    metodo: str = ""
    evaluacion: dict = field(default_factory=dict)
    n_entrenamiento: int = 0
    tramos_no_rellenados: list[tuple[pd.Timestamp, pd.Timestamp, int]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def tramos(mascara: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """Tramos consecutivos donde ``mascara`` es True: (inicio, fin, n_registros)."""
    m = pd.Series(mascara, dtype=bool)
    if not m.any():
        return []
    grupo = (m != m.shift()).cumsum()
    res = []
    for _, bloque in m[m].groupby(grupo[m]):
        res.append((bloque.index[0], bloque.index[-1], len(bloque)))
    return res


def sustituir(df: pd.DataFrame, cfg: dict, est_cfg: dict, metodo: str | None = None) -> tuple[pd.DataFrame, InfoSustitucion]:
    """Rellena ``demanda_depurada`` y ``origen`` (RN-02, RN-03, RN-05)."""
    verificar_enriquecido(df)  # RN-00
    df = df.copy()
    info = InfoSustitucion()
    metodo = metodo or cfg["metodo"]

    a_sustituir = (df["es_outlier"] | df["es_hueco"]).to_numpy(bool)
    temp_ok = df["temperatura"].notna().to_numpy()
    limpias = ~a_sustituir & df["demanda"].notna().to_numpy()

    df["demanda_depurada"] = df["demanda"].where(~a_sustituir)
    df["origen"] = np.where(a_sustituir, "no_rellenado", "original")
    df["metodo"] = ""
    if not a_sustituir.any():
        info.metodo = metodo
        return df, info

    entreno = limpias & temp_ok
    info.n_entrenamiento = int(entreno.sum())
    if entreno.sum() < int(cfg["min_registros_entrenamiento"]):
        info.avisos.append(
            f"histórico limpio insuficiente ({int(entreno.sum())} < {cfg['min_registros_entrenamiento']}): no se sustituye"
        )
        info.tramos_no_rellenados = tramos(pd.Series(a_sustituir, index=df.index))
        return df, info

    y = df["demanda"]
    if metodo == "auto":
        info.evaluacion = evaluar_metodos(df[entreno], y[entreno], cfg)
        metodo = elegir_metodo(info.evaluacion)
    info.metodo = metodo

    # RF-016: tramos demasiado largos no se rellenan.
    max_n = int(pd.Timedelta(cfg["max_duracion_relleno"]) / pd.Timedelta(cfg["frecuencia"]))
    rellenable = a_sustituir.copy()
    for inicio, fin, n in tramos(pd.Series(a_sustituir, index=df.index)):
        if n > max_n:
            rellenable[(df.index >= inicio) & (df.index <= fin)] = False
            info.tramos_no_rellenados.append((inicio, fin, n))

    capacidad = est_cfg.get("capacidad_max_mw")
    for con_temp, filas in ((True, rellenable & temp_ok), (False, rellenable & ~temp_ok)):
        if not filas.any():
            continue
        entreno_m = entreno if con_temp else limpias
        modelo = entrenar(df[entreno_m], y[entreno_m], cfg, metodo, usar_temperatura=con_temp)
        pred = np.clip(modelo.predecir(df[filas], cfg), 0, capacidad)  # RF-017, RN-01
        df.loc[filas, "demanda_depurada"] = pred
        df.loc[filas, "origen"] = "estimado"
        df.loc[filas, "metodo"] = metodo if con_temp else f"{metodo}_sin_temperatura"
        if not con_temp:
            info.avisos.append(f"{int(filas.sum())} registros estimados sin temperatura")
    return df, info


def error_validacion(df: pd.DataFrame, cfg: dict, metodo: str, fraccion: float = 0.2) -> dict[str, float]:
    """MAE/MAPE del método en el último ``fraccion`` del histórico limpio (para el informe)."""
    limpias = df[~(df["es_outlier"] | df["es_hueco"]) & df["temperatura"].notna() & df["demanda"].notna()]
    if len(limpias) < 20:
        return {"mae": float("nan"), "mape": float("nan")}
    corte = int(len(limpias) * (1 - fraccion))
    entreno, prueba = limpias.iloc[:corte], limpias.iloc[corte:]
    modelo = entrenar(entreno, entreno["demanda"], cfg, metodo)
    return metricas(prueba["demanda"], modelo.predecir(prueba, cfg))
