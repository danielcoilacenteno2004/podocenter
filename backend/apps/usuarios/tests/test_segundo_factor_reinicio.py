"""Pruebas del reinicio del segundo factor y del ingreso al admin (RF18).

Lo que se garantiza: que solo el administrador de plataforma quita un
factor, que nadie de un centro puede quitar el de otro, que el reinicio
queda en la bitácora del centro afectado, y que `/admin/` pide el código.
"""
import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro, con_segundo_factor
from apps.usuarios import totp
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol
from apps.usuarios.segundo_factor import _renovar_codigos_de_recuperacion

from ...conftest import CLAVE_DE_PRUEBA


def _reiniciar(cliente, usuario):
    return cliente.post(f"/api/v1/plataforma/usuarios/{usuario.pk}/reiniciar-segundo-factor/",
                        {"motivo": "perdió el teléfono"}, format="json")


@pytest.fixture
def plataforma(db):
    usuario = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma")
    con_segundo_factor(usuario)
    return usuario


@pytest.fixture
def admin_ajena(otro_centro):
    """Administradora de otro centro, con su factor activo."""
    from apps.sedes.models import Sede

    activar_centro(otro_centro.pk)
    sede = Sede.objects.create(centro=otro_centro, nombre="Norte", direccion="Av. Perú 1")
    usuario = Usuario.objects.create_user(
        correo="admin@limanorte.pe", password=CLAVE_DE_PRUEBA, nombres="Julia",
        apellidos="Soto", rol=Rol.ADMIN_CENTRO, centro=otro_centro)
    AsignacionSede.objects.create(usuario=usuario, sede=sede, es_predeterminada=True)
    con_segundo_factor(usuario)
    _renovar_codigos_de_recuperacion(usuario)
    return usuario


def _como(usuario):
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    return cliente


@pytest.mark.django_db
def test_la_plataforma_reinicia_el_factor_y_queda_en_la_bitacora_del_centro(
        plataforma, admin_ajena, otro_centro):
    # Quien perdió el teléfono y los códigos vuelve a dar de alta el factor;
    # el centro ve en su bitácora quién se lo quitó y por qué.
    respuesta = _reiniciar(_como(plataforma), admin_ajena)

    assert respuesta.status_code == 200
    admin_ajena.refresh_from_db()
    assert admin_ajena.segundo_factor_activo is False
    assert admin_ajena.secreto_totp == ""
    assert admin_ajena.codigos_recuperacion.count() == 0
    activar_centro(otro_centro.pk)
    registro = RegistroAuditoria.objects.get(entidad="segundo_factor", accion="BAJA")
    assert registro.datos["reiniciado_por"] == plataforma.pk
    assert registro.datos["motivo"] == "perdió el teléfono"


@pytest.mark.django_db
def test_una_administradora_de_un_centro_no_reinicia_el_factor_de_otro(
        administradora, admin_ajena):
    # Una cuenta comprometida de un centro no puede debilitar las cuentas de
    # otro centro. La regla la aplica el servidor, no la interfaz.
    respuesta = _reiniciar(_como(administradora), admin_ajena)

    assert respuesta.status_code == 403
    admin_ajena.refresh_from_db()
    assert admin_ajena.segundo_factor_activo is True
    assert admin_ajena.codigos_recuperacion.count() == 10


@pytest.mark.django_db
def test_tampoco_reinicia_el_de_su_propio_centro(administradora, podologa):
    # El reinicio es solo de la plataforma: si la administradora pudiera
    # hacerlo, una sola cuenta comprometida quitaría el factor a las demás.
    con_segundo_factor(podologa)

    respuesta = _reiniciar(_como(administradora), podologa)

    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_la_plataforma_no_reinicia_el_suyo(plataforma):
    # Otra persona debe hacerlo; si no, quien robe la contraseña de la cuenta
    # de plataforma con la sesión abierta podría quitarse el factor él mismo.
    respuesta = _reiniciar(_como(plataforma), plataforma)

    assert respuesta.data["codigo"] == "reiniciar-el-propio"


@pytest.mark.django_db
def test_el_admin_de_django_pide_el_codigo(plataforma):
    # `/admin/` es otra puerta a la misma cuenta. Sin código, la contraseña
    # sola no abre el admin; con el código, sí.
    datos = {"username": plataforma.correo, "password": CLAVE_DE_PRUEBA,
             "next": "/admin/"}
    sin_factor = Client()
    sin_codigo = sin_factor.post("/admin/login/", datos)

    codigo = totp.codigo_del_paso(plataforma.secreto_totp, totp.paso_en())
    navegador = Client()
    con_codigo = navegador.post("/admin/login/", {**datos, "codigo": codigo})

    assert sin_codigo.status_code == 200  # vuelve al formulario con el error
    assert "_auth_user_id" not in sin_factor.session
    assert con_codigo.status_code == 302
    assert navegador.get("/admin/").status_code == 200


@pytest.mark.django_db
def test_el_admin_no_deja_entrar_a_quien_aun_no_dio_de_alta_el_factor(db):
    # El admin no tiene pantalla de alta: quien no tiene factor lo activa en
    # la aplicación antes de poder entrar aquí.
    sin_factor = Usuario.objects.create_superuser(
        correo="nuevo@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Nuevo", apellidos="Soporte")
    navegador = Client()
    navegador.force_login(sin_factor)

    assert navegador.get("/admin/").status_code == 302
    respuesta = Client().post("/admin/login/", {"username": sin_factor.correo,
                                                "password": CLAVE_DE_PRUEBA})
    assert "Active primero la verificación" in respuesta.content.decode()


@pytest.mark.django_db
def test_la_accion_del_admin_reinicia_con_auditoria(plataforma, admin_ajena, otro_centro):
    # El administrador de plataforma trabaja desde el admin: la acción pasa
    # por el mismo servicio y deja la misma constancia que la API.
    navegador = Client()
    navegador.force_login(plataforma)

    navegador.post("/admin/usuarios/usuario/", {
        "action": "reiniciar_segundo_factor", "_selected_action": [admin_ajena.pk]})

    admin_ajena.refresh_from_db()
    assert admin_ajena.segundo_factor_activo is False
    activar_centro(otro_centro.pk)
    assert RegistroAuditoria.objects.filter(entidad="segundo_factor", accion="BAJA").exists()
