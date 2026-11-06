"""Reglas de aplicación de la agenda (CU08, CU09)."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import Cita

ANTICIPACION_MINIMA = timedelta(minutes=15)


def _validar_horario_de_sede(sede, inicio, fin) -> None:
    horario = sede.horario_de(timezone.localtime(inicio).weekday())
    if horario is None:
        raise ReglaDeNegocio("sede-cerrada", "La sede no atiende ese día.")
    local_inicio = timezone.localtime(inicio).time()
    local_fin = timezone.localtime(fin).time()
    if not horario.cubre(local_inicio, local_fin):
        raise ReglaDeNegocio(
            "fuera-de-horario",
            f"La sede atiende de {horario.hora_apertura:%H:%M} a {horario.hora_cierre:%H:%M}.",
        )


@transaction.atomic
def programar_cita(*, centro, usuario, sede, paciente, profesional, servicio, inicio,
                   observaciones="") -> Cita:
    """Crea una cita comprobando horario, anticipación y solapamiento (CU08)."""
    if inicio < timezone.now() + ANTICIPACION_MINIMA:
        raise ReglaDeNegocio(
            "cita-en-el-pasado", "La cita debe programarse con al menos 15 minutos de anticipación."
        )
    if not profesional.puede_usar_sede(sede.pk):
        raise ReglaDeNegocio(
            "profesional-sin-sede", "La profesional no está asignada a esa sede."
        )
    fin = inicio + timedelta(minutes=servicio.duracion_minutos)
    _validar_horario_de_sede(sede, inicio, fin)

    try:
        with transaction.atomic():
            cita = Cita.objects.create(
                centro=centro, sede=sede, paciente=paciente, profesional=profesional,
                servicio=servicio, inicio=inicio, fin=fin, observaciones=observaciones,
                creada_por=usuario,
            )
    except IntegrityError as error:
        if "ex_cita_sin_solape_por_profesional" in str(error):
            raise ReglaDeNegocio(
                "cita-solapada",
                "La profesional ya tiene otra cita en ese horario.",
            ) from error
        raise
    registrar("ALTA", "cita", cita.pk, {"inicio": inicio.isoformat(), "sede": sede.pk})
    return cita


@transaction.atomic
def cancelar_cita(*, cita: Cita, motivo: str) -> Cita:
    """Cancela una cita programada (CU09, RF08 ajustado por CC-12)."""
    if cita.estado != Cita.Estado.PROGRAMADA:
        raise ReglaDeNegocio(
            "cita-no-cancelable", f"La cita ya está en estado {cita.get_estado_display()}."
        )
    if not motivo.strip():
        raise ReglaDeNegocio("motivo-requerido", "Indique el motivo de la cancelación.")
    cita.estado = Cita.Estado.CANCELADA
    cita.motivo_cancelacion = motivo.strip()
    cita.cancelada_en = timezone.now()
    cita.save(update_fields=["estado", "motivo_cancelacion", "cancelada_en",
                             "periodo", "actualizado_en"])
    registrar("EDICION", "cita", cita.pk, {"estado": "CANCELADA", "motivo": motivo})
    return cita


def agenda_del_dia(*, centro_id: int, sede_id: int, fecha, estado=None,
                   profesional_id=None, servicio_id=None):
    """Citas de una sede en un día, para la pantalla P05.

    Los filtros son opcionales y se aplican en la base, no en el navegador:
    la observación de la Práctica N.° 7 pedía poder acotar la agenda por
    estado, profesional y servicio sin recargar toda la jornada.
    """
    inicio = timezone.make_aware(timezone.datetime.combine(fecha, timezone.datetime.min.time()))
    consulta = Cita.objects.filter(
        centro_id=centro_id, sede_id=sede_id, inicio__gte=inicio,
        inicio__lt=inicio + timedelta(days=1),
    )
    if estado:
        consulta = consulta.filter(estado=estado)
    if profesional_id:
        consulta = consulta.filter(profesional_id=profesional_id)
    if servicio_id:
        consulta = consulta.filter(servicio_id=servicio_id)
    return consulta.select_related("paciente", "profesional", "servicio").order_by("inicio")
