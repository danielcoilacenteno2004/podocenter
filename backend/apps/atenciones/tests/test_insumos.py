"""Insumos consumidos en la atención y su salida de stock (P11, CU10).

El informe (2.1.7, Tabla 39) promete que la atención descuenta stock, crea
las salidas y marca la cita como atendida en una sola transacción, con
bloqueo de fila sobre el stock. Estas pruebas lo comprueban.
"""
import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.atenciones.models import Atencion
from apps.citas.models import Cita
from apps.citas.servicios import programar_cita
from apps.core.soporte_pruebas import activar_centro, hacer_que_la_cita_ya_empezo
from apps.inventario.models import MovimientoInventario, Producto, Stock
from apps.inventario.servicios import registrar_movimiento
from apps.sedes.models import Sede

ATENCIONES = "/api/v1/atenciones/"
MONTO = {"monto_cobrado": "60.00"}


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    return hacer_que_la_cita_ya_empezo(programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    ))


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def crema(centro, podologa, sede):
    """Un insumo con 5 unidades en la sede de la cita."""
    producto = Producto.objects.create(centro=centro, codigo="INS-004", nombre="Crema urea 10 %")
    registrar_movimiento(centro=centro, usuario=podologa, sede_id=sede.pk,
                         producto_id=producto.pk, tipo="ENTRADA", cantidad=5)
    return producto


@pytest.fixture
def gasa(centro, podologa, sede):
    producto = Producto.objects.create(centro=centro, codigo="INS-015", nombre="Gasa estéril",
                                       unidad="paquete")
    registrar_movimiento(centro=centro, usuario=podologa, sede_id=sede.pk,
                         producto_id=producto.pk, tipo="ENTRADA", cantidad=2)
    return producto


def _registrar(cliente, cita, insumos):
    return cliente.post(ATENCIONES, {"cita": cita.pk, **MONTO, "insumos": insumos},
                        format="json")


def _stock(sede, producto):
    return Stock.objects.get(sede=sede, producto=producto).cantidad


@pytest.mark.django_db
def test_la_atencion_descuenta_el_stock_y_deja_una_salida_por_insumo(
    cliente, cita, sede, crema, gasa
):
    # Garantiza el efecto central: lo que se usó en la atención sale del stock
    # de la sede, con una salida por insumo ligada a esa atención.
    respuesta = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 2},
                                           {"producto": gasa.pk, "cantidad": 1}])

    assert respuesta.status_code == 201
    assert (_stock(sede, crema), _stock(sede, gasa)) == (3, 1)
    salidas = MovimientoInventario.objects.filter(tipo="SALIDA", atencion_id=respuesta.data["id"])
    assert {(m.producto_id, m.cantidad, m.existencia_resultante) for m in salidas} == {
        (crema.pk, -2, 3), (gasa.pk, -1, 1)}


@pytest.mark.django_db
def test_sin_stock_suficiente_no_se_registra_nada(cliente, cita, sede, crema, gasa):
    # Garantiza la transacción única: si falta un insumo, no queda la
    # atención, ni la cita atendida, ni la salida del insumo que sí alcanzaba.
    respuesta = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 1},
                                           {"producto": gasa.pk, "cantidad": 3}])

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "stock-insuficiente"
    assert "Gasa estéril: hay 2 paquete, se piden 3" in respuesta.data["detail"]
    assert not Atencion.objects.filter(cita=cita).exists()
    assert Cita.objects.get(pk=cita.pk).estado == Cita.Estado.PROGRAMADA
    assert (_stock(sede, crema), _stock(sede, gasa)) == (5, 2)
    assert not MovimientoInventario.objects.filter(tipo="SALIDA").exists()


@pytest.mark.django_db
def test_descuenta_de_la_sede_de_la_cita_y_no_de_otra(
    cliente, centro, podologa, cita, sede, crema
):
    # Garantiza que el inventario es por sede (RF11): tener crema en otra sede
    # no sirve para atender aquí, y esa otra sede no se toca.
    otra = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Lima 456")
    registrar_movimiento(centro=centro, usuario=podologa, sede_id=otra.pk,
                         producto_id=crema.pk, tipo="ENTRADA", cantidad=10)

    sin_stock = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 6}])
    con_stock = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 5}])

    assert sin_stock.data["codigo"] == "stock-insuficiente"
    assert con_stock.status_code == 201
    assert (_stock(sede, crema), _stock(otra, crema)) == (0, 10)


