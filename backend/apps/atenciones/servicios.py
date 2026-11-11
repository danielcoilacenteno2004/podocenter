"""Reglas de aplicación de la atención (CU10)."""
from django.db import transaction
from django.utils import timezone

from apps.citas.models import Cita
from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import Atencion


def _cita_atendible(*, centro, usuario, sede_id, cita_id) -> Cita:
    """Bloquea la cita y comprueba las precondiciones del CU10.

    `select_for_update` hace que dos registros simultáneos de la misma
    cita se pongan en fila: el segundo espera, ve la atención del primero
    y se rechaza.
    """
    cita = Cita.objects.select_for_update().filter(pk=cita_id, centro_id=centro.pk).first()
    if cita is None:
        # Con el RLS, una cita de otro centro es indistinguible de una que no
        # existe; el código es el mismo para no revelar cuál de las dos es.
        raise ReglaDeNegocio("cita-fuera-del-centro", "La cita no existe en este centro.")
    if sede_id is None:
        raise ReglaDeNegocio("sin-sede-activa", "Elija la sede en la que está atendiendo.")
    if cita.sede_id != sede_id:
        raise ReglaDeNegocio(
            "cita-de-otra-sede", "La cita es de otra sede; cambie de sede para atenderla."
        )
    if not usuario.puede_usar_sede(cita.sede_id):
        raise ReglaDeNegocio("usuario-sin-sede", "No está asignado a la sede de esta cita.")
    if Atencion.objects.filter(cita_id=cita.pk).exists():
        raise ReglaDeNegocio("atencion-duplicada", "Esta cita ya tiene su atención registrada.")
    if cita.estado != Cita.Estado.PROGRAMADA:
        raise ReglaDeNegocio(
            "cita-no-atendible",
            f"La cita está en estado {cita.get_estado_display()}; "
            "solo se registra la atención de una cita programada.",
        )
    if cita.inicio > timezone.now():
        raise ReglaDeNegocio(
            "cita-aun-no-llega",
            f"La cita es el {timezone.localtime(cita.inicio):%d/%m a las %H:%M}; "
            "la atención se registra cuando llega la hora.",
        )
    return cita


@transaction.atomic
def registrar_atencion(*, centro, usuario, sede_id, cita_id,
                       observaciones_clinicas="") -> Atencion:
    """Registra la atención de una cita programada y la marca como atendida (CU10).

    Crear la atención y cerrar la cita van en la misma transacción: si una
    falla, no queda ni una atención sobre una cita abierta ni una cita
    atendida sin su atención. Paciente, profesional y servicio se copian de
    la cita en este momento, porque la ficha clínica no debe cambiar si
    después alguien la edita.
    """
    cita = _cita_atendible(centro=centro, usuario=usuario, sede_id=sede_id, cita_id=cita_id)

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
