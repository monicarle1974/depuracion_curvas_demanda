# language: es
@h4 @mvp
Característica: H4 — Sustituir outliers por valores pronosticados
  Como analista quiero que los outliers y los huecos se reemplacen por un pronóstico basado
  en día de la semana, hora del día, estación del año y la temperatura obtenida de inia.

  Antecedentes:
    Dado la estación "EST_001" con capacidad máxima de 120 MW que no admite demanda cero
    Y un año de demanda horaria sintética con su temperatura asociada

  Escenario: H4.1 Estimación con las cuatro variables
    Dado que el valor real del "2025-07-15 19:00" se marca como outlier
    Cuando se ejecuta la detección y la sustitución
    Entonces el valor estimado del "2025-07-15 19:00" difiere menos de un 5 % del valor real
    Y el modelo usa día de la semana, hora, estación del año y temperatura

  Escenario: H4.2 Tramo de varias horas con una estimación por intervalo
    Dado un hueco de 6 horas desde "2025-09-10 15:00"
    Cuando se ejecuta la detección y la sustitución
    Entonces cada hora del tramo difiere menos de un 5 % de su valor real
    Y las estimaciones del tramo no son todas iguales

  Escenario: H4.3 El valor estimado queda identificado y se conserva el original
    Dado un pico de 1.8 veces la demanda esperada el "2025-05-05 10:00"
    Cuando se ejecuta la detección y la sustitución
    Entonces el registro "2025-05-05 10:00" tiene origen "estimado"
    Y el registro "2025-05-05 10:00" conserva su valor original

  Escenario: H4.4 Un tramo más largo que el máximo permitido no se rellena
    Dado un hueco de 192 horas desde "2025-08-01 00:00"
    Cuando se ejecuta la detección y la sustitución
    Entonces los registros del "2025-08-04" tienen origen "no_rellenado"
    Y se reporta 1 tramo no rellenado de 192 registros

  Escenario: H4.5 El modelo se entrena sin outliers
    Dado 80 anomalías inyectadas en la serie
    Y que se registran los datos de entrenamiento
    Cuando se ejecuta la detección y la sustitución
    Entonces ningún outlier ni hueco se usó para entrenar el modelo final

  Escenario: RF-017 Las estimaciones respetan los límites físicos
    Dado la capacidad máxima de "EST_001" reducida a 30 MW
    Cuando se ejecuta la detección y la sustitución
    Entonces todas las demandas depuradas están entre 0 y 30 MW

  Escenario: RN-00 La sustitución exige la temperatura
    Cuando se ejecuta la sustitución sin la columna de temperatura
    Entonces se produce un error de orden del proceso que menciona "temperatura"
