# Especificación de Funcionalidad: Registro y Resumen de Gastos Compartidos

| Campo              | Valor                                   |
|--------------------|-----------------------------------------|
| **ID**             | 001-gastos-compartidos                  |
| **Rama sugerida**  | `001-gastos-compartidos`                |
| **Fecha**          | 2026-11-05                              |
| **Estado**         | Borrador (pendiente de clarificación)   |
| **Metodología**    | Spec-Driven Development (SDD)           |

**Historia de usuario original**:

> "Yo como usuario quiero registrar mis gastos diarios, compartirlos con otras personas que también van a registrar sus gastos, clasificar por ciertas categorías y tener un resumen del total por periodo de tiempo, por persona y por categoría."

> **Nota SDD**: este documento describe **QUÉ** necesita el usuario y **POR QUÉ**. No define **CÓMO** se implementa (tecnologías, arquitectura, base de datos, frameworks). Esas decisiones pertenecen al `plan.md`. Las ambigüedades se marcan con `[NECESITA CLARIFICACIÓN]` y deben resolverse antes de pasar a la fase de planificación.

---

## 1. Contexto y objetivo

### 1.1 Problema
Las personas que comparten gastos (pareja, familia, compañeros de piso, amigos de viaje) no tienen una visión unificada de cuánto se gasta, en qué y quién lo gasta. Llevar el registro por separado dificulta conocer el total del grupo y analizar hábitos de consumo.

### 1.2 Objetivo
Permitir que varias personas registren sus gastos diarios en un espacio compartido, los clasifiquen por categorías y consulten resúmenes de totales agrupados por periodo de tiempo, por persona y por categoría.

### 1.3 Fuera de alcance (esta versión)
- Cálculo de deudas / liquidación de "quién le debe a quién".
- Registro de ingresos o presupuestos.
- Conversión automática entre monedas.
- Integración con bancos o lectura automática de tickets.
- Pagos o transferencias entre usuarios.

---

## 2. Actores

| Actor                   | Descripción                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| **Usuario**             | Persona registrada que anota sus propios gastos.                            |
| **Creador del grupo**   | Usuario que crea un grupo compartido e invita a otros.                      |
| **Miembro del grupo**   | Usuario que pertenece a un grupo y registra/consulta gastos dentro de él.   |

---

## 3. Escenarios de usuario y pruebas *(obligatorio)*

Las historias están priorizadas. Cada una es **independientemente testeable** y entrega valor por sí sola (permite construir un MVP incremental).

### Historia 1 — Registrar un gasto diario (Prioridad: P1) 🎯 MVP

Como usuario quiero anotar un gasto con su importe, fecha, descripción y categoría para llevar control de lo que gasto cada día.

**Por qué esta prioridad**: sin registro de gastos no existe ninguna otra funcionalidad; es el núcleo del valor.

**Prueba independiente**: un único usuario puede registrar, ver, editar y eliminar gastos sin necesidad de grupos ni resúmenes.

**Escenarios de aceptación**:

1. **Dado** un usuario autenticado, **cuando** introduce importe `25,50`, fecha de hoy, descripción "Supermercado" y categoría "Alimentación" y confirma, **entonces** el gasto queda guardado y aparece en su listado de gastos.
2. **Dado** un usuario que no indica fecha, **cuando** guarda el gasto, **entonces** se asigna la fecha actual por defecto.
3. **Dado** un usuario que introduce un importe `0` o negativo, **cuando** intenta guardar, **entonces** el sistema rechaza el registro e indica que el importe debe ser mayor que cero.
4. **Dado** un gasto propio existente, **cuando** el usuario modifica el importe y guarda, **entonces** el gasto se actualiza y los resúmenes reflejan el nuevo valor.
5. **Dado** un gasto propio existente, **cuando** el usuario lo elimina y confirma, **entonces** deja de aparecer en el listado y en los resúmenes.

---

### Historia 2 — Clasificar gastos por categorías (Prioridad: P1)

Como usuario quiero asignar una categoría a cada gasto para saber en qué tipo de cosas gasto mi dinero.

**Por qué esta prioridad**: la categoría es un requisito explícito de la historia y base de uno de los resúmenes.

**Prueba independiente**: registrar gastos con distintas categorías y filtrar el listado por categoría.

**Escenarios de aceptación**:

