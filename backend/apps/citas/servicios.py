"""Reglas de aplicación de la agenda (CU08, CU09)."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import BooleanField, ExpressionWrapper, Q
from django.utils import timezone

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import Cita

ANTICIPACION_MINIMA = timedelta(minutes=15)


def con_marca_de_atencion(consulta):
    """Añade `tiene_atencion` a cada cita con un solo LEFT JOIN.

    La agenda lo necesita para no ofrecer «Registrar atención» sobre una
    cita que ya la tiene; resolverlo cita por cita sería una consulta más
    por fila de la jornada.
    """
    return consulta.annotate(
        tiene_atencion=ExpressionWrapper(Q(atencion__isnull=False), output_field=BooleanField())
    )


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
    # Desactivar una sede o un servicio es la forma de retirarlos sin borrar
    # su historia (Práctica N.° 7, Tablas 23 y 29): dejan de aceptar citas nuevas.
    if not sede.esta_activa:
        raise ReglaDeNegocio("sede-inactiva", "La sede está desactivada y no admite citas.")
    if not servicio.esta_activo:
        raise ReglaDeNegocio(
            "servicio-inactivo", "El servicio está desactivado y no admite citas."
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


def horario_de_la_jornada(*, centro_id: int, sede_id, fecha):
    """Apertura y cierre de la sede ese día, o None si no abre.

    Es el mismo horario que `programar_cita` exige (`Sede.horario_de`). La
    cuadrícula de P05 lo usa para trazar sus filas: así no se dibujan horas
    en las que el servidor no aceptaría una cita.
    """
    from apps.sedes.models import Sede

    sede = Sede.objects.filter(centro_id=centro_id, pk=sede_id).first() if sede_id else None
    horario = sede.horario_de(fecha.weekday()) if sede else None
    if horario is None:
        return None
    return {"apertura": horario.hora_apertura.strftime("%H:%M"),
            "cierre": horario.hora_cierre.strftime("%H:%M")}


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
    return con_marca_de_atencion(
        consulta.select_related("paciente", "profesional", "servicio")
    ).order_by("inicio")
