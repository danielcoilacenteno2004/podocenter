"""Pruebas del inventario: movimientos, stock por sede, disponibilidad y aislamiento."""
import pytest
from django.db import IntegrityError, InternalError, ProgrammingError, connection, transaction
from rest_framework.test import APIClient

from apps.core.errores import ReglaDeNegocio
from apps.core.soporte_pruebas import activar_centro
from apps.inventario.models import MovimientoInventario, Producto, Stock
from apps.inventario.servicios import registrar_movimiento
from apps.sedes.models import Sede
from apps.usuarios.models import Usuario

from ...conftest import CLAVE_DE_PRUEBA


@pytest.fixture
def producto(centro):
    return Producto.objects.create(centro=centro, codigo="INS-004", nombre="Crema urea 10 %")


@pytest.fixture
def otra_sede(centro):
    return Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Lima 456")


@pytest.fixture
def mover(centro, podologa, sede, producto):
    def _mover(tipo, cantidad, sentido=None, motivo="Control de stock", en_sede=None):
        return registrar_movimiento(
            centro=centro, usuario=podologa, sede_id=(en_sede or sede).pk,
            producto_id=producto.pk, tipo=tipo, cantidad=cantidad, sentido=sentido, motivo=motivo,
        )
    return _mover


def _stock(sede, producto):
    return Stock.objects.get(sede=sede, producto=producto).cantidad


# --- Movimientos y su efecto en el stock ---------------------------------------------

@pytest.mark.django_db
def test_una_entrada_suma_al_stock_de_la_sede(mover, sede, producto):
    # Garantiza el efecto básico de CU11 y su trazabilidad: el movimiento
    # guarda con qué existencia dejó la sede.
    movimiento = mover("ENTRADA", 12)

    assert _stock(sede, producto) == 12
    assert (movimiento.cantidad, movimiento.existencia_resultante) == (12, 12)


@pytest.mark.django_db
def test_una_merma_resta_del_stock(mover, sede, producto):
    # Garantiza que la merma descuenta: lo vencido o roto deja de contar.
    mover("ENTRADA", 10)

    movimiento = mover("MERMA", 3, motivo="Tubo vencido")

    assert _stock(sede, producto) == 7
    assert movimiento.cantidad == -3


@pytest.mark.django_db
def test_una_merma_no_puede_dejar_el_stock_en_negativo(mover, sede, producto):
    # Regla pedida: una merma mayor que la existencia se rechaza con su
    # código y no cambia nada; el stock negativo no existe en la realidad.
    mover("ENTRADA", 2)

    with pytest.raises(ReglaDeNegocio) as error:
        mover("MERMA", 5, motivo="Caja dañada")

    assert error.value.codigo == "stock-insuficiente"
    assert _stock(sede, producto) == 2
    assert MovimientoInventario.objects.count() == 1


@pytest.mark.django_db
def test_un_ajuste_a_la_baja_no_puede_dejar_el_stock_en_negativo(mover, sede, producto):
    # Regla pedida: tampoco un ajuste puede inventar un stock negativo.
    mover("ENTRADA", 4)

    with pytest.raises(ReglaDeNegocio) as error:
        mover("AJUSTE", 6, sentido="BAJA", motivo="Conteo físico")

    assert error.value.codigo == "stock-insuficiente"
    assert _stock(sede, producto) == 4


@pytest.mark.django_db
def test_un_ajuste_puede_ser_al_alta_o_a_la_baja(mover, sede, producto):
    # Garantiza que el ajuste corrige en las dos direcciones, que es para lo
    # que sirve un conteo físico.
    mover("ENTRADA", 5)

    mover("AJUSTE", 2, sentido="ALTA", motivo="Conteo físico")
    mover("AJUSTE", 4, sentido="BAJA", motivo="Conteo físico")

    assert _stock(sede, producto) == 3


@pytest.mark.django_db
def test_un_ajuste_sin_direccion_se_rechaza(mover):
    # Garantiza que el signo del ajuste no se adivina.
    with pytest.raises(ReglaDeNegocio) as error:
        mover("AJUSTE", 1, sentido=None, motivo="Conteo")

    assert error.value.codigo == "sentido-requerido"


@pytest.mark.django_db
@pytest.mark.parametrize("tipo", ["MERMA", "AJUSTE"])
def test_la_merma_y_el_ajuste_exigen_motivo(mover, tipo):
    # Garantiza la trazabilidad de la Tabla 13: lo que resta o corrige
    # stock deja constancia de por qué.
    mover("ENTRADA", 5)

    with pytest.raises(ReglaDeNegocio) as error:
        mover(tipo, 1, sentido="BAJA", motivo="  ")

    assert error.value.codigo == "motivo-requerido"


@pytest.mark.django_db
def test_la_salida_por_consumo_no_se_registra_a_mano(mover):
    # Garantiza que nadie simula a mano la salida por consumo: la genera el
    # sistema al registrar la atención y queda ligada a ella.
    with pytest.raises(ReglaDeNegocio) as error:
        mover("SALIDA", 1)

    assert error.value.codigo == "tipo-no-elegible"


@pytest.mark.django_db
@pytest.mark.parametrize("cantidad", [0, -3, None])
def test_la_cantidad_debe_ser_un_entero_positivo(mover, cantidad):
    # Garantiza que el signo lo pone el tipo, no la cantidad (Tabla 13).
    with pytest.raises(ReglaDeNegocio) as error:
        mover("ENTRADA", cantidad)

    assert error.value.codigo == "cantidad-invalida"