1. **Dado** un usuario que registra un gasto, **cuando** abre el selector de categoría, **entonces** ve un conjunto de categorías predefinidas (p. ej. Alimentación, Transporte, Vivienda, Ocio, Salud, Educación, Servicios, Otros).
2. **Dado** un grupo, **cuando** un miembro autorizado crea la categoría "Mascotas", **entonces** la categoría queda disponible para todos los miembros del grupo.
3. **Dado** un gasto sin categoría elegida, **cuando** se guarda, **entonces** se asigna la categoría "Otros". `[NECESITA CLARIFICACIÓN: ¿la categoría es obligatoria o se asigna "Otros" por defecto?]`
4. **Dado** una categoría con gastos asociados, **cuando** se intenta eliminar, **entonces** el sistema impide la eliminación o solicita reasignar los gastos a otra categoría.

---

### Historia 3 — Compartir gastos con otras personas (Prioridad: P2)

Como usuario quiero crear un grupo e invitar a otras personas para que todos registremos nuestros gastos en un espacio común.

**Por qué esta prioridad**: aporta el componente colaborativo; depende de que el registro (P1) exista.

**Prueba independiente**: dos usuarios en un mismo grupo registran gastos y cada uno ve los gastos del otro.

**Escenarios de aceptación**:

1. **Dado** un usuario autenticado, **cuando** crea un grupo llamado "Casa", **entonces** el grupo se crea y él queda como creador y miembro.
2. **Dado** un creador de grupo, **cuando** invita a otra persona, **entonces** esa persona recibe una invitación que puede aceptar o rechazar. `[NECESITA CLARIFICACIÓN: medio de invitación — correo, enlace, código]`
3. **Dado** un miembro que acepta la invitación, **cuando** entra al grupo, **entonces** ve todos los gastos registrados en el grupo, identificando quién registró cada uno.
4. **Dado** un miembro del grupo, **cuando** registra un gasto dentro del grupo, **entonces** el resto de miembros puede verlo.
5. **Dado** un miembro, **cuando** intenta editar o eliminar un gasto registrado por otra persona, **entonces** el sistema no lo permite.
6. **Dado** un miembro, **cuando** abandona el grupo, **entonces** deja de ver los gastos del grupo y sus gastos históricos permanecen en el grupo. `[NECESITA CLARIFICACIÓN: ¿se conservan o se eliminan los gastos de quien abandona?]`
7. **Dado** un usuario que no pertenece al grupo, **cuando** intenta acceder a sus gastos, **entonces** el acceso es denegado.

---

### Historia 4 — Resumen de totales por periodo, persona y categoría (Prioridad: P2)

Como usuario quiero ver un resumen del total gastado filtrando por periodo de tiempo, persona y categoría para analizar nuestros hábitos de gasto.

**Por qué esta prioridad**: es el valor analítico final de la historia; requiere datos registrados (P1) y, para "por persona", grupos (P2).

**Prueba independiente**: con un conjunto de gastos conocido, verificar que los totales mostrados coinciden con los esperados.

**Escenarios de aceptación**:

1. **Dado** un grupo con gastos en noviembre de 2026, **cuando** el usuario selecciona el periodo "Mes: noviembre 2026", **entonces** ve el total del grupo en ese mes.
2. **Dado** un periodo seleccionado, **cuando** el usuario agrupa por persona, **entonces** ve el total gastado por cada miembro y la suma coincide con el total del periodo.
3. **Dado** un periodo seleccionado, **cuando** el usuario agrupa por categoría, **entonces** ve el total por cada categoría y su porcentaje sobre el total del periodo.
4. **Dado** un periodo, **cuando** el usuario combina filtros (p. ej. persona = "Ana" y categoría = "Ocio"), **entonces** ve el total que cumple ambos criterios.
5. **Dado** que el usuario elige periodos predefinidos (día, semana, mes, año) o un rango personalizado de fechas, **cuando** aplica el filtro, **entonces** el resumen se recalcula para ese rango (fechas inclusivas).
6. **Dado** un periodo sin gastos, **cuando** se consulta el resumen, **entonces** se muestra total `0` y un mensaje indicando que no hay gastos.

---

### 3.1 Casos límite (edge cases)

- ¿Qué ocurre si un gasto se registra con fecha futura? → `[NECESITA CLARIFICACIÓN: permitir o rechazar]`
- ¿Qué ocurre con importes con muchos decimales? → se redondean a 2 decimales.
- ¿Qué ocurre si dos miembros editan datos del grupo al mismo tiempo (p. ej. categorías)?
- ¿Qué ocurre si el creador abandona el grupo? → `[NECESITA CLARIFICACIÓN: transferir rol o impedir salida]`
- ¿Qué ocurre si miembros del grupo usan monedas distintas? → en esta versión el grupo tiene una única moneda.
- ¿Cómo se definen los límites de "semana" (lunes–domingo vs. domingo–sábado) y la zona horaria del día?
- ¿Puede un usuario pertenecer a varios grupos y además tener gastos personales fuera de grupos?

