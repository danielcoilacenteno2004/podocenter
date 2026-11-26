#!/usr/bin/env bash
# Evidencia de la Práctica 9: genera todas las imágenes de img/ a partir de texto/.
#   bash docs/pruebas/evidencia/scripts/imagenes.sh   (desde la raíz del repositorio)
set -eu
cd "$(dirname "$0")/.."
R() { python scripts/render.py "$@" >/dev/null; }
L() { wc -l < "texto/$1.txt"; }
find img -maxdepth 1 -name "*.png" -delete
R E01-1111 --nombre E01-1111-resumen --desde $(( $(L E01-1111) - 10 )) --titulo "resumen final"
R E01-1111 --nombre E01-1111-lista --lineas 75 --titulo "lista completa"
R E01-actual --nombre E01-actual-resumen --desde $(( $(L E01-actual) - 10 )) --titulo "resumen final"
R E01-actual --nombre E01-actual-lista --lineas 75 --titulo "lista completa"
R E02-1111 --lineas 100
R E02-1111 --nombre E02-1111-resumen --desde 82 --titulo "fila TOTAL y cifras separadas"
R E02-actual --lineas 115
R E02-actual --nombre E02-actual-resumen --desde 98 --titulo "fila TOTAL y cifras separadas"
R E03-1111; R E03-actual
R E04 --lineas 80
for r in RF02 RF06 RF10 RF11 RF12 RF16 RF18; do
  R E05-$r --lineas 80
  R E05-$r --nombre E05-$r-resumen --desde $(( $(L E05-$r) - 5 )) --titulo "resumen final"
done
R E06; R E07; R E09; R E10
R E08 --lineas 120
R E08 --nombre E08-resumen --desde 100 --titulo "final del informe"
R E11 --lineas 100
for p in chromium webkit movil; do R E12-$p --lineas 100; done
R E12-chromium --nombre E12-chromium-resumen --desde 24 --hasta 36 --titulo "pasos del recorrido"
R E12-webkit --nombre E12-webkit-resumen --desde 25 --hasta 37 --titulo "pasos del recorrido"
R E12-movil --nombre E12-movil-resumen --desde 25 --hasta 37 --titulo "pasos del recorrido"
R E13 --lineas 120
R E13 --nombre E13-resumen --desde 32 --hasta 110 --lineas 80 --titulo "umbrales y resultado total"
R E13-interrumpida --lineas 120
R E13-interrumpida-2 --lineas 120
R E14 --lineas 80
R E14 --nombre E14-resumen --desde 26 --hasta 75 --titulo "resumen de alertas"
python scripts/apilar.py E05-resumen.png E05-RF02-resumen.png E05-RF06-resumen.png \
  E05-RF10-resumen.png E05-RF11-resumen.png E05-RF12-resumen.png E05-RF16-resumen.png \
  E05-RF18-resumen.png >/dev/null
python scripts/apilar.py E12-resumen.png E12-chromium-resumen.png E12-webkit-resumen.png \
  E12-movil-resumen.png >/dev/null
# Corrección del 26/11 (DEF-25 a DEF-27)
R E01-correccion --nombre E01-correccion-resumen --desde $(( $(L E01-correccion) - 10 )) --titulo "resumen final"
R E01-correccion --nombre E01-correccion-lista --lineas 75 --titulo "lista completa"
R E02-correccion --lineas 115
R E02-correccion --nombre E02-correccion-resumen --desde $(( $(L E02-correccion) - 13 )) --titulo "fila TOTAL y cifras separadas"
R E03-correccion
R E05-DEF25-correccion --lineas 80
R E06-correccion; R E08-correccion; R E10-correccion
R E11-correccion --lineas 100
R E14-correccion --lineas 80
R E14-correccion --nombre E14-correccion-resumen --desde 26 --hasta 60 --titulo "resumen de alertas"
ls img/*.png | wc -l
