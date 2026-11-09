# language: es
@h1 @mvp
Característica: H1 — Cargar y validar los archivos de demanda
  Como analista quiero cargar los archivos de demanda de una o varias estaciones
  y que el sistema verifique su estructura, para trabajar sobre datos homogéneos y completos.

  Escenario: H1.1 Carga válida con resumen por estación
    Dado un archivo "est1.csv" de la estación "EST_001" con 48 horas desde "2025-03-03 00:00"
    Y un archivo "est2.csv" de la estación "EST_002" con 24 horas desde "2025-03-03 00:00"
    Cuando se ejecuta la carga
    Entonces el resumen informa 48 registros para "EST_001"
    Y el resumen informa 24 registros para "EST_002"
    Y no hay archivos rechazados

  Escenario: H1.2 Archivo inválido rechazado sin detener el resto
    Dado un archivo "est1.csv" de la estación "EST_001" con 24 horas desde "2025-03-03 00:00"
    Y un archivo "roto.csv" sin la columna "demanda"
    Y un archivo "texto.csv" con el valor de demanda "abc"
    Cuando se ejecuta la carga
    Entonces el archivo "roto.csv" se rechaza indicando "demanda"
    Y el archivo "texto.csv" se rechaza indicando "no numéricos"
    Y el resumen informa 24 registros para "EST_001"

  Esquema del escenario: H1.3 Duplicados resueltos según la política configurada
    Dado la política de duplicados "<politica>"
    Y un archivo "dup.csv" de la estación "EST_001" con la hora "2025-03-03 05:00" repetida con valores 10 y 20
    Cuando se ejecuta la carga
    Entonces la demanda de "EST_001" a las "2025-03-03 05:00" es <valor>
    Y el resumen informa 2 duplicados para "EST_001"

    Ejemplos:
      | politica | valor |
      | primero  | 10    |
      | ultimo   | 20    |
      | promedio | 15    |

  Escenario: H1.4 Huecos reindexados y marcados
    Dado un archivo "est1.csv" de la estación "EST_001" con 24 horas desde "2025-03-03 00:00" sin la hora "2025-03-03 03:00"
    Cuando se ejecuta la carga
    Entonces el resumen informa 24 registros para "EST_001"
    Y el registro "2025-03-03 03:00" de "EST_001" está marcado como hueco

  Escenario: H1.5 Carga desde la base de curvas de demanda (SQLite)
    Dado una base de curvas de demanda con "ACO" durante 48 horas y "ARA" durante 24 horas desde "2024-03-04 00:00"
    Cuando se ejecuta la carga
    Entonces el resumen informa 48 registros para "ACO"
    Y el resumen informa 24 registros para "ARA"
    Y no hay archivos rechazados

  Esquema del escenario: H1.6 La hora de la base se interpreta con el indicador de cambio horario
    Dado una base de curvas de demanda con "ACO" con una lectura a las "<hora>" con Cambio_horario <cambio>
    Cuando se ejecuta la carga
    Entonces el registro de "ACO" está a las "<hora>" hora local con desfase UTC "<desfase>"

    Ejemplos:
      | hora             | cambio | desfase |
      | 2014-12-10 20:00 | 1      | -02:00  |
      | 2024-12-10 20:00 | 0      | -03:00  |

  Escenario: H1.7 Filtro por periodo y por estaciones configuradas
    Dado una base de curvas de demanda con "ACO" durante 96 horas y "ARA" durante 96 horas desde "2024-03-04 00:00"
    Y el periodo configurado desde "2024-03-05" hasta "2024-03-06"
    Y las estaciones configuradas "ACO"
    Cuando se ejecuta la carga
    Entonces el resumen informa 48 registros para "ACO"
    Y no se cargó la estación "ARA"

  Escenario: Cambio de horario sin horas duplicadas ni perdidas
    Dado la zona horaria "Europe/Madrid"
    Y un archivo "dst.csv" de la estación "EST_001" con las horas locales del cambio de horario del "2025-10-26"
    Cuando se ejecuta la carga
    Entonces la serie de "EST_001" tiene intervalos regulares de 1 hora sin huecos
