#!/usr/bin/env bash
# Práctica 9 — datos del entorno de ejecución. Genera 08_entorno.txt.
# Se corre desde la raíz del repositorio, con el entorno de Python 3.12 activo.
set -u
SALIDA=docs/pruebas/08_entorno.txt
{
  echo "Fecha: $(date -Iseconds)"
  echo "Sistema: $(uname -s) $(uname -r)"
  echo "Python: $(python --version 2>&1)"
  python -c "import django, rest_framework; print('Django:', django.get_version()); print('Django REST Framework:', rest_framework.VERSION)"
  echo "PostgreSQL: $(PGPASSWORD=${POSTGRES_PASSWORD:-podo} psql -h localhost -U podo -d podocenter -Atc 'select version()')"
  echo "Node: $(node --version) · npm: $(npm --version)"
  echo "k6: $(k6 version 2>&1 | head -1)"
  echo "Commit evaluado (HEAD antes del commit de la evidencia): $(git rev-parse HEAD)"
  echo "Commits en la rama hasta ese HEAD: $(git rev-list --count HEAD)"
  echo "Por integrante (git shortlog -sn, aplica .mailmap):"
  git shortlog -sn HEAD
} > "$SALIDA" 2>&1
cat "$SALIDA"
