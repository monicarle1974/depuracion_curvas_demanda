# Plan de Implementación: Depuración de Archivos de Demanda Eléctrica por Estación

| Campo              | Valor                                                                 |
|--------------------|-----------------------------------------------------------------------|
| **ID**             | 002-depuracion-demanda-electrica                                      |
| **Rama sugerida**  | `002-depuracion-demanda-electrica`                                    |
| **Fecha**          | 2026-11-09                                                            |
| **Estado**         | Borrador                                                              |
| **Especificación** | [spec_depuracion_demanda_electrica.md](spec_depuracion_demanda_electrica.md) |
| **Tareas**         | [tasks.md](tasks.md)                                                  |
| **Metodología**    | Spec-Driven Development (SDD)                                         |

> **Nota SDD**: este documento define **CÓMO** se implementará lo especificado en el spec. Cada decisión se vincula a los requisitos (RF / RNF / RN / RES) que satisface. Las clarificaciones aún abiertas en el spec (C1–C12) se resuelven aquí **de forma provisional** mediante valores por defecto configurables (ver sección 9); si el negocio responde distinto, se cambia la configuración, no el diseño.

---

## 1. Resumen

Se construirá un **pipeline en Python** que procesa cada estación de forma independiente siguiendo el orden obligatorio del spec (RN-00):

```
carga y validación → enriquecimiento (calendario + temperatura inia.sql) → detección de outliers → sustitución por pronóstico → salidas
```

El pronóstico usa un modelo de regresión (lineal como base, gradient boosting como opción de IA) cuyas variables explicativas son día de la semana, hora del día, estación del año y temperatura. Los resultados se entregan como archivos depurados, un registro de cambios y un informe de calidad, sin modificar nunca los originales.

---

## 2. Contexto técnico

| Aspecto                  | Decisión                                                                 |
|--------------------------|--------------------------------------------------------------------------|
| **Lenguaje**             | Python 3.11+                                                             |
| **Datos tabulares**      | pandas, numpy                                                            |
| **Modelos**              | scikit-learn (`Ridge`, `HistGradientBoostingRegressor`, `TimeSeriesSplit`) |
| **Fuente de temperatura**| `inia.sql` = base de datos **SQLite**, leída con `sqlite3` (librería estándar) en modo **solo lectura** (`file:inia.sql?mode=ro`) |
| **Configuración**        | Archivo `config.yaml` (PyYAML)                                           |
| **Gráficos (opcional)**  | matplotlib                                                               |
| **Pruebas**              | pytest (+ pytest-cov)                                                    |
| **Ejecución**            | Línea de comandos (`python -m depuracion --config config.yaml`)           |
| **Plataforma**           | Windows / Linux, ejecución local, sin servidor                           |
| **Volumen objetivo**     | Decenas de estaciones × varios años, resolución horaria o de 15 min      |

---

## 3. Verificación contra la especificación

| Restricción / regla del spec | Cómo se cumple                                                                                       |
|------------------------------|-------------------------------------------------------------------------------------------------------|
| **RES-01** Regresión lineal o IA | `modelos.py` ofrece `lineal` (Ridge) e `ia` (HistGradientBoostingRegressor), seleccionables por configuración. |
| **RES-02** Temperatura de `inia.sql` | `temperatura.py` es el único origen de temperatura; se lee del SQLite en solo lectura.          |
| **RES-03** Cuatro variables mínimas | `calendario.py` + `temperatura.py` generan día de semana, hora, estación del año y temperatura; `modelos.py` las exige. |
| **RN-00** Orden del proceso | `pipeline.py` ejecuta las etapas en orden fijo; la detección y la sustitución reciben un DataFrame que ya contiene la columna `temperatura` (se valida al entrar). |
| **RN-01** Demanda ≥ 0 | Regla física en detección + acotado de predicciones en sustitución.                                     |
| **RN-02** Solo se sustituyen outliers o huecos | La sustitución solo actúa sobre filas con `es_outlier = True` o `es_hueco = True`.       |
| **RN-03** Outliers fuera del entrenamiento | El modelo final se entrena con la máscara `~es_outlier & ~es_hueco`.                        |
| **RN-04** Estación del año | Función configurable por hemisferio y criterio (meteorológico por defecto).                         |
| **RN-05** Valor estimado identificado | Columna `origen ∈ {original, estimado, no_rellenado}` en la salida.                           |

