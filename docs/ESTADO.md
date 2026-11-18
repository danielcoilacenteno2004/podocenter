# Estado del proyecto

Corte: 12 de noviembre de 2026. Primera entrega comprometida: **12/11/2026**.

## 1. El riesgo principal

La Tabla 64 del informe compromete para el 12/11 lo siguiente, textualmente:

> «Usuarios y roles, Sedes, Pacientes con consentimiento, Citas sin
> recordatorios, **Atenciones y servicios**, desplegado **en producción** y
> **validado con la usuaria**.»

Contra eso, el estado real es:

| Compromiso | Estado |
|---|---|
| Usuarios y roles | Pantallas: ingreso (P01), elección de sede (P03), gestión de usuarios (P17/P27, con rol y sedes editables) y perfil con cambio de contraseña (P20). El alta y «Restablecer contraseña» dan una **contraseña temporal** que se muestra una vez, y el servidor no deja hacer nada más hasta cambiarla. **Sin P02 (dos pasos) ni P23/P24 (correo): la contraseña olvidada la restablece la administradora** |
| Sedes | Pantallas P18/P28 con el **horario de atención editable** por día (CC-15). Una sede o un servicio desactivados ya no admiten citas nuevas |
| Pacientes con consentimiento | Pantallas: búsqueda (P08), alta con consentimiento (P09), ficha con historial (P10) y detalle de atención (P25). **Sin edición: se quitaron PUT, PATCH y DELETE de `/pacientes/`** porque escribían sin auditoría; vuelve con un servicio que la audite |
| Citas sin recordatorios | Terminado: agenda (P05) en cuadrícula por hora y profesional y en lista con filtros, nueva cita (P06, también desde un hueco de la cuadrícula), cancelación con reemplazo (P07) y panel del día (P04). Aunque el compromiso era «sin recordatorios», ya existen (ver RF07 en la sección 4) |
| Servicios | Terminado: pantallas P15/P26, duración de 10 a 240 minutos (Tabla 24) e **insumos habituales** de cada servicio (CC-14) |
| Inventario (adelantado de la segunda entrega) | Stock por sede (P12) con el **mínimo editable en línea** por la administradora (CU05), movimientos de Entrada, Ajuste o Merma (P13), disponibilidad entre sedes (P14) y **salida automática** por los insumos de cada atención. Alta, edición y baja de productos desde P12: **no figura entre las 29 pantallas de la Práctica 7**, se añadió porque sin ella un centro nuevo no podía llenar su inventario |
| **Atenciones** | **Casi completo.** Registro de la atención con monto cobrado, **insumos consumidos** (precargados de los habituales del servicio) y su salida de stock en la misma transacción (P11); registro diario (P16). Falta lo de la sección «No construido» |
| Desplegado en producción | **No**: la infraestructura está lista y revisada (`docs/DESPLIEGUE.md`), pero nada corre en la nube y las imágenes no se han construido (la máquina de desarrollo no tiene Docker) |
| Validado con la usuaria | **No**: la prueba de usabilidad está diseñada, no aplicada |

### Qué tiene y qué no tiene Atenciones

Construido:

- Modelo `Atencion` con vínculo uno a uno a la cita. Copia paciente,
  profesional, servicio y sede al registrarse, para que la ficha no cambie si
  después alguien edita la cita.
- Observación clínica cifrada, como los antecedentes del paciente.
- Política de seguridad por fila sobre la tabla `atencion`. Hoy son **trece**
  tablas con RLS, todas con `FORCE`:
  `SELECT relname FROM pg_class WHERE relrowsecurity;`
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
- **Insumos consumidos**: P11 precarga los habituales del servicio (CC-14) con
  el stock de la sede. Cada uno genera una salida ligada a la atención, en la
  misma transacción y con la fila de stock bloqueada. Si falta stock de uno
  solo, no se registra nada y la cita sigue programada. La base exige que
  toda salida tenga su atención.
- RNF02 (cinco interacciones o menos), con los insumos habituales
  precargados y aceptando el monto y los insumos sugeridos: **4 interacciones
  desde la cuadrícula**, la vista con que abre la agenda (pulsar la cita,
  «Registrar atención», escribir la observación y confirmar), medidas con
  Playwright el 18/11/2026 en Chromium, WebKit y a 390 px
  (`docs/pruebas/07_recorridos.txt`). **Desde la lista son 3**, porque el botón
  está en la fila (medidas el 12/11/2026).
