"""La configuración de producción no arranca con secretos por defecto."""
import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

ENTORNO = {
    "DJANGO_ALLOWED_HOSTS": "podocenter.pe",
    "DJANGO_CSRF_ORIGINS": "https://podocenter.pe",
    "DJANGO_SECRET_KEY": "x" * 64,
    "CLAVE_CIFRADO_CAMPOS": "y" * 43,
}


def _cargar(monkeypatch, sin=(), **otros):
    for nombre, valor in {**ENTORNO, **otros}.items():
        if nombre in sin:
            monkeypatch.delenv(nombre, raising=False)
        else:
            monkeypatch.setenv(nombre, valor)
    sys.modules.pop("config.settings.prod", None)
    return importlib.import_module("config.settings.prod")


@pytest.mark.parametrize("falta", ["DJANGO_SECRET_KEY", "CLAVE_CIFRADO_CAMPOS"])
def test_sin_secretos_produccion_no_arranca(monkeypatch, falta):
    # Garantiza que un despliegue con una variable olvidada falla al arrancar
    # en vez de firmar las sesiones con una clave conocida o cifrar los datos
    # clínicos con una clave derivada de otra.
    with pytest.raises(KeyError):
        _cargar(monkeypatch, sin={falta})


@pytest.mark.parametrize("valor", ["", "  ", "generar-con-Fernet.generate_key"])
def test_una_clave_vacia_o_de_plantilla_tampoco_arranca(monkeypatch, valor):
    # Garantiza que copiar .env.ejemplo sin completarlo no deja el sistema en
    # marcha con una clave vacía (que caería en SECRET_KEY) o publicada en el
    # repositorio.
    with pytest.raises(ImproperlyConfigured):
        _cargar(monkeypatch, CLAVE_CIFRADO_CAMPOS=valor)


def test_detras_de_nginx_reconoce_el_https(monkeypatch):
    # Garantiza que la redirección a HTTPS no entra en bucle: Nginx termina el
    # TLS y avisa con X-Forwarded-Proto, que Django tiene que creer.
    prod = _cargar(monkeypatch)

    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert prod.SECRET_KEY == ENTORNO["DJANGO_SECRET_KEY"]
    assert prod.CLAVE_CIFRADO_CAMPOS == ENTORNO["CLAVE_CIFRADO_CAMPOS"]
    assert prod.DEBUG is False
    assert prod.ES_PRODUCCION is True  # cargar_demo se niega a correr
    assert prod.DATABASES["default"]["OPTIONS"] == {"sslmode": "require"}


def test_cargar_produccion_no_altera_la_configuracion_en_uso(monkeypatch):
    # Garantiza que importar la configuración de producción no cambia la base
    # de datos de la que ya está en uso: antes la modificaba en su sitio y el
    # resto de la batería pasaba a exigir SSL.
    from django.conf import settings

    antes = dict(settings.DATABASES["default"].get("OPTIONS", {}))
    _cargar(monkeypatch)

    assert settings.DATABASES["default"].get("OPTIONS", {}) == antes


def _nginx() -> str:
    from django.conf import settings

    return (settings.BASE_DIR.parent / "infra" / "nginx" / "nginx.conf").read_text(
        encoding="utf-8")


def test_nginx_declara_una_csp_que_no_permite_codigo_en_linea():
    # DEF-27: sin Content-Security-Policy, un script inyectado en cualquier
    # pantalla se ejecutaría con la sesión de quien la mira. La política solo
    # sirve si no reabre la puerta con 'unsafe-inline' o 'unsafe-eval'.
    linea = next(lin for lin in _nginx().splitlines()
                 if lin.strip().startswith("add_header Content-Security-Policy"))

    assert "script-src 'self'" in linea
    assert "frame-ancestors 'none'" in linea
    assert "unsafe-inline" not in linea
    assert "unsafe-eval" not in linea
    assert linea.rstrip().endswith("always;")


def test_nginx_no_publica_su_version():
    # La versión en la cabecera Server le dice a un atacante qué fallos
    # conocidos probar primero (alerta de ZAP de la Práctica N.° 9).
    assert "server_tokens off;" in _nginx()
