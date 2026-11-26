"""Reglas de aplicación de la atención (CU10)."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
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
def registrar_atencion(*, centro, usuario, sede_id, cita_id, monto_cobrado,
                       observaciones_clinicas="", insumos=()) -> Atencion:
    """Registra la atención de una cita programada y la marca como atendida (CU10).

    Crear la atención y cerrar la cita van en la misma transacción: si una
    falla, no queda ni una atención sobre una cita abierta ni una cita
    atendida sin su atención. Paciente, profesional y servicio se copian de
    la cita en este momento, porque la ficha clínica no debe cambiar si
    después alguien la edita.

    Los insumos consumidos descuentan stock de la sede de la cita en la misma
    transacción (Informe 2.1.7, Tabla 39): si falta stock, no se registra
    nada y la cita sigue programada.
    """
    cita = _cita_atendible(centro=centro, usuario=usuario, sede_id=sede_id, cita_id=cita_id)

    atencion = Atencion.objects.create(
        centro=centro, sede_id=cita.sede_id, cita=cita,
        paciente_id=cita.paciente_id, profesional_id=cita.profesional_id,
        servicio_id=cita.servicio_id, observaciones_clinicas=observaciones_clinicas,
        monto_cobrado=monto_cobrado,
        registrada_por=usuario,
    )
    cita.estado = Cita.Estado.ATENDIDA
    cita.save(update_fields=["estado", "periodo", "actualizado_en"])
    if insumos:
        from apps.inventario.servicios import descontar_insumos

        descontar_insumos(centro=centro, usuario=usuario, sede=cita.sede, atencion=atencion,
                          insumos=insumos)

    # Las observaciones no entran en la auditoría: la bitácora guarda JSON en
    # claro y anularía el cifrado del campo.
    registrar("ALTA", "atencion", atencion.pk, {"cita": cita.pk})
    registrar("EDICION", "cita", cita.pk, {"estado": "ATENDIDA"})
    return atencion


def registro_del_dia(*, centro_id: int, sede_id: int, fecha) -> dict:
    """Atenciones e ingresos de una sede en un día (P16, RF14).

    Se calcula siempre desde las atenciones, sin una tabla de ingresos aparte
    que pueda descuadrar con lo atendido (Informe, Tabla 39). El día es el de
    la atención, en la hora local de la sede. Las atenciones anteriores al
    campo monto_cobrado se cuentan aparte y no suman al total: sumarlas como
    cero falsearía el día.
    """
    return registro_del_rango(centro_id=centro_id, sede_id=sede_id, desde=fecha, hasta=fecha)


def registro_del_rango(*, centro_id: int, sede_id: int, desde, hasta) -> dict:
    """El registro diario de varios días seguidos, ambos extremos incluidos.

    Es la misma consulta que la del día (que la llama con desde = hasta),
    para que la exportación (RF16) y la pantalla no puedan dar totales
    distintos por calcularse de dos formas.
    """
    inicio = timezone.make_aware(timezone.datetime.combine(desde, timezone.datetime.min.time()))
    fin = timezone.make_aware(timezone.datetime.combine(hasta + timedelta(days=1),
                                                        timezone.datetime.min.time()))
    atenciones = (
        Atencion.objects.filter(centro_id=centro_id, sede_id=sede_id,
                                registrada_en__gte=inicio, registrada_en__lt=fin)
        .select_related("paciente", "profesional", "servicio")
        .order_by("registrada_en")
    )
    total = atenciones.aggregate(total=Sum("monto_cobrado"))["total"] or Decimal("0.00")
    return {
        "atenciones": atenciones,
        "total": total,
        "sin_monto": atenciones.filter(monto_cobrado__isnull=True).count(),
    }


def atencion_con_auditoria(atencion: Atencion) -> Atencion:
    """Lectura de la ficha de una atención, que siempre queda auditada (RF05)."""
    registrar("CONSULTA", "atencion", atencion.pk, {"motivo": "ficha"})
    return atencion
