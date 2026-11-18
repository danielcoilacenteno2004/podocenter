#!/usr/bin/env bash
# Práctica 9 — recorridos de sistema en Chromium, WebKit y móvil (390 px). Genera 07_recorridos.txt.
# Cada proyecto empieza con cargar_demo, para que haya una cita en curso que atender.
# Uso: bash docs/pruebas/recorridos.sh RUTA_A_NODE_MODULES_CON_PLAYWRIGHT
set -u
export NODE_PATH=${1:?node_modules donde está instalado playwright}
export DJANGO_SETTINGS_MODULE=config.settings.dev
SALIDA=docs/pruebas/07_recorridos.txt
: > "$SALIDA"
for proyecto in chromium webkit movil; do
  {
    echo "================================================================"
    echo "\$ python backend/manage.py cargar_demo && node docs/pruebas/recorridos.cjs $proyecto"
    echo "Fecha: $(date -Iseconds)"
    echo "================================================================"
  } >> "$SALIDA"
  python backend/manage.py cargar_demo > /dev/null 2>&1
  node docs/pruebas/recorridos.cjs "$proyecto" >> "$SALIDA" 2>&1
  echo "[código de salida: $?]" >> "$SALIDA"
done
