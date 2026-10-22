"""Campo de texto cifrado en reposo (Fernet).

La Práctica N.° 5 exige cifrar los datos clínicos sensibles por encima del
cifrado del disco: el diagnóstico y los antecedentes no deben ser legibles
para quien obtenga una copia de la base. El resto de columnas no se cifra,
porque hay que poder buscarlas y ordenarlas.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

_PREFIJO = "fer:"


def _clave() -> Fernet:
    """Deriva la clave Fernet del valor configurado en el entorno."""
    bruta = settings.CLAVE_CIFRADO_CAMPOS or settings.SECRET_KEY
    derivada = hashlib.sha256(bruta.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derivada))


class TextoCifrado(models.TextField):
    """TextField que cifra al guardar y descifra al leer."""

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        if isinstance(value, str) and value.startswith(_PREFIJO):
            return value
        token = _clave().encrypt(str(value).encode("utf-8")).decode("ascii")
        return _PREFIJO + token

    def from_db_value(self, value, expression, connection):
        return self._descifrar(value)

    def to_python(self, value):
        return self._descifrar(value)

    @staticmethod
    def _descifrar(value):
        if not value or not isinstance(value, str) or not value.startswith(_PREFIJO):
            return value
        try:
            return _clave().decrypt(value[len(_PREFIJO):].encode("ascii")).decode("utf-8")
        except InvalidToken:
            # Dato cifrado con otra clave: se devuelve vacío en lugar de romper
            # la pantalla, y queda el registro en la auditoría de lectura.
            return ""
