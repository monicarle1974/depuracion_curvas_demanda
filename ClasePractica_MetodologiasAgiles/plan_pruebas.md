# Plan de Pruebas TDD: Depuración de Archivos de Demanda Eléctrica

| Campo              | Valor                                                                 |
|--------------------|-----------------------------------------------------------------------|
| **ID**             | 002-depuracion-demanda-electrica                                      |
| **Fecha**          | 2026-11-09                                                            |
| **Estado**         | Borrador                                                              |
| **Especificación** | [spec_depuracion_demanda_electrica.md](spec_depuracion_demanda_electrica.md) |
| **Plan**           | [plan.md](plan.md) · **Tareas**: [tasks.md](tasks.md)                 |
| **Frameworks**     | pytest · **pytest-bdd** (Gherkin en español) · hypothesis · pytest-cov |

---

## 1. Enfoque: TDD de doble ciclo (ATDD + TDD unitario)

Los escenarios **Dado / Cuando / Entonces** del spec se convierten **directamente** en pruebas funcionales ejecutables. Cada historia se desarrolla con dos ciclos anidados:

```
 ┌──────────────── CICLO EXTERNO (funcional / aceptación) ────────────────┐
 │ 1. Escribir el escenario .feature copiado del spec        → ROJO       │
 │                                                                         │
 │    ┌──────────── CICLO INTERNO (unitario) ────────────┐                │
 │    │ 2a. Prueba unitaria de la pieza mínima → ROJO    │                │
 │    │ 2b. Código mínimo para pasarla        → VERDE    │  repetir hasta │
 │    │ 2c. Refactorizar                      → VERDE    │  que el        │
 │    └──────────────────────────────────────────────────┘  escenario    │
 │                                                           pase         │
 │ 3. El escenario .feature pasa                             → VERDE      │
 │ 4. Refactorizar con toda la red de pruebas en verde                     │
 └─────────────────────────────────────────────────────────────────────────┘
```

**Reglas del equipo**
- No se escribe código de producción sin una prueba en rojo que lo pida.
- Un escenario del spec equivale a un `Escenario` en un `.feature`. El identificador (`H3.4`) va en el título, para que la trazabilidad sea inmediata.
- Si se cambia el spec, primero se cambia el `.feature` y después el código.
- Los commits se hacen en verde. Se recomienda hacer un commit por cada ciclo rojo → verde → refactor.

---

## 2. Por qué estas herramientas

| Herramienta     | Uso                                                       | Por qué es ágil y útil                                                    |
|-----------------|-----------------------------------------------------------|---------------------------------------------------------------------------|
| **pytest**      | Ejecutor único de todas las pruebas                       | Ya está en el plan; tiene fixtures, marcadores y salida legible            |
| **pytest-bdd**  | Pruebas **funcionales** escritas en Gherkin               | El Product Owner puede leer los `.feature` en español; corren con el mismo `pytest` sin otro ejecutor; reutiliza las fixtures |
| **hypothesis**  | Pruebas basadas en **propiedades** (invariantes)          | Genera cientos de casos límite automáticamente para las reglas RN-01, RN-02 y RN-05 |
| **pytest-cov**  | Cobertura                                                 | Comprueba los umbrales de la DoD (≥ 80 % en el MVP y ≥ 85 % al final)      |
| `pandas.testing`| Comparación de DataFrames y series                        | Mensajes de diferencia claros (`assert_frame_equal`)                       |
| **GitHub Actions** | Integración continua en el repositorio                 | Ejecuta las pruebas en cada push o pull request, sin coste para repositorios públicos |

> Alternativas descartadas: **behave** es un buen framework BDD, pero usa su propio ejecutor y no comparte las fixtures de pytest. **Robot Framework** es más pesado y está más orientado a la automatización de interfaces. pytest-bdd da el mismo lenguaje Gherkin con menos fricción.

---

## 3. Pirámide de pruebas

```
                 ▲   Datos reales piloto (@datos_reales)         manual-asistida, antes de la demo
                ▲▲▲  Criterios de éxito CE (@integracion)        pocos, lentos, con datos sintéticos
              ▲▲▲▲▲▲ Funcionales BDD (.feature, @h1..@h6)        1 por escenario del spec (~30)
           ▲▲▲▲▲▲▲▲▲▲ Propiedades (hypothesis)                   invariantes de negocio
       ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲ Unitarias (pytest)                        muchas, < 1 s cada una
```

