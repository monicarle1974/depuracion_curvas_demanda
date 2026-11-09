import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from pytest_bdd import given, parsers, scenarios, then, when

from depuracion.pipeline import ejecutar

scenarios("h5_salidas.feature")


def _huellas(carpeta) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(carpeta).iterdir() if p.is_file()}


@given("que se registra la huella de los archivos de entrada")
def huella(cfg, ctx):
    ctx["huellas"] = _huellas(cfg["entrada"])


@given("que los gráficos están activados")
def graficos(cfg):
    cfg["graficos"] = True


@given(parsers.parse('que la entrada es una base de curvas de demanda con un año de "{est}" con anomalías inyectadas'))
def entrada_base(cfg, ctx, tmp_path, est):
    from datos.constructores import ConstructorSerie
    from datos.sinteticos import crear_curvas, crear_inia

    serie = ConstructorSerie(est, dias=365).con_anomalias(40)
    demanda = serie.demanda()
    ctx["curvas"] = crear_curvas(tmp_path / "curvas.sqlite", {est: {"lat": -34.5, "lon": -56.4, "demanda": demanda}})
    crear_inia(cfg["inia"]["ruta"], {"LAS_BRUJAS": serie.temperatura})
    cfg["entrada"] = ctx["curvas"]
    cfg["mapeo_estaciones"][est] = {"inia": "LAS_BRUJAS", "inia_respaldo": None, "capacidad_max_mw": 120,
                                    "permite_cero": False}


@then(parsers.parse('el archivo depurado "{nombre}" tiene las columnas "{columnas}"'))
def columnas_exactas(ctx, nombre, columnas):
    depurado = pd.read_csv(_salida(ctx) / "depurados" / nombre, nrows=1)
    assert list(depurado.columns) == columnas.split(",")


@then(parsers.parse('las fechas del archivo depurado "{nombre}" coinciden con las de la base original'))
def fechas_originales(ctx, nombre):
    import sqlite3

    depurado = pd.read_csv(_salida(ctx) / "depurados" / nombre)
    con = sqlite3.connect(ctx["curvas"])
    originales = pd.read_sql("SELECT Fecha_hora, Valor, Cambio_horario FROM POTENCIA_ESTACION ORDER BY Fecha_hora", con)
    con.close()
    assert depurado["Fecha_hora"].tolist() == originales["Fecha_hora"].tolist()
    assert depurado["Cambio_horario"].tolist() == originales["Cambio_horario"].tolist()
    originales_ok = depurado["origen"] == "original"
    assert np.allclose(depurado.loc[originales_ok, "Valor"], originales.loc[originales_ok, "Valor"])


@when("se ejecuta el proceso completo en modo prueba")
def modo_prueba(cfg, ctx):
    ctx["ejecucion"] = ejecutar(cfg, dry_run=True)


def _salida(ctx) -> Path:
    return ctx["ejecucion"].ruta_salida


@then(parsers.parse('existe el archivo depurado "{nombre}"'))
def existe_depurado(ctx, nombre):
    assert (_salida(ctx) / "depurados" / nombre).is_file()


@then("los archivos de entrada no cambiaron")
def entrada_intacta(cfg, ctx):
    assert _huellas(cfg["entrada"]) == ctx["huellas"]


@then(parsers.parse('el archivo depurado "{nombre}" tiene las columnas originales y "{extra}"'))
def columnas(cfg, ctx, nombre, extra):
    original = pd.read_csv(Path(cfg["entrada"]) / nombre, nrows=1)
    depurado = pd.read_csv(_salida(ctx) / "depurados" / nombre, nrows=1)
    assert list(depurado.columns) == list(original.columns) + [extra]


@then(parsers.parse('el archivo depurado "{nombre}" tiene una fila por cada hora del año'))
def filas(ctx, nombre):
    depurado = pd.read_csv(_salida(ctx) / "depurados" / nombre)
    assert len(depurado) == 365 * 24
    assert set(depurado["origen"]) <= {"original", "estimado", "no_rellenado"}


@then(parsers.parse('el informe incluye para "{est}" outliers, huecos, no rellenados y MAE de validación'))
def informe(ctx, est):
    inf = pd.read_csv(_salida(ctx) / "informe.csv").set_index("estacion")
    fila = inf.loc[est]
    assert fila["outliers"] > 0 and fila["huecos"] == 3
    assert "no_rellenados" in inf.columns
    assert 0 < fila["mae_validacion"] < 5


@then(parsers.parse('existe el informe legible "{nombre}"'))
def informe_md(ctx, nombre):
    texto = (_salida(ctx) / nombre).read_text(encoding="utf-8")
    assert "Métricas por estación" in texto and "EST_001" in texto


@then(parsers.parse('cada valor estimado aparece en "{nombre}" con valor original, motivo y temperatura'))
def cambios(ctx, nombre):
    cambios = pd.read_csv(_salida(ctx) / nombre)
    df = ctx["ejecucion"].estaciones["EST_001"].df
    estimados = df[df["origen"] == "estimado"]
    registrados = cambios[cambios["origen"] == "estimado"]
    assert len(registrados) == len(estimados) > 0
    assert set(registrados["fecha_hora"]) == {t.isoformat() for t in estimados.index}
    no_huecos = registrados[registrados["motivo"] != "hueco"]
    assert no_huecos["valor_original"].notna().all()
    assert registrados["motivo"].ne("").all() and registrados["temperatura"].notna().all()


@then(parsers.parse('existe el archivo de salida "{ruta}"'))
def archivo_salida(ctx, ruta):
    assert (_salida(ctx) / ruta).is_file()
