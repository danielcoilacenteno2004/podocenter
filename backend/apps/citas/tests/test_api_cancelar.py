"""Pruebas de POST /api/v1/citas/{id}/cancelar/, la ruta que usa la pantalla P07."""
from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.citas.models import Cita
from apps.citas.servicios import programar_cita


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    return programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    )


def _cancelar(cliente, cita, **datos):
    return cliente.post(f"/api/v1/citas/{cita.pk}/cancelar/", datos, format="json")


@pytest.mark.django_db
def test_cancelar_con_reemplazo_devuelve_la_plantilla_de_la_cita_nueva(cliente, cita):
    # Garantiza el contrato de CC-16 que usa P07: tras cancelar, la pantalla
    # abre P06 con estos datos; si faltara uno, la cita de reemplazo saldría
    # con otro paciente o servicio sin que nadie lo note, o sin el vínculo con
    # la cancelada que evita contarla como ingreso perdido.
    respuesta = _cancelar(cliente, cita, motivo="El centro reprograma", crear_reemplazo=True)

    assert respuesta.status_code == 200
    assert respuesta.data["cita"]["estado"] == Cita.Estado.CANCELADA
    assert respuesta.data["plantilla_reemplazo"] == {
        "reemplaza": cita.pk,
        "paciente": cita.paciente_id, "profesional": cita.profesional_id,
        "servicio": cita.servicio_id, "sede": cita.sede_id,
    }
    cita.refresh_from_db()
    assert cita.motivo_cancelacion == "El centro reprograma"


@pytest.mark.django_db
def test_cancelar_sin_reemplazo_no_ofrece_plantilla(cliente, cita):
    # Garantiza que desmarcar la casilla en P07 no abre P06: sin plantilla, la
    # pantalla solo vuelve a la agenda.
    respuesta = _cancelar(cliente, cita, motivo="El paciente avisó que no puede asistir")

    assert respuesta.status_code == 200
    assert "plantilla_reemplazo" not in respuesta.data


@pytest.mark.django_db
def test_no_se_cancela_sin_motivo(cliente, cita):
    # Garantiza el «motivo obligatorio» del RF08 en la API, no solo en la
    # pantalla: una petición sin motivo no cambia la cita.
    respuesta = _cancelar(cliente, cita)

    assert respuesta.status_code == 400
    cita.refresh_from_db()
    assert cita.estado == Cita.Estado.PROGRAMADA


@pytest.mark.django_db
def test_una_cita_ya_cancelada_responde_con_su_codigo(cliente, cita):
    # Garantiza que un reenvío desde P07 recibe el código que la interfaz
    # traduce, y no un 500 ni un segundo cambio de estado.
    _cancelar(cliente, cita, motivo="Duplicada")

    respuesta = _cancelar(cliente, cita, motivo="Otra vez")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "cita-no-cancelable"


def _reponer(cliente, cita, plantilla, horas_despues=2):
    return cliente.post("/api/v1/citas/", {
        **plantilla,
        "inicio": (cita.inicio + timedelta(hours=horas_despues)).isoformat(),
    }, format="json")


@pytest.mark.django_db
def test_la_cita_de_reemplazo_queda_vinculada_a_la_cancelada(cliente, cita):
    # Garantiza que la cita creada desde la plantilla guarda a cuál repone: es
    # lo que permite al panel no contar como perdido lo que solo cambió de día.
    plantilla = _cancelar(cliente, cita, motivo="El paciente pidió otra hora",
                          crear_reemplazo=True).data["plantilla_reemplazo"]

    respuesta = _reponer(cliente, cita, plantilla)

    assert respuesta.status_code == 201
    assert Cita.objects.get(pk=respuesta.data["id"]).reemplaza_id == cita.pk


@pytest.mark.django_db
def test_una_cita_cancelada_no_se_repone_dos_veces(cliente, cita):
    # Garantiza que una cancelación tiene a lo sumo un reemplazo, con un código
    # que la pantalla traduce; dos reemplazos harían que un mismo ingreso
    # «volviera» dos veces.
    plantilla = _cancelar(cliente, cita, motivo="El paciente pidió otra hora",
                          crear_reemplazo=True).data["plantilla_reemplazo"]
    _reponer(cliente, cita, plantilla)

    respuesta = _reponer(cliente, cita, plantilla, horas_despues=4)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "reemplazo-repetido"


@pytest.mark.django_db
def test_solo_se_repone_una_cita_cancelada(cliente, cita):
    # Garantiza que el vínculo no se puede usar para marcar como reprogramada
    # una cita que sigue en pie: falsearía el importe no concretado.
    plantilla = {"reemplaza": cita.pk, "paciente": cita.paciente_id,
                 "profesional": cita.profesional_id, "servicio": cita.servicio_id,
                 "sede": cita.sede_id}

    respuesta = _reponer(cliente, cita, plantilla)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "reemplazo-invalido"
