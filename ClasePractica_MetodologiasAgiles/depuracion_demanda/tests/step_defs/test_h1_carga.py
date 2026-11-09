from pathlib import Path

import numpy as np
import pandas as pd
from pytest_bdd import given, parsers, scenarios, then, when

from datos.constructores import ts_local
from depuracion.carga import cargar_entrada

scenarios("h1_carga.feature")


def _escribir(cfg, nombre, filas):
    ruta = Path(cfg["entrada"]) / nombre
    pd.DataFrame(filas).to_csv(ruta, index=False)


def _horas(est, desde, n, omitir=None):
    fechas = pd.date_range(desde, periods=n, freq="1h")
    return [{"estacion": est, "fecha_hora": f.strftime("%Y-%m-%d %H:%M"), "demanda": 30 + i % 5}
            for i, f in enumerate(fechas) if f != omitir]


@given(parsers.parse('un archivo "{nombre}" de la estación "{est}" con {n:d} horas desde "{desde}"'))
def archivo_horas(cfg, nombre, est, n, desde):
    _escribir(cfg, nombre, _horas(est, desde, n))


@given(parsers.parse('un archivo "{nombre}" de la estación "{est}" con {n:d} horas desde "{desde}" sin la hora "{hora}"'))
def archivo_con_hueco(cfg, nombre, est, n, desde, hora):
    _escribir(cfg, nombre, _horas(est, desde, n, omitir=pd.Timestamp(hora)))


@given(parsers.parse('un archivo "{nombre}" sin la columna "{columna}"'))
def archivo_sin_columna(cfg, nombre, columna):
    filas = _horas("EST_009", "2025-03-03", 3)
    _escribir(cfg, nombre, [{k: v for k, v in f.items() if k != columna} for f in filas])


@given(parsers.parse('un archivo "{nombre}" con el valor de demanda "{valor}"'))
def archivo_texto(cfg, nombre, valor):
    _escribir(cfg, nombre, [{"estacion": "EST_008", "fecha_hora": "2025-03-03 00:00", "demanda": valor}])


@given(parsers.parse('la política de duplicados "{politica}"'))
def politica(cfg, politica):
    cfg["duplicados"] = politica


@given(parsers.parse('un archivo "{nombre}" de la estación "{est}" con la hora "{hora}" repetida con valores {a:g} y {b:g}'))
def archivo_duplicado(cfg, nombre, est, hora, a, b):
    filas = _horas(est, "2025-03-03 00:00", 12)
    filas += [{"estacion": est, "fecha_hora": hora, "demanda": a}, {"estacion": est, "fecha_hora": hora, "demanda": b}]
    filas = [f for f in filas if not (f["fecha_hora"] == hora and f["demanda"] not in (a, b))]
    _escribir(cfg, nombre, filas)


@given(parsers.parse('la zona horaria "{zona}"'))
def zona(cfg, zona):
    cfg["zona_horaria"] = zona


@given(parsers.parse('un archivo "{nombre}" de la estación "{est}" con las horas locales del cambio de horario del "{dia}"'))
def archivo_dst(cfg, nombre, est, dia):
    utc = pd.date_range(pd.Timestamp(dia, tz="UTC") - pd.Timedelta("2h"), periods=7, freq="1h")
    locales = utc.tz_convert(cfg["zona_horaria"]).tz_localize(None)
    assert locales.duplicated().any()  # el archivo contiene la hora repetida
    _escribir(cfg, nombre, [{"estacion": est, "fecha_hora": f.strftime("%Y-%m-%d %H:%M"), "demanda": 30}
                            for f in locales])


def _usar_base_curvas(cfg, tmp_path, estaciones):
    from datos.sinteticos import crear_curvas

    ruta = crear_curvas(tmp_path / "curvas.sqlite", estaciones)
    cfg["entrada"] = ruta


