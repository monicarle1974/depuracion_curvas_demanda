"""Modelos de pronóstico (RF-013..RF-015, RES-01, H6).

* ``lineal``: regresión lineal regularizada (Ridge).
* ``ia``: HistGradientBoostingRegressor (aprendizaje automático).
* ``auto``: elige por estación el de menor MAE con validación temporal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

from .features import construir_X

METODOS = ("lineal", "ia")


def crear_estimador(metodo: str, seed: int):
    if metodo == "lineal":
        return Ridge(alpha=1.0)
    if metodo == "ia":
        return HistGradientBoostingRegressor(max_iter=200, learning_rate=0.1, random_state=seed)
    raise ValueError(f"método desconocido: {metodo}")


@dataclass
class Modelo:
    metodo: str
    usar_temperatura: bool
    estimador: object
    n_entrenamiento: int

    def predecir(self, df: pd.DataFrame, cfg: dict) -> np.ndarray:
        X = construir_X(df, cfg, self.metodo, self.usar_temperatura)
        return self.estimador.predict(X.to_numpy())


def entrenar(df: pd.DataFrame, y: pd.Series, cfg: dict, metodo: str, usar_temperatura: bool = True) -> Modelo:
    X = construir_X(df, cfg, metodo, usar_temperatura)
    est = crear_estimador(metodo, cfg["seed"])
    est.fit(X.to_numpy(), np.asarray(y, dtype=float))
    return Modelo(metodo, usar_temperatura, est, len(y))


def metricas(y_real, y_pred) -> dict[str, float]:
    y_real = np.asarray(y_real, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = np.abs(y_real - y_pred)
    no_cero = np.abs(y_real) > 1e-9
    mape = float(np.mean(err[no_cero] / np.abs(y_real[no_cero]))) if no_cero.any() else float("nan")
    return {"mae": float(np.mean(err)), "mape": mape}


def evaluar_metodos(df: pd.DataFrame, y: pd.Series, cfg: dict, metodos=METODOS, n_splits: int = 5) -> dict[str, dict]:
    """Validación temporal de cada método sobre datos limpios (H6.1)."""
    n_splits = max(2, min(n_splits, len(df) // 50))
    tscv = TimeSeriesSplit(n_splits=n_splits)
    res = {}
    for metodo in metodos:
        X = construir_X(df, cfg, metodo).to_numpy()
        yv = np.asarray(y, dtype=float)
        reales, preds = [], []
        for tr, te in tscv.split(X):
            est = crear_estimador(metodo, cfg["seed"]).fit(X[tr], yv[tr])
            reales.append(yv[te])
            preds.append(est.predict(X[te]))
        res[metodo] = metricas(np.concatenate(reales), np.concatenate(preds))
    return res


def elegir_metodo(evaluacion: dict[str, dict]) -> str:
    """Método con menor MAE; ante empate, el primero en ``METODOS`` (H6.2)."""
    return min(evaluacion, key=lambda m: (evaluacion[m]["mae"], METODOS.index(m)))
