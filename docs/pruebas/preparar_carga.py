"""Práctica 9 — prepara las citas que necesita carga_atencion.js.

Una atención solo se registra sobre una cita programada que ya empezó, y la
demostración deja dos. Este script crea, en la Sede Cercado y para la
podóloga de la demostración, N citas programadas en días pasados, sin
solaparse, y repone el insumo habitual del servicio con una entrada normal
(registrar_movimiento), para que la medición no tropiece con falta de stock.

Escribe los identificadores de las citas en un JSON que lee k6:

    python docs/pruebas/preparar_carga.py 100 RUTA/citas_carga.json

Se corre después de cargar_demo y sembrar_volumen. Es un script de prueba: no
forma parte de la aplicación.
"""
import json
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.catalogo.models import Servicio, ServicioInsumo  # noqa: E402
from apps.citas.models import Cita  # noqa: E402
from apps.core.contexto import fijar_contexto  # noqa: E402
from apps.core.contexto_http import fijar_centro_en_la_sesion  # noqa: E402
from apps.core.models import Centro  # noqa: E402
from apps.inventario.servicios import registrar_movimiento  # noqa: E402
from apps.pacientes.models import Paciente  # noqa: E402
from apps.sedes.models import Sede  # noqa: E402
from apps.usuarios.models import Usuario  # noqa: E402


@transaction.atomic
def preparar(cantidad: int) -> dict:
    centro = Centro.objects.get(subdominio="piessanos")
    fijar_centro_en_la_sesion(centro.pk)
    fijar_contexto(centro_id=centro.pk)
    sede = Sede.objects.get(centro=centro, nombre="Sede Cercado")
    podologa = Usuario.objects.get(correo="podologa@piessanos.pe")
    admin = Usuario.objects.get(correo="gerencia@piessanos.pe")
    servicio = Servicio.objects.get(centro=centro, nombre="Tratamiento de onicomicosis")
    pacientes = list(Paciente.objects.filter(centro=centro).order_by("pk"))

    # De 08:00 a 18:30, una cita cada media hora, empezando hace 30 días:
    # quedan lejos de la agenda de la demostración, que es de hoy en adelante.
    ids, dia = [], timezone.localdate() - timedelta(days=30)
    while len(ids) < cantidad:
        if dia.weekday() != 6:
            hora = datetime.combine(dia, time(8, 0))
            while hora.time() <= time(18, 30) and len(ids) < cantidad:
                inicio = timezone.make_aware(hora)
                cita = Cita.objects.create(
                    centro=centro, sede=sede, paciente=pacientes[len(ids) % len(pacientes)],
                    profesional=podologa, servicio=servicio, inicio=inicio,
                    fin=inicio + timedelta(minutes=servicio.duracion_minutos), creada_por=admin,
                    observaciones="Cita para la prueba de carga (Práctica 9)",
                )
                ids.append(cita.pk)
                hora += timedelta(minutes=30)
        dia += timedelta(days=1)

    insumos = [{"producto": i.producto_id, "cantidad": i.cantidad}
               for i in ServicioInsumo.objects.filter(servicio=servicio)]
    for insumo in insumos:
        registrar_movimiento(centro=centro, usuario=admin, sede_id=sede.pk,
                             producto_id=insumo["producto"], tipo="ENTRADA",
                             cantidad=insumo["cantidad"] * cantidad + 10,
                             motivo="Reposición para la prueba de carga (Práctica 9)")
    return {"sede": sede.pk, "citas": ids, "monto": f"{servicio.precio:.2f}", "insumos": insumos}


if __name__ == "__main__":
    datos = preparar(int(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(datos), encoding="utf-8")
    print(f"{len(datos['citas'])} citas preparadas en la sede {datos['sede']}; "
          f"insumos por atención: {datos['insumos']}")
