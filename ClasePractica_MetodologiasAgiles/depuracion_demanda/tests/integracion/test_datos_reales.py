"""Pruebas con las bases reales (no corren en CI).

Ejecutar en Docker:  docker compose run --rm pruebas -m datos_reales
Las bases se montan en solo lectura en /datos (ver docker-compose.yml).
"""

import os
from pathlib import Path

import pandas as pd
import pytest

from depuracion.carga import cargar_sqlite, local_a_epoch_reloj
from depuracion.temperatura import abrir_inia, alinear, inia_cercanas, leer_temperatura

pytestmark = pytest.mark.datos_reales

INIA = Path(os.environ.get("INIA_SQLITE", "/datos/inia.sqlite"))
CURVAS = Path(os.environ.get("CURVAS_SQLITE", "/datos/BD_CurvasDemanda.sqlite"))


@pytest.fixture
def reales(cfg):
    if not INIA.is_file() or not CURVAS.is_file():
        pytest.skip("bases reales no disponibles")
    cfg["periodo"] = {"desde": "2024-01-01", "hasta": "2024-01-31"}
    return cfg


FERIADOS = Path(os.environ.get("FERIADOS_TXT", "/datos/tiposDeDia.txt"))


def test_archivo_real_de_feriados(reales):
    from depuracion.calendario import cargar_feriados

    if not FERIADOS.is_file():
        pytest.skip("tiposDeDia.txt no disponible")
    feriados, errores = cargar_feriados(FERIADOS)
    fechas = set(feriados["fecha"])
    assert errores == [], errores
    for dia in ("2024-01-01", "2024-02-12", "2024-03-29", "2024-07-18", "2024-12-25"):
        assert pd.Timestamp(dia).date() in fechas, dia


def test_inia_real_temperatura_horaria_plausible(reales):
    con = abrir_inia(INIA)
    inicio = pd.Timestamp("2024-01-01", tz=reales["zona_horaria"])
    t = leer_temperatura(con, "LAS_BRUJAS", inicio, inicio + pd.Timedelta("7D"), reales)
    horaria = alinear(t, pd.date_range(inicio, periods=7 * 24, freq="1h"), "1h", "auto")
    assert horaria.notna().mean() > 0.9
    assert 5 < horaria.mean() < 35  # enero en Uruguay


def test_curvas_reales_se_cargan_y_mapean(reales):
    res = cargar_sqlite(CURVAS, reales, ["ACO", "MVL"])
    assert set(res.series) == {"ACO", "MVL"}
    serie = res.series["ACO"]
    assert len(serie) == 31 * 24
    # La hora local reconstruida devuelve exactamente el Fecha_hora (reloj) de la base.
    import sqlite3

    epoch, _ = local_a_epoch_reloj(serie.index, reales)
    con = sqlite3.connect(f"file:{CURVAS}?mode=ro", uri=True)
    originales = [r[0] for r in con.execute(
        "SELECT Fecha_hora FROM POTENCIA_ESTACION p JOIN ESTACIONES e ON e.Id_estacion = p.Id_estacion "
        "WHERE e.Codigo_estacion = 'ACO' AND Fecha_hora BETWEEN ? AND ? ORDER BY Fecha_hora",
        (int(epoch[0]), int(epoch[-1])))]
    con.close()
    assert epoch.tolist() == originales
    con = abrir_inia(INIA)
    assert inia_cercanas(con, *res.coordenadas["ACO"], reales)[0][0] == "LAS_BRUJAS"
