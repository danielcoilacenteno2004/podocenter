"""Prueba de humo del comando `cargar_demo`.

El comando es la herramienta con la que se monta la demostración: si deja de
funcionar, la sustentación se queda sin datos. Por eso se comprueba aquí que
termina bien, que es idempotente y que las citas que siembra respetan las
mismas reglas que la agenda real.
"""
import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command

from apps.atenciones.models import Atencion
from apps.atenciones.servicios import registrar_atencion
from apps.catalogo.models import Servicio
from apps.citas.models import Cita
from apps.core.models import Centro
from apps.core.soporte_pruebas import activar_centro
from apps.pacientes.models import Paciente
from apps.sedes.models import Sede
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol

# Credencial pública del entorno de demostración, no un secreto.
CLAVE_DEMO = "Podocenter2026"  # nosec B105


@pytest.fixture
def demo(db):
    call_command("cargar_demo", verbosity=0)
    centro = Centro.objects.get(subdominio="piessanos")
    activar_centro(centro.pk)
    return centro


@pytest.mark.django_db
def test_el_comando_crea_el_centro_con_sus_dos_sedes(demo):
    # El multi-sede es el eje del proyecto: la demostración tiene que nacer con
    # dos sedes o no demuestra nada.
    assert Sede.objects.filter(centro=demo).count() == 2


@pytest.mark.django_db
def test_siembra_catalogo_y_pacientes(demo):
    # Volumen suficiente para que las búsquedas y los filtros tengan algo que
    # hacer durante la sustentación.
    assert Servicio.objects.filter(centro=demo).count() == 6
    assert Paciente.objects.filter(centro=demo).count() == 12


@pytest.mark.django_db
def test_cada_paciente_tiene_consentimiento_registrado(demo):
    # Sin consentimiento vigente no se pueden enviar recordatorios; un padrón de
    # demostración sin él daría una imagen falsa del cumplimiento del RNF06.
    for paciente in Paciente.objects.filter(centro=demo):
        assert paciente.consentimiento_vigente is not None


@pytest.mark.django_db
def test_crea_las_cuentas_de_cada_rol(demo):
    # La demostración necesita poder entrar con los tres roles para mostrar que
    # el menú y los permisos cambian.
    roles = set(Usuario.objects.values_list("rol", flat=True))

    assert roles == {Rol.ADMIN_PLATAFORMA, Rol.ADMIN_CENTRO, Rol.PODOLOGA}


@pytest.mark.django_db
def test_las_credenciales_publicadas_funcionan(demo):
    # Las credenciales que se anuncian en la pantalla de ingreso tienen que
    # funcionar de verdad; si cambian, esta prueba lo detecta antes que el
    # jurado.
    usuario = authenticate(username="podologa@piessanos.pe", password=CLAVE_DEMO)

    assert usuario is not None
    assert usuario.rol == Rol.PODOLOGA


@pytest.mark.django_db
def test_siembra_una_agenda_con_citas(demo):
    # Una agenda vacía el día de la exposición sería el peor momento para
    # descubrirlo.
    assert Cita.objects.filter(centro=demo).count() >= 10


@pytest.mark.django_db
def test_ninguna_cita_sembrada_se_solapa_con_otra(demo):
    """La regla de la agenda vale también para los datos de demostración."""
    por_profesional = {}
    for cita in Cita.objects.filter(centro=demo).order_by("inicio"):
        anteriores = por_profesional.setdefault(cita.profesional_id, [])
        assert all(cita.inicio >= fin or cita.fin <= inicio for inicio, fin in anteriores)
        anteriores.append((cita.inicio, cita.fin))


@pytest.mark.django_db
def test_volver_a_ejecutarlo_rehace_la_demostracion_sin_duplicar(demo):
    # El comando se ejecuta varias veces mientras se prepara la exposición; debe
    # dejar siempre el mismo estado, sin acumular centros ni cuentas repetidas.
    call_command("cargar_demo", verbosity=0)

    assert Centro.objects.filter(subdominio="piessanos").count() == 1
    assert Usuario.objects.filter(correo="plataforma@podocenter.pe").count() == 1
    activar_centro(Centro.objects.get(subdominio="piessanos").pk)
    assert Sede.objects.count() == 2


@pytest.mark.django_db
def test_rehace_la_demostracion_aunque_ya_tenga_atenciones_registradas(demo):
    # Es el caso real del día de la exposición: se ensaya registrando
    # atenciones y después se recarga la demostración. La atención protege su
    # cita (PROTECT), así que si la limpieza no la borra primero, el comando
    # se cae y la sustentación se queda con los datos del ensayo.
    cita = Cita.objects.filter(estado=Cita.Estado.PROGRAMADA).order_by("inicio").first()
    registrar_atencion(centro=demo, usuario=cita.profesional, sede_id=cita.sede_id,
                       cita_id=cita.pk, observaciones_clinicas="Ensayo de la exposición")

    call_command("cargar_demo", verbosity=0)

    nuevo = Centro.objects.get(subdominio="piessanos")
    activar_centro(nuevo.pk)
    assert Centro.objects.filter(subdominio="piessanos").count() == 1
    assert Atencion.objects.count() == 0
    assert Cita.objects.filter(centro=nuevo).count() >= 10


@pytest.mark.django_db
def test_con_conservar_no_toca_la_demostracion_existente(demo):
    # Protege los datos ya cargados cuando alguien repite el comando por
    # costumbre y no quiere perder lo que estuvo mostrando.
    sede_id = Sede.objects.first().pk

    call_command("cargar_demo", "--conservar", verbosity=0)

    assert Sede.objects.filter(pk=sede_id).exists()
