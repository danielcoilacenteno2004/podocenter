"""Reglas de aplicación del catálogo de servicios (RF09, CU17).

Las vistas no escriben el servicio directamente: pasan por aquí, donde se
comprueban el nombre repetido y la duración y queda la auditoría.
"""
from django.db import IntegrityError, transaction

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import DURACION_MAXIMA, DURACION_MINIMA, Servicio


def _validar(centro_id: int, datos: dict, excepto=None) -> None:
    if "nombre" in datos:
        repetido = Servicio.objects.filter(centro_id=centro_id,
                                           nombre__iexact=datos["nombre"].strip())
        if excepto is not None:
            repetido = repetido.exclude(pk=excepto)
        if repetido.exists():
            raise ReglaDeNegocio("servicio-duplicado", "Ya existe un servicio con ese nombre.")
    duracion = datos.get("duracion_minutos")
    if duracion is not None and not DURACION_MINIMA <= duracion <= DURACION_MAXIMA:
        raise ReglaDeNegocio(
            "duracion-fuera-de-rango",
            f"La duración debe estar entre {DURACION_MINIMA} y {DURACION_MAXIMA} minutos.",
        )


def _guardar(servicio: Servicio) -> None:
    try:
        with transaction.atomic():
            servicio.save()
    except IntegrityError as error:
        if "uq_servicio_centro_nombre" in str(error):
            raise ReglaDeNegocio(
                "servicio-duplicado", "Ya existe un servicio con ese nombre."
            ) from error
        raise


@transaction.atomic
def crear_servicio(*, centro, datos: dict) -> Servicio:
    """Alta de servicio (P26)."""
    _validar(centro.pk, datos)
    servicio = Servicio(centro=centro, **datos)
    _guardar(servicio)
    registrar("ALTA", "servicio", servicio.pk, {"nombre": servicio.nombre,
                                                 "precio": str(servicio.precio)})
    return servicio


@transaction.atomic
def actualizar_servicio(servicio: Servicio, *, datos: dict) -> Servicio:
    """Edición de servicio (P26). La baja es `esta_activo = False`: un
    servicio con citas o atenciones no se borra.

    Cambiar el precio no altera lo ya cobrado: cada atención guarda su monto.
    """
    _validar(servicio.centro_id, datos, excepto=servicio.pk)
    for campo, valor in datos.items():
        setattr(servicio, campo, valor)
    _guardar(servicio)
    registrar("EDICION", "servicio", servicio.pk,
              {campo: str(valor) for campo, valor in datos.items()})
    return servicio
