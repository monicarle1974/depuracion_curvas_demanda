# Tareas: Depuración de Archivos de Demanda Eléctrica por Estación

| Campo              | Valor                                                                 |
|--------------------|-----------------------------------------------------------------------|
| **ID**             | 002-depuracion-demanda-electrica                                      |
| **Fecha**          | 2026-11-09                                                            |
| **Especificación** | [spec_depuracion_demanda_electrica.md](spec_depuracion_demanda_electrica.md) |
| **Plan**           | [plan.md](plan.md)                                                    |

**Formato**: `- [ ] T0NN [P] [H#] descripción — archivo`
- `[P]`: puede ejecutarse en paralelo con otras tareas `[P]` de la misma fase (archivos distintos, sin dependencias entre sí).
- `[H#]`: historia de usuario del spec a la que pertenece.
- Rutas relativas a `depuracion_demanda/`.

**Plan de pruebas**: [plan_pruebas.md](plan_pruebas.md). Los escenarios del spec se escriben como archivos `.feature` (pytest-bdd).

**Enfoque**: en cada fase se escriben **primero las pruebas** (derivadas de los escenarios Dado / Cuando / Entonces del spec), se comprueba que fallan y luego se implementa.

**Orden de fases** (respeta RN-00): Setup → H1 Carga → **H2 Temperatura** → H3 Detección → H4 Sustitución → H5 Salidas → H6 Comparación → Pulido.

---

## Fase 0 — Setup (infraestructura compartida)

- [ ] T001 Crear la estructura de carpetas del proyecto (`src/depuracion/`, `tests/features/`, `tests/step_defs/`, `tests/unit/`, `tests/propiedades/`, `tests/integracion/`) y `pytest.ini` con marcadores — `depuracion_demanda/`
- [ ] T002 Crear `pyproject.toml` con las dependencias (pandas, numpy, scikit-learn, pyyaml, matplotlib) y el extra `test` (pytest, pytest-bdd ≥ 8, hypothesis, pytest-cov). Incluir un escenario "humo" en español que confirme que pytest-bdd reconoce `# language: es` — `pyproject.toml`, `tests/features/humo.feature`
- [ ] T052 [P] Crear el workflow de CI de GitHub Actions (sección 10.1 de [plan_pruebas.md](plan_pruebas.md)) — `.github/workflows/pruebas.yml`
- [ ] T003 [P] Crear un `README.md` inicial con el objetivo y un enlace al spec — `README.md`
- [ ] T004 Implementar la carga y validación de la configuración, con error claro si falta un campo o tiene un tipo inválido (RNF-002), y sus pruebas — `src/depuracion/config.py`, `tests/unit/test_config.py`
- [ ] T005 [P] Crear `config.yaml` de ejemplo con los valores por defecto de la sección 9 del plan, incluidos la ruta `feriados` y el bloque `aceptacion` (`muestra_outliers_por_estacion`, `min_outliers_confirmados`) — `config.yaml`
- [ ] T006 [P] Crear el generador de series sintéticas: demanda con perfil diario y semanal, efecto de la temperatura en "U", ruido e inyección de anomalías en posiciones conocidas — `tests/sinteticos.py`
- [ ] T007 Crear fixtures de pytest: series sintéticas, BD SQLite temporal con la forma de `inia.sql` y carpeta temporal de entrada/salida — `tests/conftest.py`

**Checkpoint**: `pytest` se ejecuta (sin pruebas de negocio aún) y la configuración de ejemplo se valida.

---

## Fase 1 — H1: Cargar y validar los archivos de demanda (P1) 🎯 MVP

**Objetivo**: leer los archivos de todas las estaciones y obtener series regulares con duplicados resueltos y huecos marcados.

### Pruebas
- [ ] T008 [P] [H1] Pruebas de H1.1 (carga válida con resumen por estación) y H1.2 (archivo inválido rechazado sin detener el resto) — `tests/unit/test_carga.py`
- [ ] T009 [P] [H1] Pruebas de H1.3 (duplicados según la política configurada) y H1.4 (huecos reindexados y marcados con `es_hueco`) — `tests/unit/test_carga.py`

