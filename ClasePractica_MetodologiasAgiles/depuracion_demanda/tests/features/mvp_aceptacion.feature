# language: es
@mvp
Característica: Aceptación de la revisión manual de outliers (Acuerdos MVP 12.5)
  El analista confirma una muestra de outliers por estación y la estación se acepta
  si la proporción confirmada alcanza el umbral configurable min_outliers_confirmados.

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

  Escenario: Una revisión sin completar no se acepta
    Dado una muestra de 20 outliers de "EST_001" con 19 respondidos por el analista
    Cuando se ejecuta evaluar-revision
    Entonces la estación "EST_001" queda "incompleta"

  Escenario: El proceso genera la muestra de revisión con el tamaño configurado
    Dado una carpeta de entrada con un año de demanda de "EST_001" en "est1.csv" con anomalías inyectadas
    Y la base inia con la temperatura correspondiente
    Y el tamaño de muestra configurado en 15 outliers por estación
    Cuando se ejecuta el proceso completo
    Entonces el archivo "revision_outliers.csv" tiene 15 filas de "EST_001" con la columna "confirmado" vacía
