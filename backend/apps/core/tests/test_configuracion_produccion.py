"""La configuración de producción no arranca con secretos por defecto."""
import importlib
import sys

import pytest

ENTORNO = {
    "DJANGO_ALLOWED_HOSTS": "podocenter.pe",
    "DJANGO_CSRF_ORIGINS": "https://podocenter.pe",
    "DJANGO_SECRET_KEY": "x" * 64,
    "CLAVE_CIFRADO_CAMPOS": "y" * 43,
}


def _cargar(monkeypatch, sin=()):
    for nombre, valor in ENTORNO.items():
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


def test_detras_de_nginx_reconoce_el_https(monkeypatch):
    # Garantiza que la redirección a HTTPS no entra en bucle: Nginx termina el
    # TLS y avisa con X-Forwarded-Proto, que Django tiene que creer.
    prod = _cargar(monkeypatch)

    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert prod.SECRET_KEY == ENTORNO["DJANGO_SECRET_KEY"]
    assert prod.CLAVE_CIFRADO_CAMPOS == ENTORNO["CLAVE_CIFRADO_CAMPOS"]
    assert prod.DEBUG is False
