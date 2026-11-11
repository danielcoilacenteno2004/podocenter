"""La API de pacientes no tiene vía de escritura que se salte servicios.py.

PUT, PATCH y DELETE escribían en el modelo directamente: sin auditoría y,
en el caso del borrado, con un 500 si el paciente tenía citas.
"""
import pytest
from rest_framework.test import APIClient

from apps.citas.servicios import programar_cita
from apps.pacientes.models import Paciente


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_los_antecedentes_no_se_cambian_por_fuera_del_servicio(cliente, paciente):
    # Garantiza que el dato clínico cifrado no cambia sin auditoría: antes un
    # PATCH los reescribía con un 200 y la bitácora no se enteraba.
    paciente.antecedentes = "Diabetes tipo 2"
    paciente.save(update_fields=["antecedentes"])
    ruta = f"/api/v1/pacientes/{paciente.pk}/"

    parcial = cliente.patch(ruta, {"antecedentes": "Sin antecedentes"}, format="json")
    completo = cliente.put(ruta, {
        "tipo_documento": paciente.tipo_documento, "documento": paciente.documento,
        "nombres": paciente.nombres, "apellidos": paciente.apellidos,
        "antecedentes": "Sin antecedentes",
    }, format="json")

    assert parcial.status_code == 405
    assert completo.status_code == 405
    paciente.refresh_from_db()
    assert paciente.antecedentes == "Diabetes tipo 2"


@pytest.mark.django_db
def test_un_paciente_con_citas_no_se_borra(
    cliente, centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    # Garantiza la baja lógica del diseño (Informe, Tabla 39) y que no
    # vuelva el 500: borrar un paciente con citas chocaba con la protección
    # de la cita y la API reventaba en lugar de responder.
    programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    )

    respuesta = cliente.delete(f"/api/v1/pacientes/{paciente.pk}/")

    assert respuesta.status_code == 405
    assert Paciente.objects.filter(pk=paciente.pk).exists()
