"""Reglas de aplicación del módulo de usuarios.

Las vistas no escriben en los modelos directamente: pasan por estas
funciones, que son las que conocen las reglas y dejan la auditoría.
"""
import secrets

from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import AsignacionSede, Usuario
from .roles import ROLES_DE_CENTRO, Rol


def contrasena_temporal() -> str:
    """Contraseña de un solo uso que la administradora entrega en persona.

    Mientras no exista el correo de activación (P24), es la forma de que una
    cuenta nueva pueda entrar. No se guarda en claro en ningún sitio.
    """
    return secrets.token_urlsafe(12)


@transaction.atomic
def crear_usuario(*, centro, correo, nombres, apellidos, rol, sedes_ids, password=None) -> Usuario:
    """Da de alta un usuario del centro y lo asigna a sus sedes (CU01).

    Sin `password`, la cuenta nace con una contraseña temporal que se deja en
    `usuario.contrasena_temporal` para que la vista la devuelva una sola vez,
    y con la obligación de cambiarla al entrar.
    """
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
    _sedes_del_centro(centro.pk, sedes_ids)

    temporal = None if password else contrasena_temporal()
    usuario = Usuario.objects.create_user(
        correo=correo,
        password=password or temporal,
        nombres=nombres,
        apellidos=apellidos,
        rol=rol,
        centro=centro,
        debe_cambiar_contrasena=temporal is not None,
    )
    usuario.contrasena_temporal = temporal
    for indice, sede_id in enumerate(sedes_ids):
        AsignacionSede.objects.create(
            usuario=usuario, sede_id=sede_id, es_predeterminada=(indice == 0)
        )
    registrar("ALTA", "usuario", usuario.pk, {"rol": rol, "sedes": list(sedes_ids)})
    return usuario


def _sedes_del_centro(centro_id: int, sedes_ids) -> None:
    """La clave foránea no mira el centro: sin esto se podía asignar a un
    usuario una sede de otro centro pasando su identificador."""
    from apps.sedes.models import Sede

    propias = Sede.objects.filter(centro_id=centro_id, pk__in=set(sedes_ids)).count()
    if propias != len(set(sedes_ids)):
        raise ReglaDeNegocio("sede-fuera-del-centro", "Alguna de las sedes no es de este centro.")


def _quedaria_sin_administrador(usuario: Usuario) -> bool:
    if usuario.rol != Rol.ADMIN_CENTRO or not usuario.esta_activo:
        return False
    return not (
        Usuario.objects.filter(centro=usuario.centro, rol=Rol.ADMIN_CENTRO, esta_activo=True)
        .exclude(pk=usuario.pk)
        .exists()
    )


@transaction.atomic
def actualizar_usuario(usuario: Usuario, *, datos: dict, sedes_ids=None) -> Usuario:
    """Edición de un usuario del centro (P27): datos, rol y sedes.

    Activar y desactivar tienen sus propias rutas. Aquí se aplican las mismas
    reglas que en el alta (correo único, rol permitido, al menos una sede de
    este centro) y la del último administrador: quitarle el rol a la única
    administradora dejaría al centro sin nadie que gestione a su personal.
    """
    # Bloquea a las administradoras del centro: dos ediciones simultáneas no
    # pueden quitarse el rol la una a la otra y dejar el centro sin ninguna.
    list(Usuario.objects.select_for_update().filter(centro=usuario.centro,
                                                    rol=Rol.ADMIN_CENTRO))
    correo = datos.get("correo")
    if correo and Usuario.objects.filter(correo__iexact=correo).exclude(pk=usuario.pk).exists():
        raise ReglaDeNegocio("correo-duplicado", "Ya existe un usuario con ese correo.")
    rol = datos.get("rol", usuario.rol)
    if rol == Rol.ADMIN_PLATAFORMA:
        raise ReglaDeNegocio(
            "rol-no-permitido", "El administrador de plataforma no se crea desde un centro."
        )
    if rol != usuario.rol and _quedaria_sin_administrador(usuario):
        raise ReglaDeNegocio(
            "ultimo-administrador",
            "El centro quedaría sin administrador. Designe otro antes de cambiar este rol.",
        )

    cambios = {}
    for campo in ("nombres", "apellidos", "correo", "rol"):
        if campo in datos and datos[campo] != getattr(usuario, campo):
            cambios[campo] = datos[campo]
            setattr(usuario, campo, datos[campo])
    usuario.save()

    if sedes_ids is not None:
        if not sedes_ids:
            raise ReglaDeNegocio(
                "sin-sede", "Un usuario del centro debe tener al menos una sede asignada."
            )
        _sedes_del_centro(usuario.centro_id, sedes_ids)
        _reasignar_sedes(usuario, list(dict.fromkeys(sedes_ids)))
        cambios["sedes"] = list(dict.fromkeys(sedes_ids))

    if cambios:
        registrar("EDICION", "usuario", usuario.pk, cambios)
    return usuario


