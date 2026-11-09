"""H5 — Archivos depurados, registro de cambios e informe (RF-018..RF-021)."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .carga import ArchivoOrigen
from .config import config_serializable
from .revision import generar_muestra

COLUMNAS_CAMBIOS = ["estacion", "fecha_hora", "valor_original", "valor_estimado", "motivo", "desviacion_sigma",
                    "temperatura", "origen_temperatura", "metodo", "origen"]


def _fmt_fecha(indice: pd.DatetimeIndex, con_zona: bool) -> list[str]:
    if con_zona:
        return [t.isoformat() for t in indice]
    return list(indice.strftime("%Y-%m-%d %H:%M:%S"))


def tabla_depurada(origen: ArchivoOrigen, resultados: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame:
    """Contenido de salida para un archivo de entrada: misma estructura + columna ``origen``."""
    col = cfg["columnas"]
    partes = []
    for est in origen.estaciones:
        if est not in resultados:
            continue
        df = resultados[est]
        df = df[(df.index >= origen.inicio) & (df.index <= origen.fin)]
        parte = pd.DataFrame({
            col["estacion"]: est,
            col["fecha_hora"]: _fmt_fecha(df.index, origen.fechas_con_zona),
            col["demanda"]: df["demanda_depurada"].round(6).to_numpy(),
            "origen": df["origen"].to_numpy(),
        })
        if origen.extras is not None:
            claves = pd.MultiIndex.from_arrays([[est] * len(df), df.index])
            extras = origen.extras.reindex(claves)
            for c in origen.extras.columns:
                parte[c] = extras[c].to_numpy()
        partes.append(parte)
    if not partes:
        return pd.DataFrame(columns=origen.columnas + ["origen"])
    tabla = pd.concat(partes, ignore_index=True)
    return tabla[[c for c in origen.columnas if c in tabla.columns] + ["origen"]]


def tabla_depurada_sqlite(estacion: str, df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Salida con el formato de POTENCIA_ESTACION de BD_CurvasDemanda + columna ``origen``."""
    from .carga import local_a_epoch_reloj

    epoch, cambio = local_a_epoch_reloj(pd.DatetimeIndex(df.index), cfg)
    return pd.DataFrame({
        "Codigo_estacion": estacion,
        "Fecha_hora": epoch,
        "Valor": df["demanda_depurada"].round(6).to_numpy(),
        "Cambio_horario": cambio,
        "origen": df["origen"].to_numpy(),
    })


