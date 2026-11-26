"""Recordatorios de cita al paciente (RF07, CU15 y CU16).

Capa de aplicación del recordatorio. No sabe por dónde sale el mensaje: lo
decide la configuración de cada centro (`ConfiguracionRecordatorios`), y
el envío lo hace un `CanalRecordatorio` (ver `canales.py`).

- Automático (CU15): el comando `enviar_recordatorios`, que corre con el
  planificador del servidor, avisa de las citas del día siguiente a partir
  de la hora que fijó el centro. Una sola vez por cita; ante un fallo se
  reintenta en la pasada siguiente, hasta tres intentos, y un fallo no
  detiene el resto del lote.
- Manual: el enlace «Recordar por WhatsApp» de la agenda abre WhatsApp con
  el mensaje escrito; lo envía la persona desde su teléfono.

En los dos, solo a pacientes con consentimiento vigente que acepte
recordatorios y con un dato de contacto válido para el canal.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .canales import (
    CanalRecordatorio,
    CanalWhatsAppManual,
    ErrorDeEnvio,
    canal_para,
    celular_internacional,
    texto_del_recordatorio,
)
from .models import Cita, ConfiguracionRecordatorios, Recordatorio

__all__ = [
    "MAXIMO_DE_INTENTOS", "acepta_recordatorios", "actualizar_configuracion",
    "celular_internacional", "configuracion_del_centro", "enlace_whatsapp",
    "enviar_recordatorios", "pasada_del_planificador", "texto_del_recordatorio",
]

logger = logging.getLogger(__name__)

MAXIMO_DE_INTENTOS = 3  # lo sostiene también ck_recordatorio_maximo_tres_intentos
_MANUAL = CanalWhatsAppManual()


def acepta_recordatorios(paciente) -> bool:
    consentimiento = paciente.consentimiento_vigente
    return bool(consentimiento and consentimiento.acepta_recordatorios)


def enlace_whatsapp(cita: Cita) -> str | None:
    """Enlace wa.me con el mensaje escrito, o None si no corresponde.

    Es el canal manual, disponible en la agenda sea cual sea el canal
    automático del centro. En la agenda el consentimiento llega anotado en la
    consulta (`acepta_recordatorios_vigente`), para no hacer una consulta por
    cita.
    """
    acepta = getattr(cita, "acepta_recordatorios_vigente", None)
    if acepta is None:
        acepta = acepta_recordatorios(cita.paciente)
    if cita.estado != Cita.Estado.PROGRAMADA or not acepta:
        return None
    return _MANUAL.enlace(cita)


# --- configuración del centro --------------------------------------------------

def configuracion_del_centro(centro_id: int) -> ConfiguracionRecordatorios:
    """La del centro; si no tiene, la de fábrica (desactivada), sin guardarla."""
    return (ConfiguracionRecordatorios.objects.filter(centro_id=centro_id).first()
            or ConfiguracionRecordatorios(centro_id=centro_id))


@transaction.atomic
def actualizar_configuracion(*, centro_id: int, datos: dict) -> ConfiguracionRecordatorios:
    """La administradora activa, desactiva o cambia la hora y el canal.

    El WhatsApp automático no se puede elegir hasta que la Gerencia apruebe
    su costo (CC-28): su canal existe pero está vacío.
    """
    canal = datos.get("canal")
    if canal is not None and not canal_para(canal).disponible:
        raise ReglaDeNegocio(
            "canal-no-disponible",
            "El WhatsApp automático todavía no está habilitado. Elija correo o WhatsApp manual.",
        )
    configuracion, _ = ConfiguracionRecordatorios.objects.select_for_update().get_or_create(
        centro_id=centro_id)
    cambios = {}
    for campo in ("activo", "hora_envio", "canal"):
        if campo in datos and datos[campo] != getattr(configuracion, campo):
            setattr(configuracion, campo, datos[campo])
            cambios[campo] = str(datos[campo])
    configuracion.save()
    if cambios:
        registrar("EDICION", "configuracion_recordatorios", configuracion.pk, cambios)
    return configuracion


# --- envío automático (CU15) -------------------------------------------------------

def pasada_del_planificador(*, centro_id: int, ahora=None,
                            canal: CanalRecordatorio | None = None) -> dict:
    """Lo que hace el planificador por un centro en cada pasada.

    Corre varias veces al día (cada quince minutos en producción). Solo envía
    si el centro tiene los recordatorios activos, con un canal automático y
    disponible, y ya llegó su hora de envío; entonces avisa de las citas del
    día siguiente. Las pasadas posteriores de ese día solo recogen las citas
    agendadas después y los reintentos.
    """
    ahora = ahora or timezone.now()
    configuracion = configuracion_del_centro(centro_id)
    if not configuracion.activo:
        return {"motivo": "desactivado"}
    canal = canal or canal_para(configuracion.canal)
    if not canal.automatico:
        return {"motivo": "canal-manual"}
    if not canal.disponible:
        return {"motivo": "canal-no-disponible"}
    local = timezone.localtime(ahora)
    if local.time() < configuracion.hora_envio:
        return {"motivo": "antes-de-la-hora"}
    return enviar_recordatorios(centro_id=centro_id, fecha=local.date() + timedelta(days=1),
                                canal=canal, ahora=ahora)


def _citas_por_recordar(centro_id: int, fecha):
    inicio = timezone.make_aware(timezone.datetime.combine(fecha, timezone.datetime.min.time()))
    return (
        Cita.objects.filter(centro_id=centro_id, estado=Cita.Estado.PROGRAMADA,
                            inicio__gte=inicio, inicio__lt=inicio + timedelta(days=1))
        .exclude(recordatorio__estado__in=[Recordatorio.Estado.ENVIADO,
                                           Recordatorio.Estado.FALLIDO,
                                           Recordatorio.Estado.CANCELADO])
        .select_related("paciente", "servicio", "sede", "centro")
        .order_by("inicio")
    )


def enviar_recordatorios(*, centro_id: int, fecha, canal: CanalRecordatorio, ahora=None) -> dict:
    """Envía por `canal` el recordatorio de las citas programadas de `fecha`.

    Cada cita va en su propia transacción y con su recordatorio bloqueado:
    dos pasadas simultáneas no mandan el mismo mensaje, y la restricción
    única por cita impide un segundo registro. Cualquier error del canal se
    anota en ese recordatorio y el lote sigue con la cita siguiente.
    """
    ahora = ahora or timezone.now()
    resumen = {"enviados": 0, "fallidos": 0, "reintentar": 0, "omitidos": 0, "cancelados": 0}

    # CU09: cancelar o reprogramar una cita anula su recordatorio pendiente.
    resumen["cancelados"] = Recordatorio.objects.filter(
        centro_id=centro_id, estado=Recordatorio.Estado.PENDIENTE,
    ).exclude(cita__estado=Cita.Estado.PROGRAMADA).update(
        estado=Recordatorio.Estado.CANCELADO, actualizado_en=ahora)

    for cita in _citas_por_recordar(centro_id, fecha):
        destino = canal.destino(cita.paciente)
        if destino is None or not acepta_recordatorios(cita.paciente):
            resumen["omitidos"] += 1  # CU15: sin canal autorizado se omite, sin error
            continue
        resultado = _enviar_uno(cita, canal=canal, destino=destino, ahora=ahora)
        if resultado:
            resumen[resultado] += 1
    return resumen


def _enviar_uno(cita: Cita, *, canal: CanalRecordatorio, destino: str, ahora) -> str | None:
    with transaction.atomic():
        recordatorio, _ = Recordatorio.objects.get_or_create(
            cita=cita, defaults={"centro_id": cita.centro_id, "destino": destino,
                                 "canal": canal.codigo})
        recordatorio = Recordatorio.objects.select_for_update(skip_locked=True).filter(
            pk=recordatorio.pk, estado=Recordatorio.Estado.PENDIENTE).first()
        if recordatorio is None:
            return None  # otra pasada lo tiene tomado o ya lo resolvió
        recordatorio.intentos += 1
        recordatorio.destino = destino
        recordatorio.canal = canal.codigo
        try:
            recordatorio.id_externo = canal.enviar(destino=destino, cita=cita)
        except Exception as error:
            # ErrorDeEnvio es lo esperado; cualquier otra excepción del canal
            # tampoco puede cortar el lote: se anota y se sigue.
            if not isinstance(error, ErrorDeEnvio):
                logger.exception("Error inesperado del canal %s en la cita %s",
                                 canal.codigo, cita.pk)
            recordatorio.ultimo_error = (str(error) or error.__class__.__name__)[:300]
            agotado = recordatorio.intentos >= MAXIMO_DE_INTENTOS
            if agotado:
                recordatorio.estado = Recordatorio.Estado.FALLIDO
            recordatorio.save()
            return "fallidos" if agotado else "reintentar"
        recordatorio.estado = Recordatorio.Estado.ENVIADO
        recordatorio.enviado_en = ahora
        recordatorio.ultimo_error = ""
        recordatorio.save()
        return "enviados"
