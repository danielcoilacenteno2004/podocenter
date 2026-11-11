"""Reglas de aplicación del módulo de usuarios.

Las vistas no escriben en los modelos directamente: pasan por estas
funciones, que son las que conocen las reglas y dejan la auditoría.
"""
import secrets

from django.db import transaction

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import AsignacionSede, Usuario
from .roles import ROLES_DE_CENTRO, Rol


@transaction.atomic
def crear_usuario(*, centro, correo, nombres, apellidos, rol, sedes_ids, password=None) -> Usuario:
    """Da de alta un usuario del centro y lo asigna a sus sedes (CU01)."""
    if rol == Rol.ADMIN_PLATAFORMA:
        raise ReglaDeNegocio(
            "rol-no-permitido",
            "El administrador de plataforma no se crea desde un centro.",
        )
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise ReglaDeNegocio("correo-duplicado", "Ya existe un usuario con ese correo.")
    if rol in ROLES_DE_CENTRO and not sedes_ids:
        raise ReglaDeNegocio(
            "sin-sede", "Un usuario del centro debe tener al menos una sede asignada."
        )

    usuario = Usuario.objects.create_user(
        correo=correo,
        password=password or secrets.token_urlsafe(16),
        nombres=nombres,
        apellidos=apellidos,
        rol=rol,
        centro=centro,
    )
    for indice, sede_id in enumerate(sedes_ids):
        AsignacionSede.objects.create(
            usuario=usuario, sede_id=sede_id, es_predeterminada=(indice == 0)
        )
    registrar("ALTA", "usuario", usuario.pk, {"rol": rol, "sedes": list(sedes_ids)})
    return usuario


@transaction.atomic
def desactivar_usuario(usuario: Usuario) -> Usuario:
    """Baja lógica: el histórico de atenciones debe seguir siendo trazable."""
    if usuario.rol == Rol.ADMIN_CENTRO:
        quedan = (
            Usuario.objects.filter(centro=usuario.centro, rol=Rol.ADMIN_CENTRO, esta_activo=True)
            .exclude(pk=usuario.pk)
            .count()
        )
        if quedan == 0:
            raise ReglaDeNegocio(
                "ultimo-administrador",
                "El centro quedaría sin administrador. Designe otro antes de desactivar este.",
            )
    usuario.esta_activo = False
    usuario.save(update_fields=["esta_activo", "actualizado_en"])
    registrar("BAJA", "usuario", usuario.pk)
    return usuario


def profesionales_de_la_sede(*, centro_id: int, sede_id: int):
    """Quién puede atender una cita en la sede (lista de P06).

    Es la misma condición que exige `programar_cita` a la profesional
    (`puede_usar_sede`): cuenta activa y asignación vigente a la sede. Así la
    pantalla no ofrece nunca a alguien que el servidor rechazaría.
    """
    return (
        Usuario.objects.filter(
            centro_id=centro_id, esta_activo=True,
            asignaciones__sede_id=sede_id, asignaciones__esta_activa=True,
        )
        .distinct()
        .order_by("apellidos", "nombres")
    )


def sedes_disponibles(usuario: Usuario):
    """Sedes entre las que el usuario puede elegir al iniciar sesión (P03)."""
    return usuario.asignaciones.filter(
        esta_activa=True, sede__esta_activa=True
    ).select_related("sede")
