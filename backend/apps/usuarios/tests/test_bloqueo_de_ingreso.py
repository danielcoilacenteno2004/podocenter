"""Bloqueo temporal tras cinco contraseñas erradas seguidas (Tabla 35 del Informe, DEF-25).

Sin él, una contraseña se puede adivinar probando sin límite. Las pruebas
cubren las dos puertas de entrada (la API y /admin/), que el bloqueo resista la
contraseña correcta, que caduque, que no sirva para enumerar correos y que la
administradora tenga cómo levantarlo.
"""
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro, con_segundo_factor
from apps.usuarios import bloqueo_de_ingreso, totp
from apps.usuarios.models import Usuario

from ...conftest import CLAVE_DE_PRUEBA

INGRESAR = "/api/v1/sesion/ingresar/"
USUARIOS = "/api/v1/usuarios/"
MAXIMO = bloqueo_de_ingreso.MAXIMO_DE_INTENTOS_FALLIDOS


def _ingresar(correo, contrasena):
    return APIClient().post(INGRESAR, {"correo": correo, "contrasena": contrasena},
                            format="json")


def _fallar(correo, veces):
    return [_ingresar(correo, "NoEsLaClave-123") for _ in range(veces)]


@pytest.mark.django_db
def test_el_quinto_fallo_bloquea_y_ni_la_contrasena_correcta_entra(podologa):
    # Es el caso CP-03: los cuatro primeros fallos responden como cualquier
    # credencial errada, el quinto avisa del bloqueo y, durante el bloqueo, la
    # contraseña correcta tampoco abre la sesión. Si la correcta entrara, quien
    # adivina seguiría probando con solo esperar a acertar.
    respuestas = _fallar(podologa.correo, MAXIMO)
    con_la_correcta = _ingresar(podologa.correo, CLAVE_DE_PRUEBA)

    assert [r.status_code for r in respuestas[:-1]] == [401] * (MAXIMO - 1)
    assert respuestas[-1].status_code == 422
    assert respuestas[-1].data["codigo"] == "ingreso-bloqueado"
    assert con_la_correcta.status_code == 422
    assert con_la_correcta.data["codigo"] == "ingreso-bloqueado"


@pytest.mark.django_db
def test_pasados_quince_minutos_vuelve_a_entrar(podologa):
    # El bloqueo es temporal, no una baja: pasado el plazo, la dueña de la
    # cuenta entra sin pedir nada a nadie.
    _fallar(podologa.correo, MAXIMO)
    Usuario.objects.filter(pk=podologa.pk).update(
        ingreso_bloqueado_hasta=timezone.now() - timedelta(seconds=1))

    assert _ingresar(podologa.correo, CLAVE_DE_PRUEBA).status_code == 200


@pytest.mark.django_db
def test_el_bloqueo_dura_quince_minutos(podologa):
    # Fija el plazo de la Tabla 35: ni menos, que haría el bloqueo inútil, ni
    # más, que dejaría fuera a la podóloga media mañana por equivocarse.
    antes = timezone.now()
    _fallar(podologa.correo, MAXIMO)
    hasta = Usuario.objects.get(pk=podologa.pk).ingreso_bloqueado_hasta

    assert timedelta(minutes=15) <= hasta - antes < timedelta(minutes=15, seconds=30)


@pytest.mark.django_db
def test_un_ingreso_correcto_reinicia_la_cuenta_de_fallos(podologa):
    # Los fallos tienen que ser seguidos. Quien se equivoca de vez en cuando a
    # lo largo de la semana no debe quedar bloqueada por acumulación.
    _fallar(podologa.correo, MAXIMO - 1)
    assert _ingresar(podologa.correo, CLAVE_DE_PRUEBA).status_code == 200
    respuestas = _fallar(podologa.correo, MAXIMO - 1)

    assert all(r.status_code == 401 for r in respuestas)


@pytest.mark.django_db
def test_un_correo_inexistente_nunca_se_bloquea(db):
    # El bloqueo no puede delatar qué correos existen: con un correo que no
    # está registrado, la respuesta sigue siendo el mismo 401 de siempre.
    respuestas = _fallar("nadie@centro.pe", MAXIMO + 2)

    assert all(r.status_code == 401 for r in respuestas)
    assert all(r.data["codigo"] == "credenciales-invalidas" for r in respuestas)


@pytest.mark.django_db
def test_el_bloqueo_de_una_cuenta_no_afecta_a_otra(podologa, administradora):
    # El contador es por cuenta. Si fuera global, cualquiera podría dejar fuera
    # a todo el centro equivocándose cinco veces con su propio correo.
    con_segundo_factor(administradora)
    _fallar(podologa.correo, MAXIMO)

    respuesta = _ingresar(administradora.correo, CLAVE_DE_PRUEBA)

    assert respuesta.status_code == 200
    assert respuesta.data["segundo_factor_requerido"] is True


@pytest.mark.django_db
def test_el_bloqueo_queda_en_la_bitacora_del_centro(podologa, centro):
    # La administradora tiene que poder ver que alguien intentó entrar a una
    # cuenta de su centro (OWASP A09), sin que la bitácora guarde lo escrito.
    _fallar(podologa.correo, MAXIMO)
    activar_centro(centro.pk)  # cada petición deja el contexto vacío al terminar

    registro = RegistroAuditoria.objects.get(accion="ACCESO_DENEGADO",
                                            entidad_id=str(podologa.pk))
    assert registro.datos == {"motivo": "ingreso-bloqueado"}


@pytest.mark.django_db
def test_la_contrasena_temporal_levanta_el_bloqueo(podologa, administradora, sede):
    # La salida para quien no puede esperar los 15 minutos: la administradora
    # le da una contraseña temporal, y con ella entra de inmediato.
    _fallar(podologa.correo, MAXIMO)
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))

    temporal = cliente.post(f"{USUARIOS}{podologa.pk}/restablecer-contrasena/").data[
        "contrasena_temporal"]

    assert _ingresar(podologa.correo, temporal).status_code == 200


@pytest.mark.django_db
def test_el_admin_de_django_tambien_bloquea(db):
    # /admin/ es otra puerta a las mismas cuentas, y la más valiosa: si allí no
    # hubiera bloqueo, la regla de la API no protegería nada.
    plataforma = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma")
    con_segundo_factor(plataforma)
    erradas = {"username": plataforma.correo, "password": "NoEsLaClave-123", "next": "/admin/"}
    for _ in range(MAXIMO):
        Client().post("/admin/login/", erradas)

    navegador = Client()
    codigo = totp.codigo_del_paso(plataforma.secreto_totp, totp.paso_en())
    respuesta = navegador.post("/admin/login/", {**erradas, "password": CLAVE_DE_PRUEBA,
                                                 "codigo": codigo})

    assert respuesta.status_code == 200  # vuelve al formulario con el aviso
    assert "_auth_user_id" not in navegador.session
    assert "bloqueada" in respuesta.content.decode()
