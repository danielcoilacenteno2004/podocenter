#!/usr/bin/env bash
# Evidencia de la Práctica 9: E13, carga de la consulta de disponibilidad entre sedes (RNF04).
#
#   bash docs/pruebas/evidencia/scripts/carga.sh
#
# Los mismos pasos que docs/pruebas/carga.sh: cargar_demo, sembrar_volumen (el
# comando de volumen del proyecto) y docs/pruebas/carga_rnf04.js, con escalones
# de 1, 5, 10 y 20 usuarios virtuales. Requiere Django en 127.0.0.1:8000 con la
# base local de prueba y k6 en el PATH. Se corre sin otras pruebas en paralelo,
# para no medir la contención con ellas.
set -u
EV="$(cd "$(dirname "$0")" && pwd -W)"
RAIZ="$(pwd -W)"
ETQ="rama $(git rev-parse --abbrev-ref HEAD) · servidor de desarrollo local"
python "$EV/ejecutar.py" E13 --cwd "$RAIZ" --etiqueta "$ETQ" -- \
  "python backend/manage.py cargar_demo" \
  "python backend/manage.py sembrar_volumen" \
  "k6 version" \
  "k6 run --quiet --summary-mode=full docs/pruebas/carga_rnf04.js"
