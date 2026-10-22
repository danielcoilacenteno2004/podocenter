"""Reglas de aplicación del módulo de pacientes."""
from django.db import transaction
from django.utils import timezone

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import Consentimiento, Paciente

VERSION_CONSENTIMIENTO_VIGENTE = "2026.1"


@transaction.atomic
def registrar_paciente(*, centro, usuario, datos, consentimiento) -> Paciente:
    """Alta de paciente con su consentimiento (CU06).

    El consentimiento se guarda en la misma transacción que el paciente: no
    puede existir una ficha sin constancia de la base legal del tratamiento.
    """
    documento = datos["documento"].strip()
    duplicado = Paciente.objects.filter(
        centro=centro, tipo_documento=datos["tipo_documento"], documento=documento
    ).first()
    if duplicado is not None:
        raise ReglaDeNegocio(
            "paciente-duplicado",
            f"Ya existe un paciente con ese documento: {duplicado.nombre_completo}.",
        )
    if not consentimiento.get("acepta_tratamiento_datos"):
        raise ReglaDeNegocio(
            "sin-consentimiento",
            "No se puede registrar un paciente sin su consentimiento de tratamiento de datos.",
        )

    paciente = Paciente.objects.create(centro=centro, **{**datos, "documento": documento})
    Consentimiento.objects.create(
        paciente=paciente,
        version_texto=VERSION_CONSENTIMIENTO_VIGENTE,
        acepta_tratamiento_datos=True,
        acepta_recordatorios=bool(consentimiento.get("acepta_recordatorios")),
        canal=consentimiento.get("canal", Consentimiento.Canal.PRESENCIAL),
        registrado_por=usuario,
    )
    registrar("ALTA", "paciente", paciente.pk, {"documento": documento})
    return paciente


@transaction.atomic
def revocar_consentimiento(paciente: Paciente) -> None:
    """El paciente retira su consentimiento; se dejan de enviar recordatorios."""
    vigente = paciente.consentimiento_vigente
    if vigente is None:
        raise ReglaDeNegocio("sin-consentimiento", "El paciente no tiene consentimiento vigente.")
    vigente.fue_revocado = True
    vigente.revocado_en = timezone.now()
    vigente.save(update_fields=["fue_revocado", "revocado_en", "actualizado_en"])
    registrar("EDICION", "consentimiento", vigente.pk, {"revocado": True})


def ficha_con_auditoria(paciente: Paciente) -> Paciente:
    """Lectura de la ficha clínica, que siempre queda auditada (RF05)."""
    registrar("CONSULTA", "paciente", paciente.pk, {"motivo": "ficha"})
    return paciente
