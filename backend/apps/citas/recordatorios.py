"""Recordatorios de cita al paciente por WhatsApp (RF07, CU15 y CU16).

Dos caminos con el mismo texto:

- Automático (CU15): `enviar_recordatorios` corre cada quince minutos y manda
  el recordatorio de las citas que empiezan en las próximas 24 horas. Sale por
  la API de WhatsApp Business solo cuando el centro tiene la cuenta aprobada
  por Meta y sus credenciales configuradas; mientras tanto, un proveedor
  simulado lo deja en el registro del servidor y en la tabla, sin enviar nada.
- Manual: el enlace «Recordar por WhatsApp» de la agenda abre WhatsApp con el
  mensaje escrito; lo envía la persona desde su teléfono.

En los dos, solo a pacientes con consentimiento vigente que acepte
recordatorios y con un celular registrado.
"""
import json
import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Cita, Recordatorio

logger = logging.getLogger(__name__)

ANTICIPACION = timedelta(hours=24)
MAXIMO_DE_INTENTOS = 3


def celular_internacional(telefono: str) -> str | None:
    """Celular peruano en formato internacional sin «+» (51 y nueve dígitos que
    empiezan en 9), que es el que esperan wa.me y la API. Un fijo o un número
    incompleto no sirve para WhatsApp: devuelve None."""
    digitos = re.sub(r"\D", "", telefono or "")
    if len(digitos) == 9 and digitos.startswith("9"):
        digitos = "51" + digitos
    if len(digitos) == 11 and digitos.startswith("519"):
        return digitos
    return None


def acepta_recordatorios(paciente) -> bool:
    consentimiento = paciente.consentimiento_vigente
    return bool(consentimiento and consentimiento.acepta_recordatorios)


def datos_del_mensaje(cita: Cita) -> dict:
    local = timezone.localtime(cita.inicio)
    centro = cita.centro
    return {
        "paciente": cita.paciente.nombres,
        "servicio": cita.servicio.nombre,
        "fecha": local.strftime("%d/%m/%Y"),
        "hora": local.strftime("%H:%M"),
        "centro": centro.nombre_comercial or centro.razon_social,
        "sede": f"{cita.sede.nombre}, {cita.sede.direccion}",
    }


def texto_del_recordatorio(cita: Cita) -> str:
    d = datos_del_mensaje(cita)
    return (f"Hola, {d['paciente']}. Le recordamos su cita de {d['servicio']} el {d['fecha']} "
            f"a las {d['hora']} en {d['centro']} ({d['sede']}). Si no podrá asistir, por favor "
            "avísenos respondiendo este mensaje.")


def enlace_whatsapp(cita: Cita) -> str | None:
    """Enlace wa.me con el mensaje escrito, o None si no corresponde.

    En la agenda el consentimiento llega anotado en la consulta
    (`acepta_recordatorios_vigente`), para no hacer una consulta por cita.
    """
    acepta = getattr(cita, "acepta_recordatorios_vigente", None)
    if acepta is None:
        acepta = acepta_recordatorios(cita.paciente)
    if cita.estado != Cita.Estado.PROGRAMADA or not acepta:
        return None
    celular = celular_internacional(cita.paciente.telefono)
    if celular is None:
        return None
    return f"https://wa.me/{celular}?text={quote(texto_del_recordatorio(cita))}"


# --- proveedores -------------------------------------------------------------

class ErrorDeEnvio(Exception):
    pass


class ProveedorSimulado:
    """Se usa mientras no haya credenciales: no envía nada, lo deja anotado."""

    nombre = "simulado"

    def enviar(self, *, destino: str, cita: Cita) -> str:
        logger.info("Recordatorio simulado a %s: %s", destino, texto_del_recordatorio(cita))
        return f"simulado-{uuid.uuid4()}"


