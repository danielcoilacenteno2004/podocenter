"""Contraseña temporal del alta y del restablecimiento, y su cambio obligado.

Sin esto una cuenta nueva no podía entrar: el alta le ponía una contraseña
aleatoria que nadie conocía, y la recuperación por correo (P23/P24) no existe.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.sedes.models import Sede
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol
from apps.usuarios.servicios import crear_usuario

from ...conftest import CLAVE_DE_PRUEBA

USUARIOS = "/api/v1/usuarios/"
INGRESAR = "/api/v1/sesion/ingresar/"
CAMBIAR = "/api/v1/sesion/contrasena/"
NUEVA = "Plantilla-Ortopedica-2026"


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


def _ingresar(correo, contrasena, sede=None):
    cliente = APIClient()
    respuesta = cliente.post(INGRESAR, {"correo": correo, "contrasena": contrasena},
                             format="json")
    if sede is not None:
        cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente, respuesta


def _alta(cliente, sede, correo="nueva@centro.pe"):
    return cliente.post(USUARIOS, {
        "correo": correo, "nombres": "Nadia", "apellidos": "Torres",
        "rol": Rol.PODOLOGA, "sedes_ids": [sede.pk],
    }, format="json")


@pytest.mark.django_db
def test_el_alta_devuelve_una_contrasena_temporal_con_la_que_se_entra(cliente, sede):
    # Garantiza que una cuenta creada desde P27 se puede usar: la
    # administradora recibe la contraseña para entregarla, y con ella se entra.
    respuesta = _alta(cliente, sede)
    temporal = respuesta.data["contrasena_temporal"]

    _, ingreso = _ingresar("nueva@centro.pe", temporal)

    assert respuesta.status_code == 201
    assert len(temporal) >= 12
    assert ingreso.status_code == 200
    assert ingreso.data["usuario"]["debe_cambiar_contrasena"] is True


@pytest.mark.django_db
def test_la_temporal_no_se_puede_volver_a_pedir(cliente, sede):
    # Garantiza que la contraseña sale una sola vez: ni la ficha ni el listado
    # la devuelven, porque no se guarda en claro.
    creada = _alta(cliente, sede).data

    ficha = cliente.get(f"{USUARIOS}{creada['id']}/").data

    assert "contrasena_temporal" not in ficha
    assert creada["contrasena_temporal"] not in str(cliente.get(USUARIOS).data)


@pytest.mark.django_db
def test_con_la_temporal_la_api_solo_deja_cambiarla(cliente, sede):
    # Garantiza el bloqueo en el servidor, no solo en la interfaz: quien
    # entregó la contraseña la conoce, así que hasta que el titular la cambie
    # la cuenta no puede leer pacientes. Sí puede ver sus sedes, que la
    # interfaz pide al entrar.
    temporal = _alta(cliente, sede).data["contrasena_temporal"]
    nueva, _ = _ingresar("nueva@centro.pe", temporal, sede)

    pacientes = nueva.get("/api/v1/pacientes/")
    sedes = nueva.get("/api/v1/sesion/sedes/")

    assert pacientes.status_code == 422
    assert pacientes.data["codigo"] == "cambio-de-contrasena-pendiente"
    assert sedes.status_code == 200


@pytest.mark.django_db
def test_al_cambiarla_se_levanta_el_bloqueo_y_la_temporal_deja_de_servir(cliente, sede):
    # Garantiza la salida del estado temporal: después del cambio la cuenta
    # trabaja con normalidad y la contraseña entregada ya no abre sesión.
    temporal = _alta(cliente, sede).data["contrasena_temporal"]
    nueva, _ = _ingresar("nueva@centro.pe", temporal, sede)

    cambio = nueva.post(CAMBIAR, {"contrasena_actual": temporal, "contrasena_nueva": NUEVA,
                                  "confirmacion": NUEVA}, format="json")
    pacientes = nueva.get("/api/v1/pacientes/")
    _, con_la_vieja = _ingresar("nueva@centro.pe", temporal)

    assert cambio.status_code == 200
    assert pacientes.status_code == 200
    assert con_la_vieja.status_code == 401
    assert Usuario.objects.get(correo="nueva@centro.pe").debe_cambiar_contrasena is False


@pytest.mark.django_db
def test_restablecer_da_una_temporal_nueva_y_cierra_las_sesiones(cliente, podologa, sede):
    # Garantiza el camino de quien olvidó su contraseña: la administradora le
    # da una nueva, la anterior deja de servir y una sesión que siguiera
    # abierta (un equipo olvidado) se corta.
    abierta, _ = _ingresar(podologa.correo, CLAVE_DE_PRUEBA, sede)
    assert abierta.get("/api/v1/pacientes/").status_code == 200

    respuesta = cliente.post(f"{USUARIOS}{podologa.pk}/restablecer-contrasena/")
    temporal = respuesta.data["contrasena_temporal"]

    assert respuesta.status_code == 200
    assert abierta.get("/api/v1/pacientes/").status_code in (401, 403)
    assert _ingresar(podologa.correo, CLAVE_DE_PRUEBA)[1].status_code == 401
    assert _ingresar(podologa.correo, temporal)[1].data["usuario"]["debe_cambiar_contrasena"]


@pytest.mark.django_db
def test_el_restablecimiento_queda_auditado_sin_la_contrasena(cliente, podologa):
    # Garantiza la trazabilidad (quién restableció a quién) sin que la
    # bitácora se convierta en un sitio donde leer contraseñas.
    temporal = cliente.post(f"{USUARIOS}{podologa.pk}/restablecer-contrasena/").data[
        "contrasena_temporal"]

    registro = RegistroAuditoria.objects.filter(
        entidad="usuario", entidad_id=podologa.pk).order_by("pk").last()

    assert registro.datos == {"contrasena": "restablecida"}
    assert temporal not in str(registro.datos)


@pytest.mark.django_db
def test_la_propia_contrasena_no_se_restablece(cliente, administradora):
    # Garantiza que nadie se salte P20, que pide la contraseña actual: con una
    # sesión robada no se podría fijar una contraseña nueva sin conocerla.
    respuesta = cliente.post(f"{USUARIOS}{administradora.pk}/restablecer-contrasena/")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "restablecer-la-propia"


@pytest.mark.django_db
def test_la_podologa_no_puede_restablecer(podologa, administradora, sede):
    # Garantiza que restablecer contraseñas es de la administradora: si no,
    # cualquier cuenta podría quedarse con la de otra.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))

    respuesta = cliente.post(f"{USUARIOS}{administradora.pk}/restablecer-contrasena/")

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_no_se_restablece_a_un_usuario_de_otro_centro(cliente, centro, otro_centro):
    # Garantiza el aislamiento: una administradora no puede tomar una cuenta
    # de otro centro restableciéndole la contraseña.
    activar_centro(otro_centro.pk)
    sede = Sede.objects.create(centro=otro_centro, nombre="Lima", direccion="Jr. Unión 1")
    ajena = crear_usuario(centro=otro_centro, correo="ajena@lima.pe", nombres="P",
                          apellidos="I", rol=Rol.PODOLOGA, sedes_ids=[sede.pk],
                          password=CLAVE_DE_PRUEBA)
    activar_centro(centro.pk)

    respuesta = cliente.post(f"{USUARIOS}{ajena.pk}/restablecer-contrasena/")

    assert respuesta.status_code == 404
    activar_centro(otro_centro.pk)
    assert Usuario.objects.get(pk=ajena.pk).check_password(CLAVE_DE_PRUEBA)
