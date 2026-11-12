"""Configuración común a todos los entornos.

La configuración se divide en tres módulos (base, dev, prod) para que el
entorno de producción no herede nunca un valor pensado para desarrollo
(OWASP A05 Security Misconfiguration, Práctica N.° 5, sección 6).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "cambiar-en-produccion")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_filters",
    "apps.core",
    "apps.usuarios",
    "apps.sedes",
    "apps.catalogo",
    "apps.pacientes",
    "apps.citas",
    "apps.atenciones",
    "apps.inventario",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContextoTenantMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "podocenter"),
        "USER": os.environ.get("POSTGRES_USER", "podo"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "podo"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "usuarios.Usuario"

# bcrypt como algoritmo principal (Práctica N.° 5, RNF01).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.core.errores.manejador_de_errores",
}

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Recordatorios por WhatsApp (RF07). Sin token, el envío automático es
# simulado: no sale nada y queda anotado. Con la cuenta aprobada por Meta se
# completan todas (docs/DESPLIEGUE.md).
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_NUMERO_ID = os.environ.get("WHATSAPP_NUMERO_ID", "")
WHATSAPP_VERSION_API = os.environ.get("WHATSAPP_VERSION_API", "")
WHATSAPP_PLANTILLA = os.environ.get("WHATSAPP_PLANTILLA", "")
WHATSAPP_IDIOMA = os.environ.get("WHATSAPP_IDIOMA", "es")

# Solo la configuración de producción lo enciende. Lo consultan los comandos
# que no deben correr allí por descuido, como cargar_demo.
ES_PRODUCCION = False

# Clave de cifrado de campo (Fernet) para los datos clínicos sensibles.
CLAVE_CIFRADO_CAMPOS = os.environ.get("CLAVE_CIFRADO_CAMPOS", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps.core.auditoria": {
            "handlers": ["console"], "level": "INFO", "propagate": False,
        }
    },
}
