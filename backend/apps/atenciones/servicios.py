"""Reglas de aplicación de la atención (CU10)."""
from django.db import transaction

from apps.citas.models import Cita
from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import Atencion


@transaction.atomic
def registrar_atencion(*, centro, usuario, cita: Cita, observaciones_clinicas="") -> Atencion:
    """Registra la atención de una cita programada y la marca como atendida (CU10).

    La cita se bloquea con `select_for_update` para que dos registros
    simultáneos de la misma cita no pasen ambos la comprobación de estado:
    el segundo espera, la encuentra ya atendida y se rechaza. El vínculo uno
    a uno de la tabla es el cerrojo final si algo se salta este servicio.
    """
    cita = Cita.objects.select_for_update().get(pk=cita.pk)
    if cita.estado != Cita.Estado.PROGRAMADA:
        raise ReglaDeNegocio(
            "cita-no-atendible",
            f"La cita está en estado {cita.get_estado_display()}; "
            "solo se registra la atención de una cita programada.",
        )
    if not usuario.puede_usar_sede(cita.sede_id):
        raise ReglaDeNegocio("usuario-sin-sede", "No está asignado a la sede de esta cita.")

    atencion = Atencion.objects.create(
        centro=centro, sede_id=cita.sede_id, cita=cita,
        paciente_id=cita.paciente_id, profesional_id=cita.profesional_id,
        servicio_id=cita.servicio_id, observaciones_clinicas=observaciones_clinicas,
        registrada_por=usuario,
    )
    cita.estado = Cita.Estado.ATENDIDA
    cita.save(update_fields=["estado", "periodo", "actualizado_en"])

    # Las observaciones no entran en la auditoría: la bitácora guarda JSON en
    # claro y anularía el cifrado del campo.
    registrar("ALTA", "atencion", atencion.pk, {"cita": cita.pk})
    registrar("EDICION", "cita", cita.pk, {"estado": "ATENDIDA"})
    return atencion


def atencion_con_auditoria(atencion: Atencion) -> Atencion:
    """Lectura de la ficha de una atención, que siempre queda auditada (RF05)."""
    registrar("CONSULTA", "atencion", atencion.pk, {"motivo": "ficha"})
    return atencion
