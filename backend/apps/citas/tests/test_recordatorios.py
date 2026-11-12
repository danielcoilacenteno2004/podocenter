"""Recordatorios de cita por WhatsApp (RF07; CU15 del informe).

El envío real necesita la cuenta de WhatsApp Business aprobada por Meta. Aquí
se prueba todo lo demás con un proveedor de prueba: qué citas se recuerdan,
que un reintento no duplica, los tres intentos y la cancelación.
"""
import json
from datetime import timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.citas.models import Cita, Recordatorio
from apps.citas.recordatorios import (
    ErrorDeEnvio,
    ProveedorSimulado,
    ProveedorWhatsAppCloud,
    celular_internacional,
    enviar_recordatorios,
    proveedor,
)
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.soporte_pruebas import activar_centro
from apps.pacientes.servicios import revocar_consentimiento


class ProveedorDePrueba:
    nombre = "prueba"

    def __init__(self, fallar=False):
        self.fallar = fallar
        self.enviados = []

    def enviar(self, *, destino, cita):
        if self.fallar:
            raise ErrorDeEnvio("proveedor caído")
        self.enviados.append((destino, cita.pk))
        return f"wamid.{len(self.enviados)}"


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    return programar_cita(centro=centro, usuario=podologa, sede=sede, paciente=paciente,
                          profesional=podologa, servicio=servicio,
                          inicio=proximo_lunes_a_las_nueve)


def _un_dia_antes(cita):
    """El temporizador corriendo 20 horas antes de la cita."""
    return cita.inicio - timedelta(hours=20)


@pytest.mark.parametrize("telefono, esperado", [
    ("958111222", "51958111222"), ("+51 958 111 222", "51958111222"),
    ("054-281940", None), ("95811", None), ("", None),
])
def test_solo_un_celular_peruano_sirve_como_destino(telefono, esperado):
    # Garantiza que no se intenta mandar un WhatsApp a un teléfono fijo o
    # incompleto: el proveedor lo rechazaría y el intento se perdería.
    assert celular_internacional(telefono) == esperado


@pytest.mark.django_db
def test_se_envia_una_vez_dentro_de_las_24_horas_y_queda_su_estado(centro, cita):
    # Garantiza el CU15: la cita a menos de 24 horas recibe su recordatorio,
    # se guarda lo que devolvió el proveedor, y una segunda pasada del
    # temporizador no lo vuelve a enviar.
    enviador = ProveedorDePrueba()

    primera = enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita),
                                   enviador=enviador)
    segunda = enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita),
                                   enviador=enviador)

    recordatorio = Recordatorio.objects.get(cita=cita)
    assert (primera["enviados"], segunda["enviados"]) == (1, 0)
    assert enviador.enviados == [("51958111222", cita.pk)]
    assert (recordatorio.estado, recordatorio.id_externo) == ("ENVIADO", "wamid.1")


@pytest.mark.django_db
def test_una_cita_a_mas_de_24_horas_todavia_no_se_recuerda(centro, cita):
    # Garantiza que el recordatorio llega «24 horas antes» (RF07), no al
    # agendar una cita para dentro de una semana.
    enviador = ProveedorDePrueba()

    enviar_recordatorios(centro_id=centro.pk, ahora=cita.inicio - timedelta(hours=30),
                         enviador=enviador)

    assert enviador.enviados == []


@pytest.mark.django_db
def test_sin_consentimiento_para_recordatorios_se_omite_sin_error(centro, podologa, cita):
    # Garantiza la Ley N.° 29733 en la práctica: si el paciente retiró su
    # consentimiento, no se le escribe, y eso no cuenta como fallo.
    revocar_consentimiento(cita.paciente)
    enviador = ProveedorDePrueba()

    resumen = enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita),
                                   enviador=enviador)

    assert (resumen["omitidos"], enviador.enviados) == (1, [])
    assert not Recordatorio.objects.exists()


@pytest.mark.django_db
def test_tres_envios_fallidos_lo_marcan_fallido_y_no_insiste(centro, cita):
    # Garantiza el flujo alternativo del CU15: se reintenta hasta tres veces y
    # después queda como fallido, visible para el centro, sin insistir.
    enviador = ProveedorDePrueba(fallar=True)
    for _ in range(4):
        enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita), enviador=enviador)

    recordatorio = Recordatorio.objects.get(cita=cita)
    assert (recordatorio.estado, recordatorio.intentos) == ("FALLIDO", 3)
    assert recordatorio.ultimo_error == "proveedor caído"


