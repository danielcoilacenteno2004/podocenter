"""Servicios que ofrece el centro (RF09) y sus insumos habituales (CC-14)."""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.modelos_base import ModeloDeCentro


class Servicio(ModeloDeCentro):
    """Prestación con precio y duración. La duración alimenta la agenda."""

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    duracion_minutos = models.PositiveSmallIntegerField(validators=[MinValueValidator(5)])
    precio = models.DecimalField(max_digits=8, decimal_places=2,
                                 validators=[MinValueValidator(0)])
    esta_activo = models.BooleanField(default=True)

    class Meta:
        db_table = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["centro", "nombre"], name="uq_servicio_centro_nombre")
        ]

    def __str__(self) -> str:
        return self.nombre
