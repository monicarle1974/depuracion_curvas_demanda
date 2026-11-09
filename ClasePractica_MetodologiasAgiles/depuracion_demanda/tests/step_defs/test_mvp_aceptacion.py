import pandas as pd
from pytest_bdd import given, parsers, scenarios, then, when

from depuracion.revision import COLUMNAS, evaluar

scenarios("mvp_aceptacion.feature")


def _muestra(est, n, si, respondidos=None):
    respondidos = n if respondidos is None else respondidos
    confirmado = ["si"] * si + ["no"] * (respondidos - si) + [""] * (n - respondidos)
    return pd.DataFrame({c: [None] * n for c in COLUMNAS} | {"estacion": [est] * n, "confirmado": confirmado})


@given(parsers.parse('una muestra de {n:d} outliers de "{est}" con {si:d} confirmados por el analista'))
def muestra(ctx, n, est, si):
    ctx["revision"] = _muestra(est, n, si)


@given(parsers.parse('una muestra de {n:d} outliers de "{est}" con {r:d} respondidos por el analista'))
def muestra_incompleta(ctx, n, est, r):
    ctx["revision"] = _muestra(est, n, r, respondidos=r)


@given(parsers.parse("el umbral configurado min_outliers_confirmados = {umbral:g}"))
def umbral(cfg, umbral):
    cfg["aceptacion"]["min_outliers_confirmados"] = umbral


@given(parsers.parse("el tamaño de muestra configurado en {n:d} outliers por estación"))
def tamano_muestra(cfg, n):
    cfg["aceptacion"]["muestra_outliers_por_estacion"] = n


@when("se ejecuta evaluar-revision")
def evaluar_revision(cfg, ctx):
    ctx["evaluacion"] = evaluar(ctx["revision"], cfg)


@then(parsers.parse('la estación "{est}" queda "{resultado}"'))
def resultado(ctx, est, resultado):
    ev = ctx["evaluacion"].set_index("estacion")
    assert ev.loc[est, "resultado"] == resultado


@then(parsers.parse('el archivo "{nombre}" tiene {n:d} filas de "{est}" con la columna "{col}" vacía'))
def archivo_revision(ctx, nombre, n, est, col):
    ruta = ctx["ejecucion"].ruta_salida / nombre
    rev = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    filas = rev[rev["estacion"] == est]
    assert len(filas) == n
    assert (filas[col] == "").all()
