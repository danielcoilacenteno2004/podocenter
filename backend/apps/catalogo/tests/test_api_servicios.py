"""API del catálogo de servicios (P15/P26, RF09).

Antes el nombre repetido y el borrado de un servicio con citas respondían
500, y la duración admitía desde 5 minutos aunque la Tabla 24 pide 10 a 240.
"""
import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.catalogo.models import Servicio
from apps.core.models import RegistroAuditoria

SERVICIOS = "/api/v1/servicios/"


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


def _alta(cliente, nombre="Pedicura clínica", duracion=50):
    return cliente.post(SERVICIOS, {"nombre": nombre, "duracion_minutos": duracion,
                                    "precio": "65.00"}, format="json")


@pytest.mark.django_db
def test_el_alta_crea_el_servicio_y_lo_audita(cliente):
    # Garantiza el camino normal y que el precio inicial queda en la
    # bitácora: es lo que después explica por qué se cobró lo que se cobró.
    respuesta = _alta(cliente)

    assert respuesta.status_code == 201
    registro = RegistroAuditoria.objects.filter(entidad="servicio",
                                                entidad_id=respuesta.data["id"]).last()
    assert registro.datos["precio"] == "65.00"


@pytest.mark.django_db
def test_un_nombre_repetido_es_error_de_negocio_y_no_500(cliente, servicio):
    # Garantiza que el nombre repetido, con otras mayúsculas o al editar,
    # llega como error con código y no como error del servidor.
    otro = _alta(cliente).data

    al_crear = _alta(cliente, nombre=servicio.nombre.lower())
    al_editar = cliente.patch(f"{SERVICIOS}{otro['id']}/", {"nombre": servicio.nombre},
                              format="json")

    assert (al_crear.status_code, al_crear.data["codigo"]) == (422, "servicio-duplicado")
    assert (al_editar.status_code, al_editar.data["codigo"]) == (422, "servicio-duplicado")


@pytest.mark.django_db
@pytest.mark.parametrize("duracion", [5, 9, 241])
def test_la_duracion_fuera_de_10_a_240_se_rechaza(cliente, duracion):
    # Garantiza el rango de la Tabla 24: una duración de 5 minutos dibujaba
    # en la agenda citas imposibles; una de varias horas, una jornada entera.
    respuesta = _alta(cliente, duracion=duracion)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "duracion-fuera-de-rango"


@pytest.mark.django_db
@pytest.mark.parametrize("duracion", [10, 240])
def test_los_extremos_del_rango_se_aceptan(cliente, duracion):
    # Garantiza que el rango es cerrado, como dice la Tabla 24.
    assert _alta(cliente, nombre=f"Servicio de {duracion}", duracion=duracion).status_code == 201


@pytest.mark.django_db
def test_la_base_tambien_impide_una_duracion_fuera_de_rango(centro, servicio):
    # Garantiza la defensa en la base: una escritura que se salte el servicio
    # (un script, el panel de administración) tampoco puede dejarla fuera.
    servicio.duracion_minutos = 5
    with pytest.raises(IntegrityError), transaction.atomic():
        servicio.save(update_fields=["duracion_minutos"])


@pytest.mark.django_db
def test_un_servicio_no_se_borra(cliente, servicio):
    # Garantiza que no se pierde la historia de un servicio con citas o
    # atenciones: la baja es desmarcarlo como activo. El DELETE respondía 500.
    respuesta = cliente.delete(f"{SERVICIOS}{servicio.pk}/")

    assert respuesta.status_code == 405
    assert Servicio.objects.filter(pk=servicio.pk).exists()


@pytest.mark.django_db
def test_la_podologa_consulta_pero_no_edita(podologa, sede, servicio):
    # Garantiza el reparto de permisos: la podóloga ve el catálogo para
    # agendar, y el precio solo lo cambia la administradora.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))

    assert cliente.get(SERVICIOS).status_code == 200
    assert cliente.patch(f"{SERVICIOS}{servicio.pk}/", {"precio": "1.00"},
                         format="json").status_code == 403
