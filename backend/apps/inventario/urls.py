from django.urls import path

from .views import Disponibilidad, Movimientos, Productos, StockDeLaSede

urlpatterns = [
    path("inventario/productos/", Productos.as_view(), name="inventario-productos"),
    path("inventario/stock/", StockDeLaSede.as_view(), name="inventario-stock"),
    path("inventario/movimientos/", Movimientos.as_view(), name="inventario-movimientos"),
    path("inventario/disponibilidad/", Disponibilidad.as_view(), name="inventario-disponibilidad"),
]