@pytest.mark.django_db
def test_cancelar_la_cita_anula_el_recordatorio_pendiente(centro, cita):
    # Garantiza el CU09: tras cancelar, el paciente no recibe un recordatorio
    # de una cita que ya no existe.
    enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita),
                         enviador=ProveedorDePrueba(fallar=True))
    cancelar_cita(cita=cita, motivo="El paciente avisó que no viene")
    enviador = ProveedorDePrueba()

    enviar_recordatorios(centro_id=centro.pk, ahora=_un_dia_antes(cita), enviador=enviador)

    assert Recordatorio.objects.get(cita=cita).estado == "CANCELADO"
    assert enviador.enviados == []


@pytest.mark.django_db
def test_sin_credenciales_el_envio_es_simulado(centro, cita):
    # Garantiza que, mientras Meta no apruebe la cuenta, el temporizador puede
    # correr sin mandar nada a nadie.
    assert isinstance(proveedor(), ProveedorSimulado)

    with mock.patch("apps.citas.recordatorios.timezone.now", return_value=_un_dia_antes(cita)):
        call_command("enviar_recordatorios", verbosity=0)
    activar_centro(centro.pk)  # el comando deja la conexión sin centro, como debe

    assert Recordatorio.objects.get(cita=cita).id_externo.startswith("simulado-")


@pytest.mark.django_db
@override_settings(WHATSAPP_TOKEN="t",  # noqa: S106  # nosec B106
                   WHATSAPP_NUMERO_ID="123", WHATSAPP_VERSION_API="vX",
                   WHATSAPP_PLANTILLA="recordatorio_cita", WHATSAPP_IDIOMA="es")
def test_con_credenciales_usa_una_plantilla_con_los_datos_de_la_cita(cita):
    # Garantiza la forma del pedido a la API de WhatsApp Business: un mensaje
    # que inicia el negocio debe ser una plantilla aprobada, con sus datos.
    enviador = proveedor()
    respuesta = mock.MagicMock()
    respuesta.__enter__.return_value.read.return_value = b'{"messages": [{"id": "wamid.X"}]}'

    with mock.patch("apps.citas.recordatorios.urlopen", return_value=respuesta) as abrir:
        identificador = enviador.enviar(destino="51958111222", cita=cita)

    peticion = abrir.call_args.args[0]
    cuerpo = json.loads(peticion.data)
    assert isinstance(enviador, ProveedorWhatsAppCloud)
    assert identificador == "wamid.X"
    assert peticion.full_url == "https://graph.facebook.com/vX/123/messages"
    assert cuerpo["template"]["name"] == "recordatorio_cita"
    assert cuerpo["template"]["components"][0]["parameters"][0]["text"] == "Carmen"


@pytest.mark.django_db
def test_la_agenda_trae_el_enlace_de_whatsapp_con_el_mensaje(podologa, sede, cita):
    # Garantiza el camino manual: la agenda ofrece abrir WhatsApp con el
    # mensaje escrito para el celular del paciente.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    fecha = timezone.localdate(cita.inicio).isoformat()

    fila = cliente.get("/api/v1/citas/agenda/", {"fecha": fecha}).data["citas"][0]

    assert fila["enlace_whatsapp"].startswith("https://wa.me/51958111222?text=Hola%2C%20Carmen")
    assert fila["recordatorio"] is None


@pytest.mark.django_db
def test_sin_consentimiento_o_cancelada_no_hay_enlace(podologa, sede, cita, paciente):
    # Garantiza que la interfaz no ofrece escribir a quien no lo autorizó, ni
    # recordar una cita cancelada.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    cancelar_cita(cita=cita, motivo="Reprograma")
    cancelada = cliente.get(f"/api/v1/citas/{cita.pk}/").data
    revocar_consentimiento(paciente)
    Cita.objects.filter(pk=cita.pk).update(estado=Cita.Estado.PROGRAMADA)

    sin_consentimiento = cliente.get(f"/api/v1/citas/{cita.pk}/").data

    assert cancelada["enlace_whatsapp"] is None
    assert sin_consentimiento["enlace_whatsapp"] is None
