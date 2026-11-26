"""Pruebas del alta del segundo factor y de su obligatoriedad (RF18, RNF01).

Lo que se garantiza: que un rol administrativo no puede usar el sistema sin
el factor, que el alta solo se activa con un código que pruebe que la
aplicación quedó bien configurada, y que el secreto no vuelve a salir de la
base, ni en claro dentro de ella.
"""
import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.usuarios import totp
from apps.usuarios.models import CodigoRecuperacion, Usuario
from apps.usuarios.roles import Rol
from apps.usuarios.servicios import crear_usuario

from ...conftest import CLAVE_DE_PRUEBA

ALTA = "/api/v1/sesion/segundo-factor/alta/"
CONFIRMAR = "/api/v1/sesion/segundo-factor/confirmar/"
ACTUAL = "/api/v1/sesion/actual/"
INGRESAR = "/api/v1/sesion/ingresar/"
USUARIOS = "/api/v1/usuarios/"
CENTROS = "/api/v1/centros/"


@pytest.fixture
def gerente(centro, sede):
    """Administradora recién creada, todavía sin segundo factor."""
    return crear_usuario(centro=centro, correo="gerente@centro.pe", nombres="Elsa",
                         apellidos="Rojas", rol=Rol.ADMIN_CENTRO, sedes_ids=[sede.pk],
                         password=CLAVE_DE_PRUEBA)


@pytest.fixture
def cliente(gerente, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=gerente)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


def _alta_completa(cliente):
    alta = cliente.post(ALTA).data
    codigo = totp.codigo_del_paso(alta["secreto"], totp.paso_en())
    return alta, cliente.post(CONFIRMAR, {"codigo": codigo}, format="json")


@pytest.mark.django_db
def test_una_administradora_sin_factor_no_puede_usar_la_api(cliente):
    # Es la condición E6 del piloto: sin el factor, la cuenta de mayor
    # privilegio del centro no lee ni escribe nada. El código estable permite
    # a la interfaz llevarla al alta en lugar de mostrar un error.
    respuesta = cliente.get(USUARIOS)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "segundo-factor-pendiente"


@pytest.mark.django_db
def test_al_ingresar_sin_factor_la_respuesta_avisa_que_debe_activarlo(gerente):
    # La interfaz decide a qué pantalla llevarla con este dato, igual que con
    # la contraseña temporal.
    respuesta = APIClient().post(INGRESAR, {"correo": gerente.correo,
                                            "contrasena": CLAVE_DE_PRUEBA}, format="json")

    assert respuesta.data["usuario"]["debe_activar_segundo_factor"] is True


@pytest.mark.django_db
def test_el_administrador_de_plataforma_tambien_lo_necesita(db):
    # La cuenta de plataforma da de alta centros y reinicia factores: si
    # quedara sin el suyo, sería la puerta más débil del sistema.
    plataforma = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma")
    cliente = APIClient()
    cliente.force_authenticate(user=plataforma)

    respuesta = cliente.get(CENTROS)

    assert respuesta.data["codigo"] == "segundo-factor-pendiente"


@pytest.mark.django_db
def test_el_alta_entrega_el_secreto_y_el_qr_para_la_aplicacion(cliente):
    # El QR es lo que escanea el teléfono; el secreto en texto, lo que se
    # escribe a mano si la cámara no lo lee.
    respuesta = cliente.post(ALTA)

    assert respuesta.status_code == 200
    assert len(respuesta.data["secreto"]) == 32
    assert respuesta.data["enlace"].startswith("otpauth://totp/")
    assert respuesta.data["qr"].startswith("data:image/svg+xml")


@pytest.mark.django_db
def test_confirmar_con_un_codigo_valido_activa_el_factor_y_entrega_diez_codigos(cliente, gerente):
    # Activar sin un primer código dejaría fuera a quien escaneó mal el QR.
    _, respuesta = _alta_completa(cliente)

    assert respuesta.status_code == 200
    assert len(set(respuesta.data["codigos_recuperacion"])) == 10
    assert respuesta.data["usuario"]["segundo_factor_activo"] is True
    assert cliente.get(USUARIOS).status_code == 200


@pytest.mark.django_db
def test_confirmar_con_un_codigo_incorrecto_no_activa_nada(cliente, gerente):
    # Un código mal escrito no puede dejar la cuenta con un factor que su
    # dueña no sabe generar.
    cliente.post(ALTA)

    respuesta = cliente.post(CONFIRMAR, {"codigo": "000000"}, format="json")

    assert respuesta.data["codigo"] == "codigo-incorrecto"
    gerente.refresh_from_db()
    assert gerente.segundo_factor_activo is False


@pytest.mark.django_db
def test_confirmar_sin_haber_pedido_el_alta_se_rechaza(cliente):
    # Sin secreto no hay nada que comprobar; el código estable lleva a la
    # interfaz de vuelta al primer paso del alta.
    respuesta = cliente.post(CONFIRMAR, {"codigo": "123456"}, format="json")

    assert respuesta.data["codigo"] == "segundo-factor-sin-alta"


@pytest.mark.django_db
def test_el_secreto_no_vuelve_a_salir_por_la_api_despues_del_alta(cliente, gerente, centro):
    # Quien robe la sesión no puede llevarse el secreto y generar códigos
    # para siempre. Se revisan todas las respuestas que describen la cuenta
    # y la bitácora de auditoría.
    alta, confirmacion = _alta_completa(cliente)
    secreto = alta["secreto"]

    otra_alta = cliente.post(ALTA)
    respuestas = [confirmacion, otra_alta, cliente.get(ACTUAL), cliente.get(USUARIOS)]

    assert otra_alta.data["codigo"] == "segundo-factor-ya-activo"
    for respuesta in respuestas:
        assert secreto not in respuesta.content.decode()
    activar_centro(centro.pk)
    for registro in RegistroAuditoria.objects.all():
        assert secreto not in str(registro.datos)


@pytest.mark.django_db
def test_el_secreto_y_los_codigos_no_se_guardan_en_claro(cliente, gerente):
    # Una copia de la base no debe bastar para generar los códigos de una
    # administradora ni para usar sus códigos de recuperación.
    alta, confirmacion = _alta_completa(cliente)

    with connection.cursor() as cursor:
        cursor.execute("SELECT secreto_totp FROM usuario WHERE id = %s", [gerente.pk])
        en_la_base = cursor.fetchone()[0]
    resumenes = list(CodigoRecuperacion.objects.filter(usuario=gerente)
                     .values_list("resumen", flat=True))

    assert en_la_base.startswith("fer:")
    assert alta["secreto"] not in en_la_base
    assert len(resumenes) == 10
    for codigo in confirmacion.data["codigos_recuperacion"]:
        assert all(codigo not in r and codigo.replace("-", "") not in r for r in resumenes)


@pytest.mark.django_db
def test_con_contrasena_temporal_primero_se_cambia_la_contrasena(centro, sede):
    # Orden del primer ingreso: la contraseña temporal la conoce quien la
    # entregó, así que se cambia antes de atar el factor a esa cuenta.
    nueva = crear_usuario(centro=centro, correo="nueva@centro.pe", nombres="Ana",
                          apellidos="Paz", rol=Rol.ADMIN_CENTRO, sedes_ids=[sede.pk])
    cliente = APIClient()
    cliente.force_authenticate(user=nueva)

    respuesta = cliente.post(ALTA)

    assert respuesta.data["codigo"] == "cambio-de-contrasena-pendiente"
