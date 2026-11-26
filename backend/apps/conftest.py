"""Fixtures compartidas por las pruebas del backend."""
import pytest
from django.utils import timezone

from apps.catalogo.models import Servicio
from apps.core.contexto import fijar_contexto
from apps.core.models import Centro
from apps.core.soporte_pruebas import activar_centro, con_segundo_factor
from apps.sedes.models import HorarioSede, Sede
from apps.usuarios.models import AsignacionSede, Usuario
from apps.usuarios.roles import Rol

# Credencial ficticia; solo existe dentro de la base de datos de pruebas.
CLAVE_DE_PRUEBA = "ClaveSegura2026"  # nosec B105


@pytest.fixture
def centro(db) -> Centro:
    centro = Centro.objects.create(
        razon_social="Centro Podológico Arequipa", ruc="20123456789", subdominio="arequipa"
    )
    activar_centro(centro.pk)
    return centro


@pytest.fixture
def otro_centro(db) -> Centro:
    return Centro.objects.create(
        razon_social="Podología Lima Norte", ruc="20987654321", subdominio="limanorte"
    )


@pytest.fixture
def sede(centro) -> Sede:
    sede = Sede.objects.create(centro=centro, nombre="Cercado", direccion="Av. Ejército 123")
    for dia in range(0, 6):
        HorarioSede.objects.create(
            sede=sede, dia_semana=dia, hora_apertura="08:00", hora_cierre="20:00"
        )
    return sede


@pytest.fixture
def podologa(centro, sede) -> Usuario:
    usuario = Usuario.objects.create_user(
        correo="podologa@centro.pe", password=CLAVE_DE_PRUEBA,
        nombres="Rosa", apellidos="Quispe", rol=Rol.PODOLOGA, centro=centro,
    )
    AsignacionSede.objects.create(usuario=usuario, sede=sede, es_predeterminada=True)
    fijar_contexto(centro_id=centro.pk, sede_id=sede.pk, usuario_id=usuario.pk)
    return usuario


@pytest.fixture
def administradora(centro, sede) -> Usuario:
    usuario = Usuario.objects.create_user(
        correo="admin@centro.pe", password=CLAVE_DE_PRUEBA,
        nombres="Lucía", apellidos="Ramos", rol=Rol.ADMIN_CENTRO, centro=centro,
    )
    AsignacionSede.objects.create(usuario=usuario, sede=sede, es_predeterminada=True)
    con_segundo_factor(usuario)
    return usuario


@pytest.fixture
def servicio(centro) -> Servicio:
    return Servicio.objects.create(
        centro=centro, nombre="Quiropodia general", duracion_minutos=45, precio="60.00"
    )


@pytest.fixture
def proximo_lunes_a_las_nueve():
    """Una fecha futura y dentro del horario, para no depender del día de hoy."""
    ahora = timezone.localtime()
    dias = (7 - ahora.weekday()) or 7
    objetivo = (ahora + timezone.timedelta(days=dias)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    return objetivo


@pytest.fixture
def paciente(centro, podologa):
    from apps.pacientes.servicios import registrar_paciente

    return registrar_paciente(
        centro=centro,
        usuario=podologa,
        datos={
            "tipo_documento": "DNI", "documento": "40555666",
            "nombres": "Carmen", "apellidos": "Flores", "telefono": "958111222",
        },
        consentimiento={"acepta_tratamiento_datos": True, "acepta_recordatorios": True},
    )
