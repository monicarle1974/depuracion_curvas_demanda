import pandas as pd
import pytest

from datos.constructores import escribir_feriados
from depuracion.calendario import ErrorFeriados, agregar_calendario, cargar_feriados, estacion_del_anio


@pytest.mark.parametrize("fecha,hemisferio,criterio,esperado", [
    ("2025-01-15", "sur", "meteorologico", "verano"),
    ("2025-04-15", "sur", "meteorologico", "otono"),
    ("2025-07-15", "sur", "meteorologico", "invierno"),
    ("2025-10-15", "sur", "meteorologico", "primavera"),
    ("2025-01-15", "norte", "meteorologico", "invierno"),
    ("2025-03-10", "sur", "astronomico", "verano"),
    ("2025-03-25", "sur", "astronomico", "otono"),
    ("2025-12-22", "norte", "astronomico", "invierno"),
])
def test_estacion_del_anio(fecha, hemisferio, criterio, esperado):
    assert estacion_del_anio(pd.DatetimeIndex([fecha]), hemisferio, criterio)[0] == esperado


def test_tipo_dia_sabado_domingo_y_feriado(cfg):
    idx = pd.date_range("2025-01-01", "2025-01-05 23:00", freq="1h", tz=cfg["zona_horaria"])  # mié..dom
    feriados = pd.DataFrame({"fecha": [pd.Timestamp("2025-01-01").date()], "descripcion": ["x"], "estacion": [""]})
    df = agregar_calendario(pd.DataFrame({"demanda": 1.0}, index=idx), "E1", feriados, cfg)
    por_dia = df.groupby(df.index.date)["tipo_dia"].first().tolist()
    assert por_dia == ["domingo_feriado", "laborable", "laborable", "sabado", "domingo_feriado"]
    assert df.loc["2025-01-01", "es_feriado"].all() and set(df["hora"]) == set(range(24))


def test_feriados_validacion(tmp_path):
    ruta = escribir_feriados(tmp_path / "f.csv", [("2025-01-01", "A", ""), ("2025-01-01", "A", ""),
                                                  ("2025-02-01", "", ""), ("x", "B", "")])
    validos, errores = cargar_feriados(ruta)
    assert len(validos) == 1
    assert any("duplicado" in e for e in errores)
    assert any("descripción" in e for e in errores)
    assert any("fecha inválida" in e for e in errores)


def test_feriados_columnas_faltantes(tmp_path):
    ruta = tmp_path / "f.csv"
    ruta.write_text("dia,nombre\n2025-01-01,x\n", encoding="utf-8")
    with pytest.raises(ErrorFeriados, match="columnas"):
        cargar_feriados(ruta)


def test_archivo_de_ejemplo_del_repositorio():
    from pathlib import Path

    validos, errores = cargar_feriados(Path(__file__).parents[1] / "datos" / "feriados_prueba.csv")
    assert len(validos) == 6 and len(errores) == 1
