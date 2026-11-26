#!/usr/bin/env bash
# Evidencia de la Práctica 9: E01, E02 y E03 en un árbol de trabajo dado.
#
#   bash suite.sh RUTA_DEL_ARBOL SUFIJO DIRECTORIO_TEMPORAL "ETIQUETA"
#
# RUTA_DEL_ARBOL es la raíz del repositorio o un git worktree (p. ej. el del
# commit del 11/11). SUFIJO es -1111 o -actual. El JSON de cobertura va al
# directorio temporal, fuera del repositorio. Requiere Python 3.12 activo y
# POSTGRES_PORT apuntando a la base local de prueba.
set -u
ARBOL=${1:?raíz del árbol}; SUF=${2:?sufijo}; TMP=${3:?temporal}; ETQ=${4:-}
EV="$(cd "$(dirname "$0")" && pwd -W)"
COMMIT=$(git -C "$ARBOL" rev-parse --short HEAD)

# pyproject.toml añade -q a addopts, y -v solo lo compensa: con -v la salida es
# un punto por prueba. -vv da una línea por prueba con su resultado.
python "$EV/ejecutar.py" "E01$SUF" --cwd "$ARBOL" --commit "$COMMIT" --etiqueta "$ETQ" -- \
  "pytest -vv"

python "$EV/ejecutar.py" "E02$SUF" --cwd "$ARBOL" --commit "$COMMIT" --etiqueta "$ETQ" -- \
  "pytest --cov --cov-branch --cov-report=term-missing" \
  "python -m coverage json -o '$TMP/cobertura$SUF.json' && python -c \"import json; t=json.load(open('$TMP/cobertura$SUF.json'))['totals']; print('Sentencias: %d de %d cubiertas = %.2f %%' % (t['covered_lines'], t['num_statements'], 100*t['covered_lines']/t['num_statements'])); print('Ramas:      %d de %d cubiertas = %.2f %%' % (t['covered_branches'], t['num_branches'], 100*t['covered_branches']/t['num_branches'])); print('Combinada (columna Cover): %.2f %%' % t['percent_covered'])\""

python "$EV/ejecutar.py" "E03$SUF" --cwd "$ARBOL" --commit "$COMMIT" --etiqueta "$ETQ" -- \
  "python '$EV/cobertura_por_modulo.py' '$TMP/cobertura$SUF.json'"

rm -f "$ARBOL/.coverage"
