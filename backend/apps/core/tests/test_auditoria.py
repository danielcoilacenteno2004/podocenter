"""La auditoría debe registrarse sola y no puede tumbar la operación."""
import pytest

from apps.core.auditoria import registrar
from apps.core.models import RegistroAuditoria
from apps.pacientes.servicios import ficha_con_auditoria


@pytest.mark.django_db
def test_consultar_la_ficha_de_un_paciente_deja_rastro(centro, podologa, paciente):
    RegistroAuditoria.objects.all().delete()

    ficha_con_auditoria(paciente)

    registro = RegistroAuditoria.objects.get()
    assert registro.accion == "CONSULTA"
    assert registro.entidad == "paciente"
    assert registro.entidad_id == str(paciente.pk)


@pytest.mark.django_db
def test_sin_centro_en_contexto_no_escribe_pero_tampoco_falla(db):
    from apps.core.contexto import limpiar_contexto

    limpiar_contexto()

    registrar("CONSULTA", "paciente", 1)

    assert RegistroAuditoria.objects.count() == 0


@pytest.mark.django_db
def test_una_auditoria_rechazada_no_rompe_la_operacion_en_curso(centro, otro_centro, paciente):
    # Garantiza la promesa de registrar(): si la bitácora no se puede escribir
    # (aquí, porque el centro del contexto no es el fijado en la base y la
    # política RLS rechaza la fila), la operación del usuario sigue. Antes la
    # excepción se capturaba, pero la transacción quedaba rota y la petición
    # terminaba en un 500.
    from apps.core.auditoria import registrar
    from apps.core.contexto import fijar_contexto
    from apps.pacientes.models import Paciente

    fijar_contexto(centro_id=otro_centro.pk)  # distinto del fijado en la base
    registrar("CONSULTA", "paciente", paciente.pk)

    assert Paciente.objects.count() == 1  # la transacción sigue utilizable
    fijar_contexto(centro_id=centro.pk)
    assert not RegistroAuditoria.objects.filter(entidad="paciente", accion="CONSULTA").exists()
