"""Entorno de producción (EC2 + RDS, Práctica N.° 5, sección 7).

Los valores sensibles llegan por variable de entorno; el repositorio no
contiene ninguna credencial.
"""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
ES_PRODUCCION = True
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

# Sin valor por defecto: si falta, el servidor no arranca. Un valor de
# respaldo en producción firmaría las sesiones con una clave conocida.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
# La clave de los datos clínicos es propia y obligatoria: derivarla de
# SECRET_KEY haría ilegibles los antecedentes el día que esta se rote.
CLAVE_CIFRADO_CAMPOS = os.environ["CLAVE_CIFRADO_CAMPOS"]
# Vacías o con el texto de la plantilla (.env.ejemplo) es lo mismo que no
# tenerlas: campos.py caería en SECRET_KEY y las sesiones, en un valor público.
for _nombre in ("DJANGO_SECRET_KEY", "CLAVE_CIFRADO_CAMPOS"):
    _valor = os.environ[_nombre].strip()
    if not _valor or _valor.startswith("generar-con"):
        raise ImproperlyConfigured(f"{_nombre} no está configurada (ver docs/DESPLIEGUE.md).")

# Nginx termina el HTTPS y llama a gunicorn por HTTP. Sin esto Django cree
# que toda petición es insegura y SECURE_SSL_REDIRECT entra en un bucle de
# redirecciones. Es seguro porque Nginx sobrescribe la cabecera
# (infra/nginx/nginx.conf) y gunicorn no se expone fuera de la red interna.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = os.environ["DJANGO_CSRF_ORIGINS"].split(",")
X_FRAME_OPTIONS = "DENY"

# Copia, no modificación: `DATABASES` es el mismo diccionario que el de
# base.py, y cambiarlo en su sitio alteraba también la configuración de
# desarrollo y de pruebas cargada en el mismo proceso.
DATABASES = {
    **DATABASES,
    "default": {**DATABASES["default"], "OPTIONS": {"sslmode": "require"}, "CONN_MAX_AGE": 60},
}
