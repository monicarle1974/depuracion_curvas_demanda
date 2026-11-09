"""Fixtures compartidas por todas las pruebas."""

from __future__ import annotations

from pathlib import Path

import pytest

from datos.constructores import ConstructorSerie, escribir_feriados
from depuracion.config import config_desde_dict

DATOS = Path(__file__).parent / "datos"


def config_prueba(tmp_path: Path, **extra) -> dict:
    """Configuración de prueba: rutas en ``tmp_path`` y valores por defecto del plan."""
    base = {
        "entrada": str(tmp_path / "entrada"),
        "salida": str(tmp_path / "salida"),
        "feriados": str(tmp_path / "feriados.csv"),
        "inia": {"ruta": str(tmp_path / "inia.sqlite")},
        "min_registros_entrenamiento": 500,
        "mapeo_estaciones": {
            "EST_001": {"inia": "LAS_BRUJAS", "capacidad_max_mw": 120, "permite_cero": False},
            "EST_002": {"inia": "DURAZNO", "capacidad_max_mw": 120, "permite_cero": False},
        },
    }
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            base[clave] = {**base[clave], **valor}
        else:
            base[clave] = valor
    return config_desde_dict(base)


@pytest.fixture
def cfg(tmp_path):
    (tmp_path / "entrada").mkdir()
    escribir_feriados(tmp_path / "feriados.csv", [("2025-01-01", "Año Nuevo", "")])
    return config_prueba(tmp_path)


@pytest.fixture
def constructor():
    return ConstructorSerie("EST_001", dias=365)
