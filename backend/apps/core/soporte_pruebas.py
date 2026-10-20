"""Utilidades que solo usan las pruebas.

Vive en el paquete de la aplicación —y no en `conftest`— para que
cualquier módulo de prueba pueda importarla sin depender de la ruta desde
la que se ejecuta pytest.
"""
from django.db import connection

from .contexto import fijar_contexto


def activar_centro(centro_id: int) -> None:
    """Fija el centro activo igual que lo hace `ContextoTenantMiddleware`."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.centro_id', %s, false)", [str(centro_id)])
    fijar_contexto(centro_id=centro_id)
