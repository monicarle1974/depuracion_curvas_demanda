from pathlib import Path

import numpy as np
import pandas as pd
from pytest_bdd import given, parsers, scenarios, then, when

from datos.constructores import escribir_feriados, ts_local
from datos.sinteticos import crear_inia
from depuracion.calendario import agregar_calendario, cargar_feriados
from depuracion.temperatura import abrir_inia, agregar_temperatura

scenarios("h2_temperatura.feature")


def _indice(cfg, desde, dias, freq):
    return pd.date_range(pd.Timestamp(desde, tz=cfg["zona_horaria"]), periods=int(pd.Timedelta(f"{dias}D") / pd.Timedelta(freq)),
                         freq=freq)


@given(parsers.parse('una base inia con "{a}" a {ta:g} °C y "{b}" a {tb:g} °C cada 10 minutos desde "{desde}" durante {dias:d} días'))
def inia_dos_estaciones(cfg, a, ta, b, tb, desde, dias):
    idx = _indice(cfg, desde, dias, "10min")
    crear_inia(cfg["inia"]["ruta"], {a: pd.Series(ta, index=idx), b: pd.Series(tb, index=idx)})


@given(parsers.parse('una base inia con lecturas de "{est}" cada {resolucion} desde "{desde}" durante {dias:d} días'))
def inia_patron(cfg, est, resolucion, desde, dias):
    idx = _indice(cfg, desde, dias, resolucion)
    if resolucion == "10min":  # 10, 11, ..., 15 dentro de cada hora → media horaria 12.5
        valores = 10 + idx.minute / 10
    else:  # valor = hora del día (lecturas cada 2 h)
        valores = idx.hour.astype(float)
    crear_inia(cfg["inia"]["ruta"], {est: pd.Series(np.asarray(valores, float), index=idx)}, cada=resolucion)


@given(parsers.parse('una base inia con "{est}" sin lecturas entre "{desde}" y "{hasta}"'))
def inia_con_hueco(cfg, est, desde, hasta):
    idx = _indice(cfg, "2025-01-06", 2, "10min")
    temp = pd.Series(20 + np.sin(np.arange(len(idx)) / 20), index=idx)
    temp = temp[(temp.index < ts_local(cfg, desde)) | (temp.index > ts_local(cfg, hasta))]
    crear_inia(cfg["inia"]["ruta"], {est: temp, "DURAZNO": pd.Series(25.0, index=idx)})


@given(parsers.parse('una base inia con "{a}" en ({lat_a:g}, {lon_a:g}) y "{b}" en ({lat_b:g}, {lon_b:g})'))
def inia_con_coordenadas(cfg, a, lat_a, lon_a, b, lat_b, lon_b):
    import sqlite3

    idx = _indice(cfg, "2025-01-06", 1, "1h")
    ruta = crear_inia(cfg["inia"]["ruta"], {a: pd.Series(20.0, index=idx), b: pd.Series(25.0, index=idx)})
    con = sqlite3.connect(ruta)
    con.executemany("UPDATE Estaciones SET Coord_y = ?, Coord_x = ? WHERE Nombre = ?",
                    [(lat_a, lon_a, a), (lat_b, lon_b, b)])
    con.commit()
    con.close()


@given(parsers.parse('una estación eléctrica "{est}" sin mapeo en ({lat:g}, {lon:g})'))
def estacion_sin_mapeo(cfg, ctx, est, lat, lon):
    cfg["mapeo_estaciones"].pop(est, None)
    ctx["coordenadas"] = {est: (lat, lon)}


@when(parsers.parse('se resuelve la estación INIA de "{est}"'))
def resolver(cfg, ctx, est):
    from depuracion.pipeline import resolver_mapeo

    con = abrir_inia(cfg["inia"]["ruta"])
    try:
        resolver_mapeo(cfg, est, ctx["coordenadas"], con)
    finally:
        con.close()


@then(parsers.parse('"{est}" usa "{inia}" con respaldo "{respaldo}"'))
def usa_inia(cfg, est, inia, respaldo):
    assert cfg["mapeo_estaciones"][est]["inia"] == inia
    assert cfg["mapeo_estaciones"][est]["inia_respaldo"] == respaldo


@given(parsers.parse('la estación eléctrica "{est}" asociada a "{inia}"'))
def asociada(cfg, est, inia):
    cfg["mapeo_estaciones"][est].update({"inia": inia, "inia_respaldo": None})


@given(parsers.parse('la estación eléctrica "{est}" asociada a "{inia}" con respaldo "{respaldo}"'))
def asociada_respaldo(cfg, est, inia, respaldo):
    cfg["mapeo_estaciones"][est].update({"inia": inia, "inia_respaldo": respaldo})


@given(parsers.parse('el modo de alineación "{modo}"'))
def modo_alineacion(cfg, modo):
    cfg["alineacion"] = modo


@given("que la base inia no existe")
def sin_inia(cfg):
    Path(cfg["inia"]["ruta"]).unlink(missing_ok=True)
    escribir_feriados(cfg["feriados"], [("2025-01-01", "Año Nuevo", "")])


@given("que el archivo de feriados no existe")
def sin_feriados(cfg):
    Path(cfg["feriados"]).unlink(missing_ok=True)


