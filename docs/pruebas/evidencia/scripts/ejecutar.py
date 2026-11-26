"""Evidencia de la Práctica 9: ejecuta uno o varios comandos y guarda su salida tal cual.

    python ejecutar.py ID --cwd DIR [--commit HASH] [--etiqueta TEXTO] -- "cmd 1" ["cmd 2" ...]

Cada comando corre con bash (Git Bash) en DIR, con el entorno heredado. La
salida combinada (stdout y stderr) se guarda en texto/<ID>.txt:

    línea 1        $ <comando>   (varios, separados por « ; »)
    línea 2        # fecha, commit y directorio de la ejecución
    ...            la salida completa, sin recortar
    última línea   [código de salida: N]

Si hay varios comandos, cada uno lleva su propio encabezado «$ …» y su código,
y la última línea es el código mayor. Antes de escribir se enmascaran con ****
los secretos, contraseñas, claves, tokens, cadenas de conexión y direcciones IP.
Cada ejecución se anota también en registro.jsonl, del que sale indice.json.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
BASH = r"C:\Program Files\Git\bin\bash.exe"

# Valores que nunca deben quedar en una captura, aunque sean de prueba.
SECRETOS_LITERALES = [
    "Podocenter2026",                       # contraseña pública de la demostración
    "clave-ficticia-solo-para-check-deploy-0123456789abcdefghijklmnopqrstuvwxyz",
    "Zm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyZm9vYmFyMDA=",  # clave Fernet ficticia de E09
]
PATRONES = [
    # cadenas de conexión con usuario y contraseña
    (re.compile(r"(postgres(?:ql)?://)[^\s'\"]+"), r"\1****"),
    # asignaciones de secretos: PASSWORD=..., token: ..., secret_key = ...
    (re.compile(r"(?i)\b([A-Z_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|CLAVE_CIFRADO|API_KEY)[A-Z_]*)"
                r"(\s*[=:]\s*)(['\"]?)[^\s'\",]+"), r"\1\2\3****"),
    (re.compile(r"(?i)\b(contrasena|contraseña|password)(\"?\s*:\s*\")[^\"]*"), r"\1\2****"),
    # cookies de sesión y CSRF
    (re.compile(r"(?i)\b(sessionid|csrftoken)=([^;\s]+)"), r"\1=****"),
    # direcciones IPv4 (incluida la de bucle local) e IPv6 de bucle local
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "****"),
    (re.compile(r"\[::1?\]"), "[****]"),
]


def enmascarar(texto: str) -> str:
    for literal in SECRETOS_LITERALES:
        texto = texto.replace(literal, "****")
    for patron, reemplazo in PATRONES:
        texto = patron.sub(reemplazo, texto)
    return texto


def correr(comando: str, cwd: Path) -> tuple[str, int]:
    corrida = subprocess.run(  # noqa: S603 (comandos escritos por el equipo, no por un usuario)
        [BASH, "-c", comando], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False)
    salida = (corrida.stdout or "") + (corrida.stderr or "")
    return salida.rstrip("\n"), corrida.returncode


def principal():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--cwd", required=True)
    p.add_argument("--commit", default="")
    p.add_argument("--etiqueta", default="")
    p.add_argument("comandos", nargs="+")
    a = p.parse_args()
    cwd = Path(a.cwd).resolve()
    commit = a.commit or subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 (git del PATH, sin entrada externa)
        cwd=cwd, capture_output=True, text=True,
        check=False).stdout.strip()
    inicio = datetime.now().astimezone()
    partes, codigos = [], []
    for comando in a.comandos:
        salida, codigo = correr(comando, cwd)
        codigos.append(codigo)
        if len(a.comandos) > 1:
            partes.append(f"$ {comando}\n{salida}\n[código de salida de este comando: {codigo}]")
        else:
            partes.append(salida)
    codigo_final = max(codigos, key=abs)
    texto = "\n".join([
        "$ " + " ; ".join(a.comandos),
        f"# Fecha: {inicio.isoformat(timespec='seconds')} · Commit: {commit}"
        + (f" · {a.etiqueta}" if a.etiqueta else ""),
        *(["", *("\n\n".join(partes).split("\n")), ""] if partes else []),
        f"[código de salida: {codigo_final}]",
    ])
    texto = enmascarar(texto)
    destino = AQUI / "texto" / f"{a.id}.txt"
    destino.write_text(texto + "\n", encoding="utf-8")
    with (AQUI / "registro.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "id": a.id, "comando": " ; ".join(a.comandos), "commit": commit,
            "fecha": inicio.isoformat(timespec="seconds"), "codigo_salida": codigo_final,
            "codigos_por_comando": codigos, "texto": f"texto/{a.id}.txt",
            "etiqueta": a.etiqueta,
        }, ensure_ascii=False) + "\n")
    print(f"{a.id}: código {codigo_final} · {len(texto.splitlines())} líneas → {destino.name}")


if __name__ == "__main__":
    principal()
