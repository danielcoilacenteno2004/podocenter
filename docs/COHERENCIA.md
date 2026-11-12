# Afirmaciones verificables de los documentos

Cada fila es algo que el informe o una práctica **afirma** sobre este
repositorio y que el jurado puede comprobar abriendo el código. Si cambias el
código, revisa esta tabla antes de cerrar el turno; si una afirmación deja de
ser cierta, corrige el documento en el mismo turno, no después.

El comando de la columna derecha devuelve el valor real. La columna «Estado»
dice cómo está la afirmación a la fecha de la última revisión (10/11/2026,
tras añadir Atenciones):

- **Cierta**: el código la confirma.
- **Fechada**: describe un corte pasado y sigue siendo cierta para ese corte.
- **No coincide**: el código dice otra cosa; hay que corregir el documento o
  el código.
- **Parcial**: una parte está construida y otra no.
- **Pendiente**: todavía no hay código que contrastar.

## Informe (Capítulos 1 y 2)

| Apartado | Afirma | Estado | Cómo comprobarlo |
|---|---|---|---|
| 2.6.5 | 32 pruebas, 90 % de cobertura | **Fechada** | En el commit del corte (`2d4a9b8`, 28/10) hay 32 pruebas: `git grep -hE "^def test_\|^    def test_" 2d4a9b8 -- 'backend/**/test_*.py' \| wc -l`. Hoy: 198 pruebas y 94.3 %. |
| 2.6.3 | 29 commits entre el 15 y el 28 de octubre, 15 y 14 por integrante | **No coincide** | `git log --since=2026-10-15 --until=2026-10-29 --format=%an \| sort \| uniq -c` da **26 commits, 13 y 13**. La diferencia es anterior a Atenciones. |
| 2.6.3 | Nada entra a la rama de integración con el pipeline en rojo | **No coincide** | Desde el 28/10, `npm run lint` del trabajo `frontend` no podía pasar: no había `eslint.config.js` y ESLint 9 rechaza `--ext`. Se corrigió en `453ef9c`. Las ejecuciones en GitHub no se han revisado. |
| 2.2 | Python 3.12, Django 5.2 LTS, Django REST Framework | **Cierta** | `grep -E '^(Django\|djangorestframework)' requirements.txt` → 5.2.19 y 3.18.2; `grep FROM infra/Dockerfile` → `python:3.12-slim` |
| 2.2 | PostgreSQL 17 | **Cierta** | `grep image infra/docker-compose.yml .github/workflows/ci.yml` |
| 2.6.5, Tabla 58 | Mínimo exigido de cobertura: 80 % | **Cierta** | `grep cov-fail-under .github/workflows/ci.yml`. No está en `pyproject.toml`, como decía antes esta fila. |
| 2.6.6, Tabla 59 | Sprint 1: seguridad por fila sobre siete tablas | **Fechada** | Es la bitácora del Sprint 1 y sigue siendo cierta para ese sprint. Hoy son **ocho** (se suma `atencion`): `SELECT relname FROM pg_class WHERE relrowsecurity;` |
| 2.5 | Errores de negocio en formato RFC 9457 con campo `codigo` | **Cierta** | `backend/apps/core/errores.py` |
| 2.1.5, Tabla 38 | Los conflictos de negocio (cruce de cita, DNI duplicado, stock insuficiente) responden **409** | **No coincide** | Toda `ReglaDeNegocio` responde **422**: `grep -n "422" backend/apps/core/errores.py` |
| 2.1.5, Tabla 38 | `POST /atenciones` registra la atención como transacción | **Cierta** | `backend/apps/atenciones/views.py`; atomicidad probada en `test_si_falla_el_cierre_de_la_cita_no_queda_la_atencion` |
| 2.1.7, Tabla 39 | Restricción de exclusión sobre **profesional, sede y rango horario** | **No coincide** | La restricción es sobre profesional y rango, sin la sede: `grep -n -A4 "ExclusionConstraint(" backend/apps/citas/models.py` |
| 2.1.5, Tabla 38 | `GET /reportes/registro-diario` devuelve el consolidado de atenciones e ingresos del día | **Cierta** | `backend/apps/atenciones/views.py` (`RegistroDiario`); probado en `test_registro_diario.py`. Sin las ventas de inventario |
| 2.1.7, Tabla 39 | El registro diario se calcula a partir de las atenciones: no existe una tabla de ingresos que pueda descuadrar | **Cierta** | `registro_del_dia` en `backend/apps/atenciones/servicios.py` |
| 2.1.7, Tabla 39 | La atención descuenta stock, crea las salidas y marca la cita como atendida en una sola transacción, con bloqueo de fila sobre el stock | **Parcial** | La atención es una transacción que bloquea la **cita**. El inventario existe y bloquea la fila de stock en cada movimiento (`registrar_movimiento`), pero la atención todavía no descuenta: P11 no registra insumos. |
| 2.1.5, Tabla 38 | `POST /inventario/movimientos` y `GET /inventario/disponibilidad` | **Cierta** | `backend/apps/inventario/views.py`; probado en `test_inventario.py` |
| 2.3.3, diccionario de datos | `movimiento_inventario.tipo` con `CHECK (entrada, salida)`; `stock.cantidad` entero con `CHECK (>= 0)` y único por producto y sede | **No coincide** en el tipo | Los tipos son ENTRADA, AJUSTE y MERMA, como la Práctica 7 (Tabla 13). La salida no existe todavía. `stock` sí coincide: entero, `CHECK (>= 0)`, único por producto y sede (`backend/apps/inventario/models.py`). Hay que corregir el informe |
| 2.1.7, Tabla 39 | Las atenciones no se borran: se anulan con motivo, usuario y fecha | **Parcial** | No se pueden borrar (la API no tiene DELETE y el admin es de solo lectura), pero tampoco existe la anulación con motivo. |
| 1.11.5, Tabla 14, CU10 | Postcondición: atención vinculada a paciente, cita e inventario; stock y registro diario actualizados; cita atendida | **Parcial** | Se cumple el vínculo con paciente y cita, la cita queda atendida, se guarda el monto cobrado y el registro diario lo refleja. Faltan el inventario y el descuento de stock. |
| 2.4.3, Verificación del RNF02 | Cuatro interacciones: abrir la cita, registrar, confirmar servicio e insumos, ingresar el monto y confirmar | **Parcial** | **3 interacciones medidas con el alcance construido, aceptando el monto precargado; el recorrido diseñado prevé 4 al incorporar los insumos.** Medidas con Playwright (pulsar la cita, escribir la observación, confirmar) el 10 y el 11/11/2026. Si se edita el monto, contado paso a paso llega a 6, sin medir. Falta la medición con la podóloga que exige el criterio de aceptación. |
| 1.11 | RF01–RF18 | **Cierta** | Los RF construidos son los de `docs/ESTADO.md`; el informe no afirma que estén todos implementados |