def tabla_cambios(resultados: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Registro de cambios: una fila por valor sustituido o no rellenado (RF-020, CE-004)."""
    partes = []
    for est in sorted(resultados):
        df = resultados[est]
        cambios = df[df["origen"] != "original"]
        if cambios.empty:
            continue
        partes.append(pd.DataFrame({
            "estacion": est,
            "fecha_hora": [t.isoformat() for t in cambios.index],
            "valor_original": cambios["demanda"].to_numpy(),
            "valor_estimado": cambios["demanda_depurada"].round(6).to_numpy(),
            "motivo": cambios["motivo"].to_numpy(),
            "desviacion_sigma": cambios["desviacion_sigma"].round(3).to_numpy(),
            "temperatura": cambios["temperatura"].round(3).to_numpy(),
            "origen_temperatura": cambios["origen_temperatura"].to_numpy(),
            "metodo": cambios["metodo"].to_numpy(),
            "origen": cambios["origen"].to_numpy(),
        }))
    if not partes:
        return pd.DataFrame(columns=COLUMNAS_CAMBIOS)
    return pd.concat(partes, ignore_index=True)[COLUMNAS_CAMBIOS]


def tabla_informe(estaciones: dict) -> pd.DataFrame:
    """Métricas de calidad por estación (RF-021)."""
    filas = []
    for est in sorted(estaciones):
        r = estaciones[est]
        df = r.df
        n = len(df)
        motivo = df["motivo"].astype(str)
        filas.append({
            "estacion": est,
            "registros": n,
            "outliers": int(df["es_outlier"].sum()),
            "pct_outliers": round(100 * df["es_outlier"].mean(), 3) if n else 0.0,
            "regla_fisica": int(motivo.str.startswith("regla_fisica").sum()),
            "desviacion": int((motivo == "desviacion").sum()),
            "huecos": int(df["es_hueco"].sum()),
            "estimados": int((df["origen"] == "estimado").sum()),
            "no_rellenados": int((df["origen"] == "no_rellenado").sum()),
            "tramos_no_rellenados": len(r.info.tramos_no_rellenados),
            "temp_faltante": int(df["temp_faltante"].sum()),
            "metodo": r.info.metodo,
            "mae_validacion": round(r.validacion.get("mae", np.nan), 4),
            "mape_validacion": round(r.validacion.get("mape", np.nan), 5),
            "comparacion_metodos": "; ".join(
                f"{m}: MAE={v['mae']:.3f} MAPE={v['mape']:.4f}" for m, v in r.info.evaluacion.items()
            ),
            "avisos": " | ".join(r.info.avisos),
        })
    return pd.DataFrame(filas)


def _markdown(tabla: pd.DataFrame) -> str:
    if tabla.empty:
        return "_(sin datos)_\n"
    cab = "| " + " | ".join(map(str, tabla.columns)) + " |"
    sep = "|" + "|".join("---" for _ in tabla.columns) + "|"
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |" for fila in tabla.itertuples(index=False)]
    return "\n".join([cab, sep, *filas]) + "\n"


def informe_markdown(ejecucion, informe: pd.DataFrame, cfg: dict) -> str:
    lineas = [
        "# Informe de calidad — depuración de demanda eléctrica",
        "",
        f"- Método configurado: `{cfg['metodo']}` · k = {cfg['deteccion']['k']} · "
        f"relleno máximo = {cfg['max_duracion_relleno']} · seed = {cfg['seed']}",
        f"- Umbral de aceptación de revisión: {cfg['aceptacion']['min_outliers_confirmados']:.2f} "
        f"sobre {cfg['aceptacion']['muestra_outliers_por_estacion']} outliers por estación",
        "",
        "## Métricas por estación",
        "",
        _markdown(informe.drop(columns=["comparacion_metodos", "avisos"], errors="ignore")),
    ]
    comp = informe[informe.get("comparacion_metodos", pd.Series(dtype=str)).astype(bool)] if not informe.empty else informe
    if not comp.empty:
        lineas += ["## Comparación de métodos (H6)", "", _markdown(comp[["estacion", "metodo", "comparacion_metodos"]])]
    tramos = [(est, r.info.tramos_no_rellenados) for est, r in sorted(ejecucion.estaciones.items()) if r.info.tramos_no_rellenados]
    if tramos:
        lineas += ["## Tramos no rellenados (requieren revisión manual)", ""]
        for est, ts in tramos:
            for ini, fin, n in ts:
                lineas.append(f"- {est}: {ini.isoformat()} → {fin.isoformat()} ({n} registros)")
        lineas.append("")
    avisos = [(est, r.info.avisos) for est, r in sorted(ejecucion.estaciones.items()) if r.info.avisos]
    if avisos:
        lineas += ["## Avisos", ""] + [f"- {est}: {a}" for est, lista in avisos for a in lista] + [""]
    if ejecucion.errores:
        lineas += ["## Archivos o estaciones omitidos", ""] + [f"- {e}" for e in ejecucion.errores] + [""]
    if ejecucion.errores_feriados:
        lineas += ["## Filas de feriados omitidas", ""] + [f"- {e}" for e in ejecucion.errores_feriados] + [""]
    return "\n".join(lineas)


def _escribir_tabla(tabla: pd.DataFrame, ruta: Path) -> None:
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        tabla.to_excel(ruta.with_suffix(".xlsx"), index=False)
    else:
        tabla.to_csv(ruta, index=False, lineterminator="\n")


def _graficos(resultados: dict[str, pd.DataFrame], carpeta: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    carpeta.mkdir(parents=True, exist_ok=True)
    for est, df in resultados.items():
        fig, ax = plt.subplots(figsize=(14, 4))
        ax.plot(df.index, df["demanda"], color="#9aa5b1", lw=0.6, label="original")
        ax.plot(df.index, df["demanda_depurada"], color="#1f6feb", lw=0.6, label="depurada")
        out = df[df["es_outlier"]]
        ax.scatter(out.index, out["demanda"], color="#d1242f", s=8, label="outlier", zorder=3)
        ax.set_title(f"Estación {est}")
        ax.set_ylabel("Demanda")
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(carpeta / f"{est}.png", dpi=110)
        plt.close(fig)


def escribir_salidas(ejecucion, cfg: dict, nombre: str | None = None) -> Path:
    """Escribe todas las salidas de forma atómica y devuelve la carpeta final (RF-018, RNF-004)."""
    raiz = Path(cfg["salida"])
    raiz.mkdir(parents=True, exist_ok=True)
    nombre = nombre or datetime.now().strftime("ejecucion_%Y%m%d_%H%M%S")
    final = raiz / nombre
    if final.exists():
        raise FileExistsError(f"La carpeta de salida ya existe: {final}")
    tmp = raiz / f".tmp_{nombre}"
    shutil.rmtree(tmp, ignore_errors=True)
    resultados = {est: r.df for est, r in ejecucion.estaciones.items()}
    try:
        (tmp / "depurados").mkdir(parents=True)
        if ejecucion.carga.fuente == "sqlite":
            for est, df in sorted(resultados.items()):
                tabla_depurada_sqlite(est, df, cfg).to_csv(tmp / "depurados" / f"{est}.csv", index=False,
                                                           lineterminator="\n")
        for origen in ejecucion.carga.archivos:
            _escribir_tabla(tabla_depurada(origen, resultados, cfg), tmp / "depurados" / origen.ruta.name)
        tabla_cambios(resultados).to_csv(tmp / "cambios.csv", index=False, lineterminator="\n")
        informe = tabla_informe(ejecucion.estaciones)
        informe.to_csv(tmp / "informe.csv", index=False, lineterminator="\n")
        (tmp / "informe.md").write_text(informe_markdown(ejecucion, informe, cfg), encoding="utf-8")
        generar_muestra(resultados, cfg).to_csv(tmp / "revision_outliers.csv", index=False, lineterminator="\n")
        (tmp / "config_usada.yaml").write_text(
            yaml.safe_dump(config_serializable(cfg), allow_unicode=True, sort_keys=False), encoding="utf-8")
        if cfg["graficos"]:
            _graficos(resultados, tmp / "graficos")
        tmp.rename(final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final
