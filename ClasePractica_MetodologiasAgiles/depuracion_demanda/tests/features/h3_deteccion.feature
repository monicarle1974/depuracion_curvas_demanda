# language: es
@h3 @mvp
Característica: H3 — Detectar valores atípicos
  Como analista quiero que el sistema identifique automáticamente
  los valores fuera de rango de cada estación.

  Antecedentes:
    Dado la estación "EST_001" con capacidad máxima de 120 MW que no admite demanda cero
    Y un año de demanda horaria sintética con su temperatura asociada

  Escenario: H3.1 Demanda negativa
    Dado una demanda de -5 MW el "2025-03-10 14:00"
    Cuando se ejecuta la detección
    Entonces el registro "2025-03-10 14:00" es outlier con motivo "regla_fisica:negativo"

  Escenario: H3.2 Cero en una estación que no admite demanda nula
    Dado una demanda de 0 MW el "2025-04-02 03:00"
    Cuando se ejecuta la detección
    Entonces el registro "2025-04-02 03:00" es outlier con motivo "regla_fisica:cero"

  Escenario: H3.2b Demanda por encima de la capacidad máxima
    Dado una demanda de 150 MW el "2025-04-02 12:00"
    Cuando se ejecuta la detección
    Entonces el registro "2025-04-02 12:00" es outlier con motivo "regla_fisica:capacidad"

  Escenario: H3.3 Pico anómalo con temperatura normal
    Dado un pico de 1.8 veces la demanda esperada el "2025-06-20 19:00"
    Cuando se ejecuta la detección
    Entonces el registro "2025-06-20 19:00" es outlier con motivo "desviacion"

  Escenario: H3.4 Pico coherente con una ola de calor no es outlier
    Dado una ola de calor de 38 °C durante el "2025-01-15"
    Y la demanda de ese día responde a la temperatura como el resto del año
    Cuando se ejecuta la detección
    Entonces ningún registro del "2025-01-15" es outlier
    Y la demanda máxima del "2025-01-15" supera en más de 15 MW la del día anterior

  Escenario: Feriado con baja demanda no es outlier
    Dado que el "2025-07-16" (miércoles) es feriado según el archivo de feriados
    Cuando se ejecuta la detección
    Entonces ningún registro del "2025-07-16" es outlier

  Esquema del escenario: H3.5 Un umbral más estricto detecta más outliers
    Dado 80 anomalías inyectadas en la serie
    Cuando se ejecuta la detección con k = <k_estricto> y con k = <k_laxo>
    Entonces los outliers con k = <k_estricto> son al menos tantos como con k = <k_laxo>

    Ejemplos:
      | k_estricto | k_laxo |
      | 3          | 4      |
      | 4          | 6      |

  Escenario: RN-00 La detección exige la temperatura
    Cuando se ejecuta la detección sin la columna de temperatura
    Entonces se produce un error de orden del proceso que menciona "temperatura"
