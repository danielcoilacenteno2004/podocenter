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
