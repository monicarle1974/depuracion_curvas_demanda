# language: es
@h6
Característica: H6 — Comparar métodos de estimación
  Como analista quiero comparar la regresión lineal con un modelo de IA
  para elegir el método más preciso por estación.

  Antecedentes:
    Dado la estación "EST_001" con capacidad máxima de 120 MW que no admite demanda cero
    Y 120 días de demanda horaria sintética con su temperatura asociada

  Escenario: H6.1 Reporte de error por método y estación
    Cuando se comparan los métodos con validación temporal
    Entonces se informa MAE y MAPE para "lineal" y para "ia"

  Escenario: H6.2 La selección automática elige el método de menor error
    Dado el método configurado "auto"
    Y 40 anomalías inyectadas en la serie
    Cuando se ejecuta la detección y la sustitución
    Entonces el método usado es el de menor MAE de la comparación

  Escenario: El método de IA también sustituye los outliers
    Dado el método configurado "ia"
    Y 40 anomalías inyectadas en la serie
    Cuando se ejecuta la detección y la sustitución
    Entonces los valores estimados tienen método "ia"
