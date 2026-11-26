"""Canales del recordatorio de cita (RF07): una interfaz, tres implementaciones.

El canal lo decide la Gerencia de cada centro, porque el WhatsApp
automático tiene un costo por mensaje (riesgo R9) que no se ha aprobado
(CC-28). Por eso el recordatorio no conoce el canal: pide a
`CanalRecordatorio` el destino del paciente y le entrega la cita, y el
centro elige cuál usar en su configuración.

- `CanalCorreo`: correo electrónico. En producción sale por Amazon SES, ya
  previsto en el diseño, a través del servidor SMTP de SES que se configura
  con las variables `EMAIL_*` (docs/DESPLIEGUE.md); sin ellas, Django usa el
  servidor de correo local.
- `CanalWhatsAppManual`: el botón «Recordar por WhatsApp» de la agenda, que
  abre WhatsApp con el mensaje escrito; lo envía una persona desde su
  teléfono. No es automático: el planificador no lo usa.
- `CanalWhatsAppApi`: el envío automático por la API de WhatsApp Business.
  Vacío a propósito, hasta que la Gerencia apruebe el costo (CC-28).
"""
import re
import uuid
from abc import ABC, abstractmethod
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.utils import timezone


class ErrorDeEnvio(Exception):
    """El canal no pudo entregar el mensaje; el recordatorio se reintenta."""


class CanalNoDisponible(ErrorDeEnvio):
    """El canal existe en el diseño pero no está habilitado."""


def datos_del_mensaje(cita) -> dict:
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


def texto_del_recordatorio(cita) -> str:
    """El mismo texto en todos los canales: lo que el paciente lee no
    depende de por dónde le llegó."""
    d = datos_del_mensaje(cita)
    return (f"Hola, {d['paciente']}. Le recordamos su cita de {d['servicio']} el {d['fecha']} "
            f"a las {d['hora']} en {d['centro']} ({d['sede']}). Si no podrá asistir, por favor "
            "avísenos respondiendo este mensaje.")


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


class CanalRecordatorio(ABC):
    """Lo que el recordatorio necesita de un canal, sea cual sea."""

    codigo: str
    nombre: str
    # Si el planificador puede usarlo sin una persona de por medio.
    automatico: bool
    # Si un centro puede elegirlo hoy.
    disponible: bool = True

    @abstractmethod
    def destino(self, paciente) -> str | None:
        """Dato de contacto válido para este canal, o None si no tiene."""

    @abstractmethod
    def enviar(self, *, destino: str, cita) -> str:
        """Entrega el mensaje y devuelve un identificador para el registro.

        Levanta `ErrorDeEnvio` si no pudo; el recordatorio se reintenta.
        """


class CanalCorreo(CanalRecordatorio):
    codigo = "CORREO"
    nombre = "Correo electrónico"
    automatico = True

    def destino(self, paciente) -> str | None:
        correo = (paciente.correo or "").strip()
        try:
            validate_email(correo)
        except ValidationError:
            return None
        return correo

    def enviar(self, *, destino: str, cita) -> str:
        d = datos_del_mensaje(cita)
        identificador = f"<{uuid.uuid4()}@podocenter>"
        mensaje = EmailMessage(
            subject=f"Recordatorio de su cita en {d['centro']}",
            body=texto_del_recordatorio(cita),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destino],
            # La respuesta del paciente llega al centro, no a la plataforma.
            reply_to=[cita.centro.correo_contacto] if cita.centro.correo_contacto else None,
            headers={"Message-ID": identificador},
        )
        try:
            mensaje.send(fail_silently=False)
        except Exception as error:  # SMTP, red o credenciales de SES
            raise ErrorDeEnvio(str(error)[:300] or error.__class__.__name__) from error
        return identificador


class CanalWhatsAppManual(CanalRecordatorio):
    codigo = "WHATSAPP_MANUAL"
    nombre = "WhatsApp (envío manual desde la agenda)"
    automatico = False

    def destino(self, paciente) -> str | None:
        return celular_internacional(paciente.telefono)

    def enlace(self, cita) -> str | None:
        celular = self.destino(cita.paciente)
        if celular is None:
            return None
        return f"https://wa.me/{celular}?text={quote(texto_del_recordatorio(cita))}"

    def enviar(self, *, destino: str, cita) -> str:
        raise CanalNoDisponible(
            "El WhatsApp manual lo envía una persona desde la agenda, no el planificador.")


class CanalWhatsAppApi(CanalRecordatorio):
    """Envío automático por la API de WhatsApp Business de Meta. VACÍO.

    No se implementa hasta que la Gerencia apruebe el costo por mensaje
    (CC-28, riesgo R9). Lo que hará falta cuando se apruebe:

    - una cuenta de WhatsApp Business aprobada por Meta y una plantilla de
      mensaje aprobada (un mensaje que inicia el negocio debe usarla), con los
      datos de `datos_del_mensaje` como parámetros;
    - las credenciales por variable de entorno (`WHATSAPP_*`, ya declaradas
      en la configuración), nunca en el repositorio;
    - una implementación anterior, contra la API de Meta, quedó en el
      historial: `backend/apps/citas/recordatorios.py` en el commit 08b32bc
      (`ProveedorWhatsAppCloud`). Se retiró del flujo al introducir esta
      interfaz para que nada pueda enviar por este canal sin la aprobación.

    Mientras tanto no se puede elegir en la configuración del centro
    (`canal-no-disponible`) y, si llegara a estar elegido, el planificador lo
    salta sin intentar nada.
    """

    codigo = "WHATSAPP_API"
    nombre = "WhatsApp automático (pendiente de aprobación, CC-28)"
    automatico = True
    disponible = False

    def destino(self, paciente) -> str | None:
        return celular_internacional(paciente.telefono)

    def enviar(self, *, destino: str, cita) -> str:
        raise CanalNoDisponible(
            "El envío automático por WhatsApp no está habilitado (pendiente de CC-28).")


CANALES: dict[str, CanalRecordatorio] = {
    canal.codigo: canal for canal in (CanalCorreo(), CanalWhatsAppManual(), CanalWhatsAppApi())
}


def canal_para(codigo: str) -> CanalRecordatorio:
    return CANALES[codigo]
