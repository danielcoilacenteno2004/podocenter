"""Pruebas del cambio de contraseña desde «Mi perfil y seguridad» (P20, RF18)."""
import pytest
from django.contrib.auth import authenticate
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria

from ...conftest import CLAVE_DE_PRUEBA

CAMBIAR = "/api/v1/sesion/contrasena/"
ACTUAL = "/api/v1/sesion/actual/"
NUEVA = "Calzado-Ortopedico-2026"


def _sesion_real(usuario):
    """Una sesión de verdad (cookie), no force_authenticate: el cambio de
    contraseña invalida sesiones, y eso solo se ve con sesiones reales."""
    cliente = APIClient()
    assert cliente.login(username=usuario.correo, password=CLAVE_DE_PRUEBA)
    return cliente


def _cambiar(cliente, actual=CLAVE_DE_PRUEBA, nueva=NUEVA, confirmacion=None):
    return cliente.post(CAMBIAR, {
        "contrasena_actual": actual, "contrasena_nueva": nueva,
        "confirmacion": nueva if confirmacion is None else confirmacion,
    }, format="json")


@pytest.mark.django_db
def test_cambia_la_contrasena_y_la_vieja_deja_de_servir(podologa):
    # Garantiza el efecto que importa: después del cambio se entra con la
    # nueva y no con la anterior, que es lo que protege una cuenta cuya
    # contraseña se filtró.
    cliente = _sesion_real(podologa)

    respuesta = _cambiar(cliente)

    assert respuesta.status_code == 200
    assert authenticate(username=podologa.correo, password=NUEVA) is not None
    assert authenticate(username=podologa.correo, password=CLAVE_DE_PRUEBA) is None


@pytest.mark.django_db
def test_mantiene_la_sesion_actual_y_cierra_las_demas(podologa):
    # Garantiza lo que pide la Tabla 33: quien cambia la contraseña sigue
    # trabajando, pero una sesión abierta en otro equipo (quizá la de quien
    # conocía la contraseña vieja) queda fuera.
    aqui = _sesion_real(podologa)
    en_otro_equipo = _sesion_real(podologa)

    _cambiar(aqui)

    assert aqui.get(ACTUAL).data["autenticado"] is True
    assert en_otro_equipo.get(ACTUAL).data["autenticado"] is False


@pytest.mark.django_db
def test_rechaza_el_cambio_si_la_contrasena_actual_no_es_correcta(podologa):
    # Garantiza que una sesión olvidada abierta no basta para quedarse con la
    # cuenta: sin la contraseña actual no se puede poner otra.
    cliente = _sesion_real(podologa)

    respuesta = _cambiar(cliente, actual="no-es-la-mia-2026")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "contrasena-actual-incorrecta"
    assert authenticate(username=podologa.correo, password=CLAVE_DE_PRUEBA) is not None


@pytest.mark.django_db
@pytest.mark.parametrize("nueva", ["corta1", "1234567890123", "password1234"])
def test_aplica_la_politica_de_contrasenas_de_django(podologa, nueva):
    # Garantiza que la política de la P5 (mínimo 10, no solo números, no
    # común) se aplica también al cambiar, no solo al crear la cuenta: es la
    # misma configuración, AUTH_PASSWORD_VALIDATORS.
    cliente = _sesion_real(podologa)

    respuesta = _cambiar(cliente, nueva=nueva)

    assert respuesta.status_code == 400
    assert respuesta.data["detail"]["contrasena_nueva"]
    assert authenticate(username=podologa.correo, password=CLAVE_DE_PRUEBA) is not None


@pytest.mark.django_db
def test_rechaza_una_confirmacion_que_no_coincide(podologa):
    # Garantiza que un error de tecleo no deja al usuario con una contraseña
    # que no sabe: si las dos no coinciden, no se cambia nada.
    cliente = _sesion_real(podologa)

    respuesta = _cambiar(cliente, confirmacion=NUEVA + "x")

    assert respuesta.status_code == 400
    assert authenticate(username=podologa.correo, password=CLAVE_DE_PRUEBA) is not None


@pytest.mark.django_db
def test_el_cambio_queda_en_la_bitacora_sin_ninguna_contrasena(podologa):
    # Garantiza la trazabilidad de un cambio de seguridad sin que la bitácora,
    # que se guarda en claro, contenga la contraseña vieja ni la nueva.
    cliente = _sesion_real(podologa)

    _cambiar(cliente)

    registro = RegistroAuditoria.objects.get(entidad="usuario", entidad_id=str(podologa.pk),
                                             accion="EDICION")
    assert NUEVA not in str(registro.datos)
    assert CLAVE_DE_PRUEBA not in str(registro.datos)


@pytest.mark.django_db
def test_sin_sesion_no_se_puede_cambiar_ninguna_contrasena(db):
    # Garantiza que la ruta no sirve para probar contraseñas de otros: exige
    # una sesión abierta.
    respuesta = APIClient().post(CAMBIAR, {"contrasena_actual": "x"}, format="json")

    assert respuesta.status_code == 403
