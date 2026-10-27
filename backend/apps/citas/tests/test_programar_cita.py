"""Pruebas de la regla central de la agenda: dos citas no pueden solaparse."""
import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.citas.models import Cita
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.errores import ReglaDeNegocio


def _programar(centro, usuario, sede, paciente, servicio, inicio):
    return programar_cita(
        centro=centro, usuario=usuario, sede=sede, paciente=paciente,
        profesional=usuario, servicio=servicio, inicio=inicio,
    )


@pytest.mark.django_db
def test_programa_una_cita_y_calcula_el_fin_con_la_duracion_del_servicio(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    cita = _programar(centro, podologa, sede, paciente, servicio, proximo_lunes_a_las_nueve)

    assert cita.estado == Cita.Estado.PROGRAMADA
    assert (cita.fin - cita.inicio).total_seconds() == servicio.duracion_minutos * 60


@pytest.mark.django_db
def test_rechaza_una_segunda_cita_que_se_solapa_con_la_misma_profesional(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    _programar(centro, podologa, sede, paciente, servicio, proximo_lunes_a_las_nueve)

    with pytest.raises(ReglaDeNegocio) as error:
        _programar(
            centro, podologa, sede, paciente, servicio,
            proximo_lunes_a_las_nueve + timezone.timedelta(minutes=20),
        )

    assert error.value.codigo == "cita-solapada"
    assert Cita.objects.filter(estado=Cita.Estado.PROGRAMADA).count() == 1


@pytest.mark.django_db(transaction=True)
def test_la_base_de_datos_impide_el_solape_aunque_se_salte_la_capa_de_servicios(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    """La restricción EXCLUDE es el cerrojo real: no depende del servidor."""
    fin = proximo_lunes_a_las_nueve + timezone.timedelta(minutes=45)
    Cita.objects.create(
        centro=centro, sede=sede, paciente=paciente, profesional=podologa,
        servicio=servicio, inicio=proximo_lunes_a_las_nueve, fin=fin, creada_por=podologa,
    )

    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Cita.objects.create(
            centro=centro, sede=sede, paciente=paciente, profesional=podologa,
            servicio=servicio,
            inicio=proximo_lunes_a_las_nueve + timezone.timedelta(minutes=30),
            fin=fin + timezone.timedelta(minutes=30), creada_por=podologa,
        )

    assert "ex_cita_sin_solape_por_profesional" in str(error.value)
    connection.close()


@pytest.mark.django_db
def test_permite_reutilizar_el_horario_si_la_cita_anterior_fue_cancelada(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    primera = _programar(centro, podologa, sede, paciente, servicio, proximo_lunes_a_las_nueve)
    cancelar_cita(cita=primera, motivo="El paciente avisó que no puede asistir")

    segunda = _programar(centro, podologa, sede, paciente, servicio, proximo_lunes_a_las_nueve)

    assert segunda.pk != primera.pk
    assert Cita.objects.filter(estado=Cita.Estado.PROGRAMADA).count() == 1


@pytest.mark.django_db
def test_rechaza_una_cita_fuera_del_horario_de_atencion_de_la_sede(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    madrugada = proximo_lunes_a_las_nueve.replace(hour=5)

    with pytest.raises(ReglaDeNegocio) as error:
        _programar(centro, podologa, sede, paciente, servicio, madrugada)

    assert error.value.codigo == "fuera-de-horario"


@pytest.mark.django_db
def test_rechaza_una_cita_en_el_pasado(centro, podologa, sede, servicio, paciente):
    ayer = timezone.now() - timezone.timedelta(days=1)

    with pytest.raises(ReglaDeNegocio) as error:
        _programar(centro, podologa, sede, paciente, servicio, ayer)

    assert error.value.codigo == "cita-en-el-pasado"


@pytest.mark.django_db
def test_no_deja_cancelar_dos_veces_la_misma_cita(
    centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve
):
    cita = _programar(centro, podologa, sede, paciente, servicio, proximo_lunes_a_las_nueve)
    cancelar_cita(cita=cita, motivo="Duplicada")

    with pytest.raises(ReglaDeNegocio) as error:
        cancelar_cita(cita=cita, motivo="Otra vez")

    assert error.value.codigo == "cita-no-cancelable"
