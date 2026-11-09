import numpy as np
import pandas as pd
import pytest

from depuracion.carga import (ErrorArchivo, FuenteDemandaNoDisponible, cargar_entrada, cargar_sqlite,
                              epoch_reloj_a_local, leer_archivo, local_a_epoch_reloj, regularizar,
                              resolver_duplicados)


def _csv(ruta, texto):
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_lee_csv_con_separador_punto_y_coma_y_coma_decimal(tmp_path, cfg):
    ruta = _csv(tmp_path / "a.csv", "estacion;fecha_hora;demanda\nE1;2025-01-01 00:00;12,5\n")
    df, origen = leer_archivo(ruta, cfg)
    assert df["demanda"].tolist() == [12.5]
    assert origen.columnas == ["estacion", "fecha_hora", "demanda"]


def test_mapeo_de_columnas_configurable(tmp_path, cfg):
    cfg["columnas"] = {"estacion": "COD", "fecha_hora": "FECHA", "demanda": "MW"}
    ruta = _csv(tmp_path / "a.csv", "COD,FECHA,MW,obs\nE1,2025-01-01 00:00,3,x\n")
    df, origen = leer_archivo(ruta, cfg)
    assert df.iloc[0]["demanda"] == 3 and origen.extras is not None


def test_valores_vacios_se_tratan_como_hueco(tmp_path, cfg):
    ruta = _csv(tmp_path / "a.csv", "estacion,fecha_hora,demanda\nE1,2025-01-01 00:00,\nE1,2025-01-01 01:00,4\n")
    df, _ = leer_archivo(ruta, cfg)
    assert df["demanda"].isna().sum() == 1


@pytest.mark.parametrize("texto,motivo", [
    ("estacion,fecha_hora\nE1,2025-01-01\n", "faltan columnas"),
    ("estacion,fecha_hora,demanda\n", "no contiene registros"),
    ("estacion,fecha_hora,demanda\nE1,no-es-fecha,3\n", "fechas inválidas"),
])
def test_archivos_invalidos(tmp_path, cfg, texto, motivo):
    with pytest.raises(ErrorArchivo, match=motivo):
        leer_archivo(_csv(tmp_path / "a.csv", texto), cfg)


def test_extension_no_soportada(tmp_path, cfg):
    with pytest.raises(ErrorArchivo, match="extensión"):
        leer_archivo(_csv(tmp_path / "a.txt", "x"), cfg)


def test_fechas_con_zona_se_convierten(tmp_path, cfg):
    ruta = _csv(tmp_path / "a.csv", "estacion,fecha_hora,demanda\nE1,2025-01-01T03:00:00+00:00,1\n")
    df, origen = leer_archivo(ruta, cfg)
    assert origen.fechas_con_zona
    assert df["fecha_hora"].iloc[0] == pd.Timestamp("2025-01-01 00:00", tz=cfg["zona_horaria"])


@pytest.mark.parametrize("politica,esperado", [("primero", 1.0), ("ultimo", 3.0), ("promedio", 2.0)])
def test_resolver_duplicados(politica, esperado):
    t = pd.Timestamp("2025-01-01", tz="UTC")
    df = pd.DataFrame({"fecha_hora": [t, t], "demanda": [1.0, 3.0]})
    res, n = resolver_duplicados(df, politica)
    assert n == 2 and res.loc[t, "demanda"] == esperado


def test_regularizar_marca_huecos():
    idx = pd.DatetimeIndex(["2025-01-01 00:00", "2025-01-01 03:00"], tz="UTC")
    res = regularizar(pd.DataFrame({"demanda": [1.0, 2.0]}, index=idx), "1h")
    assert len(res) == 4 and res["es_hueco"].tolist() == [False, True, True, False]


def test_conversion_epoch_reloj_ida_y_vuelta(cfg):
    epoch = np.array([1418241600, 1733860800])  # 2014-12-10 20:00 y 2024-12-10 20:00 (reloj)
    cambio = np.array([1, 0])
    local = epoch_reloj_a_local(epoch, cambio, cfg)
    assert [t.hour for t in local] == [20, 20]
    vuelta, cambio_vuelta = local_a_epoch_reloj(local, cfg)
    assert vuelta.tolist() == epoch.tolist() and cambio_vuelta.tolist() == [1, 0]


def test_base_de_curvas_inexistente(tmp_path, cfg):
    with pytest.raises(FuenteDemandaNoDisponible):
        cargar_sqlite(tmp_path / "no.sqlite", cfg)


def test_base_de_curvas_sin_tablas(tmp_path, cfg):
    import sqlite3

    ruta = tmp_path / "vacia.sqlite"
    sqlite3.connect(ruta).close()
    with pytest.raises(FuenteDemandaNoDisponible, match="tablas"):
        cargar_sqlite(ruta, cfg)


def test_estacion_pedida_inexistente_se_reporta(tmp_path, cfg):
    from datos.sinteticos import crear_curvas

    idx = pd.date_range("2025-01-01", periods=3, freq="1h", tz=cfg["zona_horaria"])
    ruta = crear_curvas(tmp_path / "c.sqlite", {"ACO": {"demanda": pd.Series(1.0, index=idx)}})
    res = cargar_sqlite(ruta, cfg, ["ACO", "XXX"])
    assert "ACO" in res.series and ("XXX", "estación inexistente en la base de curvas de demanda") in res.rechazados
    assert res.coordenadas["ACO"] == (-34.5, -56.4)


def test_filtro_de_estaciones_en_directorio(tmp_path, cfg):
    for est in ("E1", "E2"):
        _csv(tmp_path / "entrada" / f"{est}.csv", f"estacion,fecha_hora,demanda\n{est},2025-01-01 00:00,1\n")
    res = cargar_entrada(cfg, ["E2"])
    assert list(res.series) == ["E2"] and res.resumen["estacion"].tolist() == ["E2"]