---

## 4. Arquitectura

### 4.1 Flujo del pipeline

```
                ┌──────────────┐
 archivos  ───► │ 1. carga     │  valida, normaliza, detecta duplicados y huecos
 demanda        └──────┬───────┘
                       ▼
                ┌──────────────┐     ┌────────────┐
                │ 2. enriquec. │ ◄── │ inia.sql   │  (SQLite, solo lectura)
                │ calendario + │     └────────────┘
                │ temperatura  │
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ 3. detección │  reglas físicas + residuos del modelo (iterativo)
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ 4. sustituc. │  pronóstico con datos limpios, límite de duración
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │ 5. salida    │  archivos depurados, log de cambios, informe
                └──────────────┘
```

- Cada estación se procesa de forma **independiente** (RF-004): el pipeline itera por estación y un error en una no detiene las demás (excepto la falta de `inia.sql`, que aborta todo).
- Todas las etapas son **funciones puras** sobre DataFrames (entrada → salida), lo que facilita las pruebas y la reproducibilidad (RF-022).

### 4.2 Estructura del proyecto

```
ClasePractica_MetodologiasAgiles/
  depuracion_demanda/
    pyproject.toml
    config.yaml                 # configuración de ejemplo
    README.md
    src/depuracion/
      __init__.py
      __main__.py               # punto de entrada CLI
      config.py                 # carga y validación de config.yaml
      carga.py                  # RF-001..004
      calendario.py             # RF-005, RN-04, feriados
      temperatura.py            # RF-006..008
      features.py               # construcción de la matriz de variables explicativas
      modelos.py                # RF-013..015, H6
      deteccion.py              # RF-009..012
      sustitucion.py            # RF-013, RF-016, RF-017
      salida.py                 # RF-018..021
      pipeline.py               # orquestación (RN-00)
    tests/
      conftest.py               # fixtures: series sintéticas + SQLite de prueba
      sinteticos.py             # generador de datos con anomalías inyectadas
      unit/                     # una prueba por módulo
      integracion/              # pipeline completo + criterios de éxito
```

---

## 5. Diseño por etapa

### 5.1 Carga y validación (`carga.py`) — H1, RF-001..004
- Formatos de entrada: CSV (por defecto) y Excel (`.xlsx`), según la extensión. `[C1]`
- Columnas mínimas: `estacion`, `fecha_hora`, `demanda`. Los nombres reales se mapean en `config.yaml` (`columnas:`).
- Validaciones: columnas presentes, `fecha_hora` interpretable, `demanda` numérica. Si un archivo es inválido, se registra en `errores_carga` y el proceso continúa con el resto.
- **Duplicados**: se detectan y se aplica la política configurable `duplicados: primero | ultimo | promedio` (por defecto `promedio`). `[C2]`
- **Huecos**: se reindexa la serie a una frecuencia regular (`frecuencia: 1h` o se infiere con `pd.infer_freq`). Las filas nuevas se marcan `es_hueco = True` con `demanda = NaN`.
- **Zona horaria**: todo se convierte a la zona configurada (`zona_horaria: America/Montevideo`). Las horas duplicadas o inexistentes por cambio de horario se resuelven con `ambiguous="infer"` y `nonexistent="shift_forward"`.

