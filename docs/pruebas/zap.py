"""Práctica 9 — escaneo OWASP ZAP en modo baseline, con la sesión de la administradora.

«Baseline» es araña más escaneo pasivo: ZAP recorre y observa las respuestas,
sin atacar. Con la instalación de escritorio no hay `zap-baseline.py` (es de la
imagen Docker), así que se arma el mismo recorrido con el Automation Framework:

  1. Inicia sesión como gerencia@piessanos.pe y toma su cookie de sesión.
  2. Escribe un plan de ZAP (fuera del repositorio: lleva la cookie) con una
     regla `replacer` que añade esa cookie y la sede activa a cada petición,
     un `requestor` con las pantallas y rutas GET de la API (la SPA arma sus
     URL en JavaScript y la araña clásica no las ve), la araña clásica, la
     araña AJAX, la espera del escaneo pasivo y los informes.
  3. Corre ZAP y resume el JSON en 04_zap.txt.

    python docs/pruebas/zap.py DIRECTORIO_TEMPORAL

Objetivo: http://localhost:5173 (servidor de Vite, que hace de proxy de
/api y /admin hacia Django con la configuración de desarrollo).
"""
import http.cookiejar
import json
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OBJETIVO = "http://localhost:5173"
ZAP = Path(r"C:\Program Files\ZAP\Zed Attack Proxy\zap-2.17.0.jar")
JAVA = Path(r"C:\Program Files\Eclipse Adoptium\jre-17.0.21.9-hotspot\bin\java.exe")
AQUI = Path(__file__).resolve().parent
RIESGOS = {"3": "Alto", "2": "Medio", "1": "Bajo", "0": "Informativo"}

PANTALLAS = ["/", "/ingresar", "/panel", "/agenda", "/pacientes", "/inventario",
             "/registro-diario", "/usuarios", "/sedes", "/servicios", "/perfil"]
API = ["/sesion/actual/", "/sesion/sedes/", "/sesion/profesionales/", "/usuarios/", "/sedes/",
       "/servicios/", "/pacientes/", "/citas/", "/citas/agenda/", "/panel/", "/atenciones/",
       "/reportes/registro-diario/", "/inventario/productos/", "/inventario/stock/",
       "/estado/"]


def sesion_de_la_administradora():
    galletas = http.cookiejar.CookieJar()
    abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(galletas))
    abridor.open(f"{OBJETIVO}/api/v1/sesion/actual/")
    csrf = next(c.value for c in galletas if c.name == "csrftoken")
    # S310: las URL salen siempre de OBJETIVO, una constante http:// local.
    peticion = urllib.request.Request(  # noqa: S310
        f"{OBJETIVO}/api/v1/sesion/ingresar/", method="POST",
        data=json.dumps({"correo": "gerencia@piessanos.pe",
                         "contrasena": "Podocenter2026"}).encode(),  # nosec B106 (demo)
        headers={"Content-Type": "application/json", "X-CSRFToken": csrf})
    abridor.open(peticion)
    sedes = json.loads(abridor.open(f"{OBJETIVO}/api/v1/sesion/sedes/").read())["sedes"]
    sede = next(s["id"] for s in sedes if s["nombre"] == "Sede Cercado")
    productos = json.loads(abridor.open(urllib.request.Request(  # noqa: S310
        f"{OBJETIVO}/api/v1/inventario/productos/", headers={"X-Sede": str(sede)})).read())
    cookie = "; ".join(f"{c.name}={c.value}" for c in galletas)
    return cookie, sede, productos["productos"][0]["id"]


