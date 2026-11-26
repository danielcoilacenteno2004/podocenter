"""Reglas de la verificación en dos pasos (RF18, RNF01).

Capa de aplicación del segundo factor: alta con confirmación, verificación
en el ingreso con bloqueo por intentos, códigos de recuperación y reinicio
por el administrador de plataforma. Las vistas no tocan los campos del
factor; pasan por aquí, que es donde queda la auditoría.

El secreto no sale de este módulo más que una vez, en la respuesta del alta,
para que la persona lo lleve a su aplicación. No se escribe en la auditoría
ni en el registro del servidor.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

import segno
from django.db import transaction
from django.utils import timezone

from apps.core.auditoria import registrar
from apps.core.contexto import contexto_actual, fijar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.errores import ReglaDeNegocio

from . import totp
from .models import CodigoRecuperacion, Usuario
from .roles import Rol

logger = logging.getLogger(__name__)

EMISOR = "PodoCenter"
CANTIDAD_DE_CODIGOS = 10
# Cinco intentos y quince minutos: un código de seis dígitos tiene un millón
# de valores y la ventana acepta tres a la vez, así que cinco intentos cada
# quince minutos dejan el ataque por fuerza bruta fuera de lo práctico, sin
# dejar a la administradora fuera toda la jornada por equivocarse al teclear.
# Valores elegidos por el equipo (ver docs/resultados_rf.json).
MAXIMO_DE_INTENTOS_FALLIDOS = 5
DURACION_DEL_BLOQUEO = timedelta(minutes=15)

# Sin 0/O ni 1/I/L, que se confunden al copiarlos de un papel.
_ALFABETO_DE_RECUPERACION = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_LARGO_DE_RECUPERACION = 10


# --- alta ---------------------------------------------------------------------

@transaction.atomic
def iniciar_alta(usuario: Usuario) -> dict:
    """Genera el secreto del alta y lo devuelve con su QR, una sola vez.

    Volver a llamar antes de confirmar genera otro secreto y deja sin efecto
    el anterior: si la persona cerró la pantalla sin escanear, empieza de
    nuevo. Con el factor ya activo no se entrega nada: el secreto en uso no
    vuelve a salir por la API.
    """
    if usuario.segundo_factor_activo:
        raise ReglaDeNegocio(
            "segundo-factor-ya-activo",
            "La verificación en dos pasos ya está activa en su cuenta.",
        )
    secreto = totp.generar_secreto()
    usuario.secreto_totp = secreto
    usuario.ultimo_paso_totp = None
    usuario.save(update_fields=["secreto_totp", "ultimo_paso_totp", "actualizado_en"])
    enlace = totp.enlace_otpauth(secreto, cuenta=usuario.correo, emisor=EMISOR)
    registrar("EDICION", "usuario", usuario.pk, {"segundo_factor": "alta-iniciada"})
    return {
        "secreto": secreto,
        "enlace": enlace,
        "qr": segno.make(enlace, error="m").svg_data_uri(scale=5, border=2),
    }


def confirmar_alta(usuario: Usuario, codigo: str) -> list[str]:
    """Activa el factor con un primer código válido y entrega los de recuperación.

    Pedir un código antes de activar demuestra que la aplicación quedó bien
    configurada: activar sin él dejaría fuera a quien escaneó mal el QR. Los
    diez códigos de recuperación se devuelven solo aquí, en claro; en la base
    queda su resumen.
    """
    with transaction.atomic():
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
        if usuario.segundo_factor_activo:
            raise ReglaDeNegocio(
                "segundo-factor-ya-activo",
                "La verificación en dos pasos ya está activa en su cuenta.",
            )
        if not usuario.secreto_totp:
            raise ReglaDeNegocio(
                "segundo-factor-sin-alta",
                "Primero genere el código QR y escanéelo con su aplicación.",
            )
        paso = totp.paso_del_codigo(usuario.secreto_totp, codigo)
        if paso is None:
            raise ReglaDeNegocio(
                "codigo-incorrecto",
                "El código no es correcto. Escriba el que muestra ahora su aplicación.",
            )
        usuario.segundo_factor_activo = True
        usuario.ultimo_paso_totp = paso
        usuario.intentos_fallidos_segundo_factor = 0
        usuario.segundo_factor_bloqueado_hasta = None
        usuario.save(update_fields=[
            "segundo_factor_activo", "ultimo_paso_totp", "intentos_fallidos_segundo_factor",
            "segundo_factor_bloqueado_hasta", "actualizado_en",
        ])
        codigos = _renovar_codigos_de_recuperacion(usuario)
        registrar("ALTA", "segundo_factor", usuario.pk,
                  {"codigos_de_recuperacion": len(codigos)})
    return codigos


# --- ingreso ------------------------------------------------------------------

def verificar_en_el_ingreso(usuario: Usuario, *, codigo: str = "",
                            codigo_recuperacion: str = "", ahora=None) -> str:
    """Segundo paso del ingreso. Devuelve el método usado o levanta el error.

    El contador de intentos se guarda antes de levantar el error, en su propia
    transacción: si se deshiciera junto con el error, el bloqueo no llegaría a
    actuar nunca. La fila del usuario se bloquea para que dos peticiones
    simultáneas no acepten el mismo código.
    """
    ahora = ahora or timezone.now()
    with transaction.atomic():
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
        if not usuario.segundo_factor_activo:
            return "sin-segundo-factor"
        bloqueado = usuario.segundo_factor_bloqueado_hasta
        if bloqueado and bloqueado > ahora:
            error = _error_de_bloqueo(bloqueado)
        else:
            metodo = _comprobar(usuario, codigo=codigo, codigo_recuperacion=codigo_recuperacion,
                                ahora=ahora)
            if metodo is not None:
                usuario.intentos_fallidos_segundo_factor = 0
                usuario.segundo_factor_bloqueado_hasta = None
                usuario.save(update_fields=[
                    "ultimo_paso_totp", "intentos_fallidos_segundo_factor",
                    "segundo_factor_bloqueado_hasta", "actualizado_en",
                ])
                return metodo
            error = _anotar_intento_fallido(usuario, ahora,
                                            por_recuperacion=bool(codigo_recuperacion))
    raise error


def _comprobar(usuario: Usuario, *, codigo: str, codigo_recuperacion: str, ahora) -> str | None:
    if codigo_recuperacion:
        return "recuperacion" if _usar_codigo_de_recuperacion(usuario, codigo_recuperacion,
                                                              ahora) else None
    paso = totp.paso_del_codigo(usuario.secreto_totp, codigo, momento=ahora.timestamp())
    # Un código ya aceptado, o uno anterior a él, no vuelve a valer aunque
    # siga dentro de su ventana de 30 segundos: quien lo vio por encima del
    # hombro no puede usarlo después.
    if paso is None or (usuario.ultimo_paso_totp is not None
                        and paso <= usuario.ultimo_paso_totp):
        return None
    usuario.ultimo_paso_totp = paso
    return "totp"


def _anotar_intento_fallido(usuario: Usuario, ahora, *, por_recuperacion: bool):
    usuario.intentos_fallidos_segundo_factor += 1
    if usuario.intentos_fallidos_segundo_factor >= MAXIMO_DE_INTENTOS_FALLIDOS:
        usuario.intentos_fallidos_segundo_factor = 0
        usuario.segundo_factor_bloqueado_hasta = ahora + DURACION_DEL_BLOQUEO
        error = _error_de_bloqueo(usuario.segundo_factor_bloqueado_hasta)
        _auditar_en_el_centro_de(usuario, "ACCESO_DENEGADO", "sesion", usuario.pk,
                                 {"motivo": "segundo-factor-bloqueado"})
    elif por_recuperacion:
        error = ReglaDeNegocio(
            "codigo-recuperacion-incorrecto",
            "El código de recuperación no es válido o ya se usó.",
        )
    else:
        error = ReglaDeNegocio(
            "codigo-incorrecto",
            "El código no es correcto. Escriba el que muestra ahora su aplicación.",
        )
    usuario.save(update_fields=[
        "intentos_fallidos_segundo_factor", "segundo_factor_bloqueado_hasta", "actualizado_en",
    ])
    return error


def _error_de_bloqueo(hasta) -> ReglaDeNegocio:
    return ReglaDeNegocio(
        "segundo-factor-bloqueado",
        "Demasiados códigos incorrectos. Vuelva a intentarlo después de las "
        f"{timezone.localtime(hasta):%H:%M}.",
    )


# --- códigos de recuperación --------------------------------------------------

def _normalizar(codigo: str) -> str:
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


def resumen_de_codigo(codigo: str, sal: str | None = None) -> str:
    """SHA-256 con sal propia por código.

    No se usa el hash lento de las contraseñas: cada código tiene unos 50
    bits de azar, no lo elige una persona, y comprobar diez con bcrypt haría
    esperar varios segundos en el ingreso. La sal impide reconocer dos
    códigos iguales en la tabla.
    """
    sal = sal or secrets.token_hex(8)
    valor = hashlib.sha256(f"{sal}:{_normalizar(codigo)}".encode()).hexdigest()
    return f"sha256${sal}${valor}"


def _coincide(codigo: str, resumen: str) -> bool:
    try:
        _, sal, _ = resumen.split("$", 2)
    except ValueError:
        return False
    return hmac.compare_digest(resumen_de_codigo(codigo, sal), resumen)


def _generar_codigo() -> str:
    crudo = "".join(secrets.choice(_ALFABETO_DE_RECUPERACION)
                    for _ in range(_LARGO_DE_RECUPERACION))
    mitad = _LARGO_DE_RECUPERACION // 2
    return f"{crudo[:mitad]}-{crudo[mitad:]}"


def _renovar_codigos_de_recuperacion(usuario: Usuario) -> list[str]:
    usuario.codigos_recuperacion.all().delete()
    codigos = [_generar_codigo() for _ in range(CANTIDAD_DE_CODIGOS)]
    CodigoRecuperacion.objects.bulk_create(
        [CodigoRecuperacion(usuario=usuario, resumen=resumen_de_codigo(c)) for c in codigos]
    )
    return codigos


def _usar_codigo_de_recuperacion(usuario: Usuario, codigo: str, ahora) -> bool:
    if len(_normalizar(codigo)) != _LARGO_DE_RECUPERACION:
        return False
    vigentes = usuario.codigos_recuperacion.select_for_update().filter(usado_en__isnull=True)
    for candidato in vigentes:
        if _coincide(codigo, candidato.resumen):
            candidato.usado_en = ahora
            candidato.save(update_fields=["usado_en", "actualizado_en"])
            return True
    return False


def codigos_de_recuperacion_vigentes(usuario: Usuario) -> int:
    return usuario.codigos_recuperacion.filter(usado_en__isnull=True).count()


# --- reinicio por la plataforma -----------------------------------------------

@transaction.atomic
def reiniciar_segundo_factor(usuario: Usuario, *, por: Usuario, motivo: str = "") -> Usuario:
    """Quita el factor de una cuenta para que vuelva a darlo de alta.

    Es el camino de quien perdió el teléfono y los códigos de recuperación.
    Solo lo hace el administrador de plataforma, que no pertenece a ningún
    centro: si lo pudiera hacer la administradora del centro, una sola
    cuenta comprometida bastaría para desactivar el factor de las demás.
    Para un rol en que el factor es opcional, reiniciar equivale a
    desactivarlo; en uno en que es obligatorio, la cuenta no puede hacer
    nada hasta volver a darlo de alta.
    """
    if por.rol != Rol.ADMIN_PLATAFORMA:
        raise ReglaDeNegocio(
            "reinicio-no-permitido",
            "Solo el administrador de plataforma puede reiniciar la verificación en dos pasos.",
        )
    if usuario.pk == por.pk:
        raise ReglaDeNegocio(
            "reiniciar-el-propio",
            "Otro administrador de plataforma debe reiniciar su verificación en dos pasos.",
        )
    usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
    estaba_activo = usuario.segundo_factor_activo
    usuario.segundo_factor_activo = False
    usuario.secreto_totp = ""
    usuario.ultimo_paso_totp = None
    usuario.intentos_fallidos_segundo_factor = 0
    usuario.segundo_factor_bloqueado_hasta = None
    usuario.save(update_fields=[
        "segundo_factor_activo", "secreto_totp", "ultimo_paso_totp",
        "intentos_fallidos_segundo_factor", "segundo_factor_bloqueado_hasta", "actualizado_en",
    ])
    usuario.codigos_recuperacion.all().delete()
    _auditar_en_el_centro_de(usuario, "BAJA", "segundo_factor", usuario.pk, {
        "reiniciado_por": por.pk, "estaba_activo": estaba_activo, "motivo": motivo[:200],
    })
    return usuario


def _auditar_en_el_centro_de(usuario: Usuario, accion, entidad, entidad_id, datos) -> None:
    """La bitácora es por centro. El administrador de plataforma no tiene
    centro: su reinicio queda en el registro del servidor (sin secretos)."""
    if usuario.centro_id is None:
        logger.warning("%s %s %s sin centro: %s", accion, entidad, entidad_id, datos)
        return
    anterior = contexto_actual()
    fijar_centro_en_la_sesion(usuario.centro_id)
    fijar_contexto(centro_id=usuario.centro_id, sede_id=anterior.sede_id,
                   usuario_id=anterior.usuario_id or usuario.pk)
    try:
        registrar(accion, entidad, entidad_id, datos)
    finally:
        fijar_centro_en_la_sesion(anterior.centro_id)
        fijar_contexto(centro_id=anterior.centro_id, sede_id=anterior.sede_id,
                       usuario_id=anterior.usuario_id)
