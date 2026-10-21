"""Alta de usuarios, asignación de sedes y reglas de rol."""
import pytest

from apps.core.errores import ReglaDeNegocio
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol
from apps.usuarios.servicios import crear_usuario, desactivar_usuario, sedes_disponibles


@pytest.mark.django_db
def test_crea_una_podologa_y_la_asigna_a_su_sede(centro, sede):
    usuario = crear_usuario(
        centro=centro, correo="nueva@centro.pe", nombres="Elena", apellidos="Vargas",
        rol=Rol.PODOLOGA, sedes_ids=[sede.pk],
    )

    assert usuario.puede_usar_sede(sede.pk)
    assert usuario.asignaciones.get().es_predeterminada is True


@pytest.mark.django_db
def test_no_crea_un_usuario_de_centro_sin_ninguna_sede(centro):
    with pytest.raises(ReglaDeNegocio) as error:
        crear_usuario(
            centro=centro, correo="suelta@centro.pe", nombres="Sin", apellidos="Sede",
            rol=Rol.PODOLOGA, sedes_ids=[],
        )

    assert error.value.codigo == "sin-sede"


@pytest.mark.django_db
def test_no_permite_crear_un_administrador_de_plataforma_desde_un_centro(centro, sede):
    with pytest.raises(ReglaDeNegocio) as error:
        crear_usuario(
            centro=centro, correo="root@centro.pe", nombres="A", apellidos="B",
            rol=Rol.ADMIN_PLATAFORMA, sedes_ids=[sede.pk],
        )

    assert error.value.codigo == "rol-no-permitido"


@pytest.mark.django_db
def test_no_deja_al_centro_sin_administrador(centro, administradora):
    with pytest.raises(ReglaDeNegocio) as error:
        desactivar_usuario(administradora)

    assert error.value.codigo == "ultimo-administrador"
    administradora.refresh_from_db()
    assert administradora.esta_activo is True


@pytest.mark.django_db
def test_desactivar_es_baja_logica_y_conserva_la_fila(centro, sede, administradora):
    otra = crear_usuario(
        centro=centro, correo="segunda@centro.pe", nombres="Mía", apellidos="Luna",
        rol=Rol.ADMIN_CENTRO, sedes_ids=[sede.pk],
    )

    desactivar_usuario(otra)

    assert Usuario.objects.filter(pk=otra.pk, esta_activo=False).exists()


@pytest.mark.django_db
def test_la_podologa_de_una_sola_sede_no_necesita_elegir_sede(podologa):
    assert len(sedes_disponibles(podologa)) == 1


@pytest.mark.django_db
def test_los_roles_administrativos_requieren_segundo_factor(administradora, podologa):
    assert administradora.requiere_segundo_factor is True
    assert podologa.requiere_segundo_factor is False
