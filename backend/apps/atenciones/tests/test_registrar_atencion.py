"""Pruebas del registro de la atención (CU10): copia de la cita, cifrado y cierre."""
import pytest
from django.db import IntegrityError, connection, transaction

from apps.atenciones.models import Atencion
from apps.atenciones.servicios import registrar_atencion
from apps.catalogo.models import Servicio
from apps.citas.models import Cita
from apps.citas.servicios import cancelar_cita, programar_cita
from apps.core.errores import ReglaDeNegocio
from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import activar_centro
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol

from ...conftest import CLAVE_DE_PRUEBA

NOTAS = "Onicocriptosis en hallux derecho; se retira la espícula"


@pytest.fixture
def cita(centro, podologa, sede, servicio, paciente, proximo_lunes_a_las_nueve):
    return programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    )


@pytest.mark.django_db
def test_registra_la_atencion_con_los_datos_de_la_cita_y_la_marca_como_atendida(
    centro, podologa, cita
):
    # Garantiza la postcondición del CU10: la atención queda vinculada a la
    # cita y la cita sale de la agenda pendiente. Sin el cambio de estado, el
    # panel del día seguiría contándola como por atender.
    atencion = registrar_atencion(centro=centro, usuario=podologa, cita=cita,
                                  observaciones_clinicas=NOTAS)

    cita.refresh_from_db()
    assert cita.estado == Cita.Estado.ATENDIDA
    assert atencion.cita_id == cita.pk
    assert (atencion.paciente_id, atencion.profesional_id, atencion.servicio_id,
            atencion.sede_id) == (cita.paciente_id, cita.profesional_id, cita.servicio_id,
                                  cita.sede_id)
    assert atencion.registrada_por == podologa


@pytest.mark.django_db
def test_la_ficha_de_la_atencion_no_cambia_si_despues_se_edita_la_cita(
    centro, podologa, cita
):
    # Garantiza que la atención es una copia y no una referencia: la ficha
    # clínica describe lo que se hizo, y editar la cita después no puede
    # reescribir el historial del paciente.
    atencion = registrar_atencion(centro=centro, usuario=podologa, cita=cita)
    original = atencion.servicio_id
    otro = Servicio.objects.create(
        centro=centro, nombre="Podología deportiva", duracion_minutos=30, precio="80.00"
    )

    Cita.objects.filter(pk=cita.pk).update(servicio=otro)

    atencion.refresh_from_db()
    assert atencion.servicio_id == original


@pytest.mark.django_db
def test_las_observaciones_clinicas_se_guardan_cifradas_en_la_columna(
    centro, podologa, cita
):
    # Garantiza el mismo nivel de protección que los antecedentes del
    # paciente: quien obtenga una copia de la base no puede leer el dato
    # clínico, y la aplicación lo sigue leyendo en claro.
    atencion = registrar_atencion(centro=centro, usuario=podologa, cita=cita,
                                  observaciones_clinicas=NOTAS)

    with connection.cursor() as cursor:
        cursor.execute("SELECT observaciones_clinicas FROM atencion WHERE id = %s",
                       [atencion.pk])
        crudo = cursor.fetchone()[0]

    assert crudo.startswith("fer:")
    assert "hallux" not in crudo
    assert Atencion.objects.get(pk=atencion.pk).observaciones_clinicas == NOTAS


@pytest.mark.django_db
def test_rechaza_registrar_la_atencion_de_una_cita_cancelada(centro, podologa, cita):
    # Garantiza la precondición del CU10: solo se atiende una cita
    # programada. Una atención sobre una cita cancelada sería un ingreso y
    # un acto clínico que no ocurrieron.
    cancelar_cita(cita=cita, motivo="El paciente avisó que no puede asistir")

    with pytest.raises(ReglaDeNegocio) as error:
        registrar_atencion(centro=centro, usuario=podologa, cita=cita)

    assert error.value.codigo == "cita-no-atendible"
    assert Atencion.objects.count() == 0


@pytest.mark.django_db
def test_rechaza_registrar_dos_veces_la_atencion_de_la_misma_cita(centro, podologa, cita):
    # Garantiza que un doble clic o un reenvío del formulario no duplica la
    # atención: la segunda vez la cita ya está atendida y se rechaza con un
    # código que la interfaz puede traducir.
    registrar_atencion(centro=centro, usuario=podologa, cita=cita)

    with pytest.raises(ReglaDeNegocio) as error:
        registrar_atencion(centro=centro, usuario=podologa, cita=cita)

    assert error.value.codigo == "cita-no-atendible"
    assert Atencion.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_la_base_impide_dos_atenciones_de_la_misma_cita_aunque_se_salte_el_servicio(
    centro, podologa, cita
):
    # Garantiza que el uno a uno lo sostiene la base y no solo el servicio:
    # aunque un script o una vista futura escriba directo en la tabla, una
    # cita no puede tener dos atenciones.
    datos = {
        "centro": centro, "sede_id": cita.sede_id, "cita": cita,
        "paciente_id": cita.paciente_id, "profesional_id": cita.profesional_id,
        "servicio_id": cita.servicio_id, "registrada_por": podologa,
    }
    Atencion.objects.create(**datos)

    with pytest.raises(IntegrityError), transaction.atomic():
        Atencion.objects.create(**datos)

    connection.close()


@pytest.mark.django_db
def test_rechaza_la_atencion_de_quien_no_esta_asignado_a_la_sede_de_la_cita(
    centro, cita
):
    # Garantiza la precondición «usuario con sede activa» del CU10: una
    # podóloga del mismo centro que no trabaja en esa sede no puede cerrar
    # sus citas.
    ajena = Usuario.objects.create_user(
        correo="sin.sede@centro.pe", password=CLAVE_DE_PRUEBA,
        nombres="Elena", apellidos="Mamani", rol=Rol.PODOLOGA, centro=centro,
    )

    with pytest.raises(ReglaDeNegocio) as error:
        registrar_atencion(centro=centro, usuario=ajena, cita=cita)

    assert error.value.codigo == "usuario-sin-sede"
    cita.refresh_from_db()
    assert cita.estado == Cita.Estado.PROGRAMADA


@pytest.mark.django_db
def test_la_auditoria_registra_el_alta_sin_copiar_las_observaciones_clinicas(
    centro, podologa, cita
):
    # Garantiza que la bitácora no se convierte en una copia en claro del
    # dato cifrado: deja constancia de quién registró qué atención, pero no
    # de lo que dice la nota clínica.
    atencion = registrar_atencion(centro=centro, usuario=podologa, cita=cita,
                                  observaciones_clinicas=NOTAS)

    registro = RegistroAuditoria.objects.get(entidad="atencion", accion="ALTA")
    assert registro.entidad_id == str(atencion.pk)
    assert registro.usuario_id == podologa.pk
    assert "hallux" not in str(registro.datos)


@pytest.mark.django_db
def test_otro_centro_no_ve_la_atencion_aunque_consulte_sin_filtrar(
    centro, podologa, cita, otro_centro
):
    # Garantiza que la tabla nueva quedó bajo la política de seguridad por
    # fila: es el dato más sensible del sistema y no puede depender de que
    # cada consulta recuerde filtrar por centro.
    atencion = registrar_atencion(centro=centro, usuario=podologa, cita=cita)

    activar_centro(otro_centro.pk)

    assert not Atencion.objects.filter(pk=atencion.pk).exists()
    assert Atencion.objects.count() == 0
