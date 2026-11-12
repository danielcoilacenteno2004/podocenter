from django.urls import path

from .views import (
    Disponibilidad,
    MinimoDeStock,
    Movimientos,
    ProductoDetalle,
    Productos,
    StockDeLaSede,
)

urlpatterns = [
    path("inventario/productos/", Productos.as_view(), name="inventario-productos"),
    path("inventario/productos/<int:producto_id>/", ProductoDetalle.as_view(),
         name="inventario-producto"),
    path("inventario/stock/", StockDeLaSede.as_view(), name="inventario-stock"),
    path("inventario/stock/<int:producto_id>/", MinimoDeStock.as_view(),
         name="inventario-minimo"),
    path("inventario/movimientos/", Movimientos.as_view(), name="inventario-movimientos"),
    path("inventario/disponibilidad/", Disponibilidad.as_view(), name="inventario-disponibilidad"),
]
