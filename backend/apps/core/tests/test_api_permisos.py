"""Pruebas de la API: el rol decide, y el error llega en el formato acordado."""
import pytest
from rest_framework.test import APIClient

from apps.core.soporte_pruebas import activar_centro


@pytest.fixture
def cliente_podologa(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def cliente_administradora(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_la_podologa_no_puede_listar_usuarios(cliente_podologa):
    respuesta = cliente_podologa.get("/api/v1/usuarios/")

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_la_administradora_del_centro_si_puede_listar_usuarios(cliente_administradora):
    respuesta = cliente_administradora.get("/api/v1/usuarios/")

    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_la_podologa_consulta_el_catalogo_pero_no_lo_edita(cliente_podologa, servicio):
    assert cliente_podologa.get("/api/v1/servicios/").status_code == 200
    creacion = cliente_podologa.post(
        "/api/v1/servicios/",
        {"nombre": "Nuevo", "duracion_minutos": 30, "precio": "50.00"},
        format="json",
    )
    assert creacion.status_code == 403


@pytest.mark.django_db
def test_una_peticion_sin_sesion_no_llega_a_los_datos():
    respuesta = APIClient().get("/api/v1/pacientes/")

    assert respuesta.status_code in (401, 403)


@pytest.mark.django_db
def test_el_error_de_negocio_viaja_en_formato_problem_details(
    cliente_podologa, centro, sede, servicio, paciente, podologa, proximo_lunes_a_las_nueve
):
    cuerpo = {
        "sede": sede.pk, "paciente": paciente.pk, "profesional": podologa.pk,
        "servicio": servicio.pk, "inicio": proximo_lunes_a_las_nueve.isoformat(),
    }
    assert cliente_podologa.post("/api/v1/citas/", cuerpo, format="json").status_code == 201

    repetida = cliente_podologa.post("/api/v1/citas/", cuerpo, format="json")

    assert repetida.status_code == 422
    assert repetida.data["codigo"] == "cita-solapada"
    assert repetida.data["type"].endswith("/cita-solapada")


@pytest.mark.django_db
def test_la_sonda_de_estado_responde_sin_autenticacion():
    respuesta = APIClient().get("/api/v1/estado/")

    assert respuesta.status_code == 200
    assert respuesta.data["estado"] == "operativo"


@pytest.mark.django_db
def test_la_agenda_devuelve_solo_las_citas_de_la_sede_activa(
    cliente_podologa, centro, sede, servicio, paciente, podologa, proximo_lunes_a_las_nueve
):
    activar_centro(centro.pk)
    cliente_podologa.post(
        "/api/v1/citas/",
        {"sede": sede.pk, "paciente": paciente.pk, "profesional": podologa.pk,
         "servicio": servicio.pk, "inicio": proximo_lunes_a_las_nueve.isoformat()},
        format="json",
    )

    respuesta = cliente_podologa.get(
        f"/api/v1/citas/agenda/?fecha={proximo_lunes_a_las_nueve.date().isoformat()}"
    )

    assert respuesta.status_code == 200
    assert len(respuesta.data["citas"]) == 1