def plan(cookie, sede, producto, informes: Path) -> str:
    peticiones = [OBJETIVO + p for p in PANTALLAS] + [f"{OBJETIVO}/api/v1{r}" for r in API] + [
        f"{OBJETIVO}/api/v1/inventario/disponibilidad/?producto={producto}", f"{OBJETIVO}/admin/"]
    lineas_peticiones = "\n".join(f"      - url: \"{u}\"\n        method: GET" for u in peticiones)
    return f"""---
env:
  contexts:
    - name: podocenter
      urls: ["{OBJETIVO}"]
      includePaths: ["{OBJETIVO}.*"]
      excludePaths:
        - "{OBJETIVO}/api/v1/sesion/salir/.*"
        - "{OBJETIVO}/admin/logout/.*"
  parameters:
    failOnError: false
    failOnWarning: false
    progressToStdout: true
jobs:
  - type: replacer
    parameters:
      deleteAllRules: true
    rules:
      - description: "Sesión de la administradora del centro"
        matchType: req_header
        matchString: "Cookie"
        matchRegex: false
        replacementString: "{cookie}"
      - description: "Sede activa"
        matchType: req_header
        matchString: "X-Sede"
        matchRegex: false
        replacementString: "{sede}"
  - type: requestor
    requests:
{lineas_peticiones}
  - type: spider
    parameters:
      context: podocenter
      url: "{OBJETIVO}"
      maxDuration: 2
  - type: spiderAjax
    parameters:
      context: podocenter
      url: "{OBJETIVO}"
      maxDuration: 3
      browserId: edge-headless
  - type: passiveScan-wait
    parameters:
      maxDuration: 5
  - type: report
    parameters:
      template: traditional-html
      reportDir: "{AQUI.as_posix()}"
      reportFile: "04_zap"
      reportTitle: "PodoCenter — ZAP baseline (sesión de la administradora)"
  - type: report
    parameters:
      template: traditional-json
      reportDir: "{informes.as_posix()}"
      reportFile: "04_zap"
"""


def resumen(json_zap: Path, salida_zap: str) -> str:
    datos = json.loads(json_zap.read_text(encoding="utf-8"))
    alertas = [a for sitio in datos.get("site", []) for a in sitio.get("alerts", [])]
    por_riesgo = defaultdict(list)
    for a in alertas:
        por_riesgo[a["riskcode"]].append(a)
    lineas = [
        "Resumen del escaneo OWASP ZAP (baseline: araña + escaneo pasivo, sin ataques)",
        f"Fecha: {datetime.now().isoformat(timespec='seconds')}",
        f"ZAP: {datos.get('@version', '?')} · Objetivo: {OBJETIVO}",
        "Sesión: CON la sesión de la administradora (gerencia@piessanos.pe), inyectada en cada",
        "petición por una regla replacer; además, cabecera X-Sede con la Sede Cercado.",
        "Entorno: servidor de Vite (desarrollo) como proxy de Django con config.settings.dev",
        "(DEBUG=True). Las cabeceras de producción las pone Nginx y no se midieron aquí.",
        "",
        "Alertas por nivel de riesgo:",
    ]
    for codigo in ("3", "2", "1", "0"):
        lineas.append(f"  {RIESGOS[codigo]:<12} {len(por_riesgo[codigo])}")
    lineas.append("")
    for codigo in ("3", "2", "1", "0"):
        for a in por_riesgo[codigo]:
            urls = sorted({i["uri"] for i in a.get("instances", [])})
            lineas.append(f"[{RIESGOS[codigo]}] {a['alert']} (pluginid {a['pluginid']}, "
                          f"CWE-{a.get('cweid', '?')}, confianza {a.get('confidence')}) — "
                          f"{a.get('count', len(urls))} instancia(s)")
            for u in urls[:5]:
                lineas.append(f"      {u}")
            if len(urls) > 5:
                lineas.append(f"      … y {len(urls) - 5} URL más (ver 04_zap.html)")
    lineas += ["", "Salida de ZAP (consola):", salida_zap]
    return "\n".join(lineas)


def principal(temporal: Path):
    cookie, sede, producto = sesion_de_la_administradora()
    informes = temporal / "zap_informes"
    informes.mkdir(parents=True, exist_ok=True)
    archivo_plan = temporal / "zap_plan.yaml"
    archivo_plan.write_text(plan(cookie, sede, producto, informes), encoding="utf-8")
    corrida = subprocess.run(  # noqa: S603 (rutas fijas, sin entrada del usuario)
        [str(JAVA), "-Xmx2g", "-jar", str(ZAP), "-cmd", "-dir", str(temporal / "zap_home"),
         "-autorun", str(archivo_plan)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ZAP.parent,
        check=False)
    salida = ((corrida.stdout + corrida.stderr).strip()
              + f"\n[código de salida: {corrida.returncode}]")
    # ZAP repite en consola el plan, cookie incluida: no se publica una sesión.
    salida = salida.replace(cookie, "[cookie de sesión omitida]")
    (AQUI / "04_zap.txt").write_text(resumen(informes / "04_zap.json", salida), encoding="utf-8")
    print((AQUI / "04_zap.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    principal(Path(sys.argv[1]))
