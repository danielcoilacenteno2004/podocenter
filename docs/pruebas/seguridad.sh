#!/usr/bin/env bash
# Práctica 9 — análisis estático y de dependencias. Genera 05_seguridad.txt.
# Se corre desde la raíz del repositorio, con el entorno de Python 3.12 activo.
# Cada sección copia la salida de la herramienta tal cual, con su código de salida.
set -u
SALIDA=docs/pruebas/05_seguridad.txt
: > "$SALIDA"

seccion() {
  {
    echo "================================================================"
    echo "\$ $1"
    echo "Fecha: $(date -Iseconds)"
    echo "================================================================"
  } >> "$SALIDA"
}

seccion "python --version"
python --version >> "$SALIDA" 2>&1

seccion "cd frontend && npm audit"
(cd frontend && npm audit) >> "$SALIDA" 2>&1
echo "[código de salida: $?]" >> "$SALIDA"

# Solo lo que llega al navegador del usuario: sin las herramientas de desarrollo.
seccion "cd frontend && npm audit --omit=dev"
(cd frontend && npm audit --omit=dev) >> "$SALIDA" 2>&1
echo "[código de salida: $?]" >> "$SALIDA"

seccion "pip-audit -r requirements.txt"
pip-audit -r requirements.txt >> "$SALIDA" 2>&1
echo "[código de salida: $?]" >> "$SALIDA"

seccion "bandit -c pyproject.toml -r backend/apps"
bandit -c pyproject.toml -r backend/apps >> "$SALIDA" 2>&1
echo "[código de salida: $?]" >> "$SALIDA"

# Claves de un solo uso, como en el pipeline: producción no arranca sin ellas.
seccion "DJANGO_SETTINGS_MODULE=config.settings.prod python backend/manage.py check --deploy --fail-level WARNING"
DJANGO_SETTINGS_MODULE=config.settings.prod \
DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')" \
CLAVE_CIFRADO_CAMPOS="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
DJANGO_ALLOWED_HOSTS=podocenter.pe DJANGO_CSRF_ORIGINS=https://podocenter.pe \
  python backend/manage.py check --deploy --fail-level WARNING >> "$SALIDA" 2>&1
echo "[código de salida: $?]" >> "$SALIDA"
