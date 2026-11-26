"""Recordatorios automáticos de cita (RF07; CU15 del informe).

El canal lo elige la Gerencia de cada centro; aquí se prueba con el correo
(el canal automático disponible, que en pruebas no sale de la memoria) y con
canales de prueba que fallan a propósito. Lo que se garantiza: una sola vez
por cita, solo con consentimiento y contacto válido, nunca de una cita
cancelada, un fallo no corta el lote y un centro no toca lo de otro.
"""
from datetime import time, timedelta
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalogo.models import Servicio
from apps.citas.canales import (
    CanalCorreo,
    CanalNoDisponible,
    CanalRecordatorio,
    CanalWhatsAppApi,
    ErrorDeEnvio,
    celular_internacional,
)
from apps.citas.models import Cita, ConfiguracionRecordatorios, Recordatorio
from apps.citas.recordatorios import enviar_recordatorios, pasada_del_planificador
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.pacientes.models import Paciente
from apps.pacientes.servicios import registrar_paciente, revocar_consentimiento
from apps.sedes.models import HorarioSede, Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

CONFIGURACION = "/api/v1/recordatorios/configuracion/"


class CanalDePrueba(CanalRecordatorio):
    """Canal automático que anota lo que envía y puede fallar a pedido."""

    codigo = "CORREO"
    nombre = "Prueba"
    automatico = True

    def __init__(self, fallar_en=(), error=ErrorDeEnvio):
        self.fallar_en = set(fallar_en)
        self.error = error
        self.enviados = []

    def destino(self, paciente):
        return CanalCorreo().destino(paciente)

    def enviar(self, *, destino, cita):
        if cita.pk in self.fallar_en:
            raise self.error("proveedor caído")
        self.enviados.append((destino, cita.pk))
        return f"id-{len(self.enviados)}"


def _con_correo(paciente, correo="carmen@correo.pe"):
    Paciente.objects.filter(pk=paciente.pk).update(correo=correo)
    paciente.refresh_from_db()
    return paciente


@pytest.fixture
def configuracion(centro):
    return ConfiguracionRecordatorios.objects.create(
        centro=centro, activo=True, canal="CORREO", hora_envio=time(18, 0))


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    _con_correo(paciente)
    return programar_cita(centro=centro, usuario=podologa, sede=sede, paciente=paciente,
                          profesional=podologa, servicio=servicio,
                          inicio=proximo_lunes_a_las_nueve)


def _la_vispera_a_las(cita, hora=19):
    """El planificador corriendo el día anterior a la cita, a esa hora local."""
    vispera = timezone.localtime(cita.inicio) - timedelta(days=1)
    return vispera.replace(hour=hora, minute=0)


def _otra_cita(centro, podologa, sede, servicio, cita, documento, minutos=60, correo=None):
    otro = registrar_paciente(
        centro=centro, usuario=podologa,
        datos={"tipo_documento": "DNI", "documento": documento, "nombres": "Luis",
               "apellidos": "Mamani", "telefono": "958333444"},
        consentimiento={"acepta_tratamiento_datos": True, "acepta_recordatorios": True},
    )
    _con_correo(otro, correo or f"{documento}@correo.pe")
    return programar_cita(centro=centro, usuario=podologa, sede=sede, paciente=otro,
                          profesional=podologa, servicio=servicio,
                          inicio=cita.inicio + timedelta(minutes=minutos))


@pytest.mark.parametrize("telefono, esperado", [
    ("958111222", "51958111222"), ("+51 958 111 222", "51958111222"),
    ("054-281940", None), ("95811", None), ("", None),
])
def test_solo_un_celular_peruano_sirve_como_destino_de_whatsapp(telefono, esperado):
    # El enlace de WhatsApp no se ofrece para un fijo o un número incompleto:
    # la persona abriría un chat que no llega a nadie.
    assert celular_internacional(telefono) == esperado


@pytest.mark.parametrize("correo, esperado", [
    ("carmen@correo.pe", "carmen@correo.pe"), ("  carmen@correo.pe ", "carmen@correo.pe"),
    ("carmen@", None), ("", None),
])
def test_solo_un_correo_valido_sirve_como_destino(correo, esperado):
    # Un correo mal escrito se omite en lugar de gastar los tres intentos en
    # una dirección que el servidor de correo va a rechazar.
    assert CanalCorreo().destino(Paciente(correo=correo)) == esperado


