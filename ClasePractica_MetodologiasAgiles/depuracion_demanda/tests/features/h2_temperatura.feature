# language: es
@h2 @mvp
Característica: H2 — Obtener la temperatura desde inia y las variables de calendario
  Como analista quiero que la temperatura asociada a cada registro se obtenga de inia
  (antes de detectar y sustituir outliers) y que se consideren los feriados.

  Escenario: H2.1 Temperatura de la estación INIA asociada
    Dado una base inia con "LAS_BRUJAS" a 20 °C y "DURAZNO" a 30 °C cada 10 minutos desde "2025-01-06" durante 2 días
    Y la estación eléctrica "EST_001" asociada a "LAS_BRUJAS"
    Cuando se enriquece una serie horaria de "EST_001" desde "2025-01-06" durante 2 días
    Entonces todas las temperaturas de "EST_001" son 20 °C

  Esquema del escenario: H2.2 Alineación temporal configurable
    Dado una base inia con lecturas de "LAS_BRUJAS" cada <resolucion> desde "2025-01-06" durante 2 días
    Y la estación eléctrica "EST_001" asociada a "LAS_BRUJAS"
    Y el modo de alineación "<modo>"
    Cuando se enriquece una serie horaria de "EST_001" desde "2025-01-06" durante 2 días
    Entonces la temperatura de "EST_001" a las "2025-01-06 <hora>" es <esperado>

    Ejemplos:
      | resolucion | modo            | hora  | esperado |
      | 10min      | igual           | 14:00 | 10       |
      | 10min      | media_intervalo | 14:00 | 12.5     |
      | 10min      | media_diaria    | 14:00 | 12.5     |
      | 10min      | auto            | 14:00 | 12.5     |
      | 2h         | interpolar      | 13:00 | 13       |
      | 2h         | auto            | 13:00 | 13       |

  Escenario: H2.3a Hueco corto de temperatura interpolado
    Dado una base inia con "LAS_BRUJAS" sin lecturas entre "2025-01-06 10:00" y "2025-01-06 12:59"
    Y la estación eléctrica "EST_001" asociada a "LAS_BRUJAS"
    Cuando se enriquece una serie horaria de "EST_001" desde "2025-01-06" durante 2 días
    Entonces la temperatura de "EST_001" a las "2025-01-06 11:00" tiene origen "interpolada"
    Y ningún registro de "EST_001" tiene temperatura faltante

  Escenario: H2.3b Hueco largo cubierto con la estación de respaldo
    Dado una base inia con "LAS_BRUJAS" sin lecturas entre "2025-01-06 00:00" y "2025-01-06 23:59"
    Y la estación eléctrica "EST_001" asociada a "LAS_BRUJAS" con respaldo "DURAZNO"
    Cuando se enriquece una serie horaria de "EST_001" desde "2025-01-06" durante 2 días
    Entonces la temperatura de "EST_001" a las "2025-01-06 11:00" tiene origen "respaldo"
    Y ningún registro de "EST_001" tiene temperatura faltante

  Escenario: H2.3c Hueco largo sin respaldo queda marcado como faltante
    Dado una base inia con "LAS_BRUJAS" sin lecturas entre "2025-01-06 00:00" y "2025-01-06 23:59"
    Y la estación eléctrica "EST_001" asociada a "LAS_BRUJAS"
    Cuando se enriquece una serie horaria de "EST_001" desde "2025-01-06" durante 2 días
    Entonces la temperatura de "EST_001" a las "2025-01-06 11:00" tiene origen "faltante"
    Y el registro de "EST_001" a las "2025-01-06 11:00" tiene temperatura faltante

  Escenario: C4 Asignación automática de la estación INIA más cercana
    Dado una base inia con "LAS_BRUJAS" en (-34.672, -56.340) y "DURAZNO" en (-33.314, -56.524)
    Y una estación eléctrica "ACO" sin mapeo en (-34.526, -56.381)
    Cuando se resuelve la estación INIA de "ACO"
    Entonces "ACO" usa "LAS_BRUJAS" con respaldo "DURAZNO"

  Escenario: H2.4 Base inia inaccesible: el proceso se detiene sin generar salidas
    Dado una carpeta de entrada con un año de demanda de "EST_001" en "est1.csv" con anomalías inyectadas
    Y que la base inia no existe
    Cuando se ejecuta el proceso completo
    Entonces el proceso termina con código 1
    Y el error indica "temperaturas"
    Y no se generó ninguna carpeta de salida

  Escenario: Feriado general y feriado local tratados como domingo
    Dado un archivo de feriados con "2025-01-01" general y "2025-01-08" local de "EST_002"
    Cuando se agregan las variables de calendario para "EST_001" y "EST_002" en enero de 2025
    Entonces el "2025-01-01" es "domingo_feriado" para "EST_001"
    Y el "2025-01-08" es "laborable" para "EST_001"
    Y el "2025-01-08" es "domingo_feriado" para "EST_002"

  Escenario: Archivo de feriados en formato tiposDeDia del negocio
    Dado un archivo de feriados en formato tiposDeDia con el feriado fijo 7/18 y el "2024 2 12 lunes-carnaval"
    Cuando se cargan los feriados
    Entonces el "2023-07-18" y el "2024-07-18" son feriado
    Y el "2024-02-12" es feriado con descripción "lunes-carnaval"
    Y el "2024-02-14" no es feriado

  Escenario: Archivo de feriados ausente: el proceso se detiene
    Dado una carpeta de entrada con un año de demanda de "EST_001" en "est1.csv" con anomalías inyectadas
    Y la base inia con la temperatura correspondiente
    Y que el archivo de feriados no existe
    Cuando se ejecuta el proceso completo
    Entonces el proceso termina con código 1
    Y el error indica "feriados"

  Escenario: Filas inválidas del archivo de feriados se reportan
    Dado un archivo de feriados con una fecha inválida en la línea 3
    Cuando se cargan los feriados
    Entonces se reporta un error en la "línea 3"
    Y los demás feriados se cargan
