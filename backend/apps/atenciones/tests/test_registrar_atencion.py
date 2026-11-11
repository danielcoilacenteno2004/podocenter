"""Pruebas del registro de la atención (CU10): una por regla del servicio."""
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
from apps.sedes.models import Sede
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


def _registrar(centro, usuario, cita, sede_id=None, notas=""):
    return registrar_atencion(
        centro=centro, usuario=usuario, cita_id=cita.pk,
        sede_id=cita.sede_id if sede_id is None else sede_id,
        observaciones_clinicas=notas,
    )


# --- Regla: solo se registra sobre una cita PROGRAMADA -----------------------

@pytest.mark.django_db
def test_rechaza_registrar_la_atencion_de_una_cita_cancelada(centro, podologa, cita):
    # Garantiza la precondición del CU10. Una atención sobre una cita
    # cancelada dejaría constancia de un acto clínico y de un ingreso que no
    # ocurrieron, y el registro diario los sumaría.
    cancelar_cita(cita=cita, motivo="El paciente avisó que no puede asistir")

    with pytest.raises(ReglaDeNegocio) as error:
        _registrar(centro, podologa, cita)

    assert error.value.codigo == "cita-no-atendible"
    assert Atencion.objects.count() == 0


# --- Regla: una cita no puede tener dos atenciones ---------------------------

@pytest.mark.django_db
def test_rechaza_una_segunda_atencion_de_la_misma_cita(centro, podologa, cita):
    # Garantiza que un doble clic o un reenvío del formulario no duplica la
    # atención, y que la interfaz recibe un código propio para decir «ya
    # estaba registrada» en lugar de un error de estado que confunde.
    _registrar(centro, podologa, cita)

    with pytest.raises(ReglaDeNegocio) as error:
        _registrar(centro, podologa, cita)

    assert error.value.codigo == "atencion-duplicada"
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


# --- Regla: la cita tiene que ser del centro y de la sede activa -------------

@pytest.mark.django_db
def test_rechaza_una_cita_que_no_pertenece_al_centro_que_registra(
    centro, podologa, cita, otro_centro
):
    # Garantiza que el servicio no confía solo en que el llamador le pase una
    # cita de su centro: si no lo es, sale un error de negocio y no un 500 ni
    # una atención cruzada entre centros clientes.
    with pytest.raises(ReglaDeNegocio) as error:
        registrar_atencion(centro=otro_centro, usuario=podologa, cita_id=cita.pk,
                           sede_id=cita.sede_id)

    assert error.value.codigo == "cita-fuera-del-centro"


@pytest.mark.django_db
def test_rechaza_una_cita_de_otra_sede_que_la_activa(centro, podologa, cita):
    # Garantiza que la atención se registra en la sede donde se está
    # trabajando. La podóloga atiende en dos sedes: sin esta regla podría
    # cerrar una cita de la otra sede con la sesión abierta en la equivocada.
    otra = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Ejército 900")

    with pytest.raises(ReglaDeNegocio) as error:
        _registrar(centro, podologa, cita, sede_id=otra.pk)

    assert error.value.codigo == "cita-de-otra-sede"


@pytest.mark.django_db
def test_rechaza_el_registro_si_no_hay_sede_activa(centro, podologa, cita):
    # Garantiza la precondición «usuario con sede activa» del CU10: sin sede
    # elegida no hay contra qué comprobar la cita, y se rechaza en lugar de
    # aceptarla por omisión.
    with pytest.raises(ReglaDeNegocio) as error:
        registrar_atencion(centro=centro, usuario=podologa, cita_id=cita.pk, sede_id=None)

    assert error.value.codigo == "sin-sede-activa"


@pytest.mark.django_db
def test_rechaza_la_atencion_de_quien_no_esta_asignado_a_la_sede_de_la_cita(
    centro, cita
):
    # Garantiza que el servicio no depende de que la cabecera X-Sede venga ya
    # validada: quien no trabaja en esa sede no puede cerrar sus citas.
    ajena = Usuario.objects.create_user(
        correo="sin.sede@centro.pe", password=CLAVE_DE_PRUEBA,
        nombres="Elena", apellidos="Mamani", rol=Rol.PODOLOGA, centro=centro,
    )

    with pytest.raises(ReglaDeNegocio) as error:
        _registrar(centro, ajena, cita)

    assert error.value.codigo == "usuario-sin-sede"


