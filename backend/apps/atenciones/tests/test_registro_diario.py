"""Pruebas del registro diario (P16, RF14): atenciones e ingresos de un día y una sede."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.atenciones.models import Atencion
from apps.atenciones.servicios import registrar_atencion
from apps.citas.servicios import programar_cita
from apps.core.soporte_pruebas import hacer_que_la_cita_ya_empezo
from apps.sedes.models import HorarioSede, Sede
from apps.usuarios.models import AsignacionSede, Usuario

from ...conftest import CLAVE_DE_PRUEBA

REGISTRO = "/api/v1/reportes/registro-diario/"


@pytest.fixture
def atender(centro, podologa, servicio, paciente, proximo_lunes_a_las_nueve):
    """Programa, adelanta y atiende una cita; devuelve la atención.

    Las citas se atienden de una en una: una cita atendida sale de la
    restricción de solapamiento y deja libre el hueco para la siguiente.
    """
    def _atender(sede, monto):
        cita = hacer_que_la_cita_ya_empezo(programar_cita(
            centro=centro, usuario=podologa, sede=sede, paciente=paciente,
            profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
        ))
        return registrar_atencion(centro=centro, usuario=podologa, sede_id=sede.pk,
                                  cita_id=cita.pk, monto_cobrado=Decimal(monto))
    return _atender


@pytest.fixture
def otra_sede(centro, podologa):
    sede = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Lima 456")
    for dia in range(0, 6):
        HorarioSede.objects.create(sede=sede, dia_semana=dia,
                                   hora_apertura="08:00", hora_cierre="20:00")
    AsignacionSede.objects.create(usuario=podologa, sede=sede)
    return sede


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_lista_las_atenciones_del_dia_con_su_monto_y_el_total(cliente, sede, atender):
    # Garantiza el contrato de P16: cada atención del día con lo que se
    # cobró, y el total, que es la suma de esos montos y no de los precios.
    atender(sede, "60.00")
    atender(sede, "45.50")

    datos = cliente.get(REGISTRO).data

    assert datos["cantidad"] == 2
    assert datos["total"] == "105.50"
    assert [fila["monto_cobrado"] for fila in datos["atenciones"]] == ["60.00", "45.50"]
    assert datos["atenciones"][0]["paciente_nombre"]


@pytest.mark.django_db
def test_solo_cuenta_la_sede_activa(cliente, sede, otra_sede, atender):
    # Garantiza que cada sede cuadra su propia caja: lo cobrado en la otra
    # sede no aparece ni suma aquí.
    atender(sede, "60.00")
    atender(otra_sede, "80.00")

    datos = cliente.get(REGISTRO).data

    assert (datos["cantidad"], datos["total"]) == (1, "60.00")


@pytest.mark.django_db
def test_solo_cuenta_el_dia_elegido(cliente, sede, atender):
    # Garantiza que el registro es de un día: una atención de ayer sale en
    # su fecha y no en la de hoy.
    atender(sede, "60.00")
    de_ayer = atender(sede, "70.00")
    Atencion.objects.filter(pk=de_ayer.pk).update(
        registrada_en=de_ayer.registrada_en - timedelta(days=1))
    ayer = timezone.localdate() - timedelta(days=1)

    hoy = cliente.get(REGISTRO).data
    del_dia_anterior = cliente.get(REGISTRO, {"fecha": ayer.isoformat()}).data

    assert (hoy["cantidad"], hoy["total"]) == (1, "60.00")
    assert (del_dia_anterior["cantidad"], del_dia_anterior["total"]) == (1, "70.00")


@pytest.mark.django_db
def test_las_atenciones_sin_monto_se_cuentan_aparte_y_no_suman(cliente, sede, atender):
    # Garantiza que las atenciones registradas antes de existir el monto no
    # falsean el total como si se hubieran cobrado a cero: se avisan aparte.
    atender(sede, "60.00")
    antigua = atender(sede, "50.00")
    Atencion.objects.filter(pk=antigua.pk).update(monto_cobrado=None)

    datos = cliente.get(REGISTRO).data

    assert (datos["cantidad"], datos["total"], datos["sin_monto"]) == (2, "60.00", 1)


@pytest.mark.django_db
def test_un_dia_sin_atenciones_da_total_cero(cliente):
    # Garantiza que un día vacío no rompe la pantalla.
    datos = cliente.get(REGISTRO).data

    assert (datos["cantidad"], datos["total"], datos["atenciones"]) == (0, "0.00", [])


@pytest.mark.django_db
def test_sin_sede_activa_responde_con_su_codigo(podologa):
    # Garantiza que el registro siempre es de una sede concreta: sin ella,
    # la pantalla recibe un código que puede traducir.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)

    respuesta = cliente.get(REGISTRO)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede-activa"


@pytest.mark.django_db
def test_una_fecha_mal_escrita_se_rechaza_con_su_codigo(cliente):
    # Garantiza el formato de error común: nunca un 500 por un parámetro.
    respuesta = cliente.get(REGISTRO, {"fecha": "11-11-2026"})

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "fecha-invalida"


@pytest.mark.django_db
def test_el_administrador_de_plataforma_no_ve_cajas_de_los_centros(db):
    # Garantiza que la plataforma no accede a los ingresos de sus clientes.
    plataforma = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma",
    )
    cliente = APIClient()
    cliente.force_authenticate(user=plataforma)

    assert cliente.get(REGISTRO).status_code == 403
