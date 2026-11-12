"""Servicios que ofrece el centro (RF09) y sus insumos habituales (CC-14)."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.modelos_base import ModeloDeCentro

# Práctica N.° 7, Tabla 24: la duración de un servicio va de 10 a 240 minutos.
DURACION_MINIMA = 10
DURACION_MAXIMA = 240


class Servicio(ModeloDeCentro):
    """Prestación con precio y duración. La duración alimenta la agenda."""

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    duracion_minutos = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(DURACION_MINIMA), MaxValueValidator(DURACION_MAXIMA)]
    )
    precio = models.DecimalField(max_digits=8, decimal_places=2,
                                 validators=[MinValueValidator(0)])
    esta_activo = models.BooleanField(default=True)

    class Meta:
        db_table = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["centro", "nombre"], name="uq_servicio_centro_nombre"),
            models.CheckConstraint(
                condition=models.Q(duracion_minutos__gte=DURACION_MINIMA,
                                   duracion_minutos__lte=DURACION_MAXIMA),
                name="ck_servicio_duracion_en_rango",
            ),
        ]

    def __str__(self) -> str:
        return self.nombre
