"""Contraseña de un solo uso basada en tiempo (TOTP, RFC 6238).

Se implementa con la biblioteca estándar y no con una dependencia porque el
algoritmo cabe en unas líneas y así queda a la vista lo que se verifica:
HMAC-SHA1 sobre el número de intervalos de 30 segundos (RFC 4226, sección
5.3), seis dígitos. Son los parámetros por omisión de las aplicaciones
autenticadoras (Google Authenticator, Microsoft Authenticator, FreeOTP), que
ignoran cualquier otro valor en el enlace `otpauth://`.

Este módulo solo calcula: no guarda nada ni sabe de usuarios. Las reglas
(un código no se acepta dos veces, bloqueo por intentos) están en
`segundo_factor.py`.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

INTERVALO_SEGUNDOS = 30
DIGITOS = 6
# Un intervalo antes y uno después: tolera el reloj desfasado del teléfono y
# el tiempo que tarda la persona en escribir el código (RFC 6238, sección 5.2).
TOLERANCIA_PASOS = 1
_BYTES_DEL_SECRETO = 20  # 160 bits, lo que recomienda el RFC 4226 (sección 4)


def generar_secreto() -> str:
    """Secreto aleatorio en base32 sin relleno, como lo leen las aplicaciones."""
    return base64.b32encode(secrets.token_bytes(_BYTES_DEL_SECRETO)).decode("ascii").rstrip("=")


def paso_en(momento: float | None = None) -> int:
    """Número de intervalo (T en el RFC 6238) que corresponde a un instante."""
    return int((time.time() if momento is None else momento) // INTERVALO_SEGUNDOS)


def _clave(secreto: str) -> bytes:
    limpio = secreto.strip().replace(" ", "").upper()
    return base64.b32decode(limpio + "=" * (-len(limpio) % 8))


def codigo_del_paso(secreto: str, paso: int) -> str:
    """HOTP del RFC 4226 con el contador igual al paso de tiempo."""
    resumen = hmac.new(_clave(secreto), struct.pack(">Q", paso), hashlib.sha1).digest()
    desplazamiento = resumen[-1] & 0x0F
    binario = struct.unpack(">I", resumen[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(binario % 10**DIGITOS).zfill(DIGITOS)


def paso_del_codigo(secreto: str, codigo: str, momento: float | None = None) -> int | None:
    """Paso de tiempo al que corresponde el código, o None si no vale.

    Devuelve el paso, y no un sí o un no, porque quien llama necesita
    recordarlo para no aceptar el mismo código otra vez (RFC 6238, sección
    5.2). Compara en tiempo constante.
    """
    codigo = (codigo or "").strip().replace(" ", "")
    if len(codigo) != DIGITOS or not codigo.isdigit() or not secreto:
        return None
    actual = paso_en(momento)
    for paso in range(actual - TOLERANCIA_PASOS, actual + TOLERANCIA_PASOS + 1):
        if hmac.compare_digest(codigo_del_paso(secreto, paso), codigo):
            return paso
    return None


def enlace_otpauth(secreto: str, *, cuenta: str, emisor: str) -> str:
    """Enlace que codifica el QR y que entienden las aplicaciones autenticadoras.

    Formato «Key Uri Format» publicado por Google para Authenticator, que es
    el que adoptaron las demás aplicaciones.
    """
    etiqueta = quote(f"{emisor}:{cuenta}")
    parametros = urlencode({"secret": secreto, "issuer": emisor, "algorithm": "SHA1",
                            "digits": DIGITOS, "period": INTERVALO_SEGUNDOS})
    return f"otpauth://totp/{etiqueta}?{parametros}"