| Nivel           | Qué valida                                         | Velocidad objetivo | Cuándo se ejecuta          |
|-----------------|----------------------------------------------------|--------------------|----------------------------|
| Unitarias       | Funciones puras de cada módulo                     | Todo < 10 s        | Siempre (local + CI)       |
| Propiedades     | Invariantes RN-01, RN-02, RN-05, RF-022            | < 30 s             | Siempre                    |
| Funcionales BDD | Escenarios Dado/Cuando/Entonces del spec           | < 1 min            | Siempre                    |
| Integración CE  | CE-001 a CE-005 sobre 2 años sintéticos            | < 5 min            | CI y antes de cada merge   |
| Datos reales    | Revisión con `inia.sqlite` y estaciones piloto     | Minutos            | Manual, antes de la demo   |

---

## 4. Estructura de las pruebas

```
depuracion_demanda/
  pytest.ini
  tests/
    conftest.py                 # fixtures compartidas (config, generador, SQLite mini)
    datos/
      sinteticos.py             # generador de series + inyección de anomalías
      constructores.py          # builders legibles: una_serie().con_pico(...).build()
      feriados_prueba.csv
    features/                   # ← pruebas funcionales (las lee el PO)
      h1_carga.feature
      h2_temperatura.feature
      h3_deteccion.feature
      h4_sustitucion.feature
      h5_salidas.feature
      h6_comparacion.feature
      mvp_aceptacion.feature
    step_defs/                  # ← implementación de los pasos
      conftest.py               # pasos comunes (Antecedentes)
      test_h1_carga.py
      test_h2_temperatura.py
      ...
    unit/                       # TDD interno, un archivo por módulo
    propiedades/                # hypothesis
    integracion/                # criterios CE-001..CE-005, reproducibilidad
```

### 4.1 `pytest.ini`

```ini
[pytest]
testpaths = tests
bdd_features_base_dir = tests/features
markers =
    mvp: pruebas incluidas en la versión mínima
    h1: carga y validación
    h2: temperatura inia
    h3: detección
    h4: sustitución
    h5: salidas
    h6: comparación de métodos
    integracion: criterios de éxito, más lentas
    datos_reales: requieren inia.sqlite y archivos piloto (no corren en CI)
addopts = -ra --strict-markers -m "not datos_reales"
```

---

## 5. Ejemplo completo de un ciclo TDD (H3.4 — ola de calor)

### Paso 1 · ROJO: escenario funcional (copiado del spec)

`tests/features/h3_deteccion.feature`
```gherkin
# language: es
@h3 @mvp
Característica: Detectar valores atípicos
  Como analista quiero que el sistema identifique automáticamente
  los valores fuera de rango de cada estación.

  Antecedentes:
    Dado la estación "EST_001" con capacidad máxima de 120 MW que no admite demanda cero
    Y un año de demanda horaria sintética con su temperatura asociada

  Escenario: H3.1 Demanda negativa
    Dado una demanda de -5 MW el "2026-03-10 14:00"
    Cuando se ejecuta la detección
    Entonces el registro "2026-03-10 14:00" es outlier con motivo "regla_fisica:negativo"

  Escenario: H3.2 Cero en estación que no admite demanda nula
    Dado una demanda de 0 MW el "2026-04-02 03:00"
    Cuando se ejecuta la detección
    Entonces el registro "2026-04-02 03:00" es outlier con motivo "regla_fisica:cero"

  Escenario: H3.3 Pico anómalo
    Dado un pico de 3 veces la demanda esperada el "2026-06-20 19:00" con temperatura normal
    Cuando se ejecuta la detección
    Entonces el registro "2026-06-20 19:00" es outlier con motivo "desviacion"

  Escenario: H3.4 Pico coherente con ola de calor no es outlier
    Dado una ola de calor de 38 °C durante el "2026-01-15"
    Y la demanda de ese día responde a la temperatura como el resto del año
    Cuando se ejecuta la detección
    Entonces ningún registro del "2026-01-15" es outlier

  Esquema del escenario: H3.5 Un umbral más estricto detecta más
    Cuando se ejecuta la detección con k = <k_estricto> y con k = <k_laxo>
    Entonces los outliers con k = <k_estricto> son al menos tantos como con k = <k_laxo>

    Ejemplos:
      | k_estricto | k_laxo |
      | 3          | 4      |
      | 4          | 6      |
```