- **En móvil (390 px), el inventario no se puede usar**: los botones
  «Movimiento» y «Ver disponibilidad» de P12 quedan fuera de la pantalla y
  tapados por otra celda; `/inventario`, `/pacientes` y `/registro-diario`
  desbordan en horizontal. En escritorio los recorridos pasan completos. Ver
  `docs/pruebas/defectos.md` (DEF-P9-07).

No construido, y lo pide el CU10 o la P11 de la Práctica N.° 7:

- **Servicio editable** («si se brindó otro»).
- **Notas separadas** en diagnóstico, tratamiento y observaciones. Hoy hay una
  sola observación.
- **Paso de resumen** antes de confirmar.
- **Anulación de una atención** con motivo.

El recorrido diseñado tiene 4 interacciones porque incluye el paso de
resumen, que no está construido. **Cada cambio sobre lo precargado suma
interacciones**: editar el monto o la cantidad de un insumo, o agregar un
insumo que no es habitual (buscarlo y elegirlo, dos más): con uno agregado y
la observación escrita, el recorrido queda en 5 desde la lista, en el límite,
y en 6 desde la cuadrícula, por encima (cuenta hecha sobre lo medido, no
medida). La medición
válida para el RNF02 es la que se haga con la podóloga.

## 2. Lo que está sólido

- **308 pruebas** en verde, **95.7 %** de cobertura de sentencias y
  **87.2 %** de ramas, sobre PostgreSQL real y no sobre una base en memoria,
  con Python 3.12. La cifra varía unas décimas entre ejecuciones. Corrida del
  18/11/2026 para la Práctica N.° 9: `docs/pruebas/02_cobertura.txt` y, por
  módulo, `docs/pruebas/02_cobertura_por_modulo.txt`.
- **Panel del día (P04) con cifras que cuadran.** Lo cobrado sale del mismo
  cálculo que el registro diario (P16), así que las dos pantallas dan la
  misma cifra; la ocupación se mide contra la capacidad real de la sede
  (cada profesional asignada por el horario de la sede, suponiendo que
  cubre la jornada completa) y se desglosa por profesional; las citas cuya
  hora ya pasó sin registrar la atención se listan aparte, con su enlace
  para registrarla, y las que vienen se muestran en orden, con la que está
  en curso y la próxima marcadas. Cada segmento se compara con el promedio
  de los cuatro mismos días de la semana anteriores, la ocupación anticipa
  los siete días siguientes, y una cancelación con cita de reemplazo ya no
  cuenta como ingreso no concretado (`Cita.reemplaza`). La confirmación y la
  ocupación se apartan de la Tabla 7 de la Práctica N.° 7, que hay que
  actualizar (ver `docs/COHERENCIA.md`).
  Antes, con dos profesionales, la ocupación salía el doble de la real.
- **Cero vulnerabilidades** conocidas en las dependencias de Python tras
  subir a Django 5.2 LTS, DRF 3.18.2, django-filter 25.2 y cryptography
  50.0.2 (`pip-audit`, 18/11/2026). **El frontend no está igual**: `npm audit`
  da 11, y 3 altas llegan a producción (`axios` 1.7.9 y `vue` 3.5.13); ver
  `docs/pruebas/defectos.md`.
- `ruff`, `bandit` 1.9.4 y `npm run lint` limpios. `bandit` se comprobó
  además contra un archivo deliberadamente inseguro, en Python 3.12 y 3.14,
  para asegurar que **sí falla** cuando debe.
- **Aislamiento multi-inquilino probado con 21 pruebas**, contando las que
  usan el centro ajeno de prueba (`otro_centro`): 5 en `core`, 5 en
  usuarios, 4 en atenciones, 4 en inventario, 2 en catálogo y 1 en sedes.
  Comprueban que un centro no ve, no abre y no modifica datos de otro, ni
  usa sus sedes o productos. Es lo que sostiene el modelo de arriendo ante
  el jurado.