def _reasignar_sedes(usuario: Usuario, sedes_ids: list[int]) -> None:
    """Deja vigentes exactamente esas sedes. Las retiradas se desactivan,
    no se borran: la asignación explica en qué sede trabajó la persona."""
    from .models import AsignacionSede

    usuario.asignaciones.exclude(sede_id__in=sedes_ids).update(
        esta_activa=False, es_predeterminada=False
    )
    for sede_id in sedes_ids:
        AsignacionSede.objects.update_or_create(
            usuario=usuario, sede_id=sede_id, defaults={"esta_activa": True}
        )
    vigentes = usuario.asignaciones.filter(esta_activa=True)
    if not vigentes.filter(es_predeterminada=True).exists():
        vigentes.filter(sede_id=sedes_ids[0]).update(es_predeterminada=True)


@transaction.atomic
def desactivar_usuario(usuario: Usuario) -> Usuario:
    """Baja lógica: el histórico de atenciones debe seguir siendo trazable."""
    if _quedaria_sin_administrador(usuario):
        raise ReglaDeNegocio(
            "ultimo-administrador",
            "El centro quedaría sin administrador. Designe otro antes de desactivar este.",
        )
    usuario.esta_activo = False
    usuario.save(update_fields=["esta_activo", "actualizado_en"])
    registrar("BAJA", "usuario", usuario.pk)
    return usuario


@transaction.atomic
def restablecer_contrasena(usuario: Usuario, *, por: Usuario) -> str:
    """La administradora da una contraseña temporal nueva a otra cuenta.

    Es el camino para quien olvidó la suya mientras no exista la
    recuperación por correo (P23/P24). Cambiar la contraseña cambia el hash
    de sesión, así que las sesiones abiertas de esa cuenta dejan de valer.
    La propia contraseña se cambia en P20, que pide la actual.
    """
    if usuario.pk == por.pk:
        raise ReglaDeNegocio(
            "restablecer-la-propia",
            "Su propia contraseña se cambia desde «Mi perfil».",
        )
    temporal = contrasena_temporal()
    usuario.set_password(temporal)
    usuario.debe_cambiar_contrasena = True
    # Es también la salida para una cuenta bloqueada por intentos fallidos: con
    # la contraseña nueva, el bloqueo ya no protege nada.
    usuario.intentos_fallidos_ingreso = 0
    usuario.ingreso_bloqueado_hasta = None
    usuario.save(update_fields=["password", "debe_cambiar_contrasena", "intentos_fallidos_ingreso",
                                "ingreso_bloqueado_hasta", "actualizado_en"])
    registrar("EDICION", "usuario", usuario.pk, {"contrasena": "restablecida"})
    return temporal


@transaction.atomic
def cambiar_contrasena(usuario: Usuario, *, actual: str, nueva: str, confirmacion: str) -> Usuario:
    """El usuario cambia su propia contraseña (P20, RF18).

    Se apoya en `PasswordChangeForm` de Django: comprueba la contraseña
    actual y aplica los validadores de AUTH_PASSWORD_VALIDATORS (mínimo 10
    caracteres, no parecida a los datos del usuario, no común, no solo
    números), así que la política vive en un solo lugar. La auditoría no
    guarda ninguna de las contraseñas.
    """
    formulario = PasswordChangeForm(usuario, data={
        "old_password": actual, "new_password1": nueva, "new_password2": confirmacion,
    })
    if not formulario.is_valid():
        errores = formulario.errors
        if "old_password" in errores:
            raise ReglaDeNegocio(
                "contrasena-actual-incorrecta", "La contraseña actual no es correcta."
            )
        # Coincidencia y política: errores de forma, por campo, como el resto
        # de validaciones de la API (400).
        mensajes = [str(m) for m in errores.get("new_password2", [])]
        mensajes = mensajes or [str(m) for lista in errores.values() for m in lista]
        raise ValidationError({"contrasena_nueva": mensajes})
    formulario.save()
    if usuario.debe_cambiar_contrasena:
        usuario.debe_cambiar_contrasena = False
        usuario.save(update_fields=["debe_cambiar_contrasena", "actualizado_en"])
    registrar("EDICION", "usuario", usuario.pk, {"contrasena": "cambiada"})
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
