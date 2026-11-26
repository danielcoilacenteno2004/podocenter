"""Entorno de desarrollo local. Nunca se usa en el servidor."""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
CORS_PERMITIR_TODO = True
# Los recordatorios por correo se escriben en la consola: en desarrollo no
# debe salir ningún correo a un paciente.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
