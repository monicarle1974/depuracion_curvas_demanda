import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from datos.constructores import ts_local
from depuracion.deteccion import detectar_outliers
from depuracion.features import ErrorOrdenProceso

scenarios("h3_deteccion.feature")


@given(parsers.parse('una demanda de {mw:g} MW el "{ts}"'))
def demanda_fija(ctx, mw, ts):
    ctx["serie"].con_valor(ts, mw)


@given(parsers.parse('un pico de {factor:g} veces la demanda esperada el "{ts}"'))
def pico(ctx, factor, ts):
    ctx["serie"].con_pico(ts, factor)


@given(parsers.parse('una ola de calor de {temp:g} °C durante el "{dia}"'))
def ola_de_calor(ctx, temp, dia):
    ctx["serie"].con_ola_de_calor(dia, temp)


@given("la demanda de ese día responde a la temperatura como el resto del año")
def demanda_coherente():
    """El constructor genera la demanda a partir de la temperatura: no hay nada que alterar."""


@given(parsers.parse('que el "{dia}" (miércoles) es feriado según el archivo de feriados'))
def feriado(ctx, dia):
    ctx["serie"].con_feriado(dia)


@given(parsers.parse("{n:d} anomalías inyectadas en la serie"))
def anomalias(ctx, n):
    ctx["serie"].con_anomalias(n)


@when(parsers.parse("se ejecuta la detección con k = {k1:g} y con k = {k2:g}"))
def detectar_dos_k(cfg, ctx, k1, k2):
    df = ctx["serie"].enriquecido(cfg)
    est_cfg = cfg["mapeo_estaciones"][ctx["serie"].estacion]
    for k in (k1, k2):
        cfg["deteccion"]["k"] = k
        ctx[k] = int(detectar_outliers(df, cfg, est_cfg)["es_outlier"].sum())


@when("se ejecuta la detección sin la columna de temperatura")
def detectar_sin_temperatura(cfg, ctx):
    df = ctx["serie"].enriquecido(cfg).drop(columns="temperatura")
    with pytest.raises(ErrorOrdenProceso) as err:
        detectar_outliers(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    ctx["error"] = err.value


@then(parsers.parse('el registro "{ts}" es outlier con motivo "{motivo}"'))
def es_outlier(cfg, ctx, ts, motivo):
    fila = ctx["resultado"].loc[ts_local(cfg, ts)]
    assert fila["es_outlier"]
    assert fila["motivo"] == motivo


@then(parsers.parse('ningún registro del "{dia}" es outlier'))
def ninguno(ctx, dia):
    dia_df = ctx["resultado"].loc[dia]
    assert not dia_df["es_outlier"].any(), dia_df[dia_df["es_outlier"]][["demanda", "motivo", "desviacion_sigma"]]


@then(parsers.parse('la demanda máxima del "{dia}" supera en más de {mw:g} MW la del día anterior'))
def demanda_alta(ctx, dia, mw):
    import pandas as pd

    anterior = (pd.Timestamp(dia) - pd.Timedelta("1D")).strftime("%Y-%m-%d")
    res = ctx["resultado"]
    assert res.loc[dia, "demanda"].max() - res.loc[anterior, "demanda"].max() > mw


@then(parsers.parse("los outliers con k = {k1:g} son al menos tantos como con k = {k2:g}"))
def monotono(ctx, k1, k2):
    assert ctx[k1] >= ctx[k2]


@then(parsers.parse('se produce un error de orden del proceso que menciona "{texto}"'))
def error_orden(ctx, texto):
    assert texto in str(ctx["error"]) and "RN-00" in str(ctx["error"])
