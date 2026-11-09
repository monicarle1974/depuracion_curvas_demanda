import pytest

from depuracion.config import ErrorConfiguracion, cargar_config, config_desde_dict


def _minima(tmp_path):
    return {
        "entrada": str(tmp_path / "entrada"),
        "salida": str(tmp_path / "salida"),
        "feriados": str(tmp_path / "feriados.csv"),
        "inia": {"ruta": str(tmp_path / "inia.sqlite")},
        "mapeo_estaciones": {"EST_001": {"inia": "LAS_BRUJAS", "capacidad_max_mw": 120}},
    }


def test_aplica_valores_por_defecto(tmp_path):
    cfg = config_desde_dict(_minima(tmp_path))
    assert cfg["deteccion"]["k"] == 4.0
    assert cfg["aceptacion"]["min_outliers_confirmados"] == 0.80
    assert cfg["aceptacion"]["muestra_outliers_por_estacion"] == 20
    assert cfg["hemisferio"] == "sur"
    assert cfg["mapeo_estaciones"]["EST_001"]["permite_cero"] is False


def test_rechaza_campo_obligatorio_faltante(tmp_path):
    datos = _minima(tmp_path)
    del datos["feriados"]
    with pytest.raises(ErrorConfiguracion, match="feriados"):
        config_desde_dict(datos)


def test_rechaza_tipo_invalido(tmp_path):
    datos = _minima(tmp_path)
    datos["deteccion"] = {"k": "mucho"}
    with pytest.raises(ErrorConfiguracion, match="deteccion.k"):
        config_desde_dict(datos)


@pytest.mark.parametrize("umbral", [0, 1.5, -0.1])
def test_rechaza_umbral_aceptacion_fuera_de_rango(tmp_path, umbral):
    datos = _minima(tmp_path)
    datos["aceptacion"] = {"min_outliers_confirmados": umbral}
    with pytest.raises(ErrorConfiguracion, match="min_outliers_confirmados"):
        config_desde_dict(datos)


def test_rechaza_valor_no_permitido(tmp_path):
    datos = _minima(tmp_path)
    datos["metodo"] = "magia"
    with pytest.raises(ErrorConfiguracion, match="metodo"):
        config_desde_dict(datos)


def test_salida_no_puede_estar_dentro_de_entrada(tmp_path):
    datos = _minima(tmp_path)
    datos["salida"] = str(tmp_path / "entrada" / "salida")
    with pytest.raises(ErrorConfiguracion, match="salida"):
        config_desde_dict(datos)


def test_rutas_relativas_al_archivo_de_config(tmp_path):
    ruta = tmp_path / "config.yaml"
    ruta.write_text(
        "entrada: datos/demanda\nsalida: datos/depurado\nferiados: datos/feriados.csv\n"
        "inia: {ruta: ../inia.sqlite}\n"
        "mapeo_estaciones: {EST_001: {inia: LAS_BRUJAS, capacidad_max_mw: 120}}\n",
        encoding="utf-8",
    )
    cfg = cargar_config(ruta)
    assert cfg["entrada"] == (tmp_path / "datos" / "demanda").resolve()
    assert cfg["inia"]["ruta"] == (tmp_path / ".." / "inia.sqlite").resolve()


def test_archivo_de_config_inexistente(tmp_path):
    with pytest.raises(ErrorConfiguracion, match="no existe"):
        cargar_config(tmp_path / "no.yaml")
