"""Pruebas de la API de centros clientes (RF17, P19 y P29) y de la suspensión."""
import pytest
from django.contrib.auth import authenticate
from rest_framework.test import APIClient

from apps.core.models import Centro, RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

CENTROS = "/api/v1/centros/"
INGRESAR = "/api/v1/sesion/ingresar/"

ALTA = {
    "ruc": "20555666777", "razon_social": "Podología Yanahuara S.A.C.",
    "nombre_comercial": "Pies Felices", "subdominio": "piesfelices",
    "correo_contacto": "contacto@piesfelices.pe",
    "administrador": {
        "nombres": "Rocío", "apellidos": "Flores", "correo": "rflores@piesfelices.pe",
    },
}


@pytest.fixture
def plataforma(db):
    usuario = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma",
    )
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


def _ingresar(correo, contrasena):
    return APIClient().post(INGRESAR, {"correo": correo, "contrasena": contrasena}, format="json")


# --- Alta con administrador inicial ------------------------------------------

@pytest.mark.django_db
def test_el_alta_crea_el_centro_con_su_administrador_listo_para_entrar(plataforma):
    # Garantiza que un centro recién dado de alta se puede usar: tiene un
    # administrador propio y este entra con la contraseña temporal que se le
    # comunica. Sin él, nadie podría dar de alta al personal del centro.
    respuesta = plataforma.post(CENTROS, ALTA, format="json")

    assert respuesta.status_code == 201
    centro = Centro.objects.get(ruc=ALTA["ruc"])
    admin = Usuario.objects.get(correo="rflores@piesfelices.pe")
    assert (admin.rol, admin.centro_id) == (Rol.ADMIN_CENTRO, centro.pk)
    assert centro.nombre_comercial == "Pies Felices"
    ingreso = _ingresar(admin.correo, respuesta.data["contrasena_temporal"])
    assert ingreso.status_code == 200
    # La temporal la conoce también la plataforma: el administrador debe
    # cambiarla antes de usar el sistema.
    assert ingreso.data["usuario"]["debe_cambiar_contrasena"] is True


@pytest.mark.django_db
def test_la_contrasena_temporal_solo_sale_en_la_respuesta_del_alta(plataforma):
    # Garantiza que la contraseña temporal no se puede volver a pedir: no se
    # guarda en claro y la ficha del centro no la devuelve.
    creado = plataforma.post(CENTROS, ALTA, format="json")

    ficha = plataforma.get(f"{CENTROS}{creado.data['id']}/")

    assert "contrasena_temporal" not in ficha.data
    assert len(creado.data["contrasena_temporal"]) >= 16


@pytest.mark.django_db
def test_si_el_administrador_no_se_puede_crear_tampoco_queda_el_centro(plataforma, podologa):
    # Garantiza que no queden centros sin administrador: con un correo ya
    # usado, el alta se rechaza entera y el centro no se crea.
    datos = {**ALTA, "administrador": {**ALTA["administrador"], "correo": podologa.correo}}

    respuesta = plataforma.post(CENTROS, datos, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "correo-duplicado"
    assert not Centro.objects.filter(ruc=ALTA["ruc"]).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("campo", ["nombre_comercial", "correo_contacto", "administrador"])
def test_el_alta_exige_los_datos_de_la_tabla_32(plataforma, campo):
    # Garantiza que los campos obligatorios del diseño lo son también en el
    # servidor, no solo en el formulario.
    datos = {k: v for k, v in ALTA.items() if k != campo}

    respuesta = plataforma.post(CENTROS, datos, format="json")

    assert respuesta.status_code == 400
    assert not Centro.objects.filter(ruc=ALTA["ruc"]).exists()


@pytest.mark.django_db
def test_el_alta_queda_en_la_bitacora_del_centro_nuevo(plataforma):
    # Garantiza la trazabilidad del alta en la bitácora del propio centro, y
    # sin la contraseña temporal.
    creado = plataforma.post(CENTROS, ALTA, format="json")

    activar_centro(creado.data["id"])
    registros = RegistroAuditoria.objects.filter(accion="ALTA")
    assert {r.entidad for r in registros} == {"centro", "usuario"}
    assert creado.data["contrasena_temporal"] not in str([r.datos for r in registros])


# --- Suspensión ---------------------------------------------------------------

@pytest.mark.django_db
def test_suspender_exige_un_motivo(plataforma, centro):
    # Garantiza la Tabla 31: suspender a un cliente deja constancia de por qué.
    respuesta = plataforma.patch(f"{CENTROS}{centro.pk}/", {"estado": "SUSPENDIDO"},
                                 format="json")

    assert respuesta.status_code == 400
    centro.refresh_from_db()
    assert centro.estado == Centro.Estado.ACTIVO


@pytest.mark.django_db
def test_un_centro_suspendido_no_puede_iniciar_sesion(plataforma, centro, podologa):
    # Garantiza que suspender tiene efecto: con credenciales válidas, el
    # usuario de un centro suspendido no entra y recibe el mensaje del
    # servidor; además queda el intento en la bitácora del centro.
    plataforma.patch(f"{CENTROS}{centro.pk}/",
                     {"estado": "SUSPENDIDO", "motivo_suspension": "Falta de pago"}, format="json")

    respuesta = _ingresar(podologa.correo, CLAVE_DE_PRUEBA)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "centro-suspendido"
    assert "suspendido" in respuesta.data["detail"]
    activar_centro(centro.pk)
    assert RegistroAuditoria.objects.filter(accion="ACCESO_DENEGADO").exists()


@pytest.mark.django_db
def test_al_reactivar_el_centro_sus_usuarios_vuelven_a_entrar(plataforma, centro, podologa):
    # Garantiza que la suspensión es reversible y que no deja cuentas
    # inutilizadas: al reactivar, las mismas credenciales vuelven a servir.
    ruta = f"{CENTROS}{centro.pk}/"
    plataforma.patch(ruta, {"estado": "SUSPENDIDO", "motivo_suspension": "Falta de pago"},
                     format="json")

    plataforma.patch(ruta, {"estado": "ACTIVO"}, format="json")

    assert _ingresar(podologa.correo, CLAVE_DE_PRUEBA).status_code == 200


@pytest.mark.django_db
def test_la_suspension_no_afecta_al_administrador_de_plataforma(centro):
    # Garantiza que quien suspende no queda fuera: el administrador de
    # plataforma no pertenece a ningún centro.
    Usuario.objects.create_superuser(correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
                                     nombres="Soporte", apellidos="Plataforma")
    Centro.objects.filter(pk=centro.pk).update(estado=Centro.Estado.SUSPENDIDO)

    assert authenticate(username="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA)
    assert _ingresar("soporte@podocenter.pe", CLAVE_DE_PRUEBA).status_code == 200


# --- Permisos y borrado ---------------------------------------------------------

@pytest.mark.django_db
def test_solo_el_administrador_de_plataforma_gestiona_centros(administradora, sede):
    # Garantiza que la administradora de un centro no ve ni toca a los demás
    # clientes del servicio.
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)

    assert cliente.get(CENTROS).status_code == 403
    assert cliente.post(CENTROS, ALTA, format="json").status_code == 403


@pytest.mark.django_db
def test_un_centro_no_se_borra(plataforma, centro):
    # Garantiza que un cliente no desaparece con sus datos: se suspende.
    respuesta = plataforma.delete(f"{CENTROS}{centro.pk}/")

    assert respuesta.status_code == 405
    assert Centro.objects.filter(pk=centro.pk).exists()
