import numpy as np
import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import depuracion.sustitucion as sustitucion_mod
from datos.constructores import ts_local
from depuracion.deteccion import detectar_outliers
from depuracion.features import ErrorOrdenProceso, construir_X
from depuracion.sustitucion import sustituir

scenarios("h4_sustitucion.feature")


@given(parsers.parse('que el valor real del "{ts}" se marca como outlier'))
def forzar_outlier(cfg, ctx, ts):
    ctx.setdefault("forzar_outlier", []).append(ts_local(cfg, ts))


@given(parsers.parse('un hueco de {horas:d} horas desde "{desde}"'))
def hueco(ctx, horas, desde):
    ctx["serie"].con_hueco(desde, horas)
    ctx["hueco"] = (desde, horas)


@given(parsers.parse('un pico de {factor:g} veces la demanda esperada el "{ts}"'))
def pico(ctx, factor, ts):
    ctx["serie"].con_pico(ts, factor)


@given(parsers.parse("{n:d} anomalías inyectadas en la serie"))
def anomalias(ctx, n):
    ctx["serie"].con_anomalias(n)


@given("que se registran los datos de entrenamiento")
def espiar_entrenamiento(ctx, monkeypatch):
    ctx["entrenamientos"] = []
    original = sustitucion_mod.entrenar

    def espia(df, y, cfg, metodo, usar_temperatura=True):
        ctx["entrenamientos"].append(df.index)
        return original(df, y, cfg, metodo, usar_temperatura)

    monkeypatch.setattr(sustitucion_mod, "entrenar", espia)


@given(parsers.parse('la capacidad máxima de "{est}" reducida a {cap:g} MW'))
def capacidad(cfg, est, cap):
    cfg["mapeo_estaciones"][est]["capacidad_max_mw"] = cap


@when("se ejecuta la sustitución sin la columna de temperatura")
def sustituir_sin_temp(cfg, ctx):
    df = detectar_outliers(ctx["serie"].enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])
    with pytest.raises(ErrorOrdenProceso) as err:
        sustituir(df.drop(columns="temperatura"), cfg, cfg["mapeo_estaciones"]["EST_001"])
    ctx["error"] = err.value


def _error_relativo(ctx, ts):
    real = ctx["serie"].real()[ts]
    return abs(ctx["resultado"].loc[ts, "demanda_depurada"] - real) / real


@then(parsers.parse('el valor estimado del "{ts}" difiere menos de un {pct:g} % del valor real'))
def error_puntual(cfg, ctx, ts, pct):
    t = ts_local(cfg, ts)
    assert ctx["resultado"].loc[t, "origen"] == "estimado"
    assert _error_relativo(ctx, t) < pct / 100


@then("el modelo usa día de la semana, hora, estación del año y temperatura")
def cuatro_variables(cfg, ctx):
    columnas = construir_X(ctx["resultado"].head(5), cfg, "lineal").columns
    for prefijo in ("dow_", "h_", "est_", "hdd", "cdd"):
        assert any(c.startswith(prefijo) for c in columnas), prefijo


@then(parsers.parse("cada hora del tramo difiere menos de un {pct:g} % de su valor real"))
def error_tramo(cfg, ctx, pct):
    desde, horas = ctx["hueco"]
    for t in pd.date_range(ts_local(cfg, desde), periods=horas, freq="1h"):
        assert ctx["resultado"].loc[t, "origen"] == "estimado"
        assert _error_relativo(ctx, t) < pct / 100, t


@then("las estimaciones del tramo no son todas iguales")
def forma_diaria(cfg, ctx):
    desde, horas = ctx["hueco"]
    tramo = pd.date_range(ts_local(cfg, desde), periods=horas, freq="1h")
    assert ctx["resultado"].loc[tramo, "demanda_depurada"].nunique() > 1


@then(parsers.parse('el registro "{ts}" tiene origen "{origen}"'))
def origen(cfg, ctx, ts, origen):
    assert ctx["resultado"].loc[ts_local(cfg, ts), "origen"] == origen


@then(parsers.parse('el registro "{ts}" conserva su valor original'))
def conserva_original(cfg, ctx, ts):
    t = ts_local(cfg, ts)
    fila = ctx["resultado"].loc[t]
    assert np.isclose(fila["demanda"], ctx["serie"].demanda()[t])
    assert not np.isclose(fila["demanda"], fila["demanda_depurada"])


@then(parsers.parse('los registros del "{dia}" tienen origen "{origen}"'))
def origen_dia(ctx, dia, origen):
    assert (ctx["resultado"].loc[dia, "origen"] == origen).all()
    assert ctx["resultado"].loc[dia, "demanda_depurada"].isna().all()


@then(parsers.parse("se reporta {n:d} tramo no rellenado de {registros:d} registros"))
def tramo_no_rellenado(ctx, n, registros):
    tramos = ctx["info"].tramos_no_rellenados
    assert len(tramos) == n and tramos[0][2] == registros


@then("ningún outlier ni hueco se usó para entrenar el modelo final")
def entrenamiento_limpio(ctx):
    res = ctx["resultado"]
    sucios = res.index[res["es_outlier"] | res["es_hueco"]]
    assert len(sucios) > 0 and ctx["entrenamientos"]
    for indice in ctx["entrenamientos"]:
        assert not indice.isin(sucios).any()


@then(parsers.parse("todas las demandas depuradas están entre {lo:g} y {hi:g} MW"))
def limites(ctx, lo, hi):
    d = ctx["resultado"]["demanda_depurada"].dropna()
    assert d.between(lo, hi).all()
    assert (ctx["resultado"]["origen"] == "estimado").any()


@then(parsers.parse('se produce un error de orden del proceso que menciona "{texto}"'))
def error_orden(ctx, texto):
    assert texto in str(ctx["error"]) and "RN-00" in str(ctx["error"])
