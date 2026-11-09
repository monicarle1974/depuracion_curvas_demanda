"""H3 — Detección de valores atípicos (RF-009..RF-012)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import verificar_enriquecido
from .modelos import entrenar

FACTOR_MAD = 1.4826


def sigma_robusta(residuos: pd.Series) -> float:
    """Escala robusta: 1.4826 · MAD. No se contamina con picos aislados."""
    r = pd.Series(residuos, dtype=float).dropna()
    if r.empty:
        return float("nan")
    return float(FACTOR_MAD * np.median(np.abs(r - np.median(r))))


def marcar_por_desviacion(residuos: pd.Series, k: float, sigma: float | None = None) -> pd.Series:
    """True donde |residuo| > k · sigma (RF-010)."""
    r = pd.Series(residuos, dtype=float)
    s = sigma_robusta(r) if sigma is None else sigma
    if not np.isfinite(s) or s <= 0:
        return pd.Series(False, index=r.index)
    return (r.abs() > k * s).fillna(False)


def aplicar_reglas_fisicas(demanda: pd.Series, capacidad: float | None, permite_cero: bool) -> pd.Series:
    """Motivo de la regla física violada, o cadena vacía (RF-009, RN-01)."""
    motivo = pd.Series("", index=demanda.index, dtype=object)
    motivo[demanda < 0] = "regla_fisica:negativo"
    if not permite_cero:
        motivo[demanda == 0] = "regla_fisica:cero"
    if capacidad is not None:
        motivo[demanda > capacidad] = "regla_fisica:capacidad"
    return motivo


def detectar_outliers(df: pd.DataFrame, cfg: dict, est_cfg: dict, metodo: str = "lineal") -> pd.DataFrame:
    """Marca outliers y huecos. Agrega ``es_outlier``, ``motivo`` y ``desviacion_sigma``.

    1. Reglas físicas.
    2. Desviación estadística: ajuste iterativo del modelo con datos no marcados y
       residuos robustos ``|r| > k · 1.4826 · MAD``. Como el modelo incluye la
       temperatura, un pico coherente con una ola de calor no se marca (H3.4).
    3. Huecos con motivo ``hueco``.
    """
    verificar_enriquecido(df)  # RN-00
    df = df.copy()
    k = float(cfg["deteccion"]["k"])
    max_iter = int(cfg["deteccion"]["max_iter"])

    es_hueco = df["es_hueco"].to_numpy(bool) if "es_hueco" in df else df["demanda"].isna().to_numpy()
    motivo = aplicar_reglas_fisicas(df["demanda"], est_cfg.get("capacidad_max_mw"), est_cfg.get("permite_cero", False))
    fisica = (motivo != "").to_numpy()
    temp_ok = df["temperatura"].notna().to_numpy()
    candidatas = ~es_hueco & ~fisica & df["demanda"].notna().to_numpy()

    desviacion = np.full(len(df), np.nan)
    estadistico = np.zeros(len(df), dtype=bool)
    if candidatas.sum() >= int(cfg["min_registros_entrenamiento"]):
        y = df["demanda"]
        for _ in range(max_iter):
            limpias = candidatas & ~estadistico
            nuevo = np.zeros(len(df), dtype=bool)
            for con_temp, filas in ((True, candidatas & temp_ok), (False, candidatas & ~temp_ok)):
                entreno = limpias & (temp_ok if con_temp else np.ones(len(df), bool))
                if not filas.any() or entreno.sum() < 10:
                    continue
                modelo = entrenar(df[entreno], y[entreno], cfg, metodo, usar_temperatura=con_temp)
                residuos = y[filas].to_numpy() - modelo.predecir(df[filas], cfg)
                sigma = sigma_robusta(pd.Series(y[entreno].to_numpy() - modelo.predecir(df[entreno], cfg)))
                if not np.isfinite(sigma) or sigma <= 0:
                    continue
                desviacion[filas] = np.abs(residuos) / sigma
                nuevo[filas] = desviacion[filas] > k
            if np.array_equal(nuevo, estadistico):
                break
            estadistico = nuevo

    motivo = motivo.to_numpy(dtype=object, copy=True)
    motivo[estadistico & (motivo == "")] = "desviacion"
    motivo[es_hueco] = "hueco"
    df["es_outlier"] = fisica | estadistico
    df["motivo"] = motivo
    df["desviacion_sigma"] = desviacion
    return df
