# Especificación Funcional: Depuración de Archivos de Demanda Eléctrica por Estación

| Campo              | Valor                                        |
|--------------------|----------------------------------------------|
| **ID**             | 002-depuracion-demanda-electrica             |
| **Rama sugerida**  | `002-depuracion-demanda-electrica`           |
| **Fecha**          | 2026-11-09                                   |
| **Estado**         | Borrador (pendiente de clarificación)        |
| **Metodología**    | Spec-Driven Development (SDD)                |

**Requerimiento original**:

> "Dado algunos archivos de demanda eléctrica por estación, quiero elaborar un proceso que depure estos archivos, eliminando outliers. Para ello se usarán algunos algoritmos de regresión lineal o herramientas de IA. En los periodos donde hay valores fuera de rango se sustituirían con predicciones que tomarán en cuenta el día de la semana, la hora del día, la estación del año y la temperatura. Esta última se obtendrá de una BD llamada inia.sql."

> **Nota SDD**: este documento describe **QUÉ** debe hacer el proceso y **POR QUÉ**. Las decisiones de **CÓMO** (lenguaje, librerías, modelo concreto, arquitectura) pertenecen al `plan.md`. Las restricciones impuestas por el propio requerimiento (uso de regresión lineal o IA, fuente `inia.sql`) se recogen como **restricciones**, no como diseño. Las ambigüedades se marcan con `[NECESITA CLARIFICACIÓN]`.

> **Terminología**: en este documento **"estación"** se refiere a la *estación de medición* (punto de la red eléctrica cuyos datos de demanda se registran) y **"estación del año"** a la temporada climática (verano, otoño, invierno, primavera).

---

## 1. Contexto y objetivo

### 1.1 Problema
Los archivos de demanda eléctrica registrados por estación contienen valores anómalos (picos, caídas a cero, valores negativos, saltos imposibles, huecos) producidos por fallos de medición, cortes de comunicación o eventos excepcionales. Estos valores distorsionan los análisis, informes y modelos de previsión que se construyen a partir de los datos.

### 1.2 Objetivo
Disponer de un proceso que, a partir de los archivos de demanda originales:
1. **Detecte** los valores atípicos (outliers) de cada estación.
2. **Sustituya** esos valores por una **estimación** basada en el comportamiento esperado según día de la semana, hora del día, estación del año y temperatura.
3. **Entregue** archivos depurados junto con un registro trazable de todos los cambios realizados.

### 1.3 Fuera de alcance (esta versión)
- Previsión de demanda futura (forecasting) más allá de rellenar los periodos anómalos.
- Corrección en tiempo real / streaming de los datos.
- Mantenimiento o carga de la base de datos de temperaturas `inia.sql`.
- Interfaz gráfica de usuario completa (se acepta ejecución por línea de comandos o notebook). `[NECESITA CLARIFICACIÓN]`
- Diagnóstico de la causa física de cada anomalía.

---

## 2. Actores

| Actor                       | Descripción                                                                                      |
|-----------------------------|--------------------------------------------------------------------------------------------------|
| **Analista de datos**       | Ejecuta el proceso, revisa los resultados y valida las sustituciones.                            |
| **Consumidor de datos**     | Persona o sistema que utiliza los archivos depurados (informes, modelos de previsión, planificación). |
| **Fuente de temperaturas**  | Base de datos `inia.sql` que provee la temperatura histórica por fecha/hora y ubicación.         |

---

## 3. Escenarios de usuario y pruebas *(obligatorio)*

Las historias están priorizadas. Cada una es **independientemente testeable** y entrega valor por sí sola.

### Historia 1 — Cargar y validar los archivos de demanda (Prioridad: P1) 🎯 MVP

Como analista quiero cargar los archivos de demanda de una o varias estaciones y que el sistema verifique su estructura, para trabajar sobre datos homogéneos y completos.

**Por qué esta prioridad**: sin una lectura fiable de los datos de entrada no puede realizarse ninguna depuración.

**Prueba independiente**: cargar un conjunto de archivos de ejemplo y verificar que se obtiene un resumen por estación (rango de fechas, número de registros, huecos detectados).

**Escenarios de aceptación**:

