import numpy as np
from pytest_bdd import given, parsers, scenarios, then, when

from depuracion.modelos import evaluar_metodos

scenarios("h6_comparacion.feature")


@given(parsers.parse("{n:d} anomalías inyectadas en la serie"))
def anomalias(ctx, n):
    ctx["serie"].con_anomalias(n)


@when("se comparan los métodos con validación temporal")
def comparar(cfg, ctx):
    df = ctx["serie"].enriquecido(cfg)
    ctx["evaluacion"] = evaluar_metodos(df, df["demanda"], cfg)


@then(parsers.parse('se informa MAE y MAPE para "{a}" y para "{b}"'))
def metricas(ctx, a, b):
    for m in (a, b):
        assert np.isfinite(ctx["evaluacion"][m]["mae"]) and np.isfinite(ctx["evaluacion"][m]["mape"])


@then("el método usado es el de menor MAE de la comparación")
def menor_mae(ctx):
    info = ctx["info"]
    assert set(info.evaluacion) == {"lineal", "ia"}
    assert info.metodo == min(info.evaluacion, key=lambda m: info.evaluacion[m]["mae"])


@then(parsers.parse('los valores estimados tienen método "{metodo}"'))
def metodo_estimados(ctx, metodo):
    est = ctx["resultado"][ctx["resultado"]["origen"] == "estimado"]
    assert len(est) > 0 and (est["metodo"] == metodo).all()
