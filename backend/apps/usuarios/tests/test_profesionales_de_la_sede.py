"""Pruebas de la lista de profesionales de la sede activa (campo Profesional de P06)."""
import pytest
from rest_framework.test import APIClient

from apps.sedes.models import Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

PROFESIONALES = "/api/v1/sesion/profesionales/"


def _usuario(centro, correo, apellidos, sede=None, activo=True):
    usuario = Usuario.objects.create_user(
        correo=correo, password=CLAVE_DE_PRUEBA, nombres="N", apellidos=apellidos,
        rol=Rol.PODOLOGA, centro=centro, esta_activo=activo,
    )
    if sede is not None:
        AsignacionSede.objects.create(usuario=usuario, sede=sede)
    return usuario


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.mark.django_db
def test_lista_solo_a_quien_el_servidor_aceptaria_como_profesional_de_la_sede(
    cliente, centro, sede, podologa
):
    # Garantiza que P06 no ofrece a nadie que `programar_cita` rechazaría con
    # «profesional-sin-sede»: la lista sigue la misma condición que la regla
    # (cuenta activa y asignación vigente a la sede), ni más ni menos.
    otra = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Ejército 900")
    _usuario(centro, "otra.sede@centro.pe", "Mamani", sede=otra)
    _usuario(centro, "baja@centro.pe", "Condori", sede=sede, activo=False)
    vigente = _usuario(centro, "vigente@centro.pe", "Apaza", sede=sede)

    respuesta = cliente.get(PROFESIONALES)

    ids = [p["id"] for p in respuesta.data["profesionales"]]
    assert respuesta.status_code == 200
    assert ids == [vigente.pk, podologa.pk]  # ordenados por apellidos


@pytest.mark.django_db
def test_sin_sede_activa_responde_con_su_codigo(podologa):
    # Garantiza que, sin la cabecera X-Sede, la pantalla recibe un código que
    # puede traducir, y no una lista de otra sede elegida por omisión.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)

    respuesta = cliente.get(PROFESIONALES)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede-activa"


@pytest.mark.django_db
def test_el_administrador_de_plataforma_no_consulta_profesionales(db):
    # Garantiza que quien opera la plataforma no lista personal de los
    # centros clientes por esta vía.
    plataforma = Usuario.objects.create_superuser(
        correo="soporte@podocenter.pe", password=CLAVE_DE_PRUEBA,
        nombres="Soporte", apellidos="Plataforma",
    )
    cliente = APIClient()
    cliente.force_authenticate(user=plataforma)

    assert cliente.get(PROFESIONALES).status_code == 403