## Práctica N.° 7

| Apartado | Afirma | Estado | Cómo comprobarlo |
|---|---|---|---|
| Tabla 1 | 29 pantallas diseñadas | **Cierta** | El documento dice «Se construye», no «construida». Construidas **25**: P01, P03, P04, P05, P08, P09, P10, P11, P12, P15, P16, P17, P18, P19, P20 y P21 en `frontend/src/views/` (los formularios P26, P27, P28 y P29 van como ventana dentro de su listado), y P06, P07, P13, P14 y P25 como ventanas en `frontend/src/components/`. P09 solo cubre el alta; P20 cubre el perfil y el cambio de contraseña, sin el segundo factor; P21 cubre 403 y 404. |
| Tabla 1 | P04 «Se construye (3 segmentos)» | **Cierta** | `backend/apps/citas/panel.py` devuelve citas, ingresos y ocupación |
| Tabla 1 | P05 «Se construye (con filtros)» | **Cierta** | `grep -n "estado\|profesional\|servicio" backend/apps/citas/servicios.py` |
| Observaciones, Figura 3 | «La cuadrícula por hora y profesional ya estaba prevista y se mantiene junto a la vista de lista»; los huecos libres se pulsan para crear una cita | **Cierta** | `frontend/src/components/AgendaCuadricula.vue`: filas según el horario de la sede (`horario_de_la_jornada`, probado en `test_agenda_filtros.py`), una columna por profesional, y un hueco abre P06 con hora y profesional. Se alterna con la lista; no se ven las dos a la vez |
| Tabla 1 | P11 «Se construye» | **Cierta** | `frontend/src/views/RegistrarAtencionView.vue`, ruta `/citas/:citaId/atencion` |
| Tabla 10 | P11: servicio editable, monto, tabla de insumos, tres notas clínicas (diagnóstico, tratamiento, observaciones), resumen antes de confirmar | **Parcial** | Construido: el encabezado de la cita y **una** observación clínica cifrada de hasta 2000 caracteres. Construido también: el monto cobrado, obligatorio, precargado del catálogo y editable. No construido: servicio editable, insumos, las otras dos notas y el paso de resumen. |
| 4.5, Tabla 11 | El recorrido del RNF02 usa cuatro interacciones | **Parcial** | 3 medidas con el alcance construido, aceptando el monto precargado; el recorrido diseñado prevé 4 al incorporar los insumos (ver la fila del informe). |
| Tabla 42 | CC-18 verificado con **ocho** pruebas | **Cierta** | En `backend/apps/citas/tests/test_agenda_filtros.py` hay 18 pruebas: 8 de filtros (líneas 59–141) y 10 del panel |
| Tabla 42 | CC-19 verificado con **diez** pruebas | **Cierta** | Las 10 del panel en el mismo archivo (líneas 152–252) |
| Tabla 31 | Un centro suspendido no puede iniciar sesión | **Cierta** | `test_un_centro_suspendido_no_puede_iniciar_sesion` en `backend/apps/core/tests/test_api_centros.py`; la regla está en `IniciarSesion` (`backend/apps/usuarios/sesion.py`) |
| Tabla 32 | El alta del centro crea su administrador inicial y le envía un enlace para definir la contraseña (P24) | **Parcial** | El administrador se crea en la misma transacción (`crear_centro` en `backend/apps/core/servicios.py`). Sin P24, recibe una contraseña temporal que solo se muestra en la respuesta del alta |
| Tabla 13 | Tipos de movimiento: Entrada, Ajuste, Merma; las salidas las genera el sistema | **Parcial** | Entrada, Ajuste (al alta o a la baja) y Merma se eligen en P13; ni la merma ni el ajuste dejan el stock negativo (`test_inventario.py`). Las salidas automáticas no existen: P11 no registra insumos |

La Práctica 7 registra la observación de la podóloga sobre los antecedentes
(«Antes de tocar un pie diabético necesito ver los antecedentes…») para la
**P10, ficha del paciente**, no para P11. Que P11 muestre los antecedentes en
su cabecera es una decisión del equipo, posterior a esa práctica. No hay que
presentarla como una petición registrada para P11.

## Afirmaciones que hoy no se pueden comprobar

Son promesas a futuro, no mentiras, pero conviene tenerlas a la vista porque
llegan con fecha:

- Primera entrega del **12/11/2026** con Atenciones incluidas, desplegada en
  producción y validada con la usuaria (Informe, Tabla 64). Atenciones está
  construido en parte; el despliegue y la validación, no.
- Prueba de usabilidad con ocho tareas y umbral SUS ≥ 68 (Práctica 7, 7.7).
- Calibración de la tasa hora/punto de caso de uso al cerrar la primera
  entrega (Informe, 2.7.6).
