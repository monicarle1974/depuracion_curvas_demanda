"""Criterios de éxito CE-001..CE-005 y RF-022 con datos sintéticos (2 años)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datos.constructores import ConstructorSerie, escribir_feriados
from datos.sinteticos import crear_curvas, crear_inia
from depuracion.__main__ import main
from depuracion.deteccion import detectar_outliers
from depuracion.pipeline import ejecutar
from depuracion.sustitucion import sustituir

pytestmark = pytest.mark.integracion

UMBRALES = {"recall": 0.90, "falsos_positivos": 0.05, "mape": 0.05}


@pytest.fixture(scope="module")
def dos_anios():
    serie = ConstructorSerie("EST_001", dias=730, seed=11).con_anomalias(200, seed=3)
    return serie


@pytest.fixture
def detectado(cfg, dos_anios):
    return detectar_outliers(dos_anios.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])


def test_ce001_deteccion_de_anomalias(detectado, dos_anios):
    anomalias = pd.DatetimeIndex(list(dos_anios.anomalias))
    recall = detectado.loc[anomalias, "es_outlier"].mean()
    assert recall >= UMBRALES["recall"], recall


def test_ce002_falsos_positivos(detectado, dos_anios):
    normales = ~detectado.index.isin(pd.DatetimeIndex(list(dos_anios.anomalias))) & ~detectado["es_hueco"]
    tasa = detectado.loc[normales, "es_outlier"].mean()
    assert tasa < UMBRALES["falsos_positivos"], tasa


def test_ce003_mape_de_valores_ocultados(cfg):
    serie = ConstructorSerie("EST_001", dias=730, seed=5)
    rng = np.random.default_rng(1)
    ocultos = pd.DatetimeIndex(sorted(rng.choice(serie.indice, 300, replace=False)))
    for t in ocultos:
        serie.con_hueco(t.strftime("%Y-%m-%d %H:%M"))
    df = detectar_outliers(serie.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])
    res, _ = sustituir(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    real = serie.real()[ocultos]
    mape = float(((res.loc[ocultos, "demanda_depurada"] - real).abs() / real).mean())
    assert (res.loc[ocultos, "origen"] == "estimado").all()
    assert mape < UMBRALES["mape"], mape


def _preparar_entrada(cfg, dias=365):
    serie = ConstructorSerie("EST_001", dias=dias).con_anomalias(50).con_hueco("2025-02-10 03:00", 4)
    serie.escribir(cfg["entrada"], "est1.csv", ruta_inia=cfg["inia"]["ruta"])
    escribir_feriados(cfg["feriados"], [("2025-01-01", "Año Nuevo", "")])
    return serie


def _huellas(carpeta):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(carpeta).rglob("*") if p.is_file()}


def test_ce004_ce005_trazabilidad_y_originales_intactos(cfg):
    _preparar_entrada(cfg)
    antes = _huellas(cfg["entrada"])
    ej = ejecutar(cfg, nombre_ejecucion="e1")
    assert ej.codigo == 0, ej.errores
    assert _huellas(cfg["entrada"]) == antes  # CE-005
    cambios = pd.read_csv(ej.ruta_salida / "cambios.csv")
    df = ej.estaciones["EST_001"].df
    assert set(cambios.loc[cambios["origen"] == "estimado", "fecha_hora"]) == {
        t.isoformat() for t in df.index[df["origen"] == "estimado"]}  # CE-004


def test_rf022_dos_ejecuciones_identicas(cfg):
    _preparar_entrada(cfg, dias=200)
    a = ejecutar(cfg, nombre_ejecucion="a").ruta_salida
    b = ejecutar(cfg, nombre_ejecucion="b").ruta_salida
    for nombre in ("depurados/est1.csv", "cambios.csv", "informe.csv", "revision_outliers.csv"):
        assert (a / nombre).read_bytes() == (b / nombre).read_bytes(), nombre


def test_estacion_con_error_no_detiene_las_demas(cfg):
    _preparar_entrada(cfg, dias=120)
    otra = ConstructorSerie("EST_002", dias=120)
    otra.escribir(cfg["entrada"], "est2.csv")  # EST_002 → DURAZNO, que no existe en inia
    ej = ejecutar(cfg, nombre_ejecucion="p")
    assert ej.codigo == 2
    assert "EST_001" in ej.estaciones and any("EST_002" in e for e in ej.errores)


def test_estacion_sin_mapeo_ni_coordenadas(cfg):
    _preparar_entrada(cfg, dias=60)
    ConstructorSerie("EST_009", dias=60).escribir(cfg["entrada"], "est9.csv")
    ej = ejecutar(cfg, dry_run=True)
    assert ej.codigo == 2 and any("EST_009" in e and "mapeo" in e for e in ej.errores)


def test_pipeline_desde_base_sqlite_con_mapeo_automatico(cfg, tmp_path):
    serie = ConstructorSerie("ACO", dias=200).con_anomalias(30)
    cfg["entrada"] = crear_curvas(tmp_path / "curvas.sqlite",
                                  {"ACO": {"lat": -34.53, "lon": -56.38, "demanda": serie.demanda()}})
    crear_inia(cfg["inia"]["ruta"], {"LAS_BRUJAS": serie.temperatura})
    escribir_feriados(cfg["feriados"], [("2025-01-01", "Año Nuevo", "")])
    ej = ejecutar(cfg, nombre_ejecucion="s")
    assert ej.codigo == 0, ej.errores
    assert cfg["mapeo_estaciones"]["ACO"]["inia"] == "LAS_BRUJAS"
    assert cfg["mapeo_estaciones"]["ACO"]["mapeo"] == "automatico"
    assert (ej.ruta_salida / "depurados" / "ACO.csv").is_file()


def test_cli_depurar_y_evaluar_revision(cfg, tmp_path, capsys):
    import yaml

    _preparar_entrada(cfg, dias=120)
    ruta_cfg = tmp_path / "config.yaml"
    datos = {"entrada": str(cfg["entrada"]), "salida": str(cfg["salida"]), "feriados": str(cfg["feriados"]),
             "inia": {"ruta": str(cfg["inia"]["ruta"])}, "min_registros_entrenamiento": 500,
             "mapeo_estaciones": {"EST_001": {"inia": "LAS_BRUJAS", "capacidad_max_mw": 120}}}
    ruta_cfg.write_text(yaml.safe_dump(datos), encoding="utf-8")

    assert main(["depurar", "--config", str(ruta_cfg), "--dry-run"]) == 0
    assert main(["depurar", "--config", str(ruta_cfg), "--metodo", "lineal"]) == 0
    salida = next(p for p in cfg["salida"].iterdir() if p.is_dir())
    rev = pd.read_csv(salida / "revision_outliers.csv", dtype=str, keep_default_na=False)
    rev["confirmado"] = "si"
    rev.to_csv(salida / "revision_outliers.csv", index=False)
    assert main(["evaluar-revision", "--config", str(ruta_cfg), "--archivo", str(salida / "revision_outliers.csv")]) == 0
    assert "aceptada" in capsys.readouterr().out
    assert main(["depurar", "--config", str(tmp_path / "no.yaml")]) == 1
