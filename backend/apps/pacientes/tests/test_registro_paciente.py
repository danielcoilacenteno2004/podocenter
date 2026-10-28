"""Pruebas del alta de pacientes: consentimiento, duplicados y cifrado."""
import pytest

from apps.core.errores import ReglaDeNegocio
from apps.pacientes.models import Paciente
from apps.pacientes.servicios import registrar_paciente, revocar_consentimiento

DATOS = {
    "tipo_documento": "DNI",
    "documento": "70123456",
    "nombres": "Ana",
    "apellidos": "Torres",
    "telefono": "959123456",
    "antecedentes": "Diabetes tipo 2 controlada",
}
CONSENTIMIENTO = {"acepta_tratamiento_datos": True, "acepta_recordatorios": True}


@pytest.mark.django_db
def test_registra_el_paciente_con_su_consentimiento_en_la_misma_operacion(centro, podologa):
    paciente = registrar_paciente(
        centro=centro, usuario=podologa, datos=dict(DATOS), consentimiento=CONSENTIMIENTO
    )

    vigente = paciente.consentimiento_vigente
    assert vigente is not None
    assert vigente.acepta_recordatorios is True
    assert vigente.version_texto == "2026.1"


@pytest.mark.django_db
def test_no_registra_un_paciente_sin_consentimiento_de_tratamiento_de_datos(centro, podologa):
    with pytest.raises(ReglaDeNegocio) as error:
        registrar_paciente(
            centro=centro, usuario=podologa, datos=dict(DATOS),
            consentimiento={"acepta_tratamiento_datos": False},
        )

    assert error.value.codigo == "sin-consentimiento"
    assert Paciente.objects.count() == 0


@pytest.mark.django_db
def test_rechaza_un_segundo_paciente_con_el_mismo_documento(centro, podologa):
    registrar_paciente(
        centro=centro, usuario=podologa, datos=dict(DATOS), consentimiento=CONSENTIMIENTO
    )

    with pytest.raises(ReglaDeNegocio) as error:
        registrar_paciente(
            centro=centro, usuario=podologa, datos=dict(DATOS), consentimiento=CONSENTIMIENTO
        )

    assert error.value.codigo == "paciente-duplicado"


@pytest.mark.django_db
def test_los_antecedentes_se_guardan_cifrados_en_la_columna(centro, podologa):
    from django.db import connection

    paciente = registrar_paciente(
        centro=centro, usuario=podologa, datos=dict(DATOS), consentimiento=CONSENTIMIENTO
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT antecedentes FROM paciente WHERE id = %s", [paciente.pk])
        crudo = cursor.fetchone()[0]

    assert crudo.startswith("fer:")
    assert "Diabetes" not in crudo
    assert Paciente.objects.get(pk=paciente.pk).antecedentes == DATOS["antecedentes"]


@pytest.mark.django_db
def test_revocar_el_consentimiento_deja_al_paciente_sin_consentimiento_vigente(centro, podologa):
    paciente = registrar_paciente(
        centro=centro, usuario=podologa, datos=dict(DATOS), consentimiento=CONSENTIMIENTO
    )

    revocar_consentimiento(paciente)

    assert paciente.consentimiento_vigente is None
