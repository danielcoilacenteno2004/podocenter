#!/usr/bin/env bash
# Evidencia de la corrección de DEF-25, DEF-26 y DEF-27 (26/11), con sufijo -correccion
# para no sobrescribir la ejecución anterior a la corrección.
#
#   bash docs/pruebas/evidencia/scripts/correccion.sh DIRECTORIO_TEMPORAL
#
# Requiere Django en 127.0.0.1:8000 y scripts/servidor_csp.py en 127.0.0.1:8088, que sirve
# la SPA compilada con la CSP de infra/nginx/nginx.conf (no hay Nginx en este equipo).
set -u
TMP=${1:?temporal}
EV="$(cd "$(dirname "$0")" && pwd -W)"
RAIZ="$(pwd -W)"
ETQ="rama $(git rev-parse --abbrev-ref HEAD) + corrección de DEF-25 a DEF-27, sin commit"
E() { python "$EV/ejecutar.py" "$@"; }

E E05-DEF25-correccion --cwd "$RAIZ" --etiqueta "$ETQ · bloqueo tras intentos fallidos" -- \
  "pytest -vv backend/apps/usuarios/tests/test_bloqueo_de_ingreso.py backend/apps/core/tests/test_configuracion_produccion.py"
E E06-correccion --cwd "$RAIZ" --etiqueta "$ETQ" -- \
  "ruff check ." "bandit --version" "bandit -r backend -ll"
E E08-correccion --cwd "$RAIZ/frontend" --etiqueta "$ETQ" -- "npm --version" "npm audit"
E E10-correccion --cwd "$RAIZ/backend" --etiqueta "$ETQ" -- \
  "python manage.py makemigrations --check --dry-run"
E E11-correccion --cwd "$RAIZ/frontend" --etiqueta "$ETQ" -- "npm run lint" "npm run build"
E E14-correccion --cwd "$RAIZ" --etiqueta "$ETQ · SPA compilada con la CSP de Nginx" -- \
  "python backend/manage.py cargar_demo" \
  "ZAP_OBJETIVO=http://localhost:8088 python docs/pruebas/evidencia/scripts/zap_evidencia.py '$TMP/zap2'"
bash "$EV/suite.sh" "$RAIZ" -correccion "$TMP" "$ETQ"
