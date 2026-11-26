#!/usr/bin/env bash
# Evidencia de la Práctica 9: E06 a E11, en la rama actual.
#
#   bash docs/pruebas/evidencia/scripts/calidad.sh
#
# Se corre desde la raíz del repositorio, con Python 3.12 activo. E09 usa la
# configuración de producción con valores FICTICIOS, nunca los reales: la
# clave y la clave Fernet de abajo no sirven para nada fuera de esta prueba y
# ejecutar.py las enmascara igualmente en la salida.
set -u
EV="$(cd "$(dirname "$0")" && pwd -W)"
RAIZ="$(pwd -W)"
E() { python "$EV/ejecutar.py" "$@"; }
ETQ="rama $(git rev-parse --abbrev-ref HEAD)"

E E06 --cwd "$RAIZ" --etiqueta "$ETQ" -- \
  "ruff --version" "ruff check ." "bandit --version" "bandit -r backend -ll"

E E07 --cwd "$RAIZ" --etiqueta "$ETQ" -- \
  "pip-audit --version" "pip-audit -r requirements.txt" "pip-audit"

E E08 --cwd "$RAIZ/frontend" --etiqueta "$ETQ" -- \
  "npm --version" "npm audit"

E E09 --cwd "$RAIZ/backend" --etiqueta "$ETQ · valores ficticios" -- \
  "DJANGO_SETTINGS_MODULE=config.settings.prod DJANGO_ALLOWED_HOSTS=podocenter.example DJANGO_CSRF_ORIGINS=https://podocenter.example DJANGO_SECRET_KEY=clave-ficticia-solo-para-check-deploy-0123456789abcdefghijklmnopqrstuvwxyz CLAVE_CIFRADO_CAMPOS=Zm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyMDA= python manage.py check --deploy"

E E10 --cwd "$RAIZ/backend" --etiqueta "$ETQ" -- \
  "python manage.py makemigrations --check --dry-run"

E E11 --cwd "$RAIZ/frontend" --etiqueta "$ETQ" -- \
  "npm run lint" "npm run build"