@pytest.mark.django_db
def test_avisa_por_correo_de_las_citas_de_manana_y_responde_al_centro(
        centro, cita, configuracion, mailoutbox):
    # CU15 de punta a punta: la víspera, pasada la hora del centro, el
    # paciente recibe el texto con su cita; si responde, le llega al centro.
    centro.correo_contacto = "contacto@centro.pe"
    centro.save(update_fields=["correo_contacto"])

    resumen = pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert resumen["enviados"] == 1
    assert len(mailoutbox) == 1
    correo = mailoutbox[0]
    assert correo.to == ["carmen@correo.pe"]
    assert correo.reply_to == ["contacto@centro.pe"]
    assert "Hola, Carmen" in correo.body
    assert f"{timezone.localtime(cita.inicio):%d/%m/%Y}" in correo.body
    recordatorio = Recordatorio.objects.get(cita=cita)
    assert (recordatorio.estado, recordatorio.canal) == ("ENVIADO", "CORREO")
    assert recordatorio.id_externo == correo.extra_headers["Message-ID"]


@pytest.mark.django_db
def test_no_se_envia_dos_veces_la_misma_cita(centro, cita, configuracion, mailoutbox):
    # El planificador corre cada quince minutos: después de la hora de envío
    # pasa varias veces por la misma cita, y el paciente debe recibir un
    # solo mensaje.
    for hora in (19, 20, 21):
        pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita, hora))

    assert len(mailoutbox) == 1
    assert Recordatorio.objects.filter(cita=cita).count() == 1


@pytest.mark.django_db
def test_sin_consentimiento_no_se_envia(centro, cita, configuracion, mailoutbox):
    # Ley N.° 29733: si el paciente retiró su consentimiento, no se le
    # escribe, y eso no cuenta como fallo ni deja registro de envío.
    revocar_consentimiento(cita.paciente)

    resumen = pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert (resumen["omitidos"], len(mailoutbox)) == (1, 0)
    assert not Recordatorio.objects.exists()


@pytest.mark.django_db
def test_sin_un_correo_valido_se_omite(centro, cita, configuracion, mailoutbox):
    # Con el canal de correo, el paciente sin correo (o con uno mal escrito)
    # se omite; el centro puede seguir usando el WhatsApp manual de la agenda.
    _con_correo(cita.paciente, "sin-arroba")

    resumen = pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert (resumen["omitidos"], len(mailoutbox)) == (1, 0)


@pytest.mark.django_db
def test_una_cita_cancelada_no_se_avisa(centro, cita, configuracion, mailoutbox):
    # Recordar una cita que ya no existe confundiría al paciente.
    cancelar_cita(cita=cita, motivo="El paciente avisó que no viene")

    pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert mailoutbox == []


@pytest.mark.django_db
def test_cancelar_anula_el_recordatorio_que_esperaba_un_reintento(centro, cita):
    # Un primer intento fallido deja el recordatorio pendiente de reintento;
    # si entretanto se cancela la cita, el reintento no sale.
    manana = timezone.localdate(cita.inicio)
    enviar_recordatorios(centro_id=centro.pk, fecha=manana,
                         canal=CanalDePrueba(fallar_en={cita.pk}))
    cancelar_cita(cita=cita, motivo="Reprograma")
    canal = CanalDePrueba()

    enviar_recordatorios(centro_id=centro.pk, fecha=manana, canal=canal)

    assert Recordatorio.objects.get(cita=cita).estado == "CANCELADO"
    assert canal.enviados == []


@pytest.mark.django_db
@pytest.mark.parametrize("error", [ErrorDeEnvio, RuntimeError])
def test_la_falla_de_un_envio_no_corta_el_resto_del_lote(centro, podologa, sede, servicio,
                                                         cita, error):
    # Un correo rechazado, o un error inesperado del proveedor, en la primera
    # cita del día no puede dejar sin aviso a los demás pacientes.
    segunda = _otra_cita(centro, podologa, sede, servicio, cita, "41222333")
    canal = CanalDePrueba(fallar_en={cita.pk}, error=error)

    resumen = enviar_recordatorios(centro_id=centro.pk, fecha=timezone.localdate(cita.inicio),
                                   canal=canal)

    assert (resumen["reintentar"], resumen["enviados"]) == (1, 1)
    assert [pk for _, pk in canal.enviados] == [segunda.pk]
    fallido = Recordatorio.objects.get(cita=cita)
    assert (fallido.estado, fallido.intentos, fallido.ultimo_error) == (
        "PENDIENTE", 1, "proveedor caído")


@pytest.mark.django_db
def test_se_reintenta_hasta_tres_veces_y_queda_como_fallido(centro, cita):
    # Reintento limitado: tras tres intentos se deja de insistir y el estado
    # queda a la vista del centro en la agenda.
    canal = CanalDePrueba(fallar_en={cita.pk})
    for _ in range(4):
        enviar_recordatorios(centro_id=centro.pk, fecha=timezone.localdate(cita.inicio),
                             canal=canal)

    recordatorio = Recordatorio.objects.get(cita=cita)
    assert (recordatorio.estado, recordatorio.intentos) == ("FALLIDO", 3)