1. **Dado** una carpeta con archivos de demanda válidos, **cuando** el analista ejecuta la carga, **entonces** el sistema lee todos los archivos e informa, por estación, el periodo cubierto y el número de registros.
2. **Dado** un archivo con columnas faltantes o con un formato no reconocido, **cuando** se intenta cargar, **entonces** el sistema lo rechaza indicando el archivo y el motivo, y continúa con el resto.
3. **Dado** una serie con marcas de tiempo duplicadas, **cuando** se carga, **entonces** el sistema las reporta. `[NECESITA CLARIFICACIÓN: ¿se conserva la primera, la última o el promedio?]`
4. **Dado** una serie con intervalos faltantes (p. ej. falta la hora 03:00), **cuando** se carga, **entonces** el sistema identifica el hueco y lo marca como valor a estimar.

---

### Historia 2 — Obtener la temperatura desde `inia.sql` (Prioridad: P1) 🎯 MVP

Como analista quiero que la temperatura asociada a cada registro de demanda se obtenga automáticamente de la base de datos `inia.sql`, para usarla como variable explicativa en la detección de outliers y en el pronóstico que los sustituye.

**Por qué esta prioridad**: la temperatura es una de las cuatro variables exigidas para el pronóstico; debe estar disponible **antes** de detectar y sustituir outliers (Historias 3 y 4).

**Prueba independiente**: para un conjunto de fechas/horas conocidas, verificar que la temperatura obtenida coincide con la almacenada en `inia.sql`.

**Escenarios de aceptación**:

1. **Dado** un registro de demanda de la estación X en una fecha/hora, **cuando** se enriquece con temperatura, **entonces** se toma la temperatura de la estación meteorológica asociada a X para ese mismo instante. `[NECESITA CLARIFICACIÓN: tabla de correspondencia estación eléctrica ↔ estación meteorológica INIA]`
2. **Dado** que la resolución temporal de la temperatura difiere de la de la demanda (p. ej. diaria vs. horaria), **cuando** se enriquece, **entonces** el sistema aplica una regla de alineación documentada. `[NECESITA CLARIFICACIÓN: interpolar, repetir valor, usar media/máx/mín]`
3. **Dado** un instante sin temperatura disponible en `inia.sql`, **cuando** se enriquece, **entonces** el sistema lo indica y aplica la regla de respaldo definida. `[NECESITA CLARIFICACIÓN: interpolar temperatura, usar estación cercana o estimar sin temperatura]`
4. **Dado** que `inia.sql` no está accesible, **cuando** se ejecuta el proceso, **entonces** este se detiene con un mensaje claro y no genera archivos parciales.

---

### Historia 3 — Detectar valores atípicos (Prioridad: P1) 🎯 MVP

Como analista quiero que el sistema identifique automáticamente los valores fuera de rango de cada estación para no tener que revisarlos manualmente.

**Por qué esta prioridad**: es el núcleo del requerimiento ("eliminar outliers").

**Prueba independiente**: sobre una serie con anomalías introducidas artificialmente en posiciones conocidas, comprobar que el sistema las detecta.

**Escenarios de aceptación**:

1. **Dado** un registro de demanda negativa, **cuando** se ejecuta la detección, **entonces** se marca como outlier por regla física.
2. **Dado** un registro con valor `0` en una estación que nunca tiene demanda nula, **cuando** se ejecuta la detección, **entonces** se marca como outlier. `[NECESITA CLARIFICACIÓN: ¿hay estaciones donde 0 es un valor legítimo?]`
3. **Dado** un pico cuyo valor se aleja significativamente de lo esperado para ese día de la semana, hora, estación del año y temperatura, **cuando** se ejecuta la detección, **entonces** se marca como outlier estadístico.
4. **Dado** un valor alto pero coherente con una temperatura extrema (p. ej. ola de calor), **cuando** se ejecuta la detección, **entonces** NO se marca como outlier.
5. **Dado** un umbral de sensibilidad configurable, **cuando** el analista lo modifica, **entonces** el número de outliers detectados cambia de forma coherente (umbral más estricto → más detecciones).

---

### Historia 4 — Sustituir outliers por valores pronosticados (Prioridad: P1) 🎯 MVP

