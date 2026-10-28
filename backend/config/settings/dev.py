"""Entorno de desarrollo local. Nunca se usa en el servidor."""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
CORS_PERMITIR_TODO = True