- **147 commits** con «un commit, un cambio», contando el que actualiza este
  documento: 70 de Sergio Daniel Coila Centeno y 77 de Andre Nicolas Huaroc
  Condori. Andre firma ahora como «Warlocck»; `.mailmap` une esa identidad
  con la anterior, así que el recuento sale de `git shortlog -sn` (o de
  `--format=%aN`), no de `--format=%an`, que no aplica `.mailmap`.
- Entorno de demostración reproducible con un comando y probado con nueve
  pruebas, incluida una que verifica que las credenciales publicadas funcionan.
- Frontend: **25 pantallas de las 29 diseñadas en la Práctica N.° 7 (P01, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, P20, P21, P25, P26, P27, P28, P29)**, más la ventana de producto sobre P12, que no está en el diseño. El frontend no tiene pruebas automáticas; cada pantalla se comprobó con un recorrido en Playwright. La interfaz usa la paleta oficial de Artemisa (#3C5154, #57696D, #A1B5AC y blanco) declarada una sola vez como variables, y piezas comunes: tarjeta (`TarjetaSeccion`), iconos (`IconoTrazo`), marca (`MarcaArtemisa`) y barra superior con las secciones tomadas de las rutas. P01 y P04 se rediseñaron sobre esa base.
- **Configuración de producción endurecida**: no arranca sin `DJANGO_SECRET_KEY`
  y `CLAVE_CIFRADO_CAMPOS` propias (ni vacías ni con el texto de la
  plantilla), reconoce el HTTPS que termina Nginx y `check --deploy` pasa sin
  avisos. `cargar_demo` se niega a correr con ella.

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
- El paso `check --deploy` habría fallado: la configuración de producción
  heredaba un `SECRET_KEY` de respaldo (aviso W009). Ahora el pipeline
  genera claves de un solo uso (`6471501`).

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
| RF07 | **Construido, sin envío real.** El temporizador (CU15) manda cada quince minutos el recordatorio por WhatsApp de las citas de las próximas 24 horas, con tres intentos y anulado si se cancela la cita; **mientras Meta no apruebe la cuenta de WhatsApp Business del centro, el envío es simulado**. La agenda ofrece además «WhatsApp», que abre el mensaje escrito para enviarlo a mano. Falta la llamada de retorno con el estado de entrega (CU16), y el estado se ve en P05, no en P10 como dice la Práctica 7 |

## 5. Huecos de la API encontrados el 11/11 y cerrados el 12/11

Todos tienen ahora su regla en el servidor y sus pruebas:

- `PATCH /usuarios/{id}/` pasa por el servicio: aplica la regla del último
  administrador, reasigna las sedes y rechaza una sede de otro centro (el
  alta también la aceptaba). La baja va solo por su ruta.
- Un usuario nuevo recibe una contraseña temporal y debe cambiarla al entrar.
- El horario de la sede se escribe con la sede.
- Nombre repetido de sede o servicio: `sede-duplicada` y `servicio-duplicado`
  en lugar de un 500.
- Sedes y servicios ya no tienen `DELETE` (respondía 500 si tenían citas). La
  baja es desactivarlos, y desactivados no admiten citas nuevas.
- Duración de un servicio entre 10 y 240 minutos, también con un `CHECK` en
  la base.

Queda abierto: la edición de pacientes (ver la sección 6).

## 6. Lo que hay que decidir

- **La edición de pacientes.** Se quitaron PUT, PATCH y DELETE de
  `/pacientes/`. Para volver a editar falta decidir qué campos se pueden
  cambiar (¿el documento?) y pasarlos por un servicio auditado; la baja ya
  existe como `esta_activo`.

- **Qué entra de Atenciones el 12/11.** Monto, insumos con su salida de
  stock y registro diario sí. Servicio editable, las tres notas, el paso de
  resumen y la anulación no: el CU10 no se puede presentar como completo.
- **El despliegue en producción** necesita una cuenta de nube real con tarjeta
  y un dominio; no se resuelve escribiendo código. Los pasos están en
  `docs/DESPLIEGUE.md`, que todavía no se ha seguido en un servidor.
- **La prueba de usabilidad** necesita una hora de la dueña y una de la
  podóloga. Es el requisito más barato de los tres y el que lleva más tiempo
  parado. Además, es la que valida de verdad el RNF02.
