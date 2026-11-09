"""Invariantes de negocio comprobadas con datos generados (hypothesis)."""

import numpy as np
import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from depuracion.calendario import agregar_calendario, estacion_del_anio
from depuracion.deteccion import detectar_outliers, marcar_por_desviacion
from depuracion.sustitucion import sustituir

AJUSTES = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def _serie_desde(valores, cfg, huecos=()):
    idx = pd.date_range("2025-03-03", periods=len(valores), freq="1h", tz=cfg["zona_horaria"])
    d = pd.Series(valores, index=idx, dtype=float)
    d.iloc[list(huecos)] = np.nan
    df = pd.DataFrame({"estacion": "EST_001", "demanda": d, "es_hueco": d.isna()}, index=idx)
    df = agregar_calendario(df, "EST_001", None, cfg)
    df["temperatura"] = 15 + 8 * np.sin(np.arange(len(df)) / 24)
    df["origen_temperatura"] = "inia"
    df["temp_faltante"] = False
    return df


def _depurar(valores, cfg, huecos=()):
    est = cfg["mapeo_estaciones"]["EST_001"]
    df = detectar_outliers(_serie_desde(valores, cfg, huecos), cfg, est)
    return sustituir(df, cfg, est)[0]


valores = st.lists(st.floats(-50, 500, allow_nan=False), min_size=48, max_size=300)


@AJUSTES
@given(valores=valores)
def test_depurada_respeta_limites_fisicos(cfg, valores):
    """RN-01 / RF-017: nunca negativa ni por encima de la capacidad."""
    cfg["min_registros_entrenamiento"] = 24
    res = _depurar(valores, cfg)
    assert res["demanda_depurada"].dropna().between(0, 120).all()


@AJUSTES
@given(valores=valores, huecos=st.sets(st.integers(0, 47), max_size=10))
def test_solo_cambian_outliers_y_huecos(cfg, valores, huecos):
    """RN-02 / RN-05: los valores normales se conservan y todo estimado era outlier o hueco."""
    cfg["min_registros_entrenamiento"] = 24
    res = _depurar(valores, cfg, huecos)
    normales = ~(res["es_outlier"] | res["es_hueco"])
    assert (res.loc[normales, "demanda_depurada"] == res.loc[normales, "demanda"]).all()
    assert (res.loc[normales, "origen"] == "original").all()
    estimados = res["origen"] == "estimado"
    assert (res.loc[estimados, "es_outlier"] | res.loc[estimados, "es_hueco"]).all()


@AJUSTES
@given(valores=st.lists(st.floats(0, 100, allow_nan=False), min_size=48, max_size=200))
def test_reproducible(cfg, valores):
    """RF-022: misma entrada y misma seed ⇒ misma salida."""
    cfg["min_registros_entrenamiento"] = 24
    a, b = _depurar(valores, cfg), _depurar(valores, cfg)
    pd.testing.assert_frame_equal(a, b)


@settings(max_examples=200, deadline=None)
@given(residuos=st.lists(st.floats(-100, 100, allow_nan=False), min_size=5, max_size=200),
       k_bajo=st.floats(0.5, 5), delta=st.floats(0, 5))
def test_bajar_k_nunca_reduce_outliers(residuos, k_bajo, delta):
    """H3.5: con los mismos residuos, un k menor marca al menos lo mismo."""
    r = pd.Series(residuos)
    assert marcar_por_desviacion(r, k_bajo).sum() >= marcar_por_desviacion(r, k_bajo + delta).sum()


@settings(max_examples=200, deadline=None)
@given(fecha=st.datetimes(min_value=pd.Timestamp("2000-01-01").to_pydatetime(),
                          max_value=pd.Timestamp("2040-12-31").to_pydatetime()),
       hemisferio=st.sampled_from(["sur", "norte"]), criterio=st.sampled_from(["meteorologico", "astronomico"]))
def test_estacion_del_anio_es_total(fecha, hemisferio, criterio):
    """RN-04: toda fecha tiene exactamente una estación del año."""
    est = estacion_del_anio(pd.DatetimeIndex([fecha]), hemisferio, criterio)[0]
    assert est in {"verano", "otono", "invierno", "primavera"}