class ProveedorWhatsAppCloud:
    """API de WhatsApp Business de Meta. Un mensaje que inicia el negocio debe
    usar una plantilla aprobada por Meta; la plantilla del centro recibe, en
    este orden, paciente, servicio, fecha, hora, centro y sede."""

    nombre = "whatsapp"

    def __init__(self):
        self.token = settings.WHATSAPP_TOKEN
        self.numero = settings.WHATSAPP_NUMERO_ID
        self.version = settings.WHATSAPP_VERSION_API
        self.plantilla = settings.WHATSAPP_PLANTILLA
        self.idioma = settings.WHATSAPP_IDIOMA

    def carga(self, *, destino: str, cita: Cita) -> dict:
        d = datos_del_mensaje(cita)
        parametros = [{"type": "text", "text": d[c]}
                      for c in ("paciente", "servicio", "fecha", "hora", "centro", "sede")]
        return {
            "messaging_product": "whatsapp",
            "to": destino,
            "type": "template",
            "template": {
                "name": self.plantilla,
                "language": {"code": self.idioma},
                "components": [{"type": "body", "parameters": parametros}],
            },
        }

    def enviar(self, *, destino: str, cita: Cita) -> str:
        if not all([self.numero, self.version, self.plantilla]):
            raise ErrorDeEnvio(
                "Falta WHATSAPP_NUMERO_ID, WHATSAPP_VERSION_API o WHATSAPP_PLANTILLA.")
        peticion = Request(
            f"https://graph.facebook.com/{self.version}/{self.numero}/messages",
            data=json.dumps(self.carga(destino=destino, cita=cita)).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            # La URL es fija y https: no hay esquema que venga de fuera.
            with urlopen(peticion, timeout=15) as respuesta:  # noqa: S310  # nosec B310
                cuerpo = json.loads(respuesta.read().decode("utf-8"))
        except Exception as error:  # red, HTTP 4xx/5xx o respuesta ilegible
            raise ErrorDeEnvio(str(error)[:300]) from error
        try:
            return cuerpo["messages"][0]["id"]
        except (KeyError, IndexError, TypeError) as error:
            raise ErrorDeEnvio(f"Respuesta inesperada: {str(cuerpo)[:250]}") from error


def proveedor():
    return ProveedorWhatsAppCloud() if settings.WHATSAPP_TOKEN else ProveedorSimulado()


# --- envío automático (CU15) -------------------------------------------------

def _citas_por_recordar(ahora):
    return (
        Cita.objects.filter(estado=Cita.Estado.PROGRAMADA, inicio__gt=ahora,
                            inicio__lte=ahora + ANTICIPACION)
        .exclude(recordatorio__estado__in=[Recordatorio.Estado.ENVIADO,
                                           Recordatorio.Estado.FALLIDO])
        .select_related("paciente", "servicio", "sede", "centro")
    )


def enviar_recordatorios(*, centro_id: int, ahora=None, enviador=None) -> dict:
    """Una pasada del temporizador para un centro. Devuelve el resumen.

    Cada cita va en su propia transacción y con su recordatorio bloqueado:
    dos pasadas simultáneas no mandan el mismo mensaje. Si el envío falla se
    reintenta en la pasada siguiente, y a la tercera queda como fallido,
    visible para el centro.
    """
    ahora = ahora or timezone.now()
    enviador = enviador or proveedor()
    resumen = {"enviados": 0, "fallidos": 0, "reintentar": 0, "omitidos": 0, "cancelados": 0}

    # CU09: cancelar o reprogramar una cita anula su recordatorio pendiente.
    resumen["cancelados"] = Recordatorio.objects.filter(
        centro_id=centro_id, estado=Recordatorio.Estado.PENDIENTE,
    ).exclude(cita__estado=Cita.Estado.PROGRAMADA).update(
        estado=Recordatorio.Estado.CANCELADO, actualizado_en=ahora)

    for cita in _citas_por_recordar(ahora).filter(centro_id=centro_id):
        destino = celular_internacional(cita.paciente.telefono)
        if destino is None or not acepta_recordatorios(cita.paciente):
            resumen["omitidos"] += 1  # CU15: sin canal autorizado se omite, sin error
            continue
        with transaction.atomic():
            recordatorio, _ = Recordatorio.objects.get_or_create(
                cita=cita, defaults={"centro_id": centro_id, "destino": destino})
            recordatorio = Recordatorio.objects.select_for_update(skip_locked=True).filter(
                pk=recordatorio.pk, estado=Recordatorio.Estado.PENDIENTE).first()
            if recordatorio is None:
                continue  # otra pasada lo tiene tomado o ya lo resolvió
            recordatorio.intentos += 1
            recordatorio.destino = destino
            try:
                recordatorio.id_externo = enviador.enviar(destino=destino, cita=cita)
                recordatorio.estado = Recordatorio.Estado.ENVIADO
                recordatorio.enviado_en = ahora
                recordatorio.ultimo_error = ""
                resumen["enviados"] += 1
            except ErrorDeEnvio as error:
                recordatorio.ultimo_error = str(error)[:300]
                if recordatorio.intentos >= MAXIMO_DE_INTENTOS:
                    recordatorio.estado = Recordatorio.Estado.FALLIDO
                    resumen["fallidos"] += 1
                else:
                    resumen["reintentar"] += 1
            recordatorio.save()
    return resumen
