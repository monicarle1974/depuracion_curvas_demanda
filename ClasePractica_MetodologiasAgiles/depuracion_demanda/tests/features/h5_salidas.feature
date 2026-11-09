# language: es
@h5
Característica: H5 — Archivos depurados e informe de calidad
  Como consumidor de datos quiero recibir archivos depurados con el mismo formato que los
  originales y un informe de lo corregido, para poder confiar en ellos y auditar los cambios.

  Antecedentes:
    Dado una carpeta de entrada con un año de demanda de "EST_001" en "est1.csv" con anomalías inyectadas
    Y la base inia con la temperatura correspondiente

  Escenario: H5.1 Un archivo depurado por entrada y originales intactos
    Dado que se registra la huella de los archivos de entrada
    Cuando se ejecuta el proceso completo
    Entonces el proceso termina con código 0
    Y existe el archivo depurado "est1.csv"
    Y los archivos de entrada no cambiaron

  Escenario: H5.2 Misma estructura más la columna origen
    Cuando se ejecuta el proceso completo
    Entonces el archivo depurado "est1.csv" tiene las columnas originales y "origen"
    Y el archivo depurado "est1.csv" tiene una fila por cada hora del año

  Escenario: H5.3 Informe con métricas por estación
    Cuando se ejecuta el proceso completo
    Entonces el informe incluye para "EST_001" outliers, huecos, no rellenados y MAE de validación
    Y existe el informe legible "informe.md"

  Escenario: H5.4 Registro de cambios completo
    Cuando se ejecuta el proceso completo
    Entonces cada valor estimado aparece en "cambios.csv" con valor original, motivo y temperatura

  Escenario: H5.5 Gráficos opcionales
    Dado que los gráficos están activados
    Cuando se ejecuta el proceso completo
    Entonces existe el archivo de salida "graficos/EST_001.png"

  Escenario: H5.6 Salida con el formato de la base de curvas de demanda
    Dado que la entrada es una base de curvas de demanda con un año de "ACO" con anomalías inyectadas
    Cuando se ejecuta el proceso completo
    Entonces el proceso termina con código 0
    Y el archivo depurado "ACO.csv" tiene las columnas "Codigo_estacion,Fecha_hora,Valor,Cambio_horario,origen"
    Y las fechas del archivo depurado "ACO.csv" coinciden con las de la base original

  Escenario: Ejecución en modo prueba sin escribir archivos
    Cuando se ejecuta el proceso completo en modo prueba
    Entonces el proceso termina con código 0
    Y no se generó ninguna carpeta de salida
