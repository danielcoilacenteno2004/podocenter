#!/usr/bin/env bash
# Evidencia de la Práctica 9: E12, recorridos de Playwright en Chromium, WebKit y móvil.
#
#   bash docs/pruebas/evidencia/scripts/navegador.sh RUTA_A_NODE_MODULES_CON_PLAYWRIGHT
#
# Requiere Django en 127.0.0.1:8000 (config.settings.dev, base local de prueba)
# y Vite en localhost:5174 (el 5173 estaba ocupado por otro proceso el 26/11). Igual que docs/pruebas/recorridos.sh: antes de cada
# proyecto se corre cargar_demo, porque el registro de la atención consume la
# cita en curso de la demostración.
set -u
NM=${1:?node_modules donde está instalado playwright}
EV="$(cd "$(dirname "$0")" && pwd -W)"
RAIZ="$(pwd -W)"
ETQ="rama $(git rev-parse --abbrev-ref HEAD)"
for proyecto in chromium webkit movil; do
  python "$EV/ejecutar.py" "E12-$proyecto" --cwd "$RAIZ" --etiqueta "$ETQ" -- \
    "python backend/manage.py cargar_demo" \
    "BASE=http://localhost:5174 NODE_PATH='$NM' node docs/pruebas/evidencia/scripts/recorridos.cjs $proyecto"
done
