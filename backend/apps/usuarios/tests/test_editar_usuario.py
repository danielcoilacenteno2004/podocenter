"""Edición de usuarios por la API (P27): rol, sedes y datos por el servicio.

Antes el PATCH escribía directo en el modelo: quitaba el rol a la única
administradora sin la regla del último administrador e ignoraba las sedes.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.sedes.models import Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol

USUARIOS = "/api/v1/usuarios/"


@pytest.fixture
def cliente(administradora, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=administradora)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def segunda_sede(centro):
    return Sede.objects.create(centro=centro, nombre="Bustamante", direccion="Av. Dolores 320")


def _vigentes(usuario):
    return set(AsignacionSede.objects.filter(usuario=usuario, esta_activa=True)
               .values_list("sede_id", flat=True))


@pytest.mark.django_db
def test_la_unica_administradora_no_pierde_el_rol(cliente, administradora):
    # Garantiza la regla del último administrador también al editar: el
    # PATCH dejaba al centro sin nadie que pudiera gestionar a su personal.
    respuesta = cliente.patch(f"{USUARIOS}{administradora.pk}/", {"rol": Rol.PODOLOGA},
                              format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "ultimo-administrador"
    administradora.refresh_from_db()
    assert administradora.rol == Rol.ADMIN_CENTRO


@pytest.mark.django_db
def test_con_otra_administradora_el_rol_si_se_cambia(cliente, administradora, podologa):
    # Garantiza que la regla no bloquea de más: si hay otra administradora
    # activa, el cambio de rol procede y queda auditado.
    cliente.patch(f"{USUARIOS}{podologa.pk}/", {"rol": Rol.ADMIN_CENTRO}, format="json")

    respuesta = cliente.patch(f"{USUARIOS}{administradora.pk}/", {"rol": Rol.PODOLOGA},
                              format="json")

    assert respuesta.status_code == 200
    registro = RegistroAuditoria.objects.filter(entidad="usuario",
                                                entidad_id=administradora.pk).last()
    assert registro.datos == {"rol": Rol.PODOLOGA}


@pytest.mark.django_db
def test_las_sedes_se_reasignan_y_la_retirada_se_conserva_inactiva(
    cliente, podologa, sede, segunda_sede
):
    # Garantiza que editar las sedes funciona (antes se ignoraba) y que la
    # asignación retirada no se borra: explica en qué sede trabajó.
    respuesta = cliente.patch(f"{USUARIOS}{podologa.pk}/", {"sedes_ids": [segunda_sede.pk]},
                              format="json")

    assert respuesta.status_code == 200
    assert _vigentes(podologa) == {segunda_sede.pk}
    retirada = AsignacionSede.objects.get(usuario=podologa, sede=sede)
    assert retirada.esta_activa is False
    assert AsignacionSede.objects.get(usuario=podologa, sede=segunda_sede).es_predeterminada


@pytest.mark.django_db
def test_sin_sedes_ids_la_edicion_no_toca_las_sedes(cliente, podologa, sede):
    # Garantiza que cambiar el nombre no deja a la persona sin sedes porque
    # el campo vale [] por defecto.
    cliente.patch(f"{USUARIOS}{podologa.pk}/", {"nombres": "Rosa María"}, format="json")

    assert _vigentes(podologa) == {sede.pk}


@pytest.mark.django_db
def test_no_se_deja_a_un_usuario_sin_sedes(cliente, podologa):
    # Garantiza la misma regla que el alta: un usuario del centro sin sede no
    # puede elegir dónde trabaja ni atender.
    respuesta = cliente.patch(f"{USUARIOS}{podologa.pk}/", {"sedes_ids": []}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede"


@pytest.mark.django_db
def test_no_se_asigna_una_sede_de_otro_centro(cliente, centro, podologa, otro_centro, sede):
    # Garantiza el aislamiento: la clave foránea no mira el centro, así que
    # sin esta comprobación se podía colgar a una podóloga de una sede ajena,
    # al editar y también al dar de alta.
    activar_centro(otro_centro.pk)
    ajena = Sede.objects.create(centro=otro_centro, nombre="Lima", direccion="Jr. Unión 1")
    activar_centro(centro.pk)

    al_editar = cliente.patch(f"{USUARIOS}{podologa.pk}/", {"sedes_ids": [ajena.pk]},
                              format="json")
    al_crear = cliente.post(USUARIOS, {"correo": "x@centro.pe", "nombres": "X",
                                       "apellidos": "Y", "rol": Rol.PODOLOGA,
                                       "sedes_ids": [sede.pk, ajena.pk]}, format="json")

    assert (al_editar.status_code, al_editar.data["codigo"]) == (422, "sede-fuera-del-centro")
    assert (al_crear.status_code, al_crear.data["codigo"]) == (422, "sede-fuera-del-centro")
    assert _vigentes(podologa) == {sede.pk}


@pytest.mark.django_db
def test_el_correo_de_otro_usuario_no_se_puede_tomar(cliente, podologa, administradora):
    # Garantiza el correo único al editar como error de negocio: es el nombre
    # de acceso, y dos cuentas con el mismo no podrían distinguirse.
    respuesta = cliente.patch(f"{USUARIOS}{podologa.pk}/",
                              {"correo": administradora.correo.upper()}, format="json")

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "correo-duplicado"


@pytest.mark.django_db
def test_el_patch_no_desactiva_saltandose_la_regla(cliente, administradora):
    # Garantiza que la baja solo va por su ruta (que aplica el último
    # administrador): `esta_activo` en el PATCH se ignora.
    cliente.patch(f"{USUARIOS}{administradora.pk}/", {"esta_activo": False}, format="json")

    assert Usuario.objects.get(pk=administradora.pk).esta_activo is True
