"""Temporizador de recordatorios (CU15): una pasada por todos los centros.

En producción lo corre el servicio `recordatorios` del compose cada quince
minutos. Cada centro se procesa con su `app.centro_id`, como exige la
seguridad por fila.
"""
from django.core.management.base import BaseCommand

from apps.citas.recordatorios import enviar_recordatorios, proveedor
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.models import Centro


class Command(BaseCommand):
    help = "Envía los recordatorios de las citas de las próximas 24 horas."

    def handle(self, *args, **opciones):
        enviador = proveedor()
        try:
            for centro in Centro.objects.all():
                if not centro.esta_operativo:
                    continue
                fijar_centro_en_la_sesion(centro.pk)
                resumen = enviar_recordatorios(centro_id=centro.pk, enviador=enviador)
                if any(resumen.values()):
                    self.stdout.write(f"{centro.nombre_comercial or centro.razon_social} "
                                      f"({enviador.nombre}): {resumen}")
        finally:
            fijar_centro_en_la_sesion(None)
