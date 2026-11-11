"""Pruebas de la API de atenciones: forma de la respuesta, errores y auditoría."""
import pytest
from rest_framework.test import APIClient

from apps.atenciones.models import Atencion
from apps.catalogo.models import Servicio
from apps.citas.models import Cita
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.pacientes.models import Paciente
from apps.sedes.models import Sede
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

NOTAS = "Hiperqueratosis plantar; se deslamina"


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    return programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    )


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_post_registra_la_atencion_y_devuelve_los_datos_copiados_de_la_cita(cliente, cita):
    # Garantiza el contrato de POST /api/v1/atenciones/ que usará P11: basta
    # con la cita y las notas, y el resto lo pone el servidor a partir de la
    # cita, no lo que envíe el navegador.
    respuesta = cliente.post(
        "/api/v1/atenciones/",
        {"cita": cita.pk, "observaciones_clinicas": NOTAS, "servicio": 999999},
        format="json",
    )

    assert respuesta.status_code == 201
    assert respuesta.data["paciente"] == cita.paciente_id
    assert respuesta.data["servicio"] == cita.servicio_id
    assert respuesta.data["observaciones_clinicas"] == NOTAS


@pytest.mark.django_db
def test_una_cita_no_atendible_devuelve_el_error_en_formato_rfc_9457(cliente, cita):
    # Garantiza que P11 recibe la misma forma de error que el resto de
    # pantallas, con un código estable que puede traducir, y no un 400
    # genérico ni un 500.
    cancelar_cita(cita=cita, motivo="Reprogramada por el paciente")

    respuesta = cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")

    assert respuesta.status_code == 422
    assert respuesta["Content-Type"] == "application/problem+json"
    assert respuesta.data["codigo"] == "cita-no-atendible"
    assert respuesta.data["type"].endswith("/errores/cita-no-atendible")


@pytest.mark.django_db
def test_la_segunda_atencion_de_una_cita_llega_con_su_propio_codigo(cliente, cita):
    # Garantiza que un reenvío desde P11 se distingue de una cita cancelada:
    # la interfaz puede decir «ya estaba registrada» y llevar a la ficha.
    cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")

    respuesta = cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "atencion-duplicada"


@pytest.mark.django_db
def test_sin_la_cabecera_de_sede_la_api_rechaza_el_registro(podologa, cita):
    # Garantiza que la sede activa la fija la sesión del usuario (cabecera
    # X-Sede) y no se adivina: sin ella, el servidor no registra.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)

    respuesta = cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede-activa"


@pytest.mark.django_db
def test_una_cita_de_otro_centro_responde_como_si_no_existiera(
    cliente, cita, otro_centro
):
    # Garantiza que la API no confirma la existencia de datos de otro centro
    # cliente: la cita ajena y la inexistente dan el mismo código, y la ajena
    # sigue programada.
    activar_centro(otro_centro.pk)
    sede = Sede.objects.create(centro=otro_centro, nombre="San Isidro", direccion="Av. Arequipa 1")
    servicio = Servicio.objects.create(centro=otro_centro, nombre="Quiropodia",
                                       duracion_minutos=30, precio="50.00")
    paciente = Paciente.objects.create(centro=otro_centro, documento="41222333",
                                       nombres="Luis", apellidos="Paredes")
    profesional = Usuario.objects.create_user(
        correo="podologa@limanorte.pe", password=CLAVE_DE_PRUEBA, nombres="Ana",
        apellidos="Rojas", rol=Rol.PODOLOGA, centro=otro_centro,
    )
    de_otro_centro = Cita.objects.create(
        centro=otro_centro, sede=sede, paciente=paciente, profesional=profesional,
        servicio=servicio, inicio=cita.inicio, fin=cita.fin, creada_por=profesional,
    )
    activar_centro(cita.centro_id)

    ajena = cliente.post("/api/v1/atenciones/", {"cita": de_otro_centro.pk}, format="json")
    inexistente = cliente.post("/api/v1/atenciones/", {"cita": 999999}, format="json")

    assert ajena.status_code == inexistente.status_code == 422
    assert ajena.data["codigo"] == inexistente.data["codigo"] == "cita-fuera-del-centro"
    assert ajena.data["detail"] == inexistente.data["detail"]
    activar_centro(otro_centro.pk)
    de_otro_centro.refresh_from_db()
    assert de_otro_centro.estado == Cita.Estado.PROGRAMADA


@pytest.mark.django_db
def test_el_listado_no_expone_las_observaciones_y_la_ficha_deja_rastro(cliente, cita):
    # Garantiza que la nota clínica solo sale por la ficha, y que cada lectura
    # de la ficha queda en la auditoría, igual que la del paciente (RF05).
    creada = cliente.post("/api/v1/atenciones/",
                          {"cita": cita.pk, "observaciones_clinicas": NOTAS}, format="json")

    listado = cliente.get("/api/v1/atenciones/")
    ficha = cliente.get(f"/api/v1/atenciones/{creada.data['id']}/")

    assert "observaciones_clinicas" not in listado.data["results"][0]
    assert ficha.data["observaciones_clinicas"] == NOTAS
    assert RegistroAuditoria.objects.filter(
        accion="CONSULTA", entidad="atencion", entidad_id=str(creada.data["id"])
    ).exists()


@pytest.mark.django_db
def test_la_api_no_permite_editar_ni_borrar_una_atencion(cliente, cita):
    # Garantiza que la atención es inmutable desde la API: es un hecho
    # clínico ya ocurrido, y corregirla o anularla será una acción explícita
    # con motivo, no un PATCH o un DELETE.
    creada = cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")
    ruta = f"/api/v1/atenciones/{creada.data['id']}/"

    assert cliente.patch(ruta, {"observaciones_clinicas": "x"}, format="json").status_code == 405
    assert cliente.delete(ruta).status_code == 405
    assert Atencion.objects.count() == 1
