import numpy as np
import pandas as pd

from depuracion.deteccion import aplicar_reglas_fisicas, detectar_outliers, marcar_por_desviacion, sigma_robusta


def test_sigma_robusta_ignora_un_pico_aislado():
    r = pd.Series([0.1, -0.2, 0.0, 0.15, 50.0])
    assert sigma_robusta(r) < 1.0


def test_sigma_robusta_vacia():
    assert np.isnan(sigma_robusta(pd.Series([], dtype=float)))


def test_marca_si_supera_k_sigmas():
    r = pd.Series([0.0, 0.1, -0.1, 10.0, 0.05, -0.05])
    assert marcar_por_desviacion(r, k=4).tolist() == [False, False, False, True, False, False]


def test_marcar_con_sigma_cero_no_marca_nada():
    assert not marcar_por_desviacion(pd.Series([1.0, 1.0, 1.0]), k=4).any()


def test_reglas_fisicas():
    d = pd.Series([-1.0, 0.0, 50.0, 200.0, np.nan])
    assert aplicar_reglas_fisicas(d, 120, False).tolist() == [
        "regla_fisica:negativo", "regla_fisica:cero", "", "regla_fisica:capacidad", ""]
    assert aplicar_reglas_fisicas(d, None, True).tolist()[1:4] == ["", "", ""]


def test_historico_insuficiente_solo_aplica_reglas_fisicas(cfg, constructor):
    cfg["min_registros_entrenamiento"] = 10**6
    constructor.con_pico("2025-06-20 19:00", 1.8).con_valor("2025-06-21 10:00", -3)
    res = detectar_outliers(constructor.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"])
    assert res["motivo"].value_counts().to_dict().get("desviacion", 0) == 0
    assert (res["motivo"] == "regla_fisica:negativo").sum() == 1


def test_filas_sin_temperatura_se_evaluan_con_modelo_sin_temperatura(cfg, constructor):
    constructor.con_pico("2025-06-20 19:00", 1.8)
    df = constructor.enriquecido(cfg)
    df.loc["2025-06-20", "temperatura"] = np.nan
    df["temp_faltante"] = df["temperatura"].isna()
    res = detectar_outliers(df, cfg, cfg["mapeo_estaciones"]["EST_001"])
    assert res.loc[pd.Timestamp("2025-06-20 19:00", tz=cfg["zona_horaria"]), "motivo"] == "desviacion"


def test_metodo_ia_tambien_detecta(cfg):
    from datos.constructores import ConstructorSerie

    serie = ConstructorSerie(dias=120).con_pico("2025-03-10 19:00", 1.8)
    res = detectar_outliers(serie.enriquecido(cfg), cfg, cfg["mapeo_estaciones"]["EST_001"], metodo="ia")
    assert res.loc[pd.Timestamp("2025-03-10 19:00", tz=cfg["zona_horaria"]), "es_outlier"]
