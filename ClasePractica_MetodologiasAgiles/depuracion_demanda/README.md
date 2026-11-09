# Depuración de curvas de demanda eléctrica

Detecta y sustituye valores atípicos (outliers) en las curvas de demanda por estación, usando un
pronóstico basado en **día de la semana, hora del día, estación del año y temperatura** (INIA).

Documentos: [especificación](../spec_depuracion_demanda_electrica.md) · [plan](../plan.md) ·
[tareas](../tasks.md) · [plan de pruebas](../plan_pruebas.md)

## Requisitos

Solo **Docker** (Docker Desktop en Windows). Todo se instala y se ejecuta dentro del contenedor.

Las bases y el archivo de feriados se montan en **solo lectura** desde la carpeta superior
(`ClasePractica_MetodologiasAgiles/`). No se versionan:

| Archivo                   | Contenido                                                         |
|---------------------------|-------------------------------------------------------------------|
| `BD_CurvasDemanda.sqlite` | Curvas horarias por estación (`ESTACIONES`, `POTENCIA_ESTACION`)   |
| `inia.sqlite`             | Temperaturas INIA cada 10 min (`Estaciones`, `Medidores`, `Medidas`) |
| `tiposDeDia.txt`          | Feriados fijos y días especiales (Carnaval, Turismo)              |

## Uso

```bash
cd ClasePractica_MetodologiasAgiles/depuracion_demanda
docker compose build                                   # una vez (o al cambiar dependencias)

docker compose run --rm depurar                        # todas las estaciones del periodo configurado
docker compose run --rm depurar --estacion ACO --estacion MVL
docker compose run --rm depurar --metodo auto          # lineal | ia | auto
docker compose run --rm depurar --dry-run              # solo muestra el resumen, no escribe archivos

# Revisión manual (Acuerdos MVP 12.5): completar la columna "confirmado" (si/no) y evaluar
docker compose run --rm evaluar --archivo salida/ejecucion_AAAAMMDD_HHMMSS/revision_outliers.csv
```

Códigos de salida: `0` éxito · `1` error (configuración, inia, feriados o entrada) · `2` éxito parcial.

## Configuración

Todo se ajusta en [`config.yaml`](config.yaml), sin tocar el código: periodo, estaciones, umbral `k`,
duración máxima de relleno, método, umbral de aceptación, etc.

- **Mapeo a INIA**: con `mapeo_automatico: true`, cada estación usa la estación INIA con termómetro más
  cercana (y la segunda como respaldo). Las estaciones **sin coordenadas** en la base necesitan una
  entrada manual en `mapeo_estaciones`.
- **Por estación** se puede fijar `inia`, `inia_respaldo`, `capacidad_max_mw` y `permite_cero`.
- **Hora de la base**: `Fecha_hora` es la hora de reloj local guardada como epoch; `Cambio_horario = 1`
  indica horario de verano (UTC−2). Se convierte a hora local real y se restituye igual en la salida.

## Salidas (`salida/ejecucion_AAAAMMDD_HHMMSS/`)

| Archivo                  | Contenido                                                                  |
|--------------------------|----------------------------------------------------------------------------|
| `depurados/<EST>.csv`    | `Codigo_estacion, Fecha_hora, Valor, Cambio_horario, origen` (original / estimado / no_rellenado) |
| `cambios.csv`            | Cada valor sustituido: original, estimado, motivo, desviación, temperatura, método |
| `informe.md` / `.csv`    | Métricas por estación: outliers por motivo, huecos, tramos no rellenados, MAE/MAPE |
| `revision_outliers.csv`  | Muestra para la revisión del analista (columna `confirmado`)               |
| `graficos/<EST>.png`     | Serie original frente a depurada, con los outliers resaltados              |
| `config_usada.yaml`      | Configuración efectiva, incluido el mapeo INIA asignado                    |

La escritura es atómica (carpeta temporal + renombrado) y nunca modifica las entradas.

## Pruebas (TDD)

```bash
docker compose run --rm pruebas                    # todo menos datos reales
docker compose run --rm pruebas -m mvp             # alcance de la versión mínima
docker compose run --rm pruebas -m h3              # una historia
docker compose run --rm pruebas tests/features -v  # escenarios funcionales (Gherkin en español)
docker compose run --rm pruebas -m datos_reales    # contra las bases reales montadas
docker compose run --rm pruebas --cov=depuracion --cov-report=term-missing
```

| Carpeta                   | Contenido                                                          |
|---------------------------|--------------------------------------------------------------------|
| `tests/features/`         | Escenarios del spec en Gherkin (`# language: es`), pytest-bdd       |
| `tests/step_defs/`        | Implementación de los pasos                                        |
| `tests/unit/`             | Pruebas unitarias por módulo                                       |
| `tests/propiedades/`      | Invariantes con hypothesis (RN-01, RN-02, RN-05, RF-022, H3.5)     |
| `tests/integracion/`      | Criterios de éxito CE-001..CE-005, reproducibilidad, CLI, datos reales |
| `tests/datos/`            | Generador sintético y bases SQLite de prueba con el esquema real   |

La integración continua (`.github/workflows/pruebas.yml`) construye la imagen y ejecuta la suite en
cada push.