@pytest.mark.django_db(transaction=True)
def test_la_base_impide_un_stock_negativo_aunque_se_salte_el_servicio(centro, sede, producto):
    # Tercer nivel de la validación: si un error se saltara el servicio, el
    # CHECK de la tabla stock lo detiene.
    with pytest.raises(IntegrityError), transaction.atomic():
        Stock.objects.create(centro=centro, sede=sede, producto=producto, cantidad=-1)

    connection.close()


# --- API: errores del servidor, no 500 ---------------------------------------------

@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_un_movimiento_sin_sede_se_rechaza_con_su_codigo(podologa, producto):
    # Regla pedida: sin sede activa el servidor responde con un error de
    # negocio, no con un 500.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)

    respuesta = cliente.post("/api/v1/inventario/movimientos/",
                             {"producto": producto.pk, "tipo": "ENTRADA", "cantidad": 3},
                             format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede-activa"


@pytest.mark.django_db
def test_un_movimiento_sin_producto_se_rechaza_con_su_codigo(cliente):
    # Regla pedida: sin producto, error de negocio con su código.
    respuesta = cliente.post("/api/v1/inventario/movimientos/",
                             {"tipo": "ENTRADA", "cantidad": 3}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "producto-requerido"


@pytest.mark.django_db
def test_un_producto_de_otro_centro_responde_como_si_no_existiera(cliente, centro, otro_centro):
    # Garantiza que la API no confirma productos de otro centro cliente.
    activar_centro(otro_centro.pk)
    ajeno = Producto.objects.create(centro=otro_centro, codigo="X-1", nombre="Ajeno")
    activar_centro(centro.pk)

    respuesta = cliente.post("/api/v1/inventario/movimientos/",
                             {"producto": ajeno.pk, "tipo": "ENTRADA", "cantidad": 3},
                             format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "producto-fuera-del-centro"


@pytest.mark.django_db
def test_el_stock_de_la_sede_incluye_los_productos_sin_movimientos(cliente, producto, centro):
    # Garantiza P12: un producto que nunca entró a la sede aparece con 0 y,
    # con un mínimo mayor, marcado como bajo el mínimo.
    otro = Producto.objects.create(centro=centro, codigo="INS-011", nombre="Apósito")
    cliente.post("/api/v1/inventario/movimientos/",
                 {"producto": producto.pk, "tipo": "ENTRADA", "cantidad": 5}, format="json")
    Stock.objects.filter(producto=producto).update(minimo=8)

    filas = {f["codigo"]: f for f in cliente.get("/api/v1/inventario/stock/").data["stock"]}

    assert (filas["INS-004"]["cantidad"], filas["INS-004"]["bajo_minimo"]) == (5, True)
    assert filas[otro.codigo]["cantidad"] == 0


@pytest.mark.django_db
def test_la_disponibilidad_muestra_todas_las_sedes_del_centro(cliente, mover, sede, otra_sede,
                                                              producto):
    # Garantiza P14 y CU12: el mismo producto en todas las sedes, no solo la
    # activa, con la activa señalada; la consulta no mueve nada.
    mover("ENTRADA", 1)
    mover("ENTRADA", 8, en_sede=otra_sede)

    datos = cliente.get("/api/v1/inventario/disponibilidad/", {"producto": producto.pk}).data

    por_sede = {s["nombre"]: (s["cantidad"], s["es_activa"]) for s in datos["sedes"]}
    assert por_sede == {sede.nombre: (1, True), otra_sede.nombre: (8, False)}
    assert _stock(sede, producto) == 1


@pytest.mark.django_db
def test_el_administrador_de_plataforma_no_ve_inventarios(db):
    # Garantiza que la plataforma no accede al inventario de sus clientes.
    plataforma = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma",
    )
    cliente = APIClient()
    cliente.force_authenticate(user=plataforma)

    assert cliente.get("/api/v1/inventario/stock/").status_code == 403


# --- Aislamiento entre centros, con el rol sin privilegios ---------------------------

def _rol_actual():
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        return cursor.fetchone()


@pytest.mark.django_db
def test_las_pruebas_de_aislamiento_corren_con_un_rol_sin_privilegios(db):
    # Garantiza que las pruebas de aislamiento significan algo: un
    # superusuario o un rol con BYPASSRLS se saltaría las políticas y todas
    # pasarían aunque el aislamiento estuviera roto.
    assert _rol_actual() == (False, False)


@pytest.mark.django_db
def test_otro_centro_no_ve_productos_stock_ni_movimientos(mover, otro_centro):
    # Garantiza que las tres tablas nuevas quedaron bajo la política por
    # fila: consultando sin filtro desde otro centro no se ve nada.
    mover("ENTRADA", 5)
    assert _rol_actual() == (False, False)

    activar_centro(otro_centro.pk)

    assert Producto.objects.count() == 0
    assert Stock.objects.count() == 0
    assert MovimientoInventario.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_la_base_rechaza_escribir_stock_con_el_centro_de_otro_inquilino(centro, sede, producto,
                                                                       otro_centro):
    # Garantiza el WITH CHECK de la política: con el centro activo, no se
    # puede escribir una fila que diga pertenecer a otro centro.
    with pytest.raises((InternalError, ProgrammingError)), transaction.atomic():
        Stock.objects.create(centro=otro_centro, sede=sede, producto=producto, cantidad=1)

    connection.close()
