"""Revisión manual de outliers con umbral configurable (Acuerdos MVP 12.5, T051)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd

COLUMNAS = ["estacion", "fecha_hora", "valor_original", "valor_estimado", "motivo", "desviacion_sigma", "confirmado"]


def generar_muestra(resultados: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame:
    """Muestra aleatoria reproducible de outliers por estación para que la revise el analista."""
    n = int(cfg["aceptacion"]["muestra_outliers_por_estacion"])
    filas = []
    for estacion in sorted(resultados):
        df = resultados[estacion]
        outliers = df[df["es_outlier"]]
        if outliers.empty:
            continue
        muestra = outliers.sample(n=min(n, len(outliers)), random_state=int(cfg["seed"])).sort_index()
        for ts, f in muestra.iterrows():
            filas.append({
                "estacion": estacion,
                "fecha_hora": ts.isoformat(),
                "valor_original": f["demanda"],
                "valor_estimado": f.get("demanda_depurada"),
                "motivo": f["motivo"],
                "desviacion_sigma": f["desviacion_sigma"],
                "confirmado": "",
            })
    return pd.DataFrame(filas, columns=COLUMNAS)


def _normalizar(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode().strip().lower()
    return {"si": "si", "s": "si", "yes": "si", "1": "si", "true": "si",
            "no": "no", "n": "no", "0": "no", "false": "no"}.get(texto, "")


def evaluar(revision: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Acepta o rechaza cada estación según ``aceptacion.min_outliers_confirmados``."""
    umbral = float(cfg["aceptacion"]["min_outliers_confirmados"])
    filas = []
    for estacion, grupo in revision.groupby("estacion", sort=True):
        respuestas = grupo["confirmado"].map(_normalizar)
        revisados = int((respuestas != "").sum())
        confirmados = int((respuestas == "si").sum())
        proporcion = confirmados / revisados if revisados else float("nan")
        if revisados < len(grupo):
            resultado = "incompleta"
        elif proporcion >= umbral - 1e-12:
            resultado = "aceptada"
        else:
            resultado = "rechazada"
        filas.append({
            "estacion": estacion, "muestra": len(grupo), "revisados": revisados, "confirmados": confirmados,
            "proporcion": proporcion, "umbral": umbral, "resultado": resultado,
        })
    return pd.DataFrame(filas)


def evaluar_archivo(ruta: Path | str, cfg: dict) -> pd.DataFrame:
    revision = pd.read_csv(ruta, dtype={"confirmado": str}, keep_default_na=False)
    return evaluar(revision, cfg)