@pytest.mark.django_db
def test_otro_centro_no_ve_la_atencion_aunque_consulte_sin_filtrar(
    centro, podologa, cita, otro_centro
):
    # Garantiza que la tabla nueva quedó bajo la política de seguridad por
    # fila: es el dato más sensible del sistema y no puede depender de que
    # cada consulta recuerde filtrar por centro.
    atencion = _registrar(centro, podologa, cita)

    activar_centro(otro_centro.pk)

    assert not Atencion.objects.filter(pk=atencion.pk).exists()


# --- Regla: la cita pasa a ATENDIDA en la misma transacción ------------------

@pytest.mark.django_db
def test_registra_la_atencion_con_los_datos_de_la_cita_y_la_marca_como_atendida(
    centro, podologa, cita
):
    # Garantiza la postcondición del CU10: la atención queda vinculada a la
    # cita y la cita sale de la agenda pendiente. Sin el cambio de estado, el
    # panel del día seguiría contándola como por atender.
    atencion = _registrar(centro, podologa, cita, notas=NOTAS)

    cita.refresh_from_db()
    assert cita.estado == Cita.Estado.ATENDIDA
    assert (atencion.paciente_id, atencion.profesional_id, atencion.servicio_id,
            atencion.sede_id) == (cita.paciente_id, cita.profesional_id, cita.servicio_id,
                                  cita.sede_id)
    assert atencion.registrada_por == podologa


@pytest.mark.django_db
def test_si_falla_el_cierre_de_la_cita_no_queda_la_atencion(
    centro, podologa, cita, monkeypatch
):
    # Garantiza que las dos escrituras son una sola: si cerrar la cita falla
    # después de crear la atención, se revierte también la atención. Si no,
    # quedaría una atención sobre una cita que la agenda sigue mostrando
    # abierta, y se podría volver a atender.
    def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado al guardar la cita")

    monkeypatch.setattr(Cita, "save", falla)

    with pytest.raises(RuntimeError):
        _registrar(centro, podologa, cita)

    monkeypatch.undo()
    assert Atencion.objects.count() == 0
    cita.refresh_from_db()
    assert cita.estado == Cita.Estado.PROGRAMADA


@pytest.mark.django_db
def test_la_ficha_de_la_atencion_no_cambia_si_despues_se_edita_la_cita(
    centro, podologa, cita
):
    # Garantiza que la atención es una copia y no una referencia: la ficha
    # clínica describe lo que se hizo, y editar la cita después no puede
    # reescribir el historial del paciente.
    atencion = _registrar(centro, podologa, cita)
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
    atencion = _registrar(centro, podologa, cita, notas=NOTAS)

    with connection.cursor() as cursor:
        cursor.execute("SELECT observaciones_clinicas FROM atencion WHERE id = %s",
                       [atencion.pk])
        crudo = cursor.fetchone()[0]

    assert crudo.startswith("fer:")
    assert "hallux" not in crudo
    assert Atencion.objects.get(pk=atencion.pk).observaciones_clinicas == NOTAS


# --- Regla: queda constancia en la bitácora de auditoría ---------------------

@pytest.mark.django_db
def test_la_auditoria_registra_el_alta_y_el_cierre_sin_copiar_las_notas(
    centro, podologa, cita
):
    # Garantiza la trazabilidad del dato clínico: queda quién registró qué
    # atención y que la cita se cerró por ella. Y garantiza que la bitácora,
    # que se guarda en claro, no se convierte en una copia del dato cifrado.
    atencion = _registrar(centro, podologa, cita, notas=NOTAS)

    alta = RegistroAuditoria.objects.get(entidad="atencion", accion="ALTA")
    cierre = RegistroAuditoria.objects.get(entidad="cita", accion="EDICION",
                                           entidad_id=str(cita.pk))
    assert alta.entidad_id == str(atencion.pk)
    assert alta.usuario_id == podologa.pk
    assert cierre.datos == {"estado": "ATENDIDA"}
    assert "hallux" not in str(alta.datos)