### Implementación
- [ ] T010 [P] [H1] Inspeccionar el esquema real de `inia.sql` (tablas, columnas, resolución, zona horaria, rango de fechas) y actualizar `config.yaml` y la sección 5.3 del plan — `config.yaml`, `plan.md`
- [ ] T011 [H1] Implementar en `carga.py`:
  - lectura de CSV y Excel;
  - mapeo de columnas;
  - validación de tipos;
  - política de duplicados;
  - reindexado a la frecuencia configurada;
  - normalización de la zona horaria, incluido el cambio de horario;

  — `src/depuracion/carga.py`
- [ ] T012 [H1] Generar el resumen por estación (periodo, nº de registros, duplicados, huecos) y la lista de archivos rechazados con su motivo — `src/depuracion/carga.py`

**Checkpoint**: T008–T009 en verde.

---

## Fase 2 — H2: Obtener la temperatura desde `inia.sql` (P1) 🎯 MVP

**Objetivo**: cada registro de demanda queda enriquecido con día de la semana, hora, estación del año y temperatura **antes** de la detección y la sustitución (RN-00).

### Pruebas
- [ ] T013 [P] [H2] Pruebas del calendario: día de la semana, hora, estación del año (hemisferio sur/norte, criterio meteorológico/astronómico) y feriados. Para los feriados se prueba:
  - un feriado general y uno local por estación;
  - que se traten como domingo;
  - que el proceso se detenga si falta el archivo;
  - que las filas inválidas se reporten.

  — `tests/unit/test_calendario.py`
- [ ] T014 [P] [H2] Pruebas de H2.1 (temperatura correcta de la estación INIA asociada) y H2.4 (`inia.sql` inaccesible → `FuenteTemperaturaNoDisponible`) — `tests/unit/test_temperatura.py`
- [ ] T015 [P] [H2] Pruebas de H2.2 (alineación `igual` / `interpolar` / `media_diaria`) y H2.3 (faltantes: interpolación ≤ `max_hueco_temp`, estación de respaldo, `temp_faltante`) — `tests/unit/test_temperatura.py`

### Implementación
- [ ] T016 [P] [H2] Implementar `calendario.py`:
  - `dia_semana`, `tipo_dia`, `hora` y `estacion_anio`;
  - lectura y validación del **archivo de feriados** proporcionado por el negocio (`fecha`, `descripcion`, `estacion` opcional). Si el archivo falta, el proceso se detiene; las filas inválidas se reportan;

  — `src/depuracion/calendario.py`
- [ ] T017 [H2] Implementar la conexión SQLite en solo lectura (`mode=ro`), la consulta parametrizada por estación y rango de fechas, y la excepción `FuenteTemperaturaNoDisponible` — `src/depuracion/temperatura.py`
- [ ] T018 [H2] Implementar `mapeo_estaciones` (estación eléctrica → estación INIA) y la alineación temporal configurable — `src/depuracion/temperatura.py`
- [ ] T019 [H2] Implementar el tratamiento de temperaturas faltantes (interpolación, respaldo y marca `temp_faltante`) — `src/depuracion/temperatura.py`

**Checkpoint**: T013–T015 en verde; un DataFrame de ejemplo tiene las cuatro variables explicativas completas.

---

## Fase 3 — H3: Detectar valores atípicos (P1) 🎯 MVP

**Objetivo**: marcar los outliers por reglas físicas y por desviación respecto a lo esperado según día, hora, estación del año y temperatura.

### Pruebas
- [ ] T020 [P] [H3] Pruebas de `features.py` (columnas consistentes entre entrenamiento y predicción, HDD/CDD correctos) y del modelo lineal base (entrenar/predecir) — `tests/unit/test_features.py`, `tests/unit/test_modelos.py`
- [ ] T022 [P] [H3] Pruebas de H3.1 (demanda negativa) y H3.2 (cero en una estación con `permite_cero: false`; demanda por encima de la capacidad máxima) — `tests/unit/test_deteccion.py`
- [ ] T023 [P] [H3] Pruebas de H3.3 (pico anómalo detectado), H3.4 (pico durante una ola de calor **no** detectado) y H3.5 (un `k` menor da ≥ detecciones) — `tests/unit/test_deteccion.py`

