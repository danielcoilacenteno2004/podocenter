# Estado del proyecto

Corte: 10 de noviembre de 2026. Primera entrega comprometida: **12/11/2026**.

## 1. El riesgo principal

La Tabla 64 del informe compromete para el 12/11 lo siguiente, textualmente:

> «Usuarios y roles, Sedes, Pacientes con consentimiento, Citas sin
> recordatorios, **Atenciones y servicios**, desplegado **en producción** y
> **validado con la usuaria**.»

Contra eso, el estado real es:

| Compromiso | Estado |
|---|---|
| Usuarios y roles | Pantallas: ingreso (P01), elección de sede (P03), gestión de usuarios (P17/P27) y perfil con cambio de contraseña (P20). **Sin P02 (dos pasos) ni P23/P24 (recuperación de contraseña por correo): un usuario nuevo no puede ingresar, porque nadie conoce la contraseña que le asigna el alta, y P20 exige la actual.** La edición no cambia rol ni sedes (ver sección 5) |
| Sedes | Pantallas P18/P28. **El horario de atención se ve pero no se edita: la API no tiene ruta para escribirlo**, así que una sede nueva nace cerrada |
| Pacientes con consentimiento | Pantallas: búsqueda (P08), alta con consentimiento (P09), ficha con historial (P10) y detalle de atención (P25). **Sin edición: se quitaron PUT, PATCH y DELETE de `/pacientes/`** porque escribían sin auditoría; vuelve con un servicio que la audite |
| Citas sin recordatorios | Terminado: agenda con filtros (P05), nueva cita (P06), cancelación con reemplazo (P07) y panel del día (P04) |
| Servicios | Terminado: pantallas P15/P26 |
| **Atenciones** | **Parcial.** Registro de la atención con su monto cobrado (P11) y registro diario por sede y fecha (P16). **Sin insumos** (depende de Inventario) |
| Desplegado en producción | **No**: la infraestructura está escrita, nada corre en la nube |
| Validado con la usuaria | **No**: la prueba de usabilidad está diseñada, no aplicada |

### Qué tiene y qué no tiene Atenciones

Construido:

- Modelo `Atencion` con vínculo uno a uno a la cita. Copia paciente,
  profesional, servicio y sede al registrarse, para que la ficha no cambie si
  después alguien edita la cita.
- Observación clínica cifrada, como los antecedentes del paciente.
- Política de seguridad por fila sobre la tabla `atencion`. Son **ocho**
  tablas con RLS.
- Reglas en el servicio, cada una con su código RFC 9457:
  - `cita-no-atendible`: la cita no está programada.
  - `atencion-duplicada`: la cita ya tiene atención.
  - `cita-fuera-del-centro`: la cita no es del centro.
  - `sin-sede-activa` y `cita-de-otra-sede`: falta la sede activa o la cita es
    de otra.
  - `usuario-sin-sede`: el usuario no trabaja en esa sede.
- La cita pasa a atendida en la misma transacción, y queda constancia en la
  bitácora de auditoría.
- API de solo creación, listado y ficha; la lectura de la ficha queda
  auditada.
- La agenda marca qué citas ya tienen atención (`tiene_atencion`).
- Pantalla P11 con los antecedentes del paciente en la cabecera.
- Monto cobrado obligatorio, precargado con el precio del servicio y
  editable; la base impide montos negativos.
- Registro diario (P16): atenciones e ingresos de la sede activa en una
  fecha, calculado desde las atenciones (`GET /reportes/registro-diario/`).
- RNF02 (cinco interacciones o menos): **3 interacciones medidas con el alcance construido, aceptando el monto precargado; el recorrido diseñado prevé 4 al incorporar los insumos.** Medidas con Playwright el
  10 y el 11/11/2026, en escritorio y a 390 px.

No construido, y lo pide el CU10 o la P11 de la Práctica N.° 7:

- **Insumos consumidos** y descuento de stock (depende de Inventario).
- **Servicio editable** («si se brindó otro»).
- **Notas separadas** en diagnóstico, tratamiento y observaciones. Hoy hay una
  sola observación.
- **Anulación de una atención** con motivo.

La diferencia entre las 3 medidas y las 4 diseñadas está en los insumos, que
aún no existen. **Si la podóloga edita el monto**, el recorrido suma pulsar
el campo, escribir y volver a la observación: contado paso a paso, llega a 6
con observación escrita, por encima del límite. Ese caso **no se ha medido**
(el recorrido automático rellena el campo sin pulsarlo). La medición válida
para el RNF02 es la que se haga con la podóloga.

## 2. Lo que está sólido

- **173 pruebas** en verde, **94.5 %** de cobertura de sentencias, sobre
  PostgreSQL real y no sobre una base en memoria. La cifra varía unas
  décimas entre ejecuciones.
- **Cero vulnerabilidades** conocidas en las dependencias tras subir a Django
  5.2 LTS, DRF 3.18.2, django-filter 25.2 y cryptography 50.0.2.
- `ruff`, `bandit` 1.9.4 y `npm run lint` limpios. `bandit` se comprobó
  además contra un archivo deliberadamente inseguro, en Python 3.12 y 3.14,
  para asegurar que **sí falla** cuando debe.