### Paso 2 · ROJO: definición de los pasos

`tests/step_defs/test_h3_deteccion.py`
```python
import pandas as pd
from pytest_bdd import scenarios, given, when, then, parsers
from depuracion.deteccion import detectar_outliers

scenarios("h3_deteccion.feature")

@given(parsers.parse('una ola de calor de {temp:g} °C durante el "{dia}"'))
def ola_de_calor(serie, temp, dia):
    serie.fijar_temperatura(dia, temp)            # builder sintético

@given("la demanda de ese día responde a la temperatura como el resto del año")
def demanda_coherente(serie):
    serie.recalcular_demanda_esperada()           # usa la misma curva en "U"

@when("se ejecuta la detección", target_fixture="resultado")
def ejecutar_deteccion(serie, config):
    return detectar_outliers(serie.build(), config)

@then(parsers.parse('ningún registro del "{dia}" es outlier'))
def ninguno_outlier(resultado, dia):
    assert not resultado.loc[dia, "es_outlier"].any()

@then(parsers.parse('el registro "{ts}" es outlier con motivo "{motivo}"'))
def es_outlier(resultado, ts, motivo):
    fila = resultado.loc[pd.Timestamp(ts, tz="America/Montevideo")]
    assert fila.es_outlier and fila.motivo.startswith(motivo)
```

Se ejecuta `pytest -m h3` y falla, porque `detectar_outliers` no existe.

### Paso 3 · Ciclo interno: unitarias mínimas

`tests/unit/test_deteccion.py`
```python
def test_residuo_robusto_ignora_un_pico_aislado():
    r = pd.Series([0.1, -0.2, 0.0, 0.15, 50.0])
    assert sigma_robusta(r) < 1.0           # MAD no se contamina con el pico

def test_marca_si_supera_k_sigmas():
    r = pd.Series([0.0, 0.1, -0.1, 10.0])
    assert marcar_por_desviacion(r, k=4).tolist() == [False, False, False, True]
```
ROJO → implementar `sigma_robusta` y `marcar_por_desviacion` → VERDE → refactorizar.
Se repite con `aplicar_reglas_fisicas` y con el bucle iterativo hasta que **el `.feature` pasa**.

### Paso 4 · VERDE y refactor
Con `pytest -m h3` todo en verde, se refactoriza (nombres, extracción de funciones) sin romper nada y se hace commit.

---

## 6. Catálogo de escenarios funcionales

Cada fila es un `Escenario` en el `.feature` indicado. La columna **Tarea** remite a [tasks.md](tasks.md).

| Feature                  | Escenario | Descripción breve                                          | Tags              | Tarea     |
|--------------------------|-----------|------------------------------------------------------------|-------------------|-----------|
| `h1_carga.feature`       | H1.1      | Carga válida y resumen por estación                        | @h1 @mvp          | T008      |
|                          | H1.2      | Archivo inválido rechazado sin detener el resto            | @h1 @mvp          | T008      |
|                          | H1.3      | Duplicados resueltos según la política (Esquema: primero / último / promedio) | @h1 @mvp | T009 |
|                          | H1.4      | Huecos reindexados y marcados                              | @h1 @mvp          | T009      |
|                          | extra     | Cambio de horario sin horas duplicadas ni perdidas         | @h1 @mvp          | T011      |
| `h2_temperatura.feature` | H2.1      | Temperatura de la estación INIA asociada                   | @h2 @mvp          | T014      |
|                          | H2.2      | Alineación igual / interpolar / media_diaria (Esquema)     | @h2 @mvp          | T015      |
|                          | H2.3      | Temperatura faltante: interpolación, respaldo, marca       | @h2 @mvp          | T015      |
|                          | H2.4      | `inia` inaccesible → el proceso aborta sin generar salidas | @h2 @mvp          | T014      |
|                          | feriados  | Feriado general y feriado local tratados como domingo      | @h2 @mvp          | T013      |
|                          | feriados  | Archivo de feriados ausente → el proceso se detiene        | @h2 @mvp          | T013      |
| `h3_deteccion.feature`   | H3.1–H3.5 | Ver sección 5                                              | @h3 @mvp          | T022–T023 |
|                          | extra     | Feriado con baja demanda **no** es outlier                 | @h3 @mvp          | T023      |
|                          | RN-00     | Detección sin columna temperatura → error                  | @h3 @mvp          | T026      |
| `h4_sustitucion.feature` | H4.1      | Estimación con las 4 variables                             | @h4 @mvp          | T028      |
|                          | H4.2      | Tramo de varias horas con estimación por intervalo         | @h4 @mvp          | T028      |
|                          | H4.3      | `origen = estimado` y valor original conservado            | @h4 @mvp          | T028      |
|                          | H4.4      | Tramo > `max_duracion_relleno` → `no_rellenado`            | @h4 @mvp          | T028      |
|                          | H4.5      | El modelo se entrena sin outliers                          | @h4 @mvp          | T028      |
|                          | extra     | Predicción acotada a [0, capacidad]                        | @h4 @mvp          | T030      |
| `mvp_aceptacion.feature` | 12.5      | `evaluar-revision` acepta/rechaza según `min_outliers_confirmados` (Esquema: 0.80, 0.90) | @mvp | T051 |
| `h5_salidas.feature`     | H5.1–H5.5 | Archivos, log, informe, gráficos                           | @h5               | T035      |
| `h6_comparacion.feature` | H6.1–H6.2 | Reporte por método y selección automática                  | @h6               | T042      |

