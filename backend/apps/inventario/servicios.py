"""Reglas de aplicación del inventario (CU11, CU12)."""
from django.db import IntegrityError, transaction

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio
from apps.sedes.models import Sede

from .models import MovimientoInventario, Producto, Stock

Tipo = MovimientoInventario.Tipo
SENTIDOS = {"ALTA": 1, "BAJA": -1}


def _variacion(tipo, cantidad, sentido) -> int:
    """Signo de la cantidad según el tipo (Práctica 7, Tabla 13)."""
    if tipo == Tipo.ENTRADA:
        return cantidad
    if tipo == Tipo.MERMA:
        return -cantidad
    if sentido not in SENTIDOS:
        raise ReglaDeNegocio("sentido-requerido", "Indique si el ajuste es al alta o a la baja.")
    return SENTIDOS[sentido] * cantidad


def _stock_bloqueado(*, centro, sede, producto) -> Stock:
    """La fila de stock del par producto-sede, bloqueada hasta el final de la
    transacción: dos movimientos simultáneos se ponen en fila en lugar de
    leer la misma existencia y pisarse."""
    fila = Stock.objects.select_for_update().filter(sede=sede, producto=producto).first()
    if fila is not None:
        return fila
    try:
        with transaction.atomic():
            Stock.objects.create(centro=centro, sede=sede, producto=producto)
    except IntegrityError:
        pass  # otra petición la creó a la vez; se usa la suya
    return Stock.objects.select_for_update().get(sede=sede, producto=producto)


@transaction.atomic
def registrar_movimiento(*, centro, usuario, sede_id, producto_id, tipo, cantidad,
                         sentido=None, motivo="") -> MovimientoInventario:
    """Registra una entrada, un ajuste o una merma y actualiza el stock (CU11).

    El stock no puede quedar negativo: lo impide esta regla, y si algo se la
    saltara, la restricción CHECK de la tabla `stock`.
    """
    if sede_id is None:
        raise ReglaDeNegocio("sin-sede-activa", "Elija la sede del movimiento.")
    if producto_id is None:
        raise ReglaDeNegocio("producto-requerido", "Elija el producto del movimiento.")
    if tipo not in Tipo.values:
        raise ReglaDeNegocio(
            "tipo-no-elegible",
            "El movimiento debe ser una entrada, un ajuste o una merma; las salidas por "
            "consumo no se registran a mano.",
        )
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0:
        raise ReglaDeNegocio("cantidad-invalida", "La cantidad debe ser un entero mayor que 0.")
    motivo = (motivo or "").strip()
    if tipo in (Tipo.AJUSTE, Tipo.MERMA) and not motivo:
        raise ReglaDeNegocio("motivo-requerido", "Indique el motivo del ajuste o de la merma.")

    sede = Sede.objects.filter(pk=sede_id, centro=centro).first()
    if sede is None:
        raise ReglaDeNegocio("sede-fuera-del-centro", "La sede no existe en este centro.")
    producto = Producto.objects.filter(pk=producto_id, centro=centro).first()
    if producto is None:
        raise ReglaDeNegocio("producto-fuera-del-centro", "El producto no existe en este centro.")
    if not producto.esta_activo:
        raise ReglaDeNegocio("producto-inactivo", "Ese producto ya no está activo.")

    variacion = _variacion(tipo, cantidad, sentido)
    stock = _stock_bloqueado(centro=centro, sede=sede, producto=producto)
    nueva = stock.cantidad + variacion
    if nueva < 0:
        raise ReglaDeNegocio(
            "stock-insuficiente",
            f"En {sede.nombre} solo hay {stock.cantidad} {producto.unidad} de {producto.nombre}.",
        )
    stock.cantidad = nueva
    stock.save(update_fields=["cantidad", "actualizado_en"])
    movimiento = MovimientoInventario.objects.create(
        centro=centro, sede=sede, producto=producto, tipo=tipo, cantidad=variacion,
        existencia_resultante=nueva, motivo=motivo, registrado_por=usuario,
    )
    registrar("ALTA", "movimiento_inventario", movimiento.pk,
              {"tipo": tipo, "cantidad": variacion, "sede": sede.pk, "producto": producto.pk})
    return movimiento


def stock_de_la_sede(*, centro_id: int, sede_id: int) -> list[dict]:
    """Todos los productos activos con su existencia en la sede (P12).

    Un producto que nunca tuvo movimientos en la sede aparece con 0: para
    quien registra una entrada, «no hay» también es información.
    """
    filas = {s.producto_id: s for s in Stock.objects.filter(centro_id=centro_id, sede_id=sede_id)}
    resultado = []
    for producto in Producto.objects.filter(centro_id=centro_id, esta_activo=True):
        fila = filas.get(producto.pk)
        cantidad, minimo = (fila.cantidad, fila.minimo) if fila else (0, 0)
        resultado.append({"producto": producto, "cantidad": cantidad, "minimo": minimo,
                          "bajo_minimo": cantidad < minimo})
    return resultado


def disponibilidad(*, centro_id: int, producto_id: int) -> list[dict]:
    """El mismo producto en cada sede activa del centro (P14, CU12). Solo informa:
    no mueve stock entre sedes."""
    filas = {s.sede_id: s for s in Stock.objects.filter(centro_id=centro_id,
                                                        producto_id=producto_id)}
    resultado = []
    for sede in Sede.objects.filter(centro_id=centro_id, esta_activa=True).order_by("nombre"):
        fila = filas.get(sede.pk)
        resultado.append({"sede": sede, "cantidad": fila.cantidad if fila else 0,
                          "minimo": fila.minimo if fila else 0})
    return resultado
