"""Evidencia de la Práctica 9: E14, escaneo OWASP ZAP baseline contra el entorno local.

Reutiliza docs/pruebas/zap.py (el plan de ZAP y el resumen de alertas) con dos
cambios que exige la rama actual:

  1. La administradora del centro tiene ahora verificación en dos pasos
     (RF18). cargar_demo la crea sin el factor, así que tras la contraseña la
     sesión queda «pendiente» y la API solo admite el alta. Este script hace
     el alta como lo haría la persona: pide el secreto, calcula el código
     TOTP (RFC 6238) y lo confirma. Solo se usa contra la base local de prueba.
  2. El objetivo es http://localhost:5174 (el 5173 estaba ocupado el 26/11) y
     los informes van al directorio temporal, no a docs/pruebas/.

    python zap_evidencia.py DIRECTORIO_TEMPORAL

Imprime el resumen; ejecutar.py lo guarda en texto/E14.txt.
"""
import base64
import hashlib
import hmac
import http.cookiejar
import importlib.util
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
_spec = importlib.util.spec_from_file_location("zap", RAIZ / "docs" / "pruebas" / "zap.py")
zap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(zap)
# ZAP_OBJETIVO permite escanear otro servidor local, como el que imita la CSP de Nginx.
zap.OBJETIVO = OBJETIVO = os.environ.get("ZAP_OBJETIVO", "http://localhost:5174")


def _totp(secreto: str, momento: float) -> str:
    clave = base64.b32decode(secreto + "=" * (-len(secreto) % 8))
    resumen = hmac.new(clave, struct.pack(">Q", int(momento // 30)), hashlib.sha1).digest()
    d = resumen[-1] & 0x0F
    return str((struct.unpack(">I", resumen[d:d + 4])[0] & 0x7FFFFFFF) % 10**6).zfill(6)


def sesion_de_la_administradora():
    galletas = http.cookiejar.CookieJar()
    abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(galletas))

    def csrf():
        return next(c.value for c in galletas if c.name == "csrftoken")

    def post(ruta, datos):
        # S310: las URL salen siempre de OBJETIVO, una constante http:// local.
        peticion = urllib.request.Request(  # noqa: S310
            f"{OBJETIVO}/api/v1{ruta}", method="POST", data=json.dumps(datos).encode(),
            headers={"Content-Type": "application/json", "X-CSRFToken": csrf()})
        return json.loads(abridor.open(peticion).read())

    abridor.open(f"{OBJETIVO}/api/v1/sesion/actual/")
    post("/sesion/ingresar/", {"correo": "gerencia@piessanos.pe",
                               "contrasena": "Podocenter2026"})  # nosec B106 (demo)
    alta = post("/sesion/segundo-factor/alta/", {})
    post("/sesion/segundo-factor/confirmar/", {"codigo": _totp(alta["secreto"], time.time())})
    print("Segundo factor de gerencia@piessanos.pe dado de alta en la base local de prueba "
          "(secreto y códigos de recuperación no se muestran).")
    sedes = json.loads(abridor.open(f"{OBJETIVO}/api/v1/sesion/sedes/").read())["sedes"]
    sede = next(s["id"] for s in sedes if s["nombre"] == "Sede Cercado")
    productos = json.loads(abridor.open(urllib.request.Request(  # noqa: S310
        f"{OBJETIVO}/api/v1/inventario/productos/", headers={"X-Sede": str(sede)})).read())
    cookie = "; ".join(f"{c.name}={c.value}" for c in galletas)
    return cookie, sede, productos["productos"][0]["id"]


def principal(temporal: Path):
    sys.stdout.reconfigure(encoding="utf-8")
    cookie, sede, producto = sesion_de_la_administradora()
    informes = temporal / "zap_informes"
    informes.mkdir(parents=True, exist_ok=True)
    zap.AQUI = informes  # el informe HTML va al temporal, no a docs/pruebas/
    archivo_plan = temporal / "zap_plan.yaml"
    archivo_plan.write_text(zap.plan(cookie, sede, producto, informes), encoding="utf-8")
    corrida = subprocess.run(  # noqa: S603 (rutas fijas, sin entrada del usuario)
        [str(zap.JAVA), "-Xmx2g", "-jar", str(zap.ZAP), "-cmd", "-dir",
         str(temporal / "zap_home"), "-autorun", str(archivo_plan)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=zap.ZAP.parent, check=False)
    salida = ((corrida.stdout + corrida.stderr).strip()
              + f"\n[código de salida de ZAP: {corrida.returncode}]")
    salida = salida.replace(cookie, "[cookie de sesión omitida]")
    texto = zap.resumen(informes / "04_zap.json", salida).replace(
        "Fecha:", "Objetivo local de prueba; nunca producción. Fecha:", 1).replace(
        "Entorno: servidor de Vite (desarrollo)",
        "Entorno: " + ("servidor local con la CSP de infra/nginx/nginx.conf"
                       if "8088" in OBJETIVO else "servidor de Vite (desarrollo)"), 1)
    print(texto)
    sys.exit(corrida.returncode)


if __name__ == "__main__":
    principal(Path(sys.argv[1]))
