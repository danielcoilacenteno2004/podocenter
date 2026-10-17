"""Sedes del centro y su horario de atención (RF03, cambio CC-15)."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.modelos_base import ModeloDeCentro


class Sede(ModeloDeCentro):
    """Local físico donde se atiende. Es el eje de inventario y agenda."""

    nombre = models.CharField(max_length=80)
    direccion = models.CharField(max_length=200)
    telefono = models.CharField(max_length=20, blank=True)
    esta_activa = models.BooleanField(default=True)

    class Meta:
        db_table = "sede"
        verbose_name_plural = "sedes"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["centro", "nombre"], name="uq_sede_centro_nombre")
        ]

    def __str__(self) -> str:
        return self.nombre

    def horario_de(self, dia_semana: int):
        """Horario de un día (0 = lunes). Devuelve None si la sede cierra."""
        return self.horarios.filter(dia_semana=dia_semana, esta_abierta=True).first()


class HorarioSede(models.Model):
    """Apertura y cierre por día de la semana (CC-15).

    La agenda (P05) necesita saber qué franjas dibujar y cuáles bloquear.
    """

    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name="horarios")
    dia_semana = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="0 = lunes … 6 = domingo",
    )
    hora_apertura = models.TimeField()
    hora_cierre = models.TimeField()
    esta_abierta = models.BooleanField(default=True)

    class Meta:
        db_table = "horario_sede"
        verbose_name = "horario de sede"
        verbose_name_plural = "horarios de sede"
        ordering = ["dia_semana"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "dia_semana"], name="uq_horario_sede_dia"),
            models.CheckConstraint(
                condition=models.Q(hora_cierre__gt=models.F("hora_apertura")),
                name="ck_horario_cierre_posterior",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sede} día {self.dia_semana}: {self.hora_apertura}–{self.hora_cierre}"

    def cubre(self, inicio, fin) -> bool:
        return self.esta_abierta and self.hora_apertura <= inicio and fin <= self.hora_cierre
