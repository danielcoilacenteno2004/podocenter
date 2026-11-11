"""Pruebas de la API de atenciones: forma de la respuesta, errores y auditoría."""
import pytest
from rest_framework.test import APIClient

from apps.atenciones.models import Atencion
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.models import RegistroAuditoria

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
    # Garantiza que P11 recibe un código estable que puede traducir, y no un
    # 400 genérico ni un 500, cuando la cita ya no está programada.
    cancelar_cita(cita=cita, motivo="Reprogramada por el paciente")

    respuesta = cliente.post("/api/v1/atenciones/", {"cita": cita.pk}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "cita-no-atendible"


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