---

## 4. Requisitos *(obligatorio)*

### 4.1 Requisitos funcionales

**Registro de gastos**
- **RF-001**: El sistema DEBE permitir a un usuario registrar un gasto con: importe, fecha, categoría y descripción opcional.
- **RF-002**: El sistema DEBE validar que el importe sea un número mayor que cero con un máximo de 2 decimales.
- **RF-003**: El sistema DEBE asignar la fecha actual cuando no se indique otra.
- **RF-004**: El sistema DEBE permitir al autor editar y eliminar sus propios gastos.
- **RF-005**: El sistema DEBE impedir que un usuario edite o elimine gastos registrados por otra persona.
- **RF-006**: El sistema DEBE registrar automáticamente el autor y la fecha/hora de creación de cada gasto.

**Categorías**
- **RF-007**: El sistema DEBE ofrecer un conjunto de categorías predefinidas.
- **RF-008**: El sistema DEBE permitir crear categorías personalizadas a nivel de grupo. `[NECESITA CLARIFICACIÓN: ¿cualquier miembro o solo el creador?]`
- **RF-009**: El sistema DEBE asociar cada gasto a exactamente una categoría.
- **RF-010**: El sistema NO DEBE permitir eliminar una categoría con gastos asociados sin reasignarlos previamente.

**Compartir / grupos**
- **RF-011**: El sistema DEBE permitir a un usuario crear un grupo compartido.
- **RF-012**: El sistema DEBE permitir invitar a otras personas a un grupo y que estas acepten o rechacen la invitación.
- **RF-013**: El sistema DEBE mostrar a todos los miembros los gastos del grupo, indicando el autor de cada uno.
- **RF-014**: El sistema DEBE restringir el acceso a los gastos de un grupo exclusivamente a sus miembros.
- **RF-015**: El sistema DEBE permitir a un miembro abandonar un grupo.
- **RF-016**: El sistema DEBE permitir que un usuario pertenezca a más de un grupo. `[NECESITA CLARIFICACIÓN: confirmar]`

**Resúmenes**
- **RF-017**: El sistema DEBE calcular el total de gastos para un periodo de tiempo seleccionado.
- **RF-018**: El sistema DEBE ofrecer periodos predefinidos (día, semana, mes, año) y rango personalizado de fechas.
- **RF-019**: El sistema DEBE mostrar el total desglosado por persona dentro del periodo.
- **RF-020**: El sistema DEBE mostrar el total desglosado por categoría dentro del periodo, incluyendo el porcentaje sobre el total.
- **RF-021**: El sistema DEBE permitir combinar filtros de periodo, persona y categoría.
- **RF-022**: La suma de los desgloses (por persona o por categoría) DEBE coincidir exactamente con el total del periodo.
- **RF-023**: Los resúmenes DEBEN reflejar inmediatamente las altas, modificaciones y eliminaciones de gastos.

### 4.2 Requisitos no funcionales

- **RNF-001 (Usabilidad)**: Registrar un gasto debe poder completarse en 3 pasos o menos.
- **RNF-002 (Rendimiento)**: Los resúmenes deben mostrarse en menos de 2 segundos para grupos con hasta 10.000 gastos.
- **RNF-003 (Seguridad / privacidad)**: Solo usuarios autenticados acceden al sistema; los datos de un grupo no son visibles para no miembros.
- **RNF-004 (Precisión)**: Los cálculos monetarios no deben presentar errores de redondeo (precisión de 2 decimales).
- **RNF-005 (Disponibilidad)**: `[NECESITA CLARIFICACIÓN: plataforma objetivo — web, móvil o ambas; uso sin conexión]`
- **RNF-006 (Idioma)**: La interfaz estará en español; formato de moneda y fecha según configuración regional del grupo.

### 4.3 Entidades clave