### 5.2 Calendario (`calendario.py`) — RF-005, RN-04
- `dia_semana` (0–6), `hora` (0–23), `estacion_anio` (verano/otoño/invierno/primavera).
- Estación del año configurable: `hemisferio: sur | norte` y `criterio: meteorologico | astronomico`. Por defecto: sur + meteorológico (dic–feb = verano). `[C9]`
- **Feriados** (C8 resuelto): se leen de un **archivo específico proporcionado por el negocio**, cuya ruta se indica en `config.yaml` (`feriados:`). Formato del archivo:
  ```csv
  fecha,descripcion,estacion
  2026-01-01,Año Nuevo,
  2026-05-01,Día de los Trabajadores,
  2026-07-18,Feriado local,EST_002
  ```
  - `fecha` (AAAA-MM-DD) y `descripcion` son obligatorias. `estacion` es opcional: si está vacía, el feriado aplica a todas las estaciones; si tiene un valor, solo a esa estación.
  - Se validan las fechas y los duplicados. Las filas inválidas se reportan y se omiten.
  - Si falta el archivo o no se puede leer, el proceso se detiene con un mensaje claro, porque los feriados son obligatorios.
  - Un día feriado recibe `tipo_dia = feriado` y se modela con un perfil similar al domingo.

### 5.3 Temperatura (`temperatura.py`) — H2, RF-006..008
- Conexión: `sqlite3.connect("file:<ruta>?mode=ro", uri=True)`. Si no se puede abrir, se lanza `FuenteTemperaturaNoDisponible` y el pipeline aborta (H2.4).
- Esquema esperado (provisional, se ajusta al ver la BD real; tabla y columnas configurables):
  ```sql
  -- tabla: temperaturas
  estacion_met TEXT, fecha_hora TEXT (ISO 8601), temperatura REAL
  ```
- Correspondencia de estaciones en `config.yaml`:
  ```yaml
  mapeo_estaciones:
    EST_001: { inia: "LAS_BRUJAS", capacidad_max_mw: 120, permite_cero: false }
  ```
  `[C4]`, `[C3]`
- **Alineación temporal** (RF-008), `[C5]`:
  - Si la temperatura tiene la misma resolución que la demanda, se une por `fecha_hora`.
  - Si es más gruesa (p. ej. diaria), se usa la media diaria, o se interpola linealmente si hay mín/máx horarios. Esto es configurable con `alineacion: igual | interpolar | media_diaria`.
  - Si es más fina, se calcula la media por intervalo de demanda.
- **Faltantes** (H2.3), `[C6]`: primero se interpolan los huecos de hasta `max_hueco_temp` horas (por defecto 6). Si el hueco es mayor, se usa la `estacion_met_respaldo` si está configurada. Si no hay respaldo, se marca `temp_faltante = True` y esas filas no participan en el entrenamiento. Si alguna de esas filas debe sustituirse, se usa un modelo sin la variable temperatura y la sustitución queda marcada en el log.

### 5.4 Variables explicativas (`features.py`)
| Variable          | Codificación                                                                 |
|-------------------|------------------------------------------------------------------------------|
| Día de la semana  | One-hot (7) o `tipo_dia` (laborable / sábado / domingo-feriado)             |
| Hora del día      | One-hot (24) para el modelo lineal; numérica para gradient boosting          |
| Estación del año  | One-hot (4)                                                                  |
| Temperatura       | `HDD = max(0, 18 − T)` y `CDD = max(0, T − 22)` → captura la forma en "U" demanda/temperatura (calefacción y refrigeración). Umbrales configurables. |
| Interacciones (lineal) | `hora × tipo_dia`, para que la forma diaria varíe entre laborables y fines de semana |

La misma función genera la matriz para entrenar y para predecir, lo que garantiza que las columnas sean consistentes.

### 5.5 Modelos (`modelos.py`) — RF-013..015, H6
- Interfaz común: `entrenar(X, y) -> modelo` y `predecir(modelo, X) -> y_hat`.
- `lineal`: `Ridge(alpha=1.0)`. Es rápido y explicable (RNF-005), y sus coeficientes se pueden exportar.
- `ia`: `HistGradientBoostingRegressor(random_state=seed)`. Capta mejor las relaciones no lineales.
- `auto` (H6): para cada estación se evalúan ambos con `TimeSeriesSplit(n_splits=5)` sobre datos limpios. Se elige el de menor MAE y se reportan MAE y MAPE de cada uno.
- Mínimo de datos para entrenar: `min_registros_entrenamiento` (por defecto 2.160 registros, unos 90 días horarios). Si una estación no lo alcanza, no se sustituye nada y se reporta. `[Caso límite]`

