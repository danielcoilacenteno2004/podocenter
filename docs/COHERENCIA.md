# Afirmaciones verificables de los documentos

Cada fila es algo que el informe o una práctica **afirma** sobre este
repositorio y que el jurado puede comprobar abriendo el código. Si cambias el
código, revisa esta tabla antes de cerrar el turno; si una afirmación deja de
ser cierta, corrige el documento en el mismo turno, no después.

El comando de la columna derecha devuelve el valor real.

| Documento | Afirma | Cómo comprobarlo |
|---|---|---|
| Informe 2.6.5 | 32 pruebas, 90 % de cobertura, **entre el 15 y el 28 de octubre** | Es una foto fechada del corte de la Práctica N.° 8: sigue siendo cierta. El valor de hoy es otro y no la contradice. |
| Informe 2.6.3 | 29 commits entre el 15 y el 28 de octubre, 15 y 14 por integrante | `git log --since=2026-10-15 --until=2026-10-29 --format=%an \| sort \| uniq -c` |
| Informe 2.2 | Python 3.12, **Django 5.2 LTS**, Django REST Framework | `grep -E '^(Django\|djangorestframework)' requirements.txt` y `grep FROM infra/Dockerfile` |
| Informe 2.2 | PostgreSQL 17 | `grep image infra/docker-compose.yml` |
| Informe 2.6.5 | Mínimo exigido de cobertura: 80 % | `grep cov-fail-under pyproject.toml` |
| Informe 2.1.2 | Aislamiento por políticas de seguridad por fila sobre siete tablas | **Desactualizado**: son ocho desde `atencion` (`apps/atenciones/migrations/0001_initial.py`). Hay que corregir el informe. `grep -rl "ROW LEVEL SECURITY" backend/apps/*/migrations/` |
| Informe 2.5 | Errores de negocio en formato RFC 9457 con campo `codigo` | `backend/apps/core/errores.py` |
| Informe 1.11 | RF01–RF18 | Los RF construidos son los de `docs/ESTADO.md`; el informe no afirma que estén todos implementados |
| Práctica 7, Tabla 1 | 29 pantallas diseñadas | `ls frontend/src/views/` da 7: el documento dice «Se construye», no «construida» |
| Práctica 7, Tabla 1 | P04 «Se construye (3 segmentos)» | `backend/apps/citas/panel.py` devuelve citas, ingresos y ocupación |
| Práctica 7, Tabla 1 | P05 «Se construye (con filtros)» | `grep -n "estado\|profesional\|servicio" backend/apps/citas/servicios.py` |
| Práctica 7, Tabla 42 | CC-18 verificado con **ocho** pruebas | `grep -c "^def test_" backend/apps/citas/tests/test_agenda_filtros.py` menos las del panel |
| Práctica 7, Tabla 42 | CC-19 verificado con **diez** pruebas | Las del panel dentro del mismo archivo |
| Práctica 7, Tabla 13 | Tipos de movimiento: Entrada, Ajuste, Merma; las salidas las genera el sistema | Módulo de inventario no construido: nada que contrastar todavía |
| Práctica 7, 4.5 | El recorrido del RNF02 usa cuatro interacciones | Medido con Playwright el 10/11/2026: **tres** (pulsar la cita, escribir la observación, confirmar), en escritorio. Son menos porque P11 no tiene todavía monto ni insumos: el paso «revisar servicio, monto e insumos» no existe. Pendiente: la medición con la podóloga |

## Afirmaciones que hoy no se pueden comprobar

Son promesas a futuro, no mentiras, pero conviene tenerlas a la vista porque
llegan con fecha:

- Primera entrega del **12/11/2026** con Atenciones incluidas, desplegada en
  producción y validada con la usuaria (Informe, Tabla 64).
- Prueba de usabilidad con ocho tareas y umbral SUS ≥ 68 (Práctica 7, 7.7).
- Calibración de la tasa hora/punto de caso de uso al cerrar la primera
  entrega (Informe, 2.7.6).