Como analista quiero que los valores detectados como outliers (y los huecos) se reemplacen por un pronóstico basado en día de la semana, hora del día, estación del año y la temperatura obtenida de `inia.sql`, para obtener una serie continua y realista.

**Por qué esta prioridad**: es la segunda mitad explícita del requerimiento; sin ella los datos quedan incompletos.

**Dependencias**: requiere los datos cargados (Historia 1), la temperatura ya incorporada a cada registro (Historia 2) y los outliers detectados (Historia 3).

**Prueba independiente**: eliminar valores conocidos de una serie limpia, ejecutar la sustitución y comparar la estimación con el valor real.

**Escenarios de aceptación**:

1. **Dado** un outlier detectado un martes a las 19:00 de invierno con 8 °C, **cuando** se ejecuta la sustitución, **entonces** el valor se reemplaza por una estimación calculada con esas cuatro variables.
2. **Dado** un periodo anómalo de varias horas consecutivas, **cuando** se sustituye, **entonces** cada intervalo recibe su propia estimación (la serie conserva la forma diaria esperada).
3. **Dado** un registro sustituido, **cuando** se consulta el archivo depurado, **entonces** el registro está marcado como "estimado" y conserva el valor original en el registro de cambios.
4. **Dado** un periodo anómalo superior a la duración máxima permitida, **cuando** se ejecuta la sustitución, **entonces** el sistema NO lo rellena y lo reporta para revisión manual. `[NECESITA CLARIFICACIÓN: duración máxima, p. ej. 7 días]`
5. **Dado** que el modelo de estimación se entrena, **cuando** se construye, **entonces** solo utiliza datos que NO han sido marcados como outliers.

---

### Historia 5 — Generar archivos depurados e informe de calidad (Prioridad: P2)

Como consumidor de datos quiero recibir archivos depurados con el mismo formato que los originales y un informe de lo corregido, para poder confiar en ellos y auditar los cambios.

**Por qué esta prioridad**: aporta trazabilidad y confianza; los datos depurados (P1) ya son útiles sin informe.

**Prueba independiente**: ejecutar el proceso y verificar que el número de registros sustituidos en el informe coincide con los marcados en el archivo de salida.

**Escenarios de aceptación**:

1. **Dado** un proceso finalizado, **cuando** se revisa la salida, **entonces** existe un archivo depurado por cada archivo de entrada, sin sobrescribir los originales.
2. **Dado** un archivo depurado, **cuando** se compara con el original, **entonces** tiene la misma estructura y el mismo número de intervalos (más los huecos rellenados), con una columna adicional que indica si el valor es original o estimado.
3. **Dado** un proceso finalizado, **cuando** se consulta el informe, **entonces** muestra por estación: número y porcentaje de outliers, huecos rellenados, periodos no rellenados y la precisión del modelo de estimación.
4. **Dado** un proceso finalizado, **cuando** se consulta el registro de cambios, **entonces** cada sustitución incluye: estación, fecha/hora, valor original, valor estimado, motivo de detección y temperatura utilizada.
5. **Dado** el informe, **cuando** el analista lo solicita, **entonces** puede visualizar gráficamente la serie original frente a la depurada por estación. `[NECESITA CLARIFICACIÓN: ¿los gráficos son requeridos en esta versión?]`

---

### Historia 6 — Comparar métodos de estimación (Prioridad: P3)

Como analista quiero comparar el desempeño de la regresión lineal frente a un modelo de IA, para elegir el método más preciso por estación.

**Por qué esta prioridad**: mejora la calidad, pero el proceso funciona con un único método.

**Prueba independiente**: con un conjunto de validación, obtener la métrica de error de cada método y verificar que se selecciona el de menor error.

**Escenarios de aceptación**:

1. **Dado** al menos dos métodos disponibles, **cuando** se ejecuta la comparación, **entonces** el sistema reporta para cada estación el error de cada método sobre datos reservados para validación.
2. **Dado** el resultado de la comparación, **cuando** el analista elige "selección automática", **entonces** cada estación usa el método con menor error.

---

### 3.1 Casos límite (edge cases)

