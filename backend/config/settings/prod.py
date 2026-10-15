"""Entorno de producción (EC2 + RDS, Práctica N.° 5, sección 7).

Los valores sensibles llegan por variable de entorno; el repositorio no
contiene ninguna credencial.
"""
import os

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

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

DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
