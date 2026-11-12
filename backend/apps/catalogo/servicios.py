"""Reglas de aplicación del catálogo de servicios (RF09, CU17).

Las vistas no escriben el servicio directamente: pasan por aquí, donde se
comprueban el nombre repetido y la duración y queda la auditoría.
"""
from django.db import IntegrityError, transaction

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import DURACION_MAXIMA, DURACION_MINIMA, Servicio, ServicioInsumo


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


def _guardar_insumos(servicio: Servicio, insumos: list[dict]) -> dict:
    """Reemplaza los insumos habituales del servicio (CC-14).

    Mismas comprobaciones que un insumo en la atención: producto activo del
    centro, cantidad entera mayor que 0 y sin repetir. Devuelve lo guardado
    para la bitácora.
    """
    from apps.inventario.models import Producto

    pedidos = {}
    for fila in insumos:
        producto_id, cantidad = fila.get("producto"), fila.get("cantidad")
        if producto_id is None:
            raise ReglaDeNegocio("producto-requerido", "Elija el producto de cada insumo.")
        if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0:
            raise ReglaDeNegocio("cantidad-invalida",
                                 "La cantidad de cada insumo debe ser un entero mayor que 0.")
        if producto_id in pedidos:
            raise ReglaDeNegocio("insumo-repetido", "Un mismo producto aparece dos veces.")
        pedidos[producto_id] = cantidad
    productos = {p.pk: p for p in Producto.objects.filter(centro_id=servicio.centro_id,
                                                          pk__in=pedidos)}
    for producto_id in pedidos:
        if producto_id not in productos:
            raise ReglaDeNegocio("producto-fuera-del-centro",
                                 "Uno de los productos no existe en este centro.")
        if not productos[producto_id].esta_activo:
            raise ReglaDeNegocio("producto-inactivo",
                                 f"{productos[producto_id].nombre} ya no está activo.")
    servicio.insumos_habituales.all().delete()
    ServicioInsumo.objects.bulk_create([
        ServicioInsumo(centro_id=servicio.centro_id, servicio=servicio, producto_id=producto_id,
                       cantidad=cantidad)
        for producto_id, cantidad in pedidos.items()
    ])
    return {str(producto_id): cantidad for producto_id, cantidad in pedidos.items()}


@transaction.atomic
def crear_servicio(*, centro, datos: dict, insumos: list[dict] | None = None) -> Servicio:
    """Alta de servicio (P26), con sus insumos habituales si los trae."""
    _validar(centro.pk, datos)
    servicio = Servicio(centro=centro, **datos)
    _guardar(servicio)
    bitacora = {"nombre": servicio.nombre, "precio": str(servicio.precio)}
    if insumos is not None:
        bitacora["insumos_habituales"] = _guardar_insumos(servicio, insumos)
    registrar("ALTA", "servicio", servicio.pk, bitacora)
    return servicio


@transaction.atomic
def actualizar_servicio(servicio: Servicio, *, datos: dict,
                        insumos: list[dict] | None = None) -> Servicio:
    """Edición de servicio (P26). La baja es `esta_activo = False`: un
    servicio con citas o atenciones no se borra.

    Cambiar el precio no altera lo ya cobrado: cada atención guarda su monto.
    """
    _validar(servicio.centro_id, datos, excepto=servicio.pk)
    for campo, valor in datos.items():
        setattr(servicio, campo, valor)
    _guardar(servicio)
    bitacora = {campo: str(valor) for campo, valor in datos.items()}
    if insumos is not None:
        bitacora["insumos_habituales"] = _guardar_insumos(servicio, insumos)
    registrar("EDICION", "servicio", servicio.pk, bitacora)
    return servicio
