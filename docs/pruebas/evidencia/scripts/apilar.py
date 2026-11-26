"""Evidencia de la Práctica 9: apila varias imágenes ya generadas en una sola, sin alterarlas.

    python apilar.py SALIDA.png ENTRADA1.png ENTRADA2.png ...

Solo junta las capturas una debajo de otra, con una franja de separación, para
que quepan en una figura del documento. Cada una conserva su cabecera con el
comando y la fecha.
"""
import sys
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent.parent / "img"
entradas = [Image.open(AQUI / n) for n in sys.argv[2:]]
ancho = max(i.width for i in entradas)
alto = sum(i.height for i in entradas) + 12 * (len(entradas) - 1)
lienzo = Image.new("RGB", (ancho, alto), "#000000")
y = 0
for i in entradas:
    lienzo.paste(i, (0, y))
    y += i.height + 12
lienzo.save(AQUI / sys.argv[1], optimize=True)
print(sys.argv[1], lienzo.size)
