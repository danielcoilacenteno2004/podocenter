"""Inventario por sede (RF11, RF12, RF13 ajustado por CC-12).

Las tablas siguen el diccionario de datos del informe: `stock` guarda la
existencia de cada producto en cada sede, con CHECK (>= 0) y única por par
producto-sede, y `movimiento_inventario` es la única vía por la que cambia.
El stock nunca se edita directamente (CU11).
"""
from django.db import models

from apps.core.modelos_base import ModeloDeCentro


class Producto(ModeloDeCentro):
    """Insumo del centro; el catálogo es común a todas sus sedes."""

    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=120)
    unidad = models.CharField(max_length=20, default="unidad")
    esta_activo = models.BooleanField(default=True)

    class Meta:
        db_table = "producto"
        verbose_name_plural = "productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["centro", "codigo"], name="uq_producto_centro_codigo"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} {self.nombre}"


class Stock(ModeloDeCentro):
    """Existencia de un producto en una sede, con su umbral mínimo (P12, P14)."""

    sede = models.ForeignKey("sedes.Sede", on_delete=models.PROTECT, related_name="stock")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="stock")
    cantidad = models.IntegerField(default=0)
    minimo = models.IntegerField(default=0)

    class Meta:
        db_table = "stock"
        verbose_name_plural = "stock"
        constraints = [
            models.UniqueConstraint(fields=["producto", "sede"], name="uq_stock_producto_sede"),
            # Tercer nivel de la validación de stock: aunque un error se salte
            # el servicio, la base no admite existencias negativas.
            models.CheckConstraint(condition=models.Q(cantidad__gte=0),
                                   name="ck_stock_cantidad_no_negativa"),
            models.CheckConstraint(condition=models.Q(minimo__gte=0),
                                   name="ck_stock_minimo_no_negativo"),
        ]

    @property
    def bajo_minimo(self) -> bool:
        return self.cantidad < self.minimo


class MovimientoInventario(ModeloDeCentro):
    """Toda variación de stock, con su usuario, fecha y motivo (CU11).

    Entrada, ajuste y merma los elige el usuario en P13 (Práctica 7, Tabla
    13). La salida no se elige: la genera el sistema al registrar una
    atención con sus insumos (P11), y queda ligada a esa atención.
    """

    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        AJUSTE = "AJUSTE", "Ajuste"
        MERMA = "MERMA", "Merma"
        SALIDA = "SALIDA", "Salida por consumo"

    sede = models.ForeignKey("sedes.Sede", on_delete=models.PROTECT,
                             related_name="movimientos_inventario")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=8, choices=Tipo.choices)
    # Variación con signo: positiva si suma, negativa si resta.
    cantidad = models.IntegerField()
    existencia_resultante = models.IntegerField()
    motivo = models.CharField(max_length=200, blank=True)
    registrado_por = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                       related_name="movimientos_inventario")
    # Solo en las salidas: la atención que consumió el insumo.
    atencion = models.ForeignKey("atenciones.Atencion", on_delete=models.PROTECT, null=True,
                                 blank=True, related_name="insumos")

    class Meta:
        db_table = "movimiento_inventario"
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        ordering = ["-creado_en"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(cantidad=0),
                                   name="ck_movimiento_cantidad_no_cero"),
            models.CheckConstraint(condition=models.Q(existencia_resultante__gte=0),
                                   name="ck_movimiento_existencia_no_negativa"),
            # Una salida siempre resta y siempre tiene su atención; ningún
            # otro tipo la tiene.
            models.CheckConstraint(
                condition=(models.Q(tipo="SALIDA", atencion__isnull=False, cantidad__lt=0)
                           | (~models.Q(tipo="SALIDA") & models.Q(atencion__isnull=True))),
                name="ck_movimiento_salida_con_atencion",
            ),
        ]