### Implementación
- [ ] T021 [H3] Implementar `features.py` (one-hot de día/hora/estación del año, HDD/CDD, interacción `hora × tipo_dia`) y el método `lineal` (Ridge) con la interfaz `entrenar` / `predecir` — `src/depuracion/features.py`, `src/depuracion/modelos.py`
- [ ] T024 [H3] Implementar las reglas físicas (RF-009) — `src/depuracion/deteccion.py`
- [ ] T025 [H3] Implementar la detección iterativa por residuos robustos (`|r| > k · 1.4826 · MAD`, hasta `max_iter`) (RF-010) — `src/depuracion/deteccion.py`
- [ ] T026 [H3] Añadir las columnas `es_outlier`, `motivo` y `desviacion_sigma`, y marcar los huecos con motivo `hueco` (RF-011, RF-012). Validar al entrar que la columna `temperatura` existe (RN-00) — `src/depuracion/deteccion.py`
- [ ] T027 [H3] Prueba de integración con datos sintéticos: CE-001 (detección ≥ 90 %) y CE-002 (falsos positivos < 5 %) — `tests/integracion/test_criterios_deteccion.py`

**Checkpoint**: T020–T027 en verde; CE-001 y CE-002 cumplidos con datos sintéticos.

---

## Fase 4 — H4: Sustituir outliers por valores pronosticados (P1) 🎯 MVP

**Objetivo**: reemplazar outliers y huecos por un pronóstico que use la temperatura ya incorporada.

**Dependencias**: Fases 1, 2 y 3.

### Pruebas
- [ ] T028 [P] [H4] Pruebas de H4.1 (estimación con las cuatro variables), H4.2 (tramo de varias horas con una estimación por intervalo), H4.3 (`origen = estimado` y valor original conservado), H4.4 (tramo > `max_duracion_relleno` → `no_rellenado`) y H4.5 (el modelo se entrena sin outliers) — `tests/unit/test_sustitucion.py`

### Implementación
- [ ] T029 [H4] Agrupar las filas a sustituir en tramos consecutivos y aplicar el límite `max_duracion_relleno` (RF-016) — `src/depuracion/sustitucion.py`
- [ ] T030 [H4] Acotar las predicciones a `[0, capacidad_max]` (RF-017, RN-01) — `src/depuracion/sustitucion.py`
- [ ] T031 [H4] Entrenar el modelo final solo con filas limpias (RN-03), predecir y rellenar `demanda_depurada` y `origen` — `src/depuracion/sustitucion.py`
- [ ] T032 [H4] Modelo de respaldo sin temperatura para filas con `temp_faltante`, marcado en el log; y estación con histórico < `min_registros_entrenamiento` → no se sustituye y se reporta — `src/depuracion/sustitucion.py`
- [ ] T033 [H4] Prueba de integración CE-003: ocultar valores reales, estimarlos y verificar MAPE < 5 % — `tests/integracion/test_criterios_estimacion.py`
- [ ] T034 [H4] Pipeline mínimo que encadena carga → enriquecimiento → detección → sustitución en el orden de RN-00 — `src/depuracion/pipeline.py`
- [ ] T051 [H4] Revisión manual configurable:
  - generar `revision_outliers.csv` con una muestra de `aceptacion.muestra_outliers_por_estacion` outliers por estación, tomada con la `seed`, y una columna `confirmado`;
  - crear el comando `evaluar-revision`, que compara la proporción confirmada con `aceptacion.min_outliers_confirmados`;
  - escribir sus pruebas;

  — `src/depuracion/revision.py`, `tests/unit/test_revision.py`