- Estación con muy poco histórico limpio para entrenar un modelo → `[NECESITA CLARIFICACIÓN: mínimo de datos requerido]`.
- Estación cuya demanda cambia estructuralmente (nueva carga conectada, redistribución de red): ¿es un outlier o un nuevo nivel normal?
- Días feriados: su perfil se parece más a un domingo que al día de la semana real. → **Resuelto (C8)**: se consideran y se cargan desde un archivo específico de feriados proporcionado por el negocio.
- Cambio de horario (horario de verano) que genera horas duplicadas o inexistentes.
- Zonas horarias distintas entre los archivos de demanda y `inia.sql`.
- Eventos excepcionales legítimos (apagones programados, eventos masivos) que no deberían corregirse.
- Archivos de distintas estaciones con resolución temporal diferente (15 min vs. horaria).
- Valores estimados negativos producidos por el modelo → deben acotarse a un mínimo físico.
- Definición de estación del año: astronómica vs. meteorológica y hemisferio. `[NECESITA CLARIFICACIÓN]`

---

## 4. Requisitos *(obligatorio)*

### 4.1 Requisitos funcionales

**Carga y validación**
- **RF-001**: El sistema DEBE leer archivos de demanda de una o más estaciones desde una ubicación indicada. `[NECESITA CLARIFICACIÓN: formato — CSV, Excel, otro; estructura de columnas]`
- **RF-002**: El sistema DEBE validar la estructura de cada archivo (columnas obligatorias, tipos, fechas válidas) y rechazar los inválidos indicando el motivo.
- **RF-003**: El sistema DEBE identificar marcas de tiempo duplicadas y huecos en la serie de cada estación.
- **RF-004**: El sistema DEBE procesar cada estación de forma independiente.

**Enriquecimiento**
- **RF-005**: El sistema DEBE derivar para cada registro: día de la semana, hora del día y estación del año.
- **RF-006**: El sistema DEBE obtener la temperatura correspondiente a cada registro desde la base de datos `inia.sql`.
- **RF-007**: El sistema DEBE asociar cada estación eléctrica con una fuente de temperatura de `inia.sql` mediante una correspondencia configurable.
- **RF-008**: El sistema DEBE alinear temporalmente la temperatura con la demanda según una regla documentada.

**Detección de outliers**
- **RF-009**: El sistema DEBE marcar como outlier los valores que violen reglas físicas (negativos, superiores a la capacidad máxima de la estación). `[NECESITA CLARIFICACIÓN: capacidad máxima por estación]`
- **RF-010**: El sistema DEBE marcar como outlier los valores cuya desviación respecto a lo esperado (según día, hora, estación del año y temperatura) supere un umbral configurable.
- **RF-011**: El sistema DEBE marcar los huecos de la serie como valores a estimar.
- **RF-012**: El sistema DEBE registrar el motivo de cada detección (regla física, desviación estadística, hueco).

**Sustitución**
- **RF-013**: El sistema DEBE estimar el valor de cada outlier y hueco usando como variables: día de la semana, hora del día, estación del año y temperatura.
- **RF-014**: El modelo de estimación DEBE construirse únicamente con datos no marcados como outliers.
- **RF-015**: El sistema DEBE permitir al menos un método basado en regresión lineal y, opcionalmente, un método basado en IA / aprendizaje automático.
- **RF-016**: El sistema NO DEBE rellenar automáticamente periodos anómalos más largos que una duración máxima configurable; DEBE reportarlos.
- **RF-017**: Los valores estimados DEBEN respetar los límites físicos de la estación (no negativos, no superiores a la capacidad máxima).

**Salida y trazabilidad**
- **RF-018**: El sistema DEBE generar un archivo depurado por cada archivo de entrada sin modificar los originales.
- **RF-019**: Cada registro del archivo depurado DEBE indicar si su valor es original o estimado.
- **RF-020**: El sistema DEBE generar un registro de cambios con: estación, fecha/hora, valor original, valor estimado, motivo y temperatura usada.
- **RF-021**: El sistema DEBE generar un informe de calidad por estación (outliers detectados, % sustituido, periodos no rellenados, métrica de error del modelo).
- **RF-022**: Ejecutar el proceso dos veces con los mismos datos y la misma configuración DEBE producir los mismos resultados (reproducibilidad).

