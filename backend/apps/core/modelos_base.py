"""Modelos y mezclas compartidos por todos los módulos.

`ModeloDeCentro` es la pieza que sostiene el aislamiento multi-inquilino
descrito en la Práctica N.° 5: toda tabla con datos de un centro cliente
lleva `centro` y queda bajo la política de seguridad a nivel de fila (RLS)
que instala la migración `0002_rls` de este módulo.
"""
from django.db import models


class SelloDeTiempo(models.Model):
    """Fechas de creación y última modificación."""

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ModeloDeCentro(SelloDeTiempo):
    """Base de toda entidad que pertenece a un centro cliente."""

    centro = models.ForeignKey(
        "core.Centro", on_delete=models.PROTECT, related_name="%(class)ss"
    )

    class Meta:
        abstract = True