@pytest.mark.django_db
def test_solo_avisa_de_las_citas_del_dia_siguiente(centro, cita, configuracion, mailoutbox):
    # Dos días antes todavía no corresponde: el aviso es de la víspera.
    dos_dias_antes = _la_vispera_a_las(cita) - timedelta(days=1)

    pasada_del_planificador(centro_id=centro.pk, ahora=dos_dias_antes)

    assert mailoutbox == []


@pytest.mark.django_db
@pytest.mark.parametrize(("cambio", "motivo"), [
    ({"activo": False}, "desactivado"),
    ({"hora_envio": time(20, 0)}, "antes-de-la-hora"),
    ({"canal": "WHATSAPP_MANUAL"}, "canal-manual"),
    ({"canal": "WHATSAPP_API"}, "canal-no-disponible"),
])
def test_la_configuracion_del_centro_decide_si_se_envia(centro, cita, configuracion, mailoutbox,
                                                        cambio, motivo):
    # Desactivado, antes de su hora, con el canal manual o con el WhatsApp
    # automático todavía sin aprobar, el planificador no envía nada.
    ConfiguracionRecordatorios.objects.filter(pk=configuracion.pk).update(**cambio)

    resumen = pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita, 19))

    assert resumen == {"motivo": motivo}
    assert mailoutbox == []


@pytest.mark.django_db
def test_un_centro_sin_configuracion_no_envia(centro, cita, mailoutbox):
    # La configuración nace desactivada: un centro nuevo no empieza a escribir
    # a sus pacientes sin que la Gerencia lo decida.
    resumen = pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert resumen == {"motivo": "desactivado"}


def test_el_whatsapp_automatico_esta_vacio_hasta_que_se_apruebe():
    # CC-28: ningún camino del código puede mandar un WhatsApp automático.
    with pytest.raises(CanalNoDisponible):
        CanalWhatsAppApi().enviar(destino="51958111222", cita=None)
    assert CanalWhatsAppApi.disponible is False


# --- aislamiento entre centros ------------------------------------------------------

@pytest.fixture
def cita_ajena(otro_centro, proximo_lunes_a_las_nueve):
    """Una cita de mañana en otro centro, con sus recordatorios activos."""
    activar_centro(otro_centro.pk)
    sede = Sede.objects.create(centro=otro_centro, nombre="Norte", direccion="Av. Perú 1")
    for dia in range(0, 6):
        HorarioSede.objects.create(sede=sede, dia_semana=dia, hora_apertura="08:00",
                                   hora_cierre="20:00")
    podologa = Usuario.objects.create_user(
        correo="podologa@limanorte.pe", password=CLAVE_DE_PRUEBA, nombres="Eva",
        apellidos="Ríos", rol=Rol.PODOLOGA, centro=otro_centro)
    AsignacionSede.objects.create(usuario=podologa, sede=sede, es_predeterminada=True)
    servicio = Servicio.objects.create(centro=otro_centro, nombre="Quiropodia",
                                       duracion_minutos=45, precio="50.00")
    paciente = registrar_paciente(
        centro=otro_centro, usuario=podologa,
        datos={"tipo_documento": "DNI", "documento": "40777888", "nombres": "Rosa",
               "apellidos": "Huamán", "telefono": "958555666"},
        consentimiento={"acepta_tratamiento_datos": True, "acepta_recordatorios": True},
    )
    _con_correo(paciente, "rosa@correo.pe")
    ConfiguracionRecordatorios.objects.create(centro=otro_centro, activo=True, canal="CORREO")
    cita = programar_cita(centro=otro_centro, usuario=podologa, sede=sede, paciente=paciente,
                          profesional=podologa, servicio=servicio,
                          inicio=proximo_lunes_a_las_nueve)
    return cita


@pytest.mark.django_db
def test_la_pasada_de_un_centro_no_toca_las_citas_de_otro(centro, cita, configuracion,
                                                          cita_ajena, mailoutbox):
    # Aislamiento entre inquilinos: el lote de un centro solo ve sus citas,
    # aunque la del otro centro sea a la misma hora y tenga todo en regla.
    activar_centro(centro.pk)

    pasada_del_planificador(centro_id=centro.pk, ahora=_la_vispera_a_las(cita))

    assert [m.to for m in mailoutbox] == [["carmen@correo.pe"]]
    activar_centro(cita_ajena.centro_id)
    assert not Recordatorio.objects.filter(cita=cita_ajena).exists()


@pytest.mark.django_db
def test_un_centro_no_ve_la_configuracion_de_otro(centro, configuracion, cita_ajena):
    # La configuración está bajo la política de seguridad por fila: con el
    # centro propio fijado, la del otro no existe para la consulta.
    activar_centro(centro.pk)

    visibles = set(ConfiguracionRecordatorios.objects.values_list("centro_id", flat=True))

    assert visibles == {centro.pk}


