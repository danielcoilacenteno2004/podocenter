#!/usr/bin/env bash
# Evidencia de la Práctica 9: E04 (aislamiento entre centros) y E05 (pruebas por
# requerimiento crítico), en la rama actual.
#
#   bash docs/pruebas/evidencia/scripts/requisitos.sh
#
# Los filtros se ajustaron a los nombres reales de las pruebas (pytest
# --collect-only): ninguna prueba se llama «rls», y «centro» trae también las de
# alta y suspensión de centros, que no son de aislamiento. -vv por la misma razón
# que en suite.sh (pyproject añade -q).
set -u
EV="$(cd "$(dirname "$0")" && pwd -W)"
RAIZ="$(pwd -W)"
ETQ="rama $(git rev-parse --abbrev-ref HEAD)"
E() { python "$EV/ejecutar.py" "$@"; }
T=backend/apps

E E04 --cwd "$RAIZ" --etiqueta "$ETQ" -- \
  "pytest -vv -k 'aislamiento or otro_centro or otro_inquilino or rol_sin_privilegios'"

E E05-RF02 --cwd "$RAIZ" --etiqueta "$ETQ · RF02 acceso por rol" -- \
  "pytest -vv $T/core/tests/test_api_permisos.py $T/usuarios/tests/test_sesion.py"
E E05-RF06 --cwd "$RAIZ" --etiqueta "$ETQ · RF06 citas sin cruce" -- \
  "pytest -vv $T/citas/tests/test_programar_cita.py $T/citas/tests/test_agenda_filtros.py $T/citas/tests/test_api_sin_escritura_directa.py"
E E05-RF10 --cwd "$RAIZ" --etiqueta "$ETQ · RF10 registro de la atención" -- \
  "pytest -vv $T/atenciones/tests/test_registrar_atencion.py $T/atenciones/tests/test_api_atenciones.py $T/atenciones/tests/test_insumos.py"
E E05-RF11 --cwd "$RAIZ" --etiqueta "$ETQ · RF11 movimientos de inventario" -- \
  "pytest -vv $T/inventario/tests/test_inventario.py $T/inventario/tests/test_productos_y_minimo.py -k 'not disponibilidad'"
E E05-RF12 --cwd "$RAIZ" --etiqueta "$ETQ · RF12 disponibilidad entre sedes" -- \
  "pytest -vv $T/inventario/tests/test_inventario.py -k disponibilidad"
E E05-RF16 --cwd "$RAIZ" --etiqueta "$ETQ · RF16 exportación" -- \
  "pytest -vv $T/atenciones/tests/test_exportar_registro_diario.py"
E E05-RF18 --cwd "$RAIZ" --etiqueta "$ETQ · RF18 contraseña y segundo factor" -- \
  "pytest -vv $T/usuarios/tests/test_cambiar_contrasena.py $T/usuarios/tests/test_totp.py $T/usuarios/tests/test_segundo_factor_alta.py $T/usuarios/tests/test_segundo_factor_ingreso.py $T/usuarios/tests/test_segundo_factor_reinicio.py"
