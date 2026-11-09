import sqlite3

import numpy as np
import pandas as pd
import pytest

from datos.sinteticos import crear_inia
from depuracion.temperatura import (EstacionInexistente, FuenteTemperaturaNoDisponible, abrir_inia, alinear,
                                    completar_faltantes, distancia_km, inia_cercanas, leer_temperatura)

TZ = "America/Montevideo"


def test_abrir_inia_es_solo_lectura(tmp_path):
    idx = pd.date_range("2025-01-01", periods=3, freq="1h", tz=TZ)
    con = abrir_inia(crear_inia(tmp_path / "i.sqlite", {"A": pd.Series(1.0, index=idx)}))
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM Medidas")
    con.close()


def test_abrir_inia_sin_tablas(tmp_path):
    ruta = tmp_path / "v.sqlite"
    sqlite3.connect(ruta).close()
    with pytest.raises(FuenteTemperaturaNoDisponible, match="tablas"):
        abrir_inia(ruta)


def test_estacion_inia_inexistente(tmp_path, cfg):
    idx = pd.date_range("2025-01-01", periods=3, freq="1h", tz=TZ)
    con = abrir_inia(crear_inia(tmp_path / "i.sqlite", {"A": pd.Series(1.0, index=idx)}))
    with pytest.raises(EstacionInexistente):
        leer_temperatura(con, "NO_EXISTE", idx[0], idx[-1], cfg)


def test_descarta_valores_fuera_de_rango(tmp_path, cfg):
    idx = pd.date_range("2025-01-01", periods=4, freq="1h", tz=TZ)
    con = abrir_inia(crear_inia(tmp_path / "i.sqlite", {"A": pd.Series([10.0, -99.0, 12.0, 80.0], index=idx)},
                                cada="1h"))
    t = leer_temperatura(con, "A", idx[0], idx[-1], cfg)
    assert t.dropna().tolist() == [10.0, 12.0]


def test_alinear_media_intervalo_y_auto():
    idx10 = pd.date_range("2025-01-01", periods=12, freq="10min", tz=TZ)
    temp = pd.Series(np.arange(12, dtype=float), index=idx10)
    horas = pd.date_range("2025-01-01", periods=2, freq="1h", tz=TZ)
    assert alinear(temp, horas, "1h", "media_intervalo").tolist() == [2.5, 8.5]
    assert alinear(temp, horas, "1h", "auto").tolist() == [2.5, 8.5]


def test_alinear_sin_datos_devuelve_nan():
    horas = pd.date_range("2025-01-01", periods=2, freq="1h", tz=TZ)
    vacia = pd.Series(dtype=float, index=pd.DatetimeIndex([], tz=TZ))
    assert alinear(vacia, horas, "1h", "auto").isna().all()


def test_alinear_modo_invalido():
    idx = pd.date_range("2025-01-01", periods=2, freq="1h", tz=TZ)
    with pytest.raises(ValueError):
        alinear(pd.Series(1.0, index=idx), idx, "1h", "otro")


def test_completar_faltantes_respeta_limite():
    idx = pd.date_range("2025-01-01", periods=12, freq="1h", tz=TZ)
    temp = pd.Series([1.0, np.nan, 3.0] + [np.nan] * 8 + [12.0], index=idx)
    res, origen = completar_faltantes(temp, None, "2h", "1h")
    assert res.iloc[1] == 2.0 and origen.iloc[1] == "interpolada"
    assert res.iloc[3:11].isna().all() and (origen.iloc[3:11] == "faltante").all()


def test_distancia_y_cercanas(tmp_path, cfg):
    assert distancia_km(-34.9, -56.2, -34.9, -56.2) == 0
    assert 150 < distancia_km(-34.67, -56.34, -33.31, -56.52) < 160
    idx = pd.date_range("2025-01-01", periods=2, freq="1h", tz=TZ)
    ruta = crear_inia(tmp_path / "i.sqlite", {"A": pd.Series(1.0, index=idx), "B": pd.Series(1.0, index=idx)})
    con = sqlite3.connect(ruta)
    con.execute("UPDATE Estaciones SET Coord_y=-30, Coord_x=-57 WHERE Nombre='A'")
    con.commit()
    con.close()
    con = abrir_inia(ruta)
    assert [n for n, _ in inia_cercanas(con, -34.0, -56.0, cfg)] == ["B", "A"]
