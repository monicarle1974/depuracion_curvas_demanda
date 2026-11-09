from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from depuracion.revision import evaluar, evaluar_archivo, generar_muestra
from depuracion.salida import escribir_salidas, tabla_cambios


def _resultado(n=50, outliers=(3, 7, 11)):
    idx = pd.date_range("2025-01-01", periods=n, freq="1h", tz="America/Montevideo")
    df = pd.DataFrame({"demanda": np.arange(n, dtype=float), "es_outlier": False, "es_hueco": False,
                       "motivo": "", "desviacion_sigma": np.nan, "temperatura": 20.0,
                       "origen_temperatura": "inia", "metodo": "", "temp_faltante": False}, index=idx)
    df.iloc[list(outliers), df.columns.get_loc("es_outlier")] = True
    df.loc[df["es_outlier"], "motivo"] = "desviacion"
    df["demanda_depurada"] = df["demanda"]
    df["origen"] = np.where(df["es_outlier"], "estimado", "original")
    return df


def test_muestra_reproducible_y_acotada(cfg):
    cfg["aceptacion"]["muestra_outliers_por_estacion"] = 2
    a = generar_muestra({"E1": _resultado()}, cfg)
    b = generar_muestra({"E1": _resultado()}, cfg)
    assert len(a) == 2 and a.equals(b) and (a["confirmado"] == "").all()


def test_muestra_menor_que_el_tamano_configurado(cfg):
    assert len(generar_muestra({"E1": _resultado(), "E2": _resultado(outliers=())}, cfg)) == 3


@pytest.mark.parametrize("respuesta", ["sí", "SI", "s", "yes", "1"])
def test_variantes_de_si(cfg, respuesta):
    rev = pd.DataFrame({"estacion": ["E1"] * 5, "confirmado": [respuesta] * 5})
    assert evaluar(rev, cfg).iloc[0]["resultado"] == "aceptada"


def test_evaluar_archivo(tmp_path, cfg):
    ruta = tmp_path / "r.csv"
    ruta.write_text("estacion,confirmado\nE1,si\nE1,no\nE2,si\n", encoding="utf-8")
    res = evaluar_archivo(ruta, cfg).set_index("estacion")
    assert res.loc["E1", "resultado"] == "rechazada" and res.loc["E2", "resultado"] == "aceptada"


def test_tabla_cambios_vacia():
    df = _resultado(outliers=())
    assert tabla_cambios({"E1": df}).empty


def test_escritura_atomica_limpia_si_falla(cfg, monkeypatch):
    import depuracion.salida as salida

    ejecucion = SimpleNamespace(estaciones={}, carga=SimpleNamespace(archivos=[], fuente="archivos"),
                                errores=[], errores_feriados=[])
    monkeypatch.setattr(salida, "tabla_informe", lambda *_: (_ for _ in ()).throw(RuntimeError("falla")))
    with pytest.raises(RuntimeError):
        escribir_salidas(ejecucion, cfg, "x")
    assert list(cfg["salida"].iterdir()) == []


def test_no_sobrescribe_una_ejecucion_existente(cfg):
    (cfg["salida"] / "x").mkdir(parents=True)
    ejecucion = SimpleNamespace(estaciones={}, carga=SimpleNamespace(archivos=[], fuente="archivos"),
                                errores=[], errores_feriados=[])
    with pytest.raises(FileExistsError):
        escribir_salidas(ejecucion, cfg, "x")