- **Aislamiento multi-inquilino probado con nueve pruebas**: tres en `core`,
  tres en la API de usuarios y tres en atenciones. Comprueban que un centro
  no ve, no abre, no modifica y no registra atenciones sobre datos de otro. Es
  lo que sostiene el modelo de arriendo ante el jurado.
- **91 commits** con «un commit, un cambio», contando el que actualiza este
  documento: 47 de Sergio Daniel Coila Centeno y 44 de Andre Nicolas Huaroc
  Condori. La identidad de git está fijada en la configuración del
  repositorio para que no vuelva a entrar un autor con otro nombre.
- Entorno de demostración reproducible con un comando y probado con nueve
  pruebas, incluida una que verifica que las credenciales publicadas funcionan.
- Frontend: **22 pantallas de las 29 diseñadas en la Práctica N.° 7 (P01, P03, P04, P05, P06, P07, P08, P09, P10, P11, P15, P16, P17, P18, P19, P20, P21, P25, P26, P27, P28, P29)**. El frontend no tiene pruebas automáticas; cada pantalla se comprobó con un recorrido en Playwright.

### Pipeline: corregido, pendiente de ver en verde

Tres defectos del pipeline se corrigieron el 10 y el 11/11. Las correcciones
aún no se han ejecutado en GitHub:

- Las pruebas corrían con el superusuario de la imagen de PostgreSQL, que se
  salta siempre las políticas de seguridad por fila. Ahora usan un rol sin
  privilegios (`a4777da`).
- `npm run lint` no podía pasar desde el 28/10: no había configuración de
  ESLint 9 (`453ef9c`).
- `bandit` 1.8.0 aprobaba en falso con Python 3.14: se saltaba todos los
  archivos y salía con código 0. Se subió a 1.9.4 (`5398bee`). El pipeline ya
  usaba Python 3.12, la versión que exige el proyecto (ver `CLAUDE.md`).

## 3. Brechas de diseño levantadas y no resueltas

Registradas en la Práctica N.° 7 y pendientes de decisión de alcance:

1. **Atención a domicilio.** El diseño no la distingue de la atención en
   consultorio, y el centro hace entre dos y tres visitas al día. Alcanza a
   P05, P06 y al modelo de datos.
2. **Lote y fecha de vencimiento de insumos.** No están modelados. Nada impide
   consumir una crema vencida en una atención. En insumos clínicos no es un
   detalle administrativo.
3. **Traslado de stock entre sedes.** El RF12 permite consultar la
   disponibilidad en la otra sede «sin fusionar los inventarios», así que mover
   stock está fuera de alcance. En la práctica alguien carga la caja, y hoy eso
   se registraría como una merma más una entrada: infla ambas y rompe la
   trazabilidad de la unidad.

## 4. Decisiones de alcance vigentes

| Código | Qué recortó |
|---|---|
| CC-12 | Tercer indicador del panel (stock), alerta automática del RF13, pantalla de reprogramación del RF08 |
| CC-18 | *Añade* la barra de filtros de la agenda |
| CC-19 | *Añade* el panel segmentado por decisión; no revierte CC-12 |
| RF07 | Recordatorios por mensajería, pendientes de aprobación del proveedor |

## 5. Lo que la API permite y no debería (encontrado al construir las pantallas de administración, 11/11/2026)

Las pantallas rodean estos huecos sin inventar reglas; cerrarlos es trabajo
del servidor:

- **`PATCH /usuarios/{id}/` no pasa por el servicio**: cambia el rol o
  `esta_activo` de la única administradora (200) sin la regla del último
  administrador, e ignora `sedes_ids`. Por eso P27 solo edita nombres,
  apellidos y correo.
- **Nadie puede dar contraseña a un usuario nuevo**: la API le pone una
  aleatoria y P24 no existe.
- **No hay ruta para escribir el horario de una sede.**
- **Nombre repetido de sede o servicio → 500**, no un error de negocio.
- **`DELETE` de sede o servicio con citas → 500.** Las pantallas no lo usan.
- Reglas del diseño que el servidor no aplica: una sede o un servicio
  inactivo siguen aceptando citas; la duración admite desde 5 minutos (la
  Tabla 24 dice entre 10 y 240).

## 6. Lo que hay que decidir

- **La edición de pacientes.** Se quitaron PUT, PATCH y DELETE de
  `/pacientes/`. Para volver a editar falta decidir qué campos se pueden
  cambiar (¿el documento?) y pasarlos por un servicio auditado; la baja ya
  existe como `esta_activo`.

- **Qué entra de Atenciones el 12/11.** El monto cobrado y el registro diario
  ya existen; faltan los insumos, que dependen de Inventario. Hay que dejar
  por escrito que la primera entrega registra la atención sin insumos: lo
  que no es defendible es presentar el CU10 como completo.
- **El panel del día y el registro diario pueden no cuadrar.** El «ingreso
  confirmado» del panel (P04) suma el precio de catálogo de las citas
  atendidas; el registro diario (P16) suma lo cobrado de verdad. Con un
  descuento, las dos cifras difieren. Habría que decidir si el panel pasa a
  usar el monto cobrado.
- **El despliegue en producción** necesita una cuenta de nube real con tarjeta;
  no se resuelve escribiendo código.
- **La prueba de usabilidad** necesita una hora de la dueña y una de la
  podóloga. Es el requisito más barato de los tres y el que lleva más tiempo
  parado. Además, es la que valida de verdad el RNF02.
