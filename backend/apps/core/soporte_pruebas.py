"""Utilidades que solo usan las pruebas.

Vive en el paquete de la aplicación —y no en `conftest`— para que
cualquier módulo de prueba pueda importarla sin depender de la ruta desde
la que se ejecuta pytest.
"""
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from .contexto import fijar_contexto


def hacer_que_la_cita_ya_empezo(cita, hace_minutos: int = 10):
    """Mueve una cita programada al pasado reciente, sin pasar por la agenda.

    `programar_cita` exige anticipación, así que una cita «ya en curso» solo
    se consigue retrocediéndola después de crearla. La duración se conserva.
    """
    duracion = cita.fin - cita.inicio
    cita.inicio = timezone.now() - timedelta(minutes=hace_minutos)
    cita.fin = cita.inicio + duracion
    cita.save(update_fields=["inicio", "fin", "periodo", "actualizado_en"])
    return cita


def activar_centro(centro_id: int) -> None:
    """Fija el centro activo igual que lo hace `ContextoTenantMiddleware`."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.centro_id', %s, false)", [str(centro_id)])
    fijar_contexto(centro_id=centro_id)