### 4.2 Requisitos no funcionales

- **RNF-001 (Rendimiento)**: Procesar un año de datos horarios de una estación (~8.760 registros) en menos de 1 minuto. `[NECESITA CLARIFICACIÓN: volumen real — nº de estaciones y años]`
- **RNF-002 (Configurabilidad)**: Umbrales, duración máxima de relleno, método de estimación y correspondencia de estaciones se definen en configuración, sin modificar el proceso.
- **RNF-003 (Trazabilidad)**: Toda modificación de un valor debe ser auditable a partir del registro de cambios.
- **RNF-004 (Integridad)**: Los archivos originales nunca se sobrescriben.
- **RNF-005 (Explicabilidad)**: Debe poder justificarse por qué un valor fue marcado como outlier y de dónde sale su estimación.
- **RNF-006 (Seguridad)**: El acceso a `inia.sql` es de solo lectura.

### 4.3 Entidades clave

| Entidad                        | Descripción                                               | Atributos principales                                                                   |
|--------------------------------|-----------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **Estación**                   | Punto de medición de demanda eléctrica.                   | identificador, nombre, ubicación, capacidad máxima, estación meteorológica asociada     |
| **Registro de demanda**        | Medición de una estación en un instante.                  | estación, fecha/hora, demanda, unidad                                                   |
| **Registro de temperatura**    | Dato climático de `inia.sql`.                             | estación meteorológica, fecha/hora, temperatura                                         |
| **Registro enriquecido**       | Demanda con variables explicativas.                       | registro de demanda, día de la semana, hora, estación del año, temperatura              |
| **Outlier detectado**          | Valor marcado como anómalo.                               | registro, motivo, magnitud de la desviación                                             |
| **Sustitución**                | Reemplazo de un outlier o hueco.                          | registro, valor original, valor estimado, método usado                                  |
| **Modelo de estimación**       | Método entrenado para una estación.                       | estación, tipo (regresión lineal / IA), periodo de entrenamiento, métrica de error       |
| **Informe de calidad**         | Resumen de una ejecución.                                 | fecha de ejecución, configuración, métricas por estación                                |

**Relaciones**: una Estación tiene 0..N Registros de demanda y 1 fuente de temperatura asociada; un Registro de demanda puede tener 0..1 Outlier detectado y 0..1 Sustitución; cada Estación tiene 1..N Modelos de estimación (uno activo).

### 4.4 Reglas de negocio

- **RN-00 (Orden del proceso)**: 1) carga y validación → 2) obtención de la temperatura desde `inia.sql` → 3) detección de outliers → 4) sustitución por pronóstico → 5) generación de salidas. No se sustituye ningún valor hasta que la temperatura esté disponible.

- **RN-01**: La demanda nunca puede ser negativa.
- **RN-02**: Un valor solo se sustituye si fue marcado como outlier o corresponde a un hueco.
- **RN-03**: Los datos marcados como outliers no participan en el entrenamiento del modelo.
- **RN-04**: Estación del año: `[NECESITA CLARIFICACIÓN]` — propuesta para hemisferio sur: verano (dic–feb), otoño (mar–may), invierno (jun–ago), primavera (sep–nov).
- **RN-05**: Todo valor estimado queda identificado como tal en la salida.

### 4.5 Restricciones (impuestas por el requerimiento)

- **RES-01**: La estimación debe basarse en regresión lineal o herramientas de IA.
- **RES-02**: La temperatura debe obtenerse de la base de datos `inia.sql`.
- **RES-03**: Las variables explicativas mínimas son: día de la semana, hora del día, estación del año y temperatura.

---

## 5. Criterios de éxito *(obligatorio)*

Medibles y agnósticos de la tecnología:

- **CE-001**: Sobre un conjunto de prueba con anomalías inyectadas, el proceso detecta al menos el **90 %** de ellas (sensibilidad).
- **CE-002**: Menos del **5 %** de los valores normales del conjunto de prueba se marcan erróneamente como outliers (falsos positivos).
- **CE-003**: El error medio de las estimaciones, medido sobre valores reales ocultados artificialmente, es inferior al **5 %** de la demanda media de la estación (MAPE < 5 %). `[NECESITA CLARIFICACIÓN: umbral aceptable para el negocio]`
- **CE-004**: El **100 %** de los valores sustituidos aparecen en el registro de cambios con su valor original.
- **CE-005**: El **100 %** de los archivos originales permanecen sin modificar tras la ejecución.
- **CE-006**: Un analista puede ejecutar el proceso completo sobre un nuevo lote de archivos sin modificar el proceso, solo la configuración.

---

## 6. Supuestos

- Los archivos de demanda contienen, como mínimo, identificador de estación, fecha/hora y valor de demanda.
- La base de datos `inia.sql` contiene temperaturas históricas que cubren el mismo periodo que los archivos de demanda.
- `inia.sql` corresponde a datos del INIA (Instituto Nacional de Investigación Agropecuaria) y las estaciones se ubican en el hemisferio sur. `[NECESITA CLARIFICACIÓN: confirmar]`
- Existe suficiente histórico limpio por estación para construir un modelo de estimación (al menos varios meses que cubran distintas estaciones del año).
- La unidad de demanda es homogénea dentro de cada estación (p. ej. MW o kW).

---

## 7. Clarificaciones pendientes

| #   | Pregunta                                                                                    | Impacto                    |
|-----|---------------------------------------------------------------------------------------------|----------------------------|
| C1  | ¿Formato y estructura de columnas de los archivos de demanda? ¿Resolución temporal?         | RF-001, Historia 1         |
| C2  | ¿Cómo se tratan los duplicados de marca de tiempo?                                          | RF-003, Historia 1         |
| C3  | ¿Hay estaciones donde una demanda 0 es legítima? ¿Capacidad máxima por estación?            | RF-009, RF-017             |
| C4  | ¿Cuál es la correspondencia entre estación eléctrica y estación meteorológica de INIA?      | RF-007, Historia 2         |
| C5  | ¿Qué resolución tiene la temperatura en `inia.sql` y cómo se alinea con la demanda?         | RF-008, Historia 2         |
| C6  | ¿Qué hacer si falta la temperatura para un instante?                                        | Historia 2                 |
| C7  | ¿Duración máxima de un periodo anómalo que se puede rellenar automáticamente?               | RF-016, Historia 4         |
| C8  | ✅ Resuelto: sí se consideran; el negocio entrega un archivo específico de feriados         | Casos límite, RF-005       |
| C9  | ¿Definición de estación del año (astronómica / meteorológica, hemisferio)?                  | RN-04, RF-005              |
| C10 | ¿Volumen de datos (nº de estaciones, años, resolución)?                                     | RNF-001                    |
| C11 | ¿Umbral de error aceptable para las estimaciones?                                           | CE-003                     |
| C12 | ¿Se requiere interfaz gráfica o gráficos en el informe, o basta con ejecución por comandos? | Fuera de alcance, Historia 5 |

---

## 8. Checklist de calidad de la especificación

- [x] Se centra en el QUÉ y el POR QUÉ; las tecnologías solo aparecen como restricciones del requerimiento.
- [x] Historias priorizadas e independientemente testeables.
- [x] Escenarios de aceptación en formato Dado / Cuando / Entonces.
- [x] Requisitos funcionales numerados, verificables y no ambiguos.
- [x] Criterios de éxito medibles y agnósticos de la tecnología.
- [x] Entidades clave identificadas.
- [x] Casos límite identificados.
- [ ] Todas las marcas `[NECESITA CLARIFICACIÓN]` resueltas. ← **bloquea el paso a `plan.md`**

---

## 9. Siguientes pasos (flujo SDD)

1. **Clarificar** (`/clarify`): resolver la tabla de la sección 7 con el responsable del negocio y revisar una muestra de los archivos y de `inia.sql`.
2. **Planificar** (`plan.md`): elegir tecnologías, algoritmo de detección, modelo de estimación y formato de salida.
3. **Tareas** (`tasks.md`): desglose por historia (P1 → P2 → P3).
4. **Implementar**: desarrollo guiado por los escenarios de aceptación como pruebas, usando conjuntos de datos con anomalías inyectadas.