### Ejemplo: escenario con umbral configurable (MVP 12.5)

```gherkin
# language: es
@mvp
Característica: Aceptación de la revisión manual de outliers

  Esquema del escenario: La estación se acepta según el umbral configurado
    Dado una muestra de 20 outliers de "EST_001" con <confirmados> confirmados por el analista
    Y el umbral configurado min_outliers_confirmados = <umbral>
    Cuando se ejecuta evaluar-revision
    Entonces la estación "EST_001" queda "<resultado>"

    Ejemplos:
      | confirmados | umbral | resultado |
      | 16          | 0.80   | aceptada  |
      | 15          | 0.80   | rechazada |
      | 18          | 0.90   | aceptada  |
      | 17          | 0.90   | rechazada |
```

---

## 7. Datos de prueba

| Recurso                 | Descripción                                                                                 |
|-------------------------|---------------------------------------------------------------------------------------------|
| **Generador sintético** | Series horarias con: base + perfil diario + perfil semanal + respuesta a la temperatura en "U" + ruido. Usa una `seed` fija. |
| **Constructores**       | API legible para los pasos: `una_serie("EST_001").anios(1).con_pico("2026-06-20 19:00", x=3).con_hueco(...)` |
| **SQLite mini**         | Fixture que crea en `tmp_path` una BD de pocos KB con **el mismo esquema que `inia.sqlite`** (se define en T010). Nunca se usa la BD real en las pruebas automáticas. |
| **Feriados de prueba**  | `tests/datos/feriados_prueba.csv`, con un feriado general, uno local y una fila inválida.   |
| **Anomalías inyectadas**| Se registran sus posiciones exactas para medir el recall y los falsos positivos (CE-001 y CE-002). |

> `inia.sqlite` (1,3 GB) está excluido del repositorio. Solo lo usan las pruebas marcadas `@datos_reales`, que se ejecutan localmente con `pytest -m datos_reales`.

---

## 8. Pruebas de propiedades (hypothesis)

Las invariantes de negocio se prueban con datos generados automáticamente:

| Propiedad                                                        | Regla   |
|------------------------------------------------------------------|---------|
| Para cualquier serie, `demanda_depurada` nunca es < 0 ni > capacidad | RN-01, RF-017 |
| Las filas que no son outlier ni hueco conservan exactamente su valor original | RN-02 |
| Toda fila con `origen = estimado` era outlier o hueco                | RN-02, RN-05 |
| Misma entrada + misma `seed` ⇒ misma salida                          | RF-022 |
| Bajar `k` nunca reduce el número de outliers                         | H3.5 |
| La estación del año es una función total de la fecha (no hay fechas sin estación) | RN-04 |

```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=200, deadline=None)
@given(st.lists(st.floats(-50, 500, allow_nan=False), min_size=48, max_size=500))
def test_depurada_respeta_limites_fisicos(valores):
    res = depurar(serie_desde(valores), config_prueba(capacidad=120))
    assert res.demanda_depurada.dropna().between(0, 120).all()
```

---

## 9. Criterios de éxito como pruebas de integración

