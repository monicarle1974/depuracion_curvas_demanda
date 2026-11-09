"""Pasos comunes a varias características."""

from __future__ import annotations

import pandas as pd
import pytest
from pytest_bdd import given, parsers, then, when

from datos.constructores import ConstructorSerie, escribir_feriados
from depuracion.deteccion import detectar_outliers
from depuracion.pipeline import ejecutar
from depuracion.sustitucion import sustituir


@pytest.fixture
def ctx():
    """Contexto compartido entre los pasos de un escenario."""
    return {}


@given(parsers.parse('la estación "{est}" con capacidad máxima de {cap:g} MW que no admite demanda cero'))
def estacion_con_capacidad(cfg, ctx, est, cap):
    cfg["mapeo_estaciones"][est].update({"capacidad_max_mw": cap, "permite_cero": False})
    ctx["estacion"] = est


@given("un año de demanda horaria sintética con su temperatura asociada")
def un_anio(ctx):
    ctx["serie"] = ConstructorSerie(ctx.get("estacion", "EST_001"), dias=365)


@given(parsers.parse("{dias:d} días de demanda horaria sintética con su temperatura asociada"))
def n_dias(ctx, dias):
    ctx["serie"] = ConstructorSerie(ctx.get("estacion", "EST_001"), dias=dias)


@given(parsers.parse('el método configurado "{metodo}"'))
def metodo_configurado(cfg, metodo):
    cfg["metodo"] = metodo


@given(parsers.parse('una carpeta de entrada con un año de demanda de "{est}" en "{archivo}" con anomalías inyectadas'))
def carpeta_con_anomalias(cfg, ctx, est, archivo):
    serie = ConstructorSerie(est, dias=365).con_anomalias(60).con_hueco("2025-04-10 08:00", 3)
    ctx["serie"] = serie
    ctx["archivo"] = serie.escribir(cfg["entrada"], archivo)


@given("la base inia con la temperatura correspondiente")
def base_inia_correspondiente(cfg, ctx):
    from datos.sinteticos import crear_inia

    inia = cfg["mapeo_estaciones"][ctx["serie"].estacion]["inia"]
    crear_inia(cfg["inia"]["ruta"], {inia: ctx["serie"].temperatura})
    escribir_feriados(cfg["feriados"], [("2025-01-01", "Año Nuevo", "")])


@when("se ejecuta la detección")
def ejecutar_deteccion(cfg, ctx):
    est = ctx["serie"].estacion
    ctx["resultado"] = detectar_outliers(ctx["serie"].enriquecido(cfg), cfg, cfg["mapeo_estaciones"][est])


@when("se ejecuta la detección y la sustitución")
def ejecutar_deteccion_sustitucion(cfg, ctx):
    est = ctx["serie"].estacion
    est_cfg = cfg["mapeo_estaciones"][est]
    df = ctx.get("enriquecido")
    if df is None:
        df = ctx["serie"].enriquecido(cfg)
    df = detectar_outliers(df, cfg, est_cfg)
    for ts in ctx.get("forzar_outlier", []):
        df.loc[ts, ["es_outlier", "motivo"]] = [True, "desviacion"]
    ctx["resultado"], ctx["info"] = sustituir(df, cfg, est_cfg)


@when("se ejecuta el proceso completo")
def proceso_completo(cfg, ctx):
    ctx["ejecucion"] = ejecutar(cfg, nombre_ejecucion="prueba")


@then(parsers.parse("el proceso termina con código {codigo:d}"))
def codigo_salida(ctx, codigo):
    assert ctx["ejecucion"].codigo == codigo, ctx["ejecucion"].errores


@then(parsers.parse('el error indica "{texto}"'))
def error_indica(ctx, texto):
    assert any(texto in e for e in ctx["ejecucion"].errores), ctx["ejecucion"].errores


@then("no se generó ninguna carpeta de salida")
def sin_salida(cfg, ctx):
    from pathlib import Path

    assert ctx["ejecucion"].ruta_salida is None
    assert not Path(cfg["salida"]).exists() or not any(Path(cfg["salida"]).iterdir())