### 5.6 Detección (`deteccion.py`) — H3, RF-009..012
1. **Reglas físicas** (RF-009): `demanda < 0`, `demanda > capacidad_max`, y `demanda == 0` cuando la estación tiene `permite_cero: false`. Motivo registrado: `regla_fisica:<tipo>`.
2. **Desviación estadística** (RF-010), con un ajuste robusto iterativo:
   - Se entrena el modelo con los datos que todavía no están marcados.
   - Se calcula el residuo `r = y − ŷ` y la escala robusta `σ = 1.4826 · MAD(r)`.
   - Se marca como outlier toda fila con `|r| > k · σ` (`k` configurable, por defecto 4; un umbral más estricto produce más detecciones, H3.5).
   - Se repite el proceso hasta que no haya cambios o se alcancen `max_iter` iteraciones (por defecto 3).
   - Motivo registrado: `desviacion` junto con el valor de `|r|/σ`.
   - Como el modelo incluye la temperatura, un pico de demanda durante una ola de calor tiene un residuo pequeño y no se marca (H3.4).
3. **Huecos** (RF-011): las filas con `es_hueco = True` reciben el motivo `hueco`.
4. Salida: las columnas `es_outlier`, `motivo` y `desviacion_sigma` (RF-012).

### 5.7 Sustitución (`sustitucion.py`) — H4, RF-013, RF-016, RF-017
- Se entrena el modelo final solo con las filas limpias (RN-03), usando el método elegido.
- Se agrupan las filas a sustituir en **tramos consecutivos**. Si un tramo dura más que `max_duracion_relleno` (por defecto 7 días, `[C7]`), no se rellena: queda con `origen = no_rellenado` y se reporta (H4.4).
- En el resto de los tramos se predice cada intervalo por separado (H4.2), así que la forma diaria se conserva.
- Las predicciones se acotan a `[0, capacidad_max]` (RF-017).
- La columna `origen` toma el valor `estimado` y el valor original se guarda en el log (H4.3).

### 5.8 Salidas (`salida.py`) — H5, RF-018..021
- **Escritura atómica**: todo se escribe en `<salida>/.tmp_<timestamp>/` y se renombra al terminar sin errores. Nunca se escribe sobre la carpeta de entrada (RF-018, RNF-004).
- **Archivo depurado** (uno por cada archivo de entrada, con el mismo formato): las columnas originales más `origen`.
- **Log de cambios** `cambios.csv` (RF-020):
  `estacion, fecha_hora, valor_original, valor_estimado, motivo, desviacion_sigma, temperatura, metodo, origen_temperatura`
- **Informe de calidad** `informe.md` + `informe.csv` (RF-021), con estos datos por estación: registros, % de outliers por motivo, huecos rellenados, tramos no rellenados, método usado, y MAE/MAPE de validación.
- **Gráficos** opcionales (`graficos: true`): un PNG por estación con la serie original frente a la depurada y los outliers resaltados (H5.5). `[C12]`
- Se guarda también una copia de `config.yaml` y la `seed` usada, para poder reproducir la ejecución (RF-022).

### 5.9 Orquestación y CLI (`pipeline.py`, `__main__.py`)
```
python -m depuracion --config config.yaml [--estacion EST_001] [--metodo lineal|ia|auto] [--dry-run]
```
- `--dry-run` ejecuta la carga, la detección y el informe, pero no genera archivos depurados. Sirve para ajustar `k`.
- Códigos de salida: `0` (éxito), `1` (`inia.sql` no disponible o configuración inválida), `2` (éxito parcial, con archivos o estaciones omitidos).

---

## 6. Modelo de datos interno

DataFrame enriquecido por estación (índice: `fecha_hora` con zona horaria):

