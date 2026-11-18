"""Siembra el volumen de movimientos de inventario que estima el informe.

La Tabla 51 del Informe (2.3.7, volumetría) estima unos 21 600 movimientos
de inventario a dos años para un centro. Las pruebas de carga de la Práctica
N.° 9 los necesitan para medir el sistema con un volumen representativo y no
con la media docena de movimientos que deja `cargar_demo`.

    python manage.py sembrar_volumen                  # 21 600 en 730 días
    python manage.py sembrar_volumen --cantidad 5000

Trabaja sobre el centro de demostración y no toca `cargar_demo`: hay que
correr ese comando antes. Lo que siembra:

- Solo entradas, ajustes y mermas. La salida por consumo exige una atención
  (`ck_movimiento_salida_con_atencion`), y sembrar 7 000 atenciones con sus
  citas es otro volumen, no este.
- Cada producto de cada sede lleva su propia historia, con la existencia
  resultante encadenada y nunca negativa. Cada historia termina en cero con
  un ajuste de cierre, justo antes del inventario inicial de la demostración:
  así el libro cuadra y el stock actual no cambia.
- Volver a correrlo borra lo sembrado antes (se reconoce por el motivo) y lo
  rehace; no duplica.
"""
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.core.contexto import fijar_contexto, limpiar_contexto
from apps.core.contexto_http import fijar_centro_en_la_sesion
from apps.core.models import Centro
from apps.inventario.models import MovimientoInventario, Producto
from apps.sedes.models import Sede
from apps.usuarios.models import Usuario
from apps.usuarios.roles import Rol

SUBDOMINIO_DEMO = "piessanos"
MARCA = "Volumen sembrado (Tabla 51)"
CANTIDAD_POR_DEFECTO = 21_600
DIAS_POR_DEFECTO = 730


class Command(BaseCommand):
    help = "Siembra los movimientos de inventario de dos años (Tabla 51) en la demostración."

    def add_arguments(self, parser):
        parser.add_argument("--cantidad", type=int, default=CANTIDAD_POR_DEFECTO,
                            help="Movimientos a sembrar (por defecto, 21 600).")
        parser.add_argument("--dias", type=int, default=DIAS_POR_DEFECTO,
                            help="Días hacia atrás que cubre la historia (por defecto, 730).")
        parser.add_argument("--semilla", type=int, default=51,
                            help="Semilla del azar, para que dos corridas siembren lo mismo.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if settings.ES_PRODUCCION:
            raise CommandError("sembrar_volumen no se ejecuta con la configuración de producción.")
        centro = Centro.objects.filter(subdominio=SUBDOMINIO_DEMO).first()
        if centro is None:
            raise CommandError("No existe el centro de demostración: corra antes cargar_demo.")
        # El RLS filtra por `app.centro_id`; sin fijarlo, ni se ve ni se escribe.
        fijar_centro_en_la_sesion(centro.pk)
        fijar_contexto(centro_id=centro.pk)
        try:
            sembrados = self._sembrar(centro, opciones)
        finally:
            limpiar_contexto()
        self.stdout.write(self.style.SUCCESS(
            f"{sembrados} movimientos sembrados en {centro.nombre_comercial} "
            f"({opciones['dias']} días)."))

    def _sembrar(self, centro, opciones):
        sedes = list(Sede.objects.filter(centro=centro).order_by("pk"))
        productos = list(Producto.objects.filter(centro=centro).order_by("pk"))
        responsable = Usuario.objects.filter(centro=centro, rol=Rol.ADMIN_CENTRO).first()
        if not sedes or not productos or responsable is None:
            raise CommandError("El centro de demostración no tiene sedes, productos o "
                               "administradora: corra antes cargar_demo.")
        cadenas = [(sede, producto) for sede in sedes for producto in productos]
        cantidad = opciones["cantidad"]
        if cantidad < 2 * len(cadenas):
            raise CommandError(f"La cantidad mínima es {2 * len(cadenas)}: dos movimientos "
                               "por producto y sede, uno de historia y el cierre.")

        borrados, _ = MovimientoInventario.objects.filter(centro=centro, motivo=MARCA).delete()
        if borrados:
            self.stdout.write(f"  {borrados} movimientos sembrados antes, borrados.")

        # Azar reproducible para datos de prueba, no para nada secreto.
        azar = random.Random(opciones["semilla"])  # noqa: S311  # nosec B311
        primero = (MovimientoInventario.objects.filter(centro=centro)
                   .order_by("creado_en").values_list("creado_en", flat=True).first())
        cierre = (primero or timezone.now()) - timedelta(hours=1)
        inicio = cierre - timedelta(days=opciones["dias"])

        # Movimientos de historia, repartidos por igual entre las cadenas y
        # en orden cronológico; el último de cada cadena se reserva al cierre.
        de_historia = cantidad - len(cadenas)
        asignacion = [i % len(cadenas) for i in range(de_historia)]
        azar.shuffle(asignacion)
        segundos = int((cierre - inicio).total_seconds()) - 3600
        momentos = sorted(inicio + timedelta(seconds=azar.randrange(segundos))
                          for _ in range(de_historia))
        ultimo = {indice: posicion for posicion, indice in enumerate(asignacion)}

        existencia = [0] * len(cadenas)
        filas, fechas = [], []
        for posicion, (indice, momento) in enumerate(zip(asignacion, momentos, strict=True)):
            tipo, variacion = self._movimiento(azar, existencia[indice],
                                               forzar_entrada=ultimo[indice] == posicion)
            existencia[indice] += variacion
            sede, producto = cadenas[indice]
            filas.append(self._fila(centro, sede, producto, responsable, tipo, variacion,
                                    existencia[indice]))
            fechas.append(momento)

        # Cierre: cada cadena vuelve a cero antes del inventario inicial.
        for indice, (sede, producto) in enumerate(cadenas):
            filas.append(self._fila(centro, sede, producto, responsable, "AJUSTE",
                                    -existencia[indice], 0))
            fechas.append(cierre + timedelta(seconds=indice))

        creados = MovimientoInventario.objects.bulk_create(filas, batch_size=2000)
        # `creado_en` es auto_now_add y bulk_create lo pisa con la hora actual:
        # se reescribe la fecha histórica en una sola pasada.
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE movimiento_inventario SET creado_en = %s, actualizado_en = %s "
                "WHERE id = %s",
                [(fecha, fecha, m.pk) for m, fecha in zip(creados, fechas, strict=True)],
            )
        return len(creados)

    @staticmethod
    def _movimiento(azar, existencia, *, forzar_entrada):
        """Tipo y variación con signo; nunca deja la existencia negativa.

        Proporción aproximada: 40 % entradas, 30 % mermas y 30 % ajustes.
        Forzar la entrada garantiza que el cierre reste algo y no sea cero.
        """
        tirada = azar.random()
        if forzar_entrada or tirada < 0.40 or existencia == 0:
            return "ENTRADA", azar.randint(5, 30)
        if tirada < 0.70:
            return "MERMA", -min(existencia, azar.randint(1, 3))
        variacion = azar.choice([-1, 1]) * azar.randint(1, 3)
        if existencia + variacion < 0:
            variacion = -existencia
        return "AJUSTE", variacion

    @staticmethod
    def _fila(centro, sede, producto, responsable, tipo, variacion, resultante):
        return MovimientoInventario(
            centro=centro, sede=sede, producto=producto, tipo=tipo, cantidad=variacion,
            existencia_resultante=resultante, motivo=MARCA, registrado_por=responsable,
        )
