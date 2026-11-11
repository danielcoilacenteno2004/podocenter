"""API de inventario (RF11, RF12): P12, P13 y P14.

Rutas de la Tabla 38 del informe: POST /inventario/movimientos y
GET /inventario/disponibilidad. El stock de la sede (P12) y el catálogo de
productos son de lectura: el stock solo cambia por un movimiento.
"""
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errores import ReglaDeNegocio
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Producto
from .servicios import disponibilidad, registrar_movimiento, stock_de_la_sede


def _entero(valor):
    """Un entero de la petición, o None si no lo es: el servicio decide el error."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
        return int(valor.strip())
    return None


def _producto(p: Producto) -> dict:
    return {"id": p.pk, "codigo": p.codigo, "nombre": p.nombre, "unidad": p.unidad}


class _VistaDeInventario(ContextoDeCentro, APIView):
    """Mismo acceso que Pacientes y Atenciones: la podóloga y la administradora."""

    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}

    def _sede_activa(self, request):
        if request.sede_id is None:
            raise ReglaDeNegocio("sin-sede-activa", "Elija la sede de la que quiere ver el stock.")
        return request.sede_id


class Productos(_VistaDeInventario):
    """Catálogo de productos activos, para buscar en P13 (desde 2 caracteres)."""

    def get(self, request):
        consulta = Producto.objects.filter(centro_id=request.centro_id, esta_activo=True)
        texto = (request.query_params.get("buscar") or "").strip()
        if texto:
            consulta = consulta.filter(Q(nombre__icontains=texto) | Q(codigo__icontains=texto))
        return Response({"productos": [_producto(p) for p in consulta]})


class StockDeLaSede(_VistaDeInventario):
    """P12 — existencias de la sede activa."""

    def get(self, request):
        filas = stock_de_la_sede(centro_id=request.centro_id, sede_id=self._sede_activa(request))
        return Response({"stock": [
            {**_producto(f["producto"]), "cantidad": f["cantidad"], "minimo": f["minimo"],
             "bajo_minimo": f["bajo_minimo"]}
            for f in filas
        ]})


class Movimientos(_VistaDeInventario):
    """P13 — registra un movimiento en la sede activa."""

    def post(self, request):
        datos = request.data
        movimiento = registrar_movimiento(
            centro=request.user.centro, usuario=request.user, sede_id=request.sede_id,
            producto_id=_entero(datos.get("producto")), tipo=datos.get("tipo"),
            cantidad=_entero(datos.get("cantidad")), sentido=datos.get("sentido"),
            motivo=datos.get("motivo", ""),
        )
        return Response({
            "id": movimiento.pk, "producto": movimiento.producto_id, "tipo": movimiento.tipo,
            "cantidad": movimiento.cantidad,
            "existencia_resultante": movimiento.existencia_resultante,
            "motivo": movimiento.motivo, "creado_en": movimiento.creado_en,
        }, status=status.HTTP_201_CREATED)


class Disponibilidad(_VistaDeInventario):
    """P14 — el mismo producto en todas las sedes del centro, no solo la activa."""

    def get(self, request):
        producto = Producto.objects.filter(
            pk=_entero(request.query_params.get("producto")), centro_id=request.centro_id
        ).first()
        if producto is None:
            raise ReglaDeNegocio(
                "producto-fuera-del-centro", "El producto no existe en este centro."
            )
        filas = disponibilidad(centro_id=request.centro_id, producto_id=producto.pk)
        return Response({
            "producto": _producto(producto),
            "sedes": [
                {"id": f["sede"].pk, "nombre": f["sede"].nombre, "cantidad": f["cantidad"],
                 "minimo": f["minimo"], "es_activa": f["sede"].pk == request.sede_id}
                for f in filas
            ],
        })
