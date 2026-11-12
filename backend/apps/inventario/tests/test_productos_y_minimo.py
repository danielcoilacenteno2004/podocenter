"""Catálogo de productos y mínimo de stock por sede (CU05, Tabla 12).

Antes los productos solo existían si los creaba un script: un centro nuevo no
tenía con qué llenar su inventario, y el mínimo no se podía cambiar.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.inventario.models import Producto, Stock
from apps.sedes.models import Sede

PRODUCTOS = "/api/v1/inventario/productos/"
STOCK = "/api/v1/inventario/stock/"


def _cliente(usuario, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def admin(administradora, sede):
    return _cliente(administradora, sede)


@pytest.fixture
def podo(podologa, sede):
    return _cliente(podologa, sede)


@pytest.fixture
def producto(centro):
    return Producto.objects.create(centro=centro, codigo="INS-004", nombre="Crema urea 10 %")


@pytest.mark.django_db
def test_la_administradora_da_de_alta_un_producto_que_aparece_sin_stock(admin):
    # Garantiza que un centro nuevo puede armar su catálogo: el producto
    # aparece en P12 con 0, listo para su primera entrada.
    respuesta = admin.post(PRODUCTOS, {"codigo": "INS-030", "nombre": "Bisturí n.° 15",
                                       "unidad": "caja"}, format="json")

    fila = next(f for f in admin.get(STOCK).data["stock"] if f["codigo"] == "INS-030")
    assert respuesta.status_code == 201
    assert (fila["cantidad"], fila["unidad"]) == (0, "caja")


@pytest.mark.django_db
def test_el_codigo_repetido_es_error_de_negocio(admin, producto):
    # Garantiza que el código, que es por el que se busca en P13 y P11, no se
    # repite dentro del centro, sin importar mayúsculas.
    respuesta = admin.post(PRODUCTOS, {"codigo": "ins-004", "nombre": "Otra"}, format="json")

    assert (respuesta.status_code, respuesta.data["codigo"]) == (422, "producto-duplicado")


@pytest.mark.django_db
def test_sin_nombre_no_hay_producto(admin):
    # Garantiza un error con código en lugar de un producto sin nombre.
    respuesta = admin.post(PRODUCTOS, {"codigo": "INS-031", "nombre": "  "}, format="json")

    assert respuesta.data["codigo"] == "nombre-requerido"


@pytest.mark.django_db
def test_desactivar_lo_saca_del_inventario_y_se_puede_recuperar(admin, producto):
    # Garantiza la baja lógica: el producto deja de ofrecerse, sus movimientos
    # siguen, y la administradora puede encontrarlo para reactivarlo.
    admin.patch(f"{PRODUCTOS}{producto.pk}/", {"esta_activo": False}, format="json")

    en_p12 = [f["id"] for f in admin.get(STOCK).data["stock"]]
    con_inactivos = [p["id"] for p in admin.get(PRODUCTOS, {"inactivos": "1"}).data["productos"]]
    assert producto.pk not in en_p12
    assert producto.pk in con_inactivos


@pytest.mark.django_db
def test_la_podologa_no_cambia_el_catalogo(podo, producto):
    # Garantiza el reparto de la Tabla 12: la podóloga consulta y registra
    # movimientos, pero el catálogo es de la administradora.
    alta = podo.post(PRODUCTOS, {"codigo": "X", "nombre": "X"}, format="json")
    edicion = podo.patch(f"{PRODUCTOS}{producto.pk}/", {"nombre": "Y"}, format="json")

    assert (alta.status_code, edicion.status_code) == (403, 403)


@pytest.mark.django_db
def test_el_minimo_de_la_sede_decide_bajo_minimo_y_queda_auditado(admin, producto, sede):
    # Garantiza el CU05: el umbral se fija por sede, cambia el estado que ve
    # P12 y deja rastro de su valor anterior.
    respuesta = admin.patch(f"{STOCK}{producto.pk}/", {"minimo": 3}, format="json")

    fila = next(f for f in admin.get(STOCK).data["stock"] if f["id"] == producto.pk)
    registro = RegistroAuditoria.objects.filter(entidad="stock").last()
    assert respuesta.status_code == 200
    assert (fila["minimo"], fila["bajo_minimo"]) == (3, True)
    assert (registro.datos["minimo"], registro.datos["anterior"]) == (3, 0)


@pytest.mark.django_db
def test_el_minimo_es_por_sede(admin, centro, producto, sede):
    # Garantiza que fijar el mínimo en una sede no lo cambia en la otra: cada
    # local consume a su ritmo (RF11).
    otra = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Lima 456")

    admin.patch(f"{STOCK}{producto.pk}/", {"minimo": 7}, format="json")

    assert Stock.objects.get(sede=sede, producto=producto).minimo == 7
    assert not Stock.objects.filter(sede=otra, producto=producto, minimo=7).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("valor", [-1, "dos", None])
def test_un_minimo_invalido_se_rechaza(admin, producto, valor):
    # Garantiza un error con código, no un 500 ni un umbral negativo.
    respuesta = admin.patch(f"{STOCK}{producto.pk}/", {"minimo": valor}, format="json")

    assert (respuesta.status_code, respuesta.data["codigo"]) == (422, "minimo-invalido")


@pytest.mark.django_db
def test_la_podologa_no_cambia_el_minimo(podo, producto):
    # Garantiza la Tabla 12: «solo el Administrador del centro puede editarlo».
    assert podo.patch(f"{STOCK}{producto.pk}/", {"minimo": 2}, format="json").status_code == 403


@pytest.mark.django_db
def test_no_se_toca_el_producto_de_otro_centro(admin, centro, otro_centro):
    # Garantiza el aislamiento: ni editar ni fijar el mínimo de un producto
    # ajeno, que responde como si no existiera.
    activar_centro(otro_centro.pk)
    ajeno = Producto.objects.create(centro=otro_centro, codigo="X-1", nombre="Ajeno")
    activar_centro(centro.pk)

    edicion = admin.patch(f"{PRODUCTOS}{ajeno.pk}/", {"nombre": "Mío"}, format="json")
    minimo = admin.patch(f"{STOCK}{ajeno.pk}/", {"minimo": 1}, format="json")

    assert edicion.data["codigo"] == minimo.data["codigo"] == "producto-fuera-del-centro"