| Columna            | Tipo     | Origen                    |
|--------------------|----------|---------------------------|
| `estacion`         | str      | carga                     |
| `demanda`          | float    | carga (NaN si es hueco)   |
| `es_hueco`         | bool     | carga                     |
| `dia_semana`, `tipo_dia`, `hora`, `estacion_anio` | int/cat | calendario |
| `temperatura`      | float    | inia.sql                  |
| `temp_faltante`    | bool     | temperatura               |
| `es_outlier`       | bool     | detección                 |
| `motivo`           | str      | detección                 |
| `desviacion_sigma` | float    | detección                 |
| `demanda_depurada` | float    | sustitución               |
| `origen`           | cat      | sustitución               |

### 6.1 Configuración (`config.yaml`) — RNF-002

```yaml
entrada: ./datos/demanda/
salida:  ./datos/depurado/
inia_sqlite: ./datos/inia.sql
inia_tabla: temperaturas
inia_columnas: { estacion: estacion_met, fecha_hora: fecha_hora, temperatura: temperatura }
columnas: { estacion: estacion, fecha_hora: fecha_hora, demanda: demanda }
frecuencia: 1h
zona_horaria: America/Montevideo
hemisferio: sur
criterio_estacion: meteorologico
feriados: ./datos/feriados.csv
duplicados: promedio
alineacion: interpolar
max_hueco_temp: 6h
temperatura_confort: { hdd_base: 18, cdd_base: 22 }
deteccion: { k: 4.0, max_iter: 3 }
metodo: auto            # lineal | ia | auto
max_duracion_relleno: 7d
min_registros_entrenamiento: 2160
graficos: true
seed: 42
aceptacion:                       # criterios de revisión manual del MVP (sección 12.5)
  muestra_outliers_por_estacion: 20
  min_outliers_confirmados: 0.80  # proporción mínima confirmada por el analista
mapeo_estaciones:
  EST_001: { inia: LAS_BRUJAS, capacidad_max_mw: 120, permite_cero: false }
```

---

## 7. Manejo de errores

| Situación                                   | Comportamiento                                                     |
|---------------------------------------------|--------------------------------------------------------------------|
| Archivo de demanda inválido                 | Se omite, se registra en el informe y el código de salida es 2     |
| `inia.sql` inexistente o no abrible         | Aborta antes de procesar y no genera salidas (H2.4); código 1      |
| Estación sin correspondencia INIA           | Se omite la estación y se reporta                                  |
| Histórico limpio insuficiente               | Solo se ejecutan las reglas físicas, no hay sustitución; se reporta |
| `config.yaml` inválido                      | Mensaje con el campo erróneo; código 1                             |
| Error inesperado durante la escritura       | Se borra el directorio temporal; los originales quedan intactos    |

---

## 8. Estrategia de pruebas

- **Datos sintéticos** (`tests/sinteticos.py`): series horarias de 2 años, construidas así:
  - componentes de demanda: base + perfil diario + perfil semanal + efecto de la temperatura en forma de "U" + ruido;
  - temperatura sintética con estacionalidad anual;
  - una BD SQLite temporal con la misma forma que `inia.sql`;
  - inyección controlada de anomalías (picos, ceros, negativos, tramos planos y huecos) en posiciones conocidas.
- **Pruebas unitarias**: una por escenario Dado/Cuando/Entonces del spec (H1.1 … H6.2).
- **Pruebas de integración** que validan los criterios de éxito:
  | Criterio | Prueba |
  |----------|--------|
  | CE-001 ≥ 90 % de detección | Recall sobre las anomalías inyectadas |
  | CE-002 < 5 % de falsos positivos | Proporción de filas normales marcadas como outliers |
  | CE-003 MAPE < 5 % | Se ocultan valores reales, se estiman y se compara |
  | CE-004 100 % trazado | Cada fila `estimado` tiene su fila en `cambios.csv` |
  | CE-005 originales intactos | Hash SHA-256 de las entradas antes y después |
  | RF-022 reproducible | Dos ejecuciones con la misma `seed` dan salidas idénticas |