@pytest.mark.django_db
def test_el_comando_procesa_cada_centro_con_su_configuracion(centro, cita, configuracion,
                                                             cita_ajena, mailoutbox):
    # Una pasada del planificador recorre todos los centros, cada uno con su
    # centro fijado en la base; el centro con los recordatorios desactivados
    # no recibe nada aunque el otro sí.
    activar_centro(cita_ajena.centro_id)
    ConfiguracionRecordatorios.objects.filter(centro_id=cita_ajena.centro_id).update(activo=False)

    with mock.patch("apps.citas.recordatorios.timezone.now",
                    return_value=_la_vispera_a_las(cita)):
        call_command("enviar_recordatorios", verbosity=0)

    assert [m.to for m in mailoutbox] == [["carmen@correo.pe"]]


@pytest.mark.django_db
def test_si_falla_un_centro_el_comando_sigue_con_los_demas(centro, otro_centro):
    # Un error en un centro (por ejemplo, un dato corrupto) no deja sin
    # recordatorios a los demás centros clientes.
    llamados = []

    def pasada(*, centro_id):
        llamados.append(centro_id)
        if centro_id == centro.pk:
            raise RuntimeError("dato corrupto")
        return {"enviados": 1}

    with mock.patch("apps.citas.management.commands.enviar_recordatorios"
                    ".pasada_del_planificador", side_effect=pasada):
        call_command("enviar_recordatorios", verbosity=0)

    assert set(llamados) == {centro.pk, otro_centro.pk}


# --- configuración por la administradora --------------------------------------------

@pytest.fixture
def como_administradora(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_la_configuracion_nace_desactivada_y_con_el_canal_manual(como_administradora):
    # Activar los envíos y elegir el canal es una decisión de la Gerencia:
    # el sistema no la toma por ella.
    datos = como_administradora.get(CONFIGURACION).data

    assert (datos["activo"], datos["hora_envio"], datos["canal"]) == (
        False, "18:00:00", "WHATSAPP_MANUAL")
    assert {c["codigo"]: c["disponible"] for c in datos["canales"]} == {
        "CORREO": True, "WHATSAPP_MANUAL": True, "WHATSAPP_API": False}


@pytest.mark.django_db
def test_la_administradora_activa_los_recordatorios_y_queda_auditado(como_administradora,
                                                                    centro):
    # El cambio de canal y de hora deja constancia: es lo que explica después
    # por qué los pacientes empezaron a recibir correos.
    respuesta = como_administradora.put(
        CONFIGURACION, {"activo": True, "hora_envio": "17:30", "canal": "CORREO"}, format="json")

    assert respuesta.status_code == 200
    assert (respuesta.data["activo"], respuesta.data["hora_envio"]) == (True, "17:30:00")
    registro = RegistroAuditoria.objects.get(entidad="configuracion_recordatorios")
    assert registro.datos == {"activo": "True", "hora_envio": "17:30:00", "canal": "CORREO"}


@pytest.mark.django_db
def test_no_se_puede_elegir_el_whatsapp_automatico_sin_aprobacion(como_administradora):
    # CC-28: el canal existe en el diseño, pero elegirlo hoy no tendría
    # efecto; se rechaza con su código para que la interfaz lo explique.
    respuesta = como_administradora.put(CONFIGURACION, {"canal": "WHATSAPP_API"}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "canal-no-disponible"


@pytest.mark.django_db
def test_la_podologa_no_cambia_la_configuracion(podologa, sede):
    # Es una decisión de costo del centro, no de la operación diaria.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))

    assert cliente.put(CONFIGURACION, {"activo": True}, format="json").status_code == 403


# --- WhatsApp manual desde la agenda -----------------------------------------------

@pytest.mark.django_db
def test_la_agenda_trae_el_enlace_de_whatsapp_con_el_mensaje(podologa, sede, cita):
    # El camino manual sigue disponible sea cual sea el canal automático:
    # la agenda ofrece abrir WhatsApp con el mensaje escrito.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    fecha = timezone.localdate(cita.inicio).isoformat()

    fila = cliente.get("/api/v1/citas/agenda/", {"fecha": fecha}).data["citas"][0]

    assert fila["enlace_whatsapp"].startswith("https://wa.me/51958111222?text=Hola%2C%20Carmen")
    assert fila["recordatorio"] is None


@pytest.mark.django_db
def test_sin_consentimiento_o_cancelada_no_hay_enlace(podologa, sede, cita, paciente):
    # La interfaz no ofrece escribir a quien no lo autorizó, ni recordar una
    # cita cancelada.
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
