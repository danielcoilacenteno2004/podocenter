"""Planificador de recordatorios (RF07, CU15): una pasada por todos los centros.

Lo ejecuta el planificador del servidor; en producción, el servicio
`recordatorios` del compose cada quince minutos. En cada pasada, cada centro
decide según su configuración si ya toca avisar de las citas de mañana
(`pasada_del_planificador`). Cada centro se procesa con su `app.centro_id`,
como exige la seguridad por fila, y un error en uno no detiene a los demás.
"""
import logging

from django.core.management.base import BaseCommand

from apps.citas.recordatorios import pasada_del_planificador
from apps.core.contexto import fijar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.models import Centro

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envía, por el canal de cada centro, los recordatorios de las citas de mañana."

    def handle(self, *args, **opciones):
        try:
            for centro in Centro.objects.all().order_by("pk"):
                if not centro.esta_operativo:
                    continue
                fijar_centro_en_la_sesion(centro.pk)
                fijar_contexto(centro_id=centro.pk)
                try:
                    resumen = pasada_del_planificador(centro_id=centro.pk)
                except Exception:
                    logger.exception("Falló la pasada de recordatorios del centro %s", centro.pk)
                    continue
                if any(isinstance(v, int) and v for v in resumen.values()):
                    nombre = centro.nombre_comercial or centro.razon_social
                    self.stdout.write(f"{nombre}: {resumen}")
        finally:
            fijar_centro_en_la_sesion(None)
            fijar_contexto()