- Cobertura objetivo: ≥ 85 % en `src/depuracion`.

---

## 9. Decisiones provisionales sobre las clarificaciones del spec

| #   | Valor por defecto asumido                                   | Si la respuesta es otra…                         |
|-----|-------------------------------------------------------------|--------------------------------------------------|
| C1  | CSV con columnas `estacion, fecha_hora, demanda`, horario    | Ajustar `columnas`/`frecuencia`; añadir lector si es otro formato |
| C2  | Duplicados → promedio                                        | Cambiar `duplicados`                             |
| C3  | `permite_cero: false`; capacidad máxima en `mapeo_estaciones`| Cambiar por estación                             |
| C4  | Mapeo manual en `mapeo_estaciones`                           | Si existen coordenadas, calcular la estación INIA más cercana |
| C5  | `alineacion: interpolar`                                     | Cambiar `alineacion`                             |
| C6  | Interpolar ≤ 6 h; luego estación de respaldo; luego modelo sin temperatura | Cambiar `max_hueco_temp` / respaldo  |
| C7  | `max_duracion_relleno: 7d`                                   | Cambiar el valor                                 |
| C8  | ✅ **Resuelto**: el negocio entrega un archivo de feriados (formato en 5.2), tratados como domingo | —                     |
| C9  | Hemisferio sur, criterio meteorológico                       | Cambiar `hemisferio` / `criterio_estacion`       |
| C10 | Decenas de estaciones × 2–5 años                             | Si es mucho mayor, paralelizar por estación (`joblib`) |
| C11 | MAPE < 5 %                                                   | Ajustar el umbral de la prueba CE-003            |
| C12 | Solo CLI + PNG opcionales                                    | Añadir notebook o dashboard en otra iteración    |

---

## 10. Riesgos y mitigaciones

| Riesgo                                                    | Mitigación                                                                 |
|-----------------------------------------------------------|----------------------------------------------------------------------------|
| Cambios estructurales de demanda vistos como outliers     | Entrenar con ventana móvil (`ventana_entrenamiento`) y revisar tramos largos marcados en el informe |
| Poco histórico limpio                                     | Umbral `min_registros_entrenamiento` y reporte explícito                   |
| Esquema real de `inia.sql` distinto al supuesto           | Tabla y columnas configurables; tarea temprana de inspección de la BD (T010) |
| Horario de verano / zonas horarias distintas              | Normalización a una sola zona horaria en carga y en temperatura            |
| Detección demasiado agresiva                              | Modo `--dry-run` y `k` configurable para calibrar con el analista          |

---

## 11. Trazabilidad requisitos → módulos → tareas

| Requisito        | Módulo                  | Tareas (ver [tasks.md](tasks.md)) |
|------------------|-------------------------|-----------------------------------|
| RF-001, RF-002   | `carga.py`              | T008–T012                         |
| RF-003           | `carga.py`              | T009, T011                        |
| RF-004           | `pipeline.py`           | T045                              |
| RF-005           | `calendario.py`         | T013, T016                        |
| RF-006–RF-008    | `temperatura.py`        | T014, T015, T017–T019             |
| RF-009–RF-012    | `deteccion.py`          | T022–T027                         |
| RF-013–RF-015    | `modelos.py`, `sustitucion.py` | T020, T021, T028–T033      |
| RF-016, RF-017   | `sustitucion.py`        | T029, T030, T033                  |
| RF-018–RF-021    | `salida.py`             | T035–T041                         |
| RF-022           | `pipeline.py`, pruebas  | T043, T048                        |
| RNF-002          | `config.py`             | T004, T005                        |
| RNF-004          | `salida.py`             | T036, T040                        |
| H6               | `modelos.py`            | T042–T044                         |

---

## 12. Acuerdos de la versión mínima (MVP)

> Estos acuerdos fijan qué se entrega en la primera versión utilizable, cómo se acepta y qué se compromete cada parte. Deben revisarse y firmarse (o aprobarse en la reunión de planificación) por el responsable del negocio y el equipo **antes de iniciar la Fase 1**.

