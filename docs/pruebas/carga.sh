#!/usr/bin/env bash
# Práctica 9 — pruebas de carga. Genera 03_carga.txt con los resúmenes de k6 tal cual.
# Requiere el servidor en http://127.0.0.1:8000, Python 3.12 activo y k6 en el PATH.
# Uso: bash docs/pruebas/carga.sh DIRECTORIO_TEMPORAL
set -u
TMP=${1:?directorio temporal para el JSON de citas}
SALIDA=docs/pruebas/03_carga.txt
export DJANGO_SETTINGS_MODULE=config.settings.dev
: > "$SALIDA"

seccion() {
  {
    echo "================================================================"
    echo "\$ $1"
    echo "Fecha: $(date -Iseconds)"
    echo "================================================================"
  } >> "$SALIDA"
}

seccion "python backend/manage.py cargar_demo"
python backend/manage.py cargar_demo >> "$SALIDA" 2>&1
seccion "python backend/manage.py sembrar_volumen"
python backend/manage.py sembrar_volumen >> "$SALIDA" 2>&1
seccion "volumen en la base tras sembrar_volumen"
python backend/manage.py shell -c "
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.models import Centro
from apps.inventario.models import MovimientoInventario
c = Centro.objects.get(subdominio='piessanos'); fijar_centro_en_la_sesion(c.pk)
q = MovimientoInventario.objects.filter(centro=c)
print('movimiento_inventario del centro de demostración:', q.count())
for t in ('ENTRADA', 'AJUSTE', 'MERMA', 'SALIDA'): print(' ', t, q.filter(tipo=t).count())
" >> "$SALIDA" 2>&1

seccion "k6 version"
k6 version >> "$SALIDA" 2>&1
seccion "k6 run --quiet --summary-mode=full docs/pruebas/carga_rnf04.js"
k6 run --quiet --summary-mode=full docs/pruebas/carga_rnf04.js >> "$SALIDA" 2>"$TMP/k6_rnf04.err"
echo "[código de salida: $?]" >> "$SALIDA"

seccion "python docs/pruebas/preparar_carga.py 100 citas_carga.json"
python docs/pruebas/preparar_carga.py 100 "$TMP/citas_carga.json" >> "$SALIDA" 2>&1
seccion "k6 run --quiet --summary-mode=full -e CITAS=citas_carga.json docs/pruebas/carga_atencion.js"
k6 run --quiet --summary-mode=full -e CITAS="$TMP/citas_carga.json" docs/pruebas/carga_atencion.js \
  >> "$SALIDA" 2>"$TMP/k6_atencion.err"
echo "[código de salida: $?]" >> "$SALIDA"
