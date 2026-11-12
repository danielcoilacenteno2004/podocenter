"""Insumos habituales de cada servicio (CC-14, Práctica N.° 7).

P11 los precarga al registrar la atención. Sin ellos cada insumo suma dos
interacciones y el RNF02 (cinco o menos) deja de cumplirse con dos insumos.
"""
import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.catalogo.models import Servicio, ServicioInsumo
from apps.core.soporte_pruebas import activar_centro
from apps.inventario.models import Producto

SERVICIOS = "/api/v1/servicios/"


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def fresa(centro):
    return Producto.objects.create(centro=centro, codigo="INS-001",
                                   nombre="Fresa de pulido desechable")


@pytest.fixture
def gasa(centro):
    return Producto.objects.create(centro=centro, codigo="INS-015", nombre="Gasa estéril",
                                   unidad="paquete")


def _insumos(cliente, servicio, insumos):
    return cliente.patch(f"{SERVICIOS}{servicio.pk}/", {"insumos_habituales": insumos},
                         format="json")


@pytest.mark.django_db
def test_el_servicio_guarda_sus_insumos_y_los_devuelve_con_su_nombre(
    cliente, servicio, fresa, gasa
):
    # Garantiza el contrato que usa P11: la ficha del servicio trae cada
    # insumo habitual con lo necesario para pintarlo sin otra consulta.
    respuesta = _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": 1},
                                             {"producto": gasa.pk, "cantidad": 2}])

    assert respuesta.status_code == 200
    assert [(i["nombre"], i["cantidad"], i["unidad"])
            for i in respuesta.data["insumos_habituales"]] == [
        ("Fresa de pulido desechable", 1, "unidad"), ("Gasa estéril", 2, "paquete")]


@pytest.mark.django_db
def test_enviar_la_lista_la_reemplaza_y_no_enviarla_la_conserva(cliente, servicio, fresa, gasa):
    # Garantiza que quitar un insumo funciona, y que editar el precio no
    # borra los insumos por omisión.
    _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": 1},
                                 {"producto": gasa.pk, "cantidad": 1}])
    _insumos(cliente, servicio, [{"producto": gasa.pk, "cantidad": 3}])
    cliente.patch(f"{SERVICIOS}{servicio.pk}/", {"precio": "65.00"}, format="json")

    assert list(ServicioInsumo.objects.filter(servicio=servicio)
                .values_list("producto_id", "cantidad")) == [(gasa.pk, 3)]


@pytest.mark.django_db
@pytest.mark.parametrize("cantidad", [0, -1, None])
def test_una_cantidad_no_positiva_se_rechaza(cliente, servicio, fresa, cantidad):
    # Garantiza que no se precarga en P11 una fila que el servidor rechazaría
    # al registrar la atención.
    respuesta = _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": cantidad}])

    assert (respuesta.status_code, respuesta.data["codigo"]) == (422, "cantidad-invalida")


@pytest.mark.django_db
def test_un_producto_inactivo_o_repetido_se_rechaza(cliente, servicio, fresa):
    # Garantiza las mismas reglas que un insumo en la atención.
    repetido = _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": 1},
                                            {"producto": fresa.pk, "cantidad": 1}])
    fresa.esta_activo = False
    fresa.save(update_fields=["esta_activo"])
    inactivo = _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": 1}])

    assert repetido.data["codigo"] == "insumo-repetido"
    assert inactivo.data["codigo"] == "producto-inactivo"


@pytest.mark.django_db
def test_un_producto_de_otro_centro_no_se_declara(cliente, centro, otro_centro, servicio):
    # Garantiza el aislamiento: el producto de otro centro responde como si no
    # existiera y no queda ligado a este servicio.
    activar_centro(otro_centro.pk)
    ajeno = Producto.objects.create(centro=otro_centro, codigo="X-1", nombre="Ajeno")
    activar_centro(centro.pk)

    respuesta = _insumos(cliente, servicio, [{"producto": ajeno.pk, "cantidad": 1}])

    assert respuesta.data["codigo"] == "producto-fuera-del-centro"
    assert not ServicioInsumo.objects.exists()


@pytest.mark.django_db
def test_la_base_impide_una_cantidad_cero(centro, servicio, fresa):
    # Garantiza la defensa en la base, aunque se salte el servicio.
    with pytest.raises(IntegrityError), transaction.atomic():
        ServicioInsumo.objects.create(centro=centro, servicio=servicio, producto=fresa,
                                      cantidad=0)


@pytest.mark.django_db
def test_otro_centro_no_ve_los_insumos_habituales(centro, otro_centro, servicio, fresa):
    # Garantiza que la tabla nueva tiene su política de seguridad por fila,
    # como el resto de tablas con centro.
    ServicioInsumo.objects.create(centro=centro, servicio=servicio, producto=fresa, cantidad=1)

    activar_centro(otro_centro.pk)

    assert ServicioInsumo.objects.count() == 0


@pytest.mark.django_db
def test_el_listado_no_hace_una_consulta_por_servicio(cliente, centro, servicio, fresa):
    # Garantiza que P15 no se vuelve lento con el catálogo: los insumos se
    # traen de una vez para todos los servicios.
    _insumos(cliente, servicio, [{"producto": fresa.pk, "cantidad": 1}])
    with CaptureQueriesContext(connection) as con_uno:
        cliente.get(SERVICIOS)

    otro = Servicio.objects.create(centro=centro, nombre="Pedicura", duracion_minutos=30,
                                   precio="40.00")
    _insumos(cliente, otro, [{"producto": fresa.pk, "cantidad": 2}])
    with CaptureQueriesContext(connection) as con_dos:
        cliente.get(SERVICIOS)

    assert len(con_dos) == len(con_uno)
