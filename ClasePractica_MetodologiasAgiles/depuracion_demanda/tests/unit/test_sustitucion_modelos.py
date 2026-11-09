import numpy as np
import pandas as pd
import pytest

from depuracion.deteccion import detectar_outliers
from depuracion.features import ErrorOrdenProceso, construir_X
from depuracion.modelos import crear_estimador, elegir_metodo, metricas
from depuracion.sustitucion import error_validacion, sustituir, tramos


def test_tramos_consecutivos():
    idx = pd.date_range("2025-01-01", periods=8, freq="1h")
    m = pd.Series([0, 1, 1, 0, 1, 0, 1, 1], index=idx, dtype=bool)
    assert [(n) for _, _, n in tramos(m)] == [2, 1, 2]
    assert tramos(pd.Series(False, index=idx)) == []


def test_metricas():
    m = metricas([10, 20, 0], [11, 18, 1])
    assert m["mae"] == pytest.approx(4 / 3) and m["mape"] == pytest.approx((0.1 + 0.1) / 2)


def test_elegir_metodo_menor_mae_y_desempate():
    assert elegir_metodo({"lineal": {"mae": 2}, "ia": {"mae": 1}}) == "ia"
    assert elegir_metodo({"lineal": {"mae": 1}, "ia": {"mae": 1}}) == "lineal"


def test_estimador_desconocido():
    with pytest.raises(ValueError):
        crear_estimador("magia", 0)


def test_columnas_X_estables_entre_entrenar_y_predecir(cfg, constructor):
    df = constructor.enriquecido(cfg)
    a = construir_X(df.iloc[:24], cfg)          # solo enero, un día
    b = construir_X(df.iloc[4000:4100], cfg)    # otra estación del año
    assert list(a.columns) == list(b.columns)
    assert list(construir_X(df.iloc[:5], cfg, "ia").columns)[-3:] == ["hdd", "cdd", "temperatura"]


def test_construir_X_exige_calendario(cfg):
    with pytest.raises(ErrorOrdenProceso, match="dia_semana"):
        construir_X(pd.DataFrame({"temperatura": [1.0]}), cfg)


def test_sin_outliers_no_se_modifica_nada(cfg, constructor):
    df = constructor.enriquecido(cfg)
    df["es_outlier"] = False
    df["motivo"] = ""
    df["desviacion_sigma"] = np.nan
    res, info = sustituir(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    assert (res["origen"] == "original").all() and res["demanda_depurada"].equals(res["demanda"])


def test_historico_insuficiente_no_sustituye(cfg, constructor):
    constructor.con_hueco("2025-03-01 10:00", 3)
    df = detectar_outliers(constructor.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])
    cfg["min_registros_entrenamiento"] = 10**6
    res, info = sustituir(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    assert (res.loc[res["es_hueco"], "origen"] == "no_rellenado").all()
    assert info.avisos and "insuficiente" in info.avisos[0]


def test_filas_sin_temperatura_se_estiman_sin_temperatura(cfg, constructor):
    constructor.con_hueco("2025-03-01 10:00", 3)
    df = constructor.enriquecido(cfg)
    df.loc["2025-03-01", "temperatura"] = np.nan
    df["temp_faltante"] = df["temperatura"].isna()
    df = detectar_outliers(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    res, info = sustituir(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    huecos = res[res["es_hueco"]]
    assert (huecos["origen"] == "estimado").all() and (huecos["metodo"] == "lineal_sin_temperatura").all()
    assert any("sin temperatura" in a for a in info.avisos)


def test_error_validacion(cfg, constructor):
    df = detectar_outliers(constructor.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])
    m = error_validacion(df, cfg, "lineal")
    assert m["mape"] < 0.05
    assert np.isnan(error_validacion(df.iloc[:10], cfg, "lineal")["mae"])