@pytest.mark.django_db
@pytest.mark.parametrize("insumos, codigo", [
    ([{"producto": None, "cantidad": 1}], "producto-requerido"),
    ([{"producto": 1, "cantidad": 0}], "cantidad-invalida"),
    ([{"producto": 1, "cantidad": -2}], "cantidad-invalida"),
])
def test_un_insumo_mal_formado_se_rechaza_con_su_codigo(cliente, cita, crema, insumos, codigo):
    # Garantiza errores de negocio con código, no un 500 ni un 400 suelto:
    # P11 los muestra junto a la fila del insumo.
    for fila in insumos:
        if fila["producto"] == 1:
            fila["producto"] = crema.pk

    respuesta = _registrar(cliente, cita, insumos)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == codigo
    assert not Atencion.objects.filter(cita=cita).exists()


@pytest.mark.django_db
def test_el_mismo_producto_dos_veces_se_rechaza(cliente, cita, crema):
    # Garantiza que no se descuenta dos veces por un error de captura: dos
    # filas del mismo producto se suman antes de enviar.
    respuesta = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 1},
                                           {"producto": crema.pk, "cantidad": 1}])

    assert respuesta.data["codigo"] == "insumo-repetido"


@pytest.mark.django_db
def test_un_producto_inactivo_no_se_consume(cliente, cita, crema):
    # Garantiza que un producto retirado del catálogo no sigue saliendo.
    crema.esta_activo = False
    crema.save(update_fields=["esta_activo"])

    respuesta = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 1}])

    assert respuesta.data["codigo"] == "producto-inactivo"


@pytest.mark.django_db
def test_un_producto_de_otro_centro_no_se_consume(cliente, cita, centro, otro_centro):
    # Garantiza el aislamiento: con el identificador de un producto ajeno no
    # se descuenta su stock ni se confirma que exista.
    activar_centro(otro_centro.pk)
    ajeno = Producto.objects.create(centro=otro_centro, codigo="X-1", nombre="Ajeno")
    activar_centro(centro.pk)

    respuesta = _registrar(cliente, cita, [{"producto": ajeno.pk, "cantidad": 1}])

    assert respuesta.data["codigo"] == "producto-fuera-del-centro"


@pytest.mark.django_db
def test_la_ficha_de_la_atencion_trae_sus_insumos(cliente, cita, crema):
    # Garantiza que P25 puede mostrar qué se usó en la atención: la salida
    # queda ligada a ella y se lee desde la ficha.
    creada = _registrar(cliente, cita, [{"producto": crema.pk, "cantidad": 2}]).data

    ficha = cliente.get(f"{ATENCIONES}{creada['id']}/").data

    assert ficha["insumos_consumidos"] == [{"producto": crema.pk, "codigo": "INS-004",
                                            "nombre": "Crema urea 10 %", "unidad": "unidad",
                                            "cantidad": 2}]


@pytest.mark.django_db
def test_sin_insumos_la_atencion_se_registra_igual(cliente, cita):
    # Garantiza que los insumos son opcionales: hay atenciones que no gastan
    # nada del inventario (una evaluación, por ejemplo).
    respuesta = cliente.post(ATENCIONES, {"cita": cita.pk, **MONTO}, format="json")

    assert respuesta.status_code == 201
    assert respuesta.data["insumos_consumidos"] == []


@pytest.mark.django_db
def test_la_base_impide_una_salida_sin_atencion(centro, podologa, sede, crema):
    # Garantiza la defensa en la base: una salida suelta, sin la atención que
    # la explica, no se puede escribir ni saltándose el servicio.
    with pytest.raises(IntegrityError), transaction.atomic():
        MovimientoInventario.objects.create(
            centro=centro, sede=sede, producto=crema, tipo="SALIDA", cantidad=-1,
            existencia_resultante=4, registrado_por=podologa,
        )
