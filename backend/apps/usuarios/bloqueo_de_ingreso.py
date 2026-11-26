"""Bloqueo temporal de la cuenta tras intentos fallidos de contraseña (RNF01, CU02).

La Tabla 35 del Informe fija la regla: al quinto intento fallido seguido, la
cuenta queda bloqueada 15 minutos, y durante ese tiempo no entra ni con la
contraseña correcta. Sin esto, una contraseña se puede adivinar probando sin
límite (OWASP A07, DEF-25 de la Práctica N.° 9).

Solo se cuentan los intentos contra cuentas que existen. Un correo que no
existe responde siempre 401, como una contraseña errada: el bloqueo no puede
servir para averiguar qué correos están registrados, salvo después de cinco
fallos contra una cuenta real, que es lo que la regla pide avisar.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.errores import ReglaDeNegocio

from .models import Usuario
from .segundo_factor import _auditar_en_el_centro_de

MAXIMO_DE_INTENTOS_FALLIDOS = 5
DURACION_DEL_BLOQUEO = timedelta(minutes=15)


def _cuenta(correo: str) -> Usuario | None:
    return Usuario.objects.filter(correo=correo).first()


def _error(hasta) -> ReglaDeNegocio:
    return ReglaDeNegocio(
        "ingreso-bloqueado",
        "La cuenta está bloqueada por demasiados intentos fallidos. Vuelva a intentarlo "
        f"después de las {timezone.localtime(hasta):%H:%M} o pida a la administradora que "
        "le dé una contraseña temporal.",
    )


def comprobar(correo: str, *, ahora=None) -> None:
    """Rechaza el ingreso de una cuenta bloqueada antes de mirar la contraseña."""
    ahora = ahora or timezone.now()
    cuenta = _cuenta(correo)
    if cuenta and cuenta.ingreso_bloqueado_hasta and cuenta.ingreso_bloqueado_hasta > ahora:
        raise _error(cuenta.ingreso_bloqueado_hasta)


def anotar_fallo(correo: str, *, ahora=None) -> None:
    """Suma un intento fallido y, al quinto, bloquea la cuenta y lo dice.

    El contador se guarda en su propia transacción y con la fila bloqueada:
    si se deshiciera junto con el error, el bloqueo no actuaría nunca, y dos
    intentos simultáneos no deben leer el mismo contador.
    """
    ahora = ahora or timezone.now()
    with transaction.atomic():
        cuenta = Usuario.objects.select_for_update().filter(correo=correo).first()
        if cuenta is None:
            return
        cuenta.intentos_fallidos_ingreso += 1
        bloquea = cuenta.intentos_fallidos_ingreso >= MAXIMO_DE_INTENTOS_FALLIDOS
        if bloquea:
            cuenta.intentos_fallidos_ingreso = 0
            cuenta.ingreso_bloqueado_hasta = ahora + DURACION_DEL_BLOQUEO
        cuenta.save(update_fields=[
            "intentos_fallidos_ingreso", "ingreso_bloqueado_hasta", "actualizado_en",
        ])
    if bloquea:
        _auditar_en_el_centro_de(cuenta, "ACCESO_DENEGADO", "sesion", cuenta.pk,
                                 {"motivo": "ingreso-bloqueado"})
        raise _error(cuenta.ingreso_bloqueado_hasta)


def levantar(usuario: Usuario) -> None:
    """Deja la cuenta sin intentos ni bloqueo: tras un ingreso correcto o una
    contraseña temporal nueva."""
    if usuario.intentos_fallidos_ingreso or usuario.ingreso_bloqueado_hasta:
        usuario.intentos_fallidos_ingreso = 0
        usuario.ingreso_bloqueado_hasta = None
        usuario.save(update_fields=[
            "intentos_fallidos_ingreso", "ingreso_bloqueado_hasta", "actualizado_en",
        ])