| Entidad        | Descripción                                    | Atributos principales                                                          |
|----------------|------------------------------------------------|--------------------------------------------------------------------------------|
| **Usuario**    | Persona que usa el sistema.                    | identificador, nombre, correo                                                  |
| **Grupo**      | Espacio compartido de gastos.                  | identificador, nombre, moneda, creador, fecha de creación                      |
| **Membresía**  | Relación usuario–grupo.                        | usuario, grupo, rol (creador / miembro), estado (invitado / activo / salido)   |
| **Categoría**  | Clasificación de un gasto.                     | identificador, nombre, tipo (predefinida / personalizada), grupo (si aplica)   |
| **Gasto**      | Desembolso registrado por un usuario.          | identificador, importe, fecha, descripción, categoría, autor, grupo, fecha de registro |
| **Invitación** | Solicitud para unirse a un grupo.              | grupo, invitado, invitante, estado (pendiente / aceptada / rechazada), fecha   |

**Relaciones**: un Usuario pertenece a 0..N Grupos (vía Membresía); un Grupo tiene 1..N Miembros y 0..N Gastos; cada Gasto tiene 1 autor y 1 Categoría.

### 4.4 Reglas de negocio

- **RN-01**: Importe > 0, máximo 2 decimales.
- **RN-02**: Solo el autor puede modificar o eliminar su gasto.
- **RN-03**: Cada grupo opera con una única moneda.
- **RN-04**: Los rangos de fechas de los resúmenes son inclusivos en ambos extremos.
- **RN-05**: Los totales por persona y por categoría siempre suman el total general del periodo.

---

## 5. Criterios de éxito *(obligatorio)*

Medibles y agnósticos de la tecnología:

- **CE-001**: El 90 % de los usuarios registra su primer gasto en menos de 30 segundos sin ayuda.
- **CE-002**: Un usuario puede invitar a otra persona y que esta vea los gastos del grupo en menos de 2 minutos.
- **CE-003**: El 100 % de los resúmenes coincide con la suma manual de los gastos del periodo (verificado con datos de prueba).
- **CE-004**: El 95 % de las consultas de resumen se muestran en menos de 2 segundos.
- **CE-005**: 0 accesos de no miembros a gastos de un grupo en pruebas de seguridad.

---

## 6. Supuestos

- Los usuarios disponen de un mecanismo de autenticación (registro/inicio de sesión), que se especificará aparte.
- Un gasto pertenece a un grupo o es personal (sin grupo); los gastos personales solo los ve su autor.
- Los resúmenes por persona solo tienen sentido dentro de un grupo.
- No se reparte el importe de un gasto entre varias personas en esta versión.

---

## 7. Clarificaciones pendientes

| #  | Pregunta                                                                   | Impacto            |
|----|----------------------------------------------------------------------------|--------------------|
| C1 | ¿La categoría es obligatoria o se asigna "Otros" por defecto?              | RF-009, Historia 2 |
| C2 | ¿Quién puede crear/editar categorías personalizadas del grupo?             | RF-008             |
| C3 | ¿Cómo se invita (correo, enlace, código)?                                  | RF-012             |
| C4 | ¿Qué pasa con los gastos de un miembro que abandona el grupo?              | RF-015             |
| C5 | ¿Qué pasa si el creador abandona el grupo?                                 | RF-015             |
| C6 | ¿Se permiten gastos con fecha futura?                                      | RF-001             |
| C7 | ¿Un usuario puede estar en varios grupos y tener gastos personales?        | RF-016, Supuestos  |
| C8 | ¿Plataforma objetivo (web / móvil) y necesidad de uso sin conexión?        | RNF-005            |
| C9 | ¿Inicio de semana (lunes o domingo) y zona horaria de referencia?          | RF-018             |

---

## 8. Checklist de calidad de la especificación

- [x] Se centra en el QUÉ y el POR QUÉ, sin detalles de implementación.
- [x] Historias priorizadas e independientemente testeables.
- [x] Escenarios de aceptación en formato Dado / Cuando / Entonces.
- [x] Requisitos funcionales numerados, verificables y no ambiguos.
- [x] Criterios de éxito medibles y agnósticos de la tecnología.
- [x] Entidades clave identificadas.
- [x] Casos límite identificados.
- [ ] Todas las marcas `[NECESITA CLARIFICACIÓN]` resueltas. ← **bloquea el paso a `plan.md`**

---

## 9. Siguientes pasos (flujo SDD)

1. **Clarificar** (`/clarify`): resolver la tabla de la sección 7 con el Product Owner.
2. **Planificar** (`plan.md`): decisiones técnicas, arquitectura, modelo de datos y contratos.
3. **Tareas** (`tasks.md`): desglose en tareas ordenadas por historia (P1 → P2).
4. **Implementar**: desarrollo guiado por los escenarios de aceptación como pruebas.