### 12.1 Objetivo del MVP
Demostrar, sobre datos reales de **estaciones piloto**, que el proceso detecta los outliers y los sustituye por pronósticos coherentes con el día de la semana, la hora, la estación del año y la temperatura de `inia.sql`. Si la demostración resulta convincente, se continúa con las entregas 2 y 3.

### 12.2 Alcance incluido
| Incluido                                                     | Historias / requisitos          | Tareas      |
|--------------------------------------------------------------|---------------------------------|-------------|
| Carga y validación de archivos CSV de demanda                | H1 · RF-001–RF-003              | T001–T012   |
| Enriquecimiento con calendario y temperatura de `inia.sql`   | H2 · RF-005–RF-008              | T013–T019   |
| Detección por reglas físicas y por desviación estadística    | H3 · RF-009–RF-012              | T020–T027   |
| Sustitución por pronóstico con **regresión lineal (Ridge)**  | H4 · RF-013, RF-014, RF-016, RF-017 | T028–T034 |
| Exportación simple a CSV por estación con las columnas `demanda_depurada` y `origen` | H4.3 (parcial) | T034 |

### 12.3 Fuera del MVP (se entrega después)
| Excluido del MVP                                           | Entrega prevista   |
|------------------------------------------------------------|--------------------|
| Archivos depurados con el formato original, escritura atómica, `cambios.csv` e `informe.md` (H5) | Entrega 2 |
| Gráficos original frente a depurada (H5.5)                 | Entrega 2          |
| Modelo de IA (Gradient Boosting) y selección automática (H6) | Entrega 3        |
| Lectura de archivos Excel                                  | Entrega 2          |
| Independencia completa entre estaciones, códigos de salida, CLI completa y `--dry-run` | Cierre (Fase 7) |
| Procesamiento en paralelo / grandes volúmenes              | Solo si C10 lo requiere |

### 12.4 Supuestos congelados para el MVP
Durante el MVP se trabaja con estos valores. Si alguno cambia, se trata como un **cambio de alcance** (ver 12.9).

| Tema                     | Valor acordado para el MVP                                         |
|--------------------------|--------------------------------------------------------------------|
| Estaciones piloto        | 2 a 3 estaciones elegidas por el negocio, con ≥ 1 año de histórico |
| Formato de entrada       | CSV con `estacion, fecha_hora, demanda`, resolución horaria        |
| Fuente de temperatura    | `inia.sql` (SQLite), mapeo manual estación → estación INIA         |
| Estación del año         | Hemisferio sur, criterio meteorológico                             |
| Feriados                 | **Se consideran**: archivo de feriados proporcionado por el negocio (formato en 5.2) |
| Umbral de aceptación     | `aceptacion.min_outliers_confirmados = 0.80` y una muestra de 20 por estación, **configurables** |
| Umbral de detección      | `k = 4`, `max_iter = 3`                                            |
| Relleno máximo           | 7 días consecutivos                                                |
| Método de pronóstico     | Solo regresión lineal (Ridge)                                      |
| Zona horaria             | `America/Montevideo`                                               |

### 12.5 Criterios de aceptación del MVP
El MVP se considera **aceptado** cuando se cumplen todos estos criterios:

1. **Datos sintéticos** (pruebas automáticas):
   - CE-001: se detecta ≥ 90 % de las anomalías inyectadas.
   - CE-002: < 5 % de falsos positivos.
   - CE-003: MAPE < 5 % en los valores ocultados.
2. **Datos reales de las estaciones piloto** (revisión con el analista):
   - El proceso genera `revision_outliers.csv` con una muestra aleatoria (con la `seed` fija) de `aceptacion.muestra_outliers_por_estacion` outliers por estación (por defecto 20). El archivo incluye una columna `confirmado` (si/no) que completa el analista.
   - El comando `python -m depuracion evaluar-revision --config config.yaml` calcula la proporción confirmada por estación. Una estación se acepta si esa proporción es **≥ `aceptacion.min_outliers_confirmados`** (por defecto 0,80; el valor es **configurable**).
   - Los feriados del archivo proporcionado se reflejan en el modelo: la demanda de un día feriado no se marca como outlier solo por ser más baja que la de un día laborable.
   - Las series depuradas no presentan valores negativos, ni valores por encima de la capacidad, ni saltos visibles en los tramos rellenados.
   - Un pico durante un evento de temperatura extrema conocido **no** se marca como outlier.