| Criterio | Prueba (`tests/integracion/`)                              | Umbral (desde `config`)        |
|----------|------------------------------------------------------------|--------------------------------|
| CE-001   | Recall de las anomalías inyectadas                         | ≥ 0,90                         |
| CE-002   | Tasa de falsos positivos                                   | < 0,05                         |
| CE-003   | MAPE sobre valores reales ocultados                        | < 0,05                         |
| CE-004   | Cada `estimado` está en `cambios.csv`                      | 100 %                          |
| CE-005   | Hash SHA-256 de las entradas antes = después               | 100 %                          |
| RF-022   | Dos ejecuciones dan salidas idénticas                      | byte a byte                    |

Los umbrales se leen de la configuración de prueba, no se escriben fijos en el código, para que estén alineados con los acuerdos del MVP.

---

## 10. Ejecución diaria

```bash
pytest                          # todo menos datos reales
pytest -m mvp                   # solo el alcance de la versión mínima
pytest -m "h3 and not integracion"   # trabajar en una historia
pytest tests/features -v        # ver los escenarios funcionales
pytest -m integracion           # criterios de éxito
pytest -m datos_reales          # local, con inia.sqlite y archivos piloto
pytest --cov=depuracion --cov-report=term-missing --cov-fail-under=80
```

### 10.1 Integración continua (GitHub Actions)

`.github/workflows/pruebas.yml`
```yaml
name: pruebas
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: ClasePractica_MetodologiasAgiles/depuracion_demanda } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: pytest --cov=depuracion --cov-fail-under=80
```

Una rama solo se fusiona en `main` si este workflow está en verde.

---

## 11. Definición de terminado (pruebas)

Una tarea de [tasks.md](tasks.md) está terminada cuando:
- [ ] Sus escenarios del spec existen como `Escenario` en un `.feature` y pasan.
- [ ] Hay pruebas unitarias para cada función nueva y todas pasan.
- [ ] Si afecta a una regla RN-xx, la propiedad correspondiente de hypothesis pasa.
- [ ] La cobertura de los módulos tocados es ≥ 80 % (MVP) o ≥ 85 % (final).
- [ ] El workflow de CI está en verde.
- [ ] No quedan pruebas marcadas `skip` o `xfail` sin un issue asociado.

---

## 12. Orden de trabajo por fase

| Fase (tasks.md) | Primero (ROJO)                                    | Después (VERDE)               |
|-----------------|---------------------------------------------------|-------------------------------|
| 0 Setup         | Escenario "humo": `pytest` encuentra y ejecuta un `.feature` en español | `pytest.ini`, fixtures, generador |
| 1 H1            | `h1_carga.feature` + unitarias de `carga.py`      | `carga.py`                    |
| 2 H2            | `h2_temperatura.feature` (incluye feriados)       | `calendario.py`, `temperatura.py` |
| 3 H3            | `h3_deteccion.feature` + propiedades de `k`       | `features.py`, `modelos.py`, `deteccion.py` |
| 4 H4            | `h4_sustitucion.feature` + `mvp_aceptacion.feature` + propiedades RN-01/02/05 | `sustitucion.py`, `revision.py` |
| 5 H5            | `h5_salidas.feature` + CE-004, CE-005             | `salida.py`                   |
| 6 H6            | `h6_comparacion.feature`                          | `modelos.py` (ia, auto)       |
| 7 Pulido        | Reproducibilidad RF-022 y escenarios de la CLI     | `pipeline.py`, `__main__.py`  |

---

## 13. Riesgos y buenas prácticas

| Riesgo                                                    | Práctica                                                                  |
|-----------------------------------------------------------|---------------------------------------------------------------------------|
| Gherkin en español no reconocido por la versión de pytest-bdd | Usar pytest-bdd ≥ 8 (parser oficial de Gherkin con `# language: es`) y verificarlo con el escenario "humo" de la Fase 0 |
| Pruebas lentas por entrenar modelos                       | Series de 1 año en las funcionales; 2 años solo en `@integracion`; fixtures con `scope="session"` |
| Pruebas frágiles por la aleatoriedad                      | `seed` fija en el generador, en los modelos y en el muestreo de revisión  |
| Pasos Gherkin duplicados o demasiado técnicos             | Pasos comunes en `step_defs/conftest.py`; redacción en lenguaje de negocio y revisión con el PO |
| Esquema real de `inia.sqlite` distinto al de la fixture   | La fixture SQLite mini se genera a partir del esquema descubierto en T010 |
