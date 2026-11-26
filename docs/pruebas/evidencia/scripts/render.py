"""Evidencia de la Práctica 9: convierte texto/<ID>.txt en una o varias imágenes PNG.

    python render.py ID [--nombre NOMBRE] [--lineas N] [--desde A] [--hasta B] [--titulo T]

Fondo oscuro, fuente monoespaciada, 1400 px de ancho. La cabecera repite el
comando (línea 1 del texto) y la fecha (línea 2). Debajo va la salida con el
número de línea del archivo de texto a la izquierda, para que se pueda
comprobar que no falta ninguna. Las líneas largas se parten y siguen en la
línea de abajo, sin número; no se quita ningún carácter.

--desde y --hasta eligen un tramo de líneas del archivo (numeradas desde 1),
por ejemplo el resumen final de pytest o la tabla de cobertura. Si el tramo
tiene más de --lineas, se divide en NOMBRE-a.png, NOMBRE-b.png, …
"""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent.parent
FUENTE = r"C:\Windows\Fonts\CascadiaMono.ttf"
ANCHO, MARGEN, TAM, ALTO_LINEA = 1400, 18, 15, 20
FONDO, CABECERA, TEXTO, TENUE = "#1e1e1e", "#2d2d30", "#d4d4d4", "#6e7681"
COMANDO, VERDE, ROJO, AMARILLO = "#4ec9b0", "#6cc070", "#f14c4c", "#d7ba7d"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def color_de(linea: str) -> str:
    # Rojo solo para un fallo real: no para el nombre de una métrica como http_req_failed.
    if re.search(r"\b(FAILED|ERROR|FAIL)\b|✗|\b[1-9]\d* failed\b|\bError\b", linea):
        return ROJO
    if re.search(r"\bPASSED\b|✓|passed\b|All checks passed|No issues identified|No changes",
                 linea):
        return VERDE
    if re.search(r"\b(SKIPPED|XFAIL|WARNING|warning)\b", linea):
        return AMARILLO
    return TEXTO


def partir(linea: str, maximo: int) -> list[str]:
    linea = ANSI.sub("", linea).expandtabs(4).replace("\r", "")
    if not linea:
        return [""]
    return [linea[i:i + maximo] for i in range(0, len(linea), maximo)]


def dibujar(destino: Path, comando: str, meta: str, filas: list[tuple[str, str]],
            pie: str):
    fuente = ImageFont.truetype(FUENTE, TAM)
    ancho_car = fuente.getlength("M")
    max_cab = int((ANCHO - 2 * MARGEN) / ancho_car)
    cab = partir(comando, max_cab)
    alto_cab = MARGEN + ALTO_LINEA * (len(cab) + 1) + MARGEN // 2
    alto = alto_cab + MARGEN + ALTO_LINEA * (len(filas) + 1) + MARGEN
    img = Image.new("RGB", (ANCHO, alto), FONDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ANCHO, alto_cab], fill=CABECERA)
    y = MARGEN
    for trozo in cab:
        d.text((MARGEN, y), trozo, font=fuente, fill=COMANDO)
        y += ALTO_LINEA
    d.text((MARGEN, y), meta, font=fuente, fill=TENUE)
    y = alto_cab + MARGEN
    for numero, texto in filas:
        d.text((MARGEN, y), numero, font=fuente, fill=TENUE)
        d.text((MARGEN + ancho_car * 6, y), texto, font=fuente, fill=color_de(texto))
        y += ALTO_LINEA
    d.text((MARGEN, y), pie, font=fuente, fill=TENUE)
    img.save(destino, optimize=True)


def principal():
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--nombre")
    p.add_argument("--lineas", type=int, default=75)
    p.add_argument("--desde", type=int, default=3)
    p.add_argument("--hasta", type=int)
    p.add_argument("--titulo", default="")
    a = p.parse_args()
    lineas = (AQUI / "texto" / f"{a.id}.txt").read_text(encoding="utf-8").split("\n")
    if lineas and lineas[-1] == "":
        lineas.pop()
    comando, meta = lineas[0], lineas[1].lstrip("# ")
    hasta = a.hasta or len(lineas)
    tramo = list(range(a.desde, hasta + 1))
    fuente = ImageFont.truetype(FUENTE, TAM)
    max_car = int((ANCHO - 2 * MARGEN) / fuente.getlength("M")) - 6
    paginas = [tramo[i:i + a.lineas] for i in range(0, len(tramo), a.lineas)] or [[]]
    nombre = a.nombre or a.id
    letras = "abcdefghijklmnopqrstuvwxyz"
    creadas = []
    for k, pagina in enumerate(paginas):
        filas = []
        for n in pagina:
            for j, trozo in enumerate(partir(lineas[n - 1], max_car)):
                filas.append((f"{n:>4}" if j == 0 else "", trozo))
        parte = f" · parte {letras[k]} de {len(paginas)}" if len(paginas) > 1 else ""
        rango = f"líneas {pagina[0]} a {pagina[-1]} de {len(lineas)}" if pagina else ""
        pie = f"{a.titulo + ' · ' if a.titulo else ''}texto/{a.id}.txt, {rango}{parte}"
        archivo = f"{nombre}-{letras[k]}.png" if len(paginas) > 1 else f"{nombre}.png"
        dibujar(AQUI / "img" / archivo, comando, meta, filas, pie)
        creadas.append(archivo)
    print(" ".join(creadas))


if __name__ == "__main__":
    principal()
