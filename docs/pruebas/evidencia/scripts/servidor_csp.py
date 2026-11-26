"""Sirve frontend/dist con la CSP de infra/nginx/nginx.conf y reenvía a Django /api, /admin
y /static.

Imita lo que hará Nginx en producción, para probar en el navegador que la política no
rompe la SPA ni el admin. Solo para verificación local.
    python servidor_csp.py RAIZ_DEL_REPO PUERTO
"""
import http.server
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(sys.argv[1])
PUERTO = int(sys.argv[2])
DIST = RAIZ / "frontend" / "dist"
CONF = (RAIZ / "infra" / "nginx" / "nginx.conf").read_text(encoding="utf-8")
CSP = re.search(r'add_header Content-Security-Policy "([^"]+)"', CONF).group(1)
DJANGO = "http://127.0.0.1:8000"


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


ABRIDOR = urllib.request.build_opener(SinRedireccion)


class Manejador(http.server.BaseHTTPRequestHandler):
    def _cabeceras_comunes(self):
        self.send_header("Content-Security-Policy", CSP)

    def _proxy(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else None
        cabeceras = {k: v for k, v in self.headers.items() if k.lower() not in ("host",)}
        cabeceras["Host"] = f"localhost:{PUERTO}"
        # S310: el destino es siempre DJANGO, una constante http:// local.
        peticion = urllib.request.Request(  # noqa: S310
            DJANGO + self.path, data=cuerpo, headers=cabeceras, method=self.command)
        try:
            r = ABRIDOR.open(peticion)
        except urllib.error.HTTPError as e:
            r = e
        datos = r.read()
        self.send_response(r.status if hasattr(r, "status") else r.code)
        for k, v in r.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length",
                                 "content-security-policy"):
                self.send_header(k, v)
        self._cabeceras_comunes()
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _estatico(self):
        ruta = self.path.split("?")[0]
        archivo = DIST / ruta.lstrip("/")
        if not archivo.is_file():
            archivo = DIST / "index.html"
        datos = archivo.read_bytes()
        tipo = {".js": "application/javascript", ".css": "text/css", ".html": "text/html",
                ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}.get(
            archivo.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self._cabeceras_comunes()
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _atender(self):
        if re.match(r"^/(api|admin|static)/", self.path):
            self._proxy()
        else:
            self._estatico()

    # Nombres que exige BaseHTTPRequestHandler.
    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _atender  # noqa: N815

    def log_message(self, *a):
        pass


print("CSP:", CSP, flush=True)
http.server.ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador).serve_forever()
