"""La API de citas no tiene vía de escritura que se salte servicios.py.

PUT, PATCH y DELETE escribían en el modelo directamente: no comprobaban ni
el horario de la sede, ni la anticipación, ni el solapamiento. Estas pruebas
fijan que ya no existen.
"""
import pytest
from django.utils import timezone
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
def dos_citas(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    """Dos citas de la misma podóloga, de 9:00 y de 10:00, que no se tocan."""
    def programar(inicio):
        return programar_cita(
            centro=centro, usuario=podologa, sede=sede, paciente=paciente,
            profesional=podologa, servicio=servicio, inicio=inicio,
        )
    return (programar(proximo_lunes_a_las_nueve),
            programar(proximo_lunes_a_las_nueve + timezone.timedelta(hours=1)))


@pytest.mark.django_db
def test_no_se_puede_solapar_una_cita_editandola_por_la_api(cliente, dos_citas):
    # Garantiza la regla central de la agenda también por esta vía: mover la
    # cita de las 10:00 a las 9:20 la solaparía con la de las 9:00. Antes la
    # petición llegaba al modelo sin pasar por programar_cita; la restricción
    # EXCLUDE de la base frenaba el solape, pero la API respondía con un 500.
    primera, segunda = dos_citas
    solapada = primera.inicio + timezone.timedelta(minutes=20)

    respuesta = cliente.patch(f"/api/v1/citas/{segunda.pk}/",
                              {"inicio": solapada.isoformat()}, format="json")

    assert respuesta.status_code == 405
    segunda.refresh_from_db()
    assert segunda.inicio == primera.inicio + timezone.timedelta(hours=1)


@pytest.mark.django_db
def test_no_se_puede_sacar_una_cita_del_horario_de_la_sede_por_la_api(
    cliente, dos_citas, paciente, servicio, podologa, sede
):
    # Garantiza que el horario de la sede no se esquiva reescribiendo la cita
    # entera. Se adelanta la de las 9:00 a las 5:00 (hora de la sede, que abre
    # a las 8:00), sin tocar a ninguna otra: antes de quitar el PUT esto se
    # guardaba con un 200, porque programar_cita no intervenía.
    primera, _ = dos_citas
    madrugada = timezone.localtime(primera.inicio).replace(hour=5)

    respuesta = cliente.put(f"/api/v1/citas/{primera.pk}/", {
        "sede": sede.pk, "paciente": paciente.pk, "profesional": podologa.pk,
        "servicio": servicio.pk, "inicio": madrugada.isoformat(),
    }, format="json")

    assert respuesta.status_code == 405
    primera.refresh_from_db()
    assert timezone.localtime(primera.inicio).hour == 9


@pytest.mark.django_db
def test_una_cita_no_se_borra_se_cancela(cliente, dos_citas):
    # Garantiza la baja lógica que declara el diseño (Informe, Tabla 39): una
    # cita no desaparece de la agenda; se cancela con su motivo.
    primera, _ = dos_citas

    respuesta = cliente.delete(f"/api/v1/citas/{primera.pk}/")

    assert respuesta.status_code == 405
    assert Cita.objects.filter(pk=primera.pk).exists()
