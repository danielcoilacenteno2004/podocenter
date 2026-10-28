# Bitácora — Sprint 2

**Periodo:** 22/10/2026 – 28/10/2026
**Objetivo del sprint:** Pacientes con consentimiento, catálogo de servicios y
el núcleo de la agenda de citas.
**Capacidad planificada:** 2 integrantes × 28 h/semana = 8 días de línea base.

## Qué se implementó

| Actividad de la línea base | Avance | Evidencia |
|---|---|---|
| Pacientes (5 días) | 100 % | `apps/pacientes`, 5 pruebas |
| Citas + notificaciones (5 días) | 60 % | `apps/citas`, 7 pruebas; sin notificaciones |

- Alta de paciente y consentimiento informado versionado en una sola
  transacción: no puede existir una ficha sin constancia de la base legal del
  tratamiento (RNF06, riesgo R12).
- Campo `TextoCifrado` con Fernet para los antecedentes clínicos. La prueba
  `test_los_antecedentes_se_guardan_cifrados_en_la_columna` lee la columna con
  SQL directo y comprueba que el texto no es legible.
- Agenda con la restricción `EXCLUDE` sobre el rango `[inicio, fin)` por
  profesional, que es lo que impide el solape aunque dos peticiones lleguen a
  la vez.
- Cancelación con motivo obligatorio y plantilla de cita de reemplazo (CC-16).
- Todos los errores de negocio salen en formato RFC 9457 con un código
  estable, que es lo que las pantallas de la Práctica N.° 7 esperan.

## Qué quedó pendiente

- **Notificaciones por WhatsApp (RF07).** Bloqueadas por el riesgo R9: la
  aprobación de Meta para la cuenta de WhatsApp Business no ha llegado. El
  trámite se inició el 20/10.
- Módulos de Atenciones, Inventario y Registro diario: no se tocaron.

## Desviaciones respecto al plan

1. **Defecto encontrado por una prueba, no por el navegador.** La prueba de la
   agenda devolvía cero citas recién creadas. La causa: el contexto de
   inquilino se fijaba en el middleware, que corre *antes* de que DRF
   autentique al usuario, así que `request.centro_id` quedaba en `None` en
   toda la API. Se resolvió extrayendo la resolución del contexto a
   `apps/core/contexto_http.py` y volviéndola a aplicar en `initial()` desde
   el mixin `ContextoDeCentro`. Medio día.
2. **Citas quedó al 60 %.** Las notificaciones son un tercio de la actividad y
   dependen de un trámite externo. Se decidió no simularlas: la condición de
   corte de la Práctica N.° 7 se activa y se propone la entrega por etapas.

## Decisiones tomadas

- Se descartó la regla `N818` de ruff (sufijo `Error` en las excepciones)
  porque obliga a mezclar inglés y español en un mismo identificador. Queda
  registrada en `pyproject.toml` con su justificación, no silenciada en el
  código.
- La validación de stock y solapamiento vive en tres niveles —interfaz,
  servidor y base de datos— tal como anticipó la reflexión 1 de la Práctica
  N.° 7.
