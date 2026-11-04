"""Pruebas del inicio y cierre de sesión (CU02, RF02).

Interesa comprobar tres cosas: que una credencial válida abre sesión, que
una inválida no distingue entre correo inexistente y contraseña errada, y
que el acceso queda registrado en la bitácora de auditoría.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

INGRESAR = "/api/v1/sesion/ingresar/"
SALIR = "/api/v1/sesion/salir/"
ACTUAL = "/api/v1/sesion/actual/"


@pytest.fixture
def cliente():
    return APIClient()


@pytest.mark.django_db
def test_sin_sesion_el_estado_dice_que_no_hay_nadie(cliente):
    # El estado es público: responde 200 con `autenticado: false` en lugar de
    # 401, porque la SPA lo consulta al arrancar y un 401 ahí ensuciaría la
    # consola.
    respuesta = cliente.get(ACTUAL)

    assert respuesta.status_code == 200
    assert respuesta.data == {"autenticado": False, "usuario": None}


@pytest.mark.django_db
def test_la_cookie_csrf_se_entrega_al_consultar_el_estado(cliente):
    # Esta consulta es la que siembra la cookie CSRF. Sin ella el POST de
    # ingreso sería rechazado por el middleware y el formulario no funcionaría
    # nunca.
    respuesta = cliente.get(ACTUAL)

    assert "csrftoken" in respuesta.cookies


@pytest.mark.django_db
def test_credenciales_validas_abren_la_sesion(cliente, podologa):
    # Camino feliz del CU02. Se comprueba además que la respuesta traiga el rol,
    # porque de él depende qué menú dibuja el cliente.
    respuesta = cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )

    assert respuesta.status_code == 200
    assert respuesta.data["autenticado"] is True
    assert respuesta.data["usuario"]["rol"] == Rol.PODOLOGA
    assert respuesta.data["usuario"]["nombre_completo"] == podologa.nombre_completo


@pytest.mark.django_db
def test_el_correo_se_normaliza_antes_de_comparar(cliente, podologa):
    # La podóloga escribe su correo desde el celular, donde el teclado suele
    # poner mayúscula inicial y a veces un espacio al pegar. Eso no puede
    # impedirle entrar.
    respuesta = cliente.post(
        INGRESAR,
        {"correo": f"  {podologa.correo.upper()}  ", "contrasena": CLAVE_DE_PRUEBA},
        format="json",
    )

    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_la_respuesta_no_devuelve_la_contrasena(cliente, podologa):
    # Ningún campo de credencial puede viajar de vuelta al navegador, ni
    # siquiera en su forma cifrada (OWASP A02).
    respuesta = cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )

    assert "password" not in respuesta.data["usuario"]
    assert "contrasena" not in respuesta.data["usuario"]


@pytest.mark.django_db
def test_la_contrasena_errada_no_abre_la_sesion(cliente, podologa):
    # El rechazo llega con un código estable, que es lo que la pantalla P01
    # traduce al mensaje en español (Práctica N.° 7, Tabla de errores).
    respuesta = cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": "noEsLaClave"}, format="json"
    )

    assert respuesta.status_code == 401
    assert respuesta.data["codigo"] == "credenciales-invalidas"


@pytest.mark.django_db
def test_un_correo_inexistente_responde_igual_que_una_clave_errada(cliente, podologa):
    """No se confirma qué correos existen: evita enumerar cuentas."""
    con_clave_mala = cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": "noEsLaClave"}, format="json"
    )
    con_correo_inexistente = cliente.post(
        INGRESAR, {"correo": "nadie@ejemplo.pe", "contrasena": "noEsLaClave"}, format="json"
    )

    assert con_clave_mala.status_code == con_correo_inexistente.status_code == 401
    assert con_clave_mala.data["detail"] == con_correo_inexistente.data["detail"]


@pytest.mark.django_db
def test_faltan_datos_y_el_error_lo_dice(cliente):
    # Un formulario vacío debe producir un error de negocio con código propio,
    # no una traza del servidor.
    respuesta = cliente.post(INGRESAR, {"correo": "", "contrasena": ""}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "credenciales-incompletas"


@pytest.mark.django_db
def test_un_usuario_desactivado_no_puede_entrar(cliente, podologa):
    """Y recibe el mismo 401 genérico: la baja de una cuenta no se anuncia."""
    podologa.esta_activo = False
    podologa.save(update_fields=["esta_activo"])

    respuesta = cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )

    assert respuesta.status_code == 401
    assert respuesta.data["codigo"] == "credenciales-invalidas"


@pytest.mark.django_db
def test_el_acceso_queda_en_la_bitacora(cliente, centro, podologa):
    # El RNF06 exige poder reconstruir quién entró al sistema y cuándo; sin este
    # registro, la trazabilidad de los accesos a datos clínicos se rompe.
    cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )
    activar_centro(centro.pk)

    registro = RegistroAuditoria.objects.filter(accion="ACCESO", entidad="sesion").first()
    assert registro is not None
    assert registro.usuario_id == podologa.pk


@pytest.mark.django_db
def test_tras_ingresar_el_estado_devuelve_al_usuario(cliente, podologa):
    # Es lo que permite recargar una pantalla interna sin volver al formulario:
    # la SPA restaura la sesión preguntando por ella.
    cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )

    respuesta = cliente.get(ACTUAL)

    assert respuesta.data["autenticado"] is True
    assert respuesta.data["usuario"]["correo"] == podologa.correo


@pytest.mark.django_db
def test_el_ingreso_deja_constancia_de_la_fecha_de_acceso(cliente, podologa):
    # El último acceso se muestra en la pantalla de perfil y sirve para detectar
    # cuentas abandonadas que conviene desactivar.
    assert podologa.ultimo_acceso_en is None

    cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )
    podologa.refresh_from_db()

    assert podologa.ultimo_acceso_en is not None


@pytest.mark.django_db
def test_al_salir_la_sesion_se_cierra(cliente, podologa):
    # Cerrar sesión tiene que invalidar la cookie en el servidor, no solo borrar
    # el estado del navegador: en un equipo compartido eso es la diferencia.
    cliente.post(
        INGRESAR, {"correo": podologa.correo, "contrasena": CLAVE_DE_PRUEBA}, format="json"
    )

    salida = cliente.post(SALIR)

    assert salida.status_code == 200
    assert cliente.get(ACTUAL).data["autenticado"] is False


@pytest.mark.django_db
def test_salir_sin_sesion_no_es_un_error(cliente):
    # Pulsar «Salir» dos veces, o con la sesión ya expirada, no debe producir un
    # error que el usuario no pueda entender ni resolver.
    assert cliente.post(SALIR).status_code == 200