@given(parsers.parse('una base de curvas de demanda con "{a}" durante {na:d} horas y "{b}" durante {nb:d} horas desde "{desde}"'))
def base_curvas(cfg, tmp_path, a, na, b, nb, desde):
    def serie(n):
        idx = pd.date_range(pd.Timestamp(desde, tz=cfg["zona_horaria"]), periods=n, freq="1h")
        return pd.Series(30.0 + np.arange(n) % 7, index=idx)

    _usar_base_curvas(cfg, tmp_path, {a: {"demanda": serie(na)}, b: {"demanda": serie(nb)}})


@given(parsers.parse('una base de curvas de demanda con "{est}" con una lectura a las "{hora}" con Cambio_horario {cambio:d}'))
def base_curvas_cambio(cfg, tmp_path, est, hora, cambio):
    idx = pd.DatetimeIndex([pd.Timestamp(hora)])  # hora de reloj local, sin zona
    _usar_base_curvas(cfg, tmp_path, {est: {"demanda": pd.Series([42.0], index=idx), "cambio": [cambio]}})


@given(parsers.parse('el periodo configurado desde "{desde}" hasta "{hasta}"'))
def periodo(cfg, desde, hasta):
    cfg["periodo"] = {"desde": desde, "hasta": hasta}


@given(parsers.parse('las estaciones configuradas "{lista}"'))
def estaciones(cfg, lista):
    cfg["estaciones"] = [e.strip() for e in lista.split(",")]


@when("se ejecuta la carga")
def carga(cfg, ctx):
    ctx["carga"] = cargar_entrada(cfg)


@then(parsers.parse('el registro de "{est}" está a las "{hora}" hora local con desfase UTC "{desfase}"'))
def hora_local(ctx, est, hora, desfase):
    serie = ctx["carga"].series[est]
    t = serie.index[0]
    assert len(serie) == 1
    assert t.strftime("%Y-%m-%d %H:%M") == hora
    assert t.isoformat().endswith(desfase)


@then(parsers.parse('no se cargó la estación "{est}"'))
def no_cargada(ctx, est):
    assert est not in ctx["carga"].series


def _resumen(ctx, est):
    r = ctx["carga"].resumen
    return r[r["estacion"] == est].iloc[0]


@then(parsers.parse('el resumen informa {n:d} registros para "{est}"'))
def resumen_registros(ctx, n, est):
    assert _resumen(ctx, est)["registros"] == n


@then(parsers.parse('el resumen informa {n:d} duplicados para "{est}"'))
def resumen_duplicados(ctx, n, est):
    assert _resumen(ctx, est)["duplicados"] == n


@then("no hay archivos rechazados")
def sin_rechazos(ctx):
    assert ctx["carga"].rechazados == []


@then(parsers.parse('el archivo "{nombre}" se rechaza indicando "{texto}"'))
def rechazado(ctx, nombre, texto):
    motivos = dict(ctx["carga"].rechazados)
    assert nombre in motivos and texto in motivos[nombre], motivos


@then(parsers.parse('la demanda de "{est}" a las "{hora}" es {valor:g}'))
def demanda_en(cfg, ctx, est, hora, valor):
    assert ctx["carga"].series[est].loc[ts_local(cfg, hora), "demanda"] == valor


@then(parsers.parse('el registro "{hora}" de "{est}" está marcado como hueco'))
def es_hueco(cfg, ctx, hora, est):
    fila = ctx["carga"].series[est].loc[ts_local(cfg, hora)]
    assert fila["es_hueco"] and pd.isna(fila["demanda"])


@then(parsers.parse('la serie de "{est}" tiene intervalos regulares de 1 hora sin huecos'))
def regular(ctx, est):
    serie = ctx["carga"].series[est]
    pasos = pd.Series(serie.index.tz_convert("UTC")).diff().dropna()
    assert (pasos == pd.Timedelta("1h")).all()
    assert not serie["es_hueco"].any()
    assert len(serie) == 7