@given(parsers.parse('un archivo de feriados con "{general}" general y "{local}" local de "{est}"'))
def feriados_general_local(cfg, ctx, general, local, est):
    escribir_feriados(cfg["feriados"], [(general, "General", ""), (local, "Local", est)])


@given(parsers.parse("un archivo de feriados con una fecha inválida en la línea {n:d}"))
def feriados_invalidos(cfg, n):
    filas = [("2025-01-01", "Año Nuevo", ""), ("2025-05-01", "Trabajadores", ""), ("2025-12-25", "Navidad", "")]
    filas.insert(n - 2, ("2025-02-30", "Fecha imposible", ""))
    escribir_feriados(cfg["feriados"], filas)


@when(parsers.parse('se enriquece una serie horaria de "{est}" desde "{desde}" durante {dias:d} días'))
def enriquecer(cfg, ctx, est, desde, dias):
    idx = _indice(cfg, desde, dias, "1h")
    serie = pd.DataFrame({"estacion": est, "demanda": 30.0, "es_hueco": False}, index=idx)
    con = abrir_inia(cfg["inia"]["ruta"])
    try:
        ctx[est] = agregar_temperatura(serie, est, con, cfg)
    finally:
        con.close()


@when(parsers.parse('se agregan las variables de calendario para "{a}" y "{b}" en enero de 2025'))
def calendario(cfg, ctx, a, b):
    feriados, _ = cargar_feriados(cfg["feriados"])
    idx = _indice(cfg, "2025-01-01", 31, "1h")
    for est in (a, b):
        ctx[est] = agregar_calendario(pd.DataFrame({"demanda": 1.0}, index=idx), est, feriados, cfg)


@given(parsers.parse('un archivo de feriados en formato tiposDeDia con el feriado fijo {mes:d}/{dia:d} y el "{especial}"'))
def feriados_tipos_dia(cfg, mes, dia, especial):
    from pathlib import Path

    ruta = Path(cfg["feriados"]).with_name("tiposDeDia.txt")
    ruta.write_text(
        "// TIPOS DE DIAS DE LOS 7 DIAS DE LA SEMANA DO, LU, MA, MI, JU, VI, SA\n"
        "TIPOS_DIA_SEMANA 1 2 3 4 5 6 7\n"
        "// FERIADOS CON IGUAL FECHA EN TODOS LOS AÑOS\n"
        "FERIADOS_COMUNES CANTIDAD 1   // mes / día / tipo de día\n"
        f"{mes} {dia}\n"
        "// DIAS ESPECIALES\n"
        "2023 4 3 lunes-turismo\n"
        f"{especial}    // comentario al final\n",
        encoding="latin-1",
    )
    cfg["feriados"] = ruta


@when("se cargan los feriados")
def cargar(cfg, ctx):
    ctx["feriados"], ctx["errores_feriados"] = cargar_feriados(cfg["feriados"])


@then(parsers.parse('todas las temperaturas de "{est}" son {t:g} °C'))
def todas(ctx, est, t):
    assert np.allclose(ctx[est]["temperatura"], t)


@then(parsers.parse('la temperatura de "{est}" a las "{hora}" es {esperado:g}'))
def temperatura_en(cfg, ctx, est, hora, esperado):
    assert ctx[est].loc[ts_local(cfg, hora), "temperatura"] == np.float64(esperado)


@then(parsers.parse('la temperatura de "{est}" a las "{hora}" tiene origen "{origen}"'))
def origen_en(cfg, ctx, est, hora, origen):
    assert ctx[est].loc[ts_local(cfg, hora), "origen_temperatura"] == origen


@then(parsers.parse('ningún registro de "{est}" tiene temperatura faltante'))
def sin_faltantes(ctx, est):
    assert not ctx[est]["temp_faltante"].any()


@then(parsers.parse('el registro de "{est}" a las "{hora}" tiene temperatura faltante'))
def con_faltante(cfg, ctx, est, hora):
    assert ctx[est].loc[ts_local(cfg, hora), "temp_faltante"]


@then(parsers.parse('el "{dia}" es "{tipo}" para "{est}"'))
def tipo_dia(cfg, ctx, dia, tipo, est):
    assert (ctx[est].loc[dia, "tipo_dia"] == tipo).all()


@then(parsers.parse('se reporta un error en la "{texto}"'))
def error_feriado(ctx, texto):
    assert any(texto in e for e in ctx["errores_feriados"]), ctx["errores_feriados"]


@then(parsers.parse('el "{a}" y el "{b}" son feriado'))
def son_feriado(ctx, a, b):
    fechas = set(ctx["feriados"]["fecha"])
    assert pd.Timestamp(a).date() in fechas and pd.Timestamp(b).date() in fechas


@then(parsers.parse('el "{dia}" es feriado con descripción "{descripcion}"'))
def feriado_con_descripcion(ctx, dia, descripcion):
    f = ctx["feriados"]
    fila = f[f["fecha"] == pd.Timestamp(dia).date()]
    assert fila["descripcion"].tolist() == [descripcion]


@then(parsers.parse('el "{dia}" no es feriado'))
def no_feriado(ctx, dia):
    assert pd.Timestamp(dia).date() not in set(ctx["feriados"]["fecha"])


@then("los demás feriados se cargan")
def demas_feriados(ctx):
    assert len(ctx["feriados"]) == 3
