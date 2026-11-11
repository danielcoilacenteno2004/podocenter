"""Reglas de aplicación de los centros clientes (RF17, CU18)."""
import secrets

from django.db import transaction

from apps.core.auditoria import registrar
from apps.core.contexto import fijar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.errores import ReglaDeNegocio
from apps.core.models import Centro
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol


@transaction.atomic
def crear_centro(*, datos: dict, administrador: dict, usuario) -> tuple[Centro, Usuario, str]:
    """Da de alta un centro cliente con su administrador inicial (P29).

    Un centro sin administrador no se puede usar: solo un administrador del
    propio centro puede dar de alta a su personal. Por eso los dos se crean
    en la misma transacción: si el administrador no se puede crear, tampoco
    queda el centro.

    El diseño envía al administrador un enlace para definir su contraseña
    (P24), que no existe todavía. Mientras tanto se genera una contraseña
    temporal fuerte que se devuelve una sola vez, en esta respuesta; no se
    guarda en claro en ningún sitio y el administrador la cambia en P20.

    El administrador nace sin sedes, porque el centro todavía no tiene
    ninguna: es la excepción a «al menos una sede» de crear_usuario.
    """
    correo = administrador["correo"].strip().lower()
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise ReglaDeNegocio("correo-duplicado", "Ya existe un usuario con ese correo.")

    centro = Centro.objects.create(**datos)
    temporal = secrets.token_urlsafe(12)
    admin = Usuario.objects.create_user(
        correo=correo, password=temporal, nombres=administrador["nombres"],
        apellidos=administrador["apellidos"], rol=Rol.ADMIN_CENTRO, centro=centro,
    )
    _auditar_en(centro, usuario, [
        ("ALTA", "centro", centro.pk, {"ruc": centro.ruc}),
        ("ALTA", "usuario", admin.pk, {"rol": Rol.ADMIN_CENTRO, "inicial": True}),
    ])
    return centro, admin, temporal


def registrar_cambio_de_centro(centro: Centro, usuario, cambios: dict) -> None:
    """Deja en la bitácora del centro un cambio hecho desde la plataforma."""
    _auditar_en(centro, usuario, [("EDICION", "centro", centro.pk, cambios)])


def _auditar_en(centro: Centro, usuario, registros) -> None:
    """La bitácora es por centro: se escribe bajo el centro afectado y se
    deja la conexión sin centro, como estaba la petición de plataforma."""
    fijar_centro_en_la_sesion(centro.pk)
    fijar_contexto(centro_id=centro.pk, usuario_id=usuario.pk)
    try:
        for accion, entidad, entidad_id, datos in registros:
            registrar(accion, entidad, entidad_id, datos)
    finally:
        fijar_centro_en_la_sesion(None)
        fijar_contexto(centro_id=None, usuario_id=usuario.pk)