**🎯 Checkpoint MVP**: con datos sintéticos, el pipeline produce una serie depurada por estación que cumple CE-001, CE-002 y CE-003. Se puede hacer la demo al analista. La aceptación final se rige por los [Acuerdos de la versión mínima](plan.md#12-acuerdos-de-la-versión-mínima-mvp) (sección 12 del plan).

---

## Fase 5 — H5: Archivos depurados e informe de calidad (P2)

**Objetivo**: entregar resultados trazables sin tocar los originales.

### Pruebas
- [ ] T035 [P] [H5] Pruebas de H5.1 (un archivo de salida por cada entrada, originales sin tocar), H5.2 (misma estructura + columna `origen`), H5.3 (contenido del informe) y H5.4 (campos de `cambios.csv`) — `tests/unit/test_salida.py`

### Implementación
- [ ] T036 [H5] Escritura atómica: carpeta temporal y renombrado final; limpieza si hay error (RF-018, RNF-004) — `src/depuracion/salida.py`
- [ ] T037 [H5] Escribir los archivos depurados con el mismo formato y columnas que la entrada, más `origen` — `src/depuracion/salida.py`
- [ ] T038 [H5] Escribir el registro de cambios `cambios.csv` (RF-020) — `src/depuracion/salida.py`
- [ ] T039 [H5] Generar `informe.md` e `informe.csv` por estación, con métricas de outliers, huecos, tramos no rellenados y MAE/MAPE (RF-021); guardar una copia de la configuración y la `seed` — `src/depuracion/salida.py`
- [ ] T040 [H5] Prueba de integración CE-004 (100 % de los estimados están en el log) y CE-005 (hash SHA-256 de los originales sin cambios) — `tests/integracion/test_criterios_salida.py`
- [ ] T041 [P] [H5] Gráficos opcionales por estación (original frente a depurada, con los outliers resaltados) (H5.5) — `src/depuracion/salida.py`

**Checkpoint**: T035–T040 en verde.

---

## Fase 6 — H6: Comparar métodos de estimación (P3)

### Pruebas
- [ ] T042 [P] [H6] Pruebas de H6.1 (reporte de error por método y estación) y H6.2 (`metodo: auto` elige el de menor MAE) — `tests/unit/test_modelos.py`

### Implementación
- [ ] T043 [H6] Implementar el método `ia` (`HistGradientBoostingRegressor` con `random_state = seed`) — `src/depuracion/modelos.py`
- [ ] T044 [H6] Implementar `metodo: auto`: validación con `TimeSeriesSplit(5)` sobre datos limpios, selección por MAE y métricas en el informe — `src/depuracion/modelos.py`, `src/depuracion/salida.py`

**Checkpoint**: T042 en verde; el informe muestra la comparación lineal frente a IA.

---

## Fase 7 — Pulido y validación final

- [ ] T045 Procesar cada estación de forma independiente: un error en una estación no detiene las demás (RF-004); manejo de errores de la sección 7 del plan; códigos de salida 0/1/2 — `src/depuracion/pipeline.py`
- [ ] T046 CLI: `--config`, `--estacion`, `--metodo` y `--dry-run` — `src/depuracion/__main__.py`
- [ ] T047 [P] Completar el `README.md`: instalación, configuración, ejecución e interpretación del informe — `README.md`
- [ ] T048 Prueba de reproducibilidad (RF-022): dos ejecuciones con la misma configuración y `seed` dan salidas idénticas — `tests/integracion/test_reproducibilidad.py`
- [ ] T049 Ejecución completa con datos sintéticos de varias estaciones y medición de la cobertura (≥ 85 %) — `tests/`
- [ ] T050 Sesión con el analista sobre datos reales: calibrar `k`, revisar los tramos no rellenados y cerrar las clarificaciones C1–C12 del spec — `config.yaml`, `spec_depuracion_demanda_electrica.md`

---

## Dependencias entre fases

```
Fase 0 ──► Fase 1 (H1) ──► Fase 2 (H2) ──► Fase 3 (H3) ──► Fase 4 (H4) ══► MVP
                                                              │
                                                              ├──► Fase 5 (H5)
                                                              └──► Fase 6 (H6)
                                                                        │
                                                    Fase 5 + Fase 6 ──► Fase 7
```

- La **Fase 2 (temperatura) es requisito** de las Fases 3 y 4 (RN-00).
- Las Fases 5 y 6 pueden desarrollarse en paralelo una vez cerrado el MVP.
- T010 (inspección de `inia.sql`) conviene hacerla lo antes posible: puede cambiar el diseño de la Fase 2.

## Estrategia incremental

1. **MVP (Fases 0–4)**: serie depurada en memoria con el método lineal; validable con datos sintéticos.
2. **Entrega 2 (Fase 5)**: archivos, log e informe; ya se puede usar en producción.
3. **Entrega 3 (Fase 6)**: comparación con IA y selección automática.
4. **Cierre (Fase 7)**: robustez, CLI completa, documentación y calibración con datos reales.