3. **Orden del proceso** (RN-00): queda demostrado mediante una prueba automática que la detección y la sustitución fallan si falta la columna de temperatura.
4. **Originales intactos**: la ejecución no modifica ningún archivo de entrada.

### 12.6 Definición de terminado (DoD) para cada tarea del MVP
- [ ] Las pruebas de los escenarios Dado/Cuando/Entonces correspondientes están escritas y pasan.
- [ ] La cobertura de los módulos tocados es ≥ 80 %.
- [ ] El código fue revisado por otra persona del equipo.
- [ ] Los parámetros nuevos están en `config.yaml` con un valor por defecto documentado.
- [ ] Ningún valor está fijo en el código: rutas, umbrales y estaciones van en la configuración.
- [ ] La tarea está marcada en [tasks.md](tasks.md).

### 12.7 Compromisos de las partes
| Parte                        | Compromiso                                                                 | Plazo                    |
|------------------------------|----------------------------------------------------------------------------|--------------------------|
| **Negocio / Product Owner**  | Elegir las estaciones piloto y entregar sus archivos de demanda             | Antes de la Fase 1       |
| **Negocio / Product Owner**  | Dar acceso de lectura a `inia.sql` y la tabla de correspondencia con las estaciones INIA (C4) | Antes de la Fase 2 |
| **Negocio / Product Owner**  | Entregar el **archivo de feriados** que cubra todo el periodo de los datos piloto (formato en 5.2) | Antes de la Fase 2 |
| **Negocio / Product Owner**  | Indicar la capacidad máxima de cada estación piloto y si admite demanda cero (C3) | Antes de la Fase 3 |
| **Negocio / Product Owner**  | Confirmar el valor de `aceptacion.min_outliers_confirmados` (por defecto 0,80) | Antes de la demo del MVP |
| **Analista de datos**        | Revisar la muestra de outliers y validar los criterios de 12.5 (punto 2)   | Durante la demo del MVP  |
| **Equipo de desarrollo**     | Entregar el MVP con los criterios 12.5 (puntos 1, 3 y 4) cumplidos y una demo | Al cerrar la Fase 4   |
| **Equipo de desarrollo**     | Informar los riesgos detectados (p. ej. esquema de `inia.sql`) apenas aparezcan | Continuo              |

### 12.8 Demo y cierre del MVP
- **Formato**: sesión de 1 h con el Product Owner y el analista.
- **Contenido**:
  - ejecución en vivo sobre una estación piloto;
  - recorrido por los outliers detectados y sus sustituciones;
  - métricas obtenidas con los datos sintéticos;
  - lista de las clarificaciones (C1–C12) que siguen abiertas.
- **Resultado esperado**: una de estas tres decisiones:
  - **Aceptado**: se pasa a la Entrega 2.
  - **Aceptado con ajustes**: se calibran parámetros, sin cambiar el alcance.
  - **Rechazado**: se reabre el diseño de la detección o del pronóstico.

### 12.9 Gestión de cambios durante el MVP
- Los cambios de **parámetros** (umbral, duración máxima, mapeo de estaciones) se aceptan sin renegociar, porque se resuelven en la configuración.
- Los cambios de **alcance** (nuevas fuentes, nuevos formatos, otras variables explicativas, otro tipo de modelo) se registran como nuevas historias. Se priorizan para entregas posteriores y **no entran en el MVP**, salvo que el negocio acepte mover la fecha de la demo.
- Cualquier cambio que afecte al spec se refleja primero en [spec_depuracion_demanda_electrica.md](spec_depuracion_demanda_electrica.md) y después en este plan.
