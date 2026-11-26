"""Agenda de citas (RF06, RF08).

La regla que da forma a este módulo es que dos citas de la misma podóloga
no pueden solaparse. La Práctica N.° 6 decidió sostenerla en la base con
una restricción EXCLUDE sobre un rango de tiempo, y no solo en el
servidor, porque dos peticiones simultáneas pueden pasar la validación de
aplicación y chocar al escribir.
"""
from datetime import time

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.utils import timezone

from apps.core.modelos_base import ModeloDeCentro


class Cita(ModeloDeCentro):
    class Estado(models.TextChoices):
        PROGRAMADA = "PROGRAMADA", "Programada"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"
        NO_ASISTIO = "NO_ASISTIO", "No asistió"

    sede = models.ForeignKey("sedes.Sede", on_delete=models.PROTECT, related_name="citas")
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT,
                                 related_name="citas")
    profesional = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                    related_name="citas")
    servicio = models.ForeignKey("catalogo.Servicio", on_delete=models.PROTECT,
                                 related_name="citas")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    periodo = DateTimeRangeField(
        help_text="Rango [inicio, fin) que sostiene la restricción de solapamiento",
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PROGRAMADA)
    observaciones = models.CharField(max_length=300, blank=True)
    motivo_cancelacion = models.CharField(max_length=200, blank=True)
    cancelada_en = models.DateTimeField(null=True, blank=True)
    creada_por = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                   related_name="citas_creadas")
    # Cita cancelada a la que esta reemplaza (P07, CC-16). Distingue una
    # cancelación reprogramada de un ingreso perdido: sin el vínculo, el panel
    # contaba como no concretado lo que solo cambió de día.
    reemplaza = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="reemplazo")

    class Meta:
        db_table = "cita"
        verbose_name_plural = "citas"
        ordering = ["inicio"]
        indexes = [
            models.Index(fields=["sede", "inicio"], name="idx_cita_sede_inicio"),
            models.Index(fields=["paciente", "-inicio"], name="idx_cita_paciente"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fin__gt=models.F("inicio")), name="ck_cita_fin_posterior"
            ),
            ExclusionConstraint(
                name="ex_cita_sin_solape_por_profesional",
                expressions=[
                    ("periodo", RangeOperators.OVERLAPS),
                    ("profesional", RangeOperators.EQUAL),
                ],
                condition=models.Q(estado="PROGRAMADA"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.paciente} · {self.inicio:%d/%m %H:%M}"

    def save(self, *args, **kwargs):
        """Mantiene `periodo` sincronizado con inicio y fin."""
        self.periodo = (self.inicio, self.fin)
        super().save(*args, **kwargs)

    @property
    def esta_vigente(self) -> bool:
        return self.estado == self.Estado.PROGRAMADA and self.fin > timezone.now()


class CanalDeRecordatorio(models.TextChoices):
    """Los canales de `apps.citas.canales`; el código es el mismo."""

    CORREO = "CORREO", "Correo electrónico"
    WHATSAPP_MANUAL = "WHATSAPP_MANUAL", "WhatsApp (envío manual desde la agenda)"
    WHATSAPP_API = "WHATSAPP_API", "WhatsApp automático (pendiente de aprobación, CC-28)"


class ConfiguracionRecordatorios(ModeloDeCentro):
    """Cómo y cuándo recuerda las citas cada centro (RF07).

    Una por centro. Nace desactivada y con el canal manual: activar el envío
    automático y elegir el canal es una decisión de la Gerencia (costo del
    WhatsApp, riesgo R9), no del sistema. La hora es la hora local a partir
    de la cual se avisa de las citas del día siguiente.
    """

    activo = models.BooleanField(default=False)
    hora_envio = models.TimeField(default=time(18, 0))
    canal = models.CharField(max_length=16, choices=CanalDeRecordatorio.choices,
                             default=CanalDeRecordatorio.WHATSAPP_MANUAL)

    class Meta:
        db_table = "configuracion_recordatorios"
        verbose_name = "configuración de recordatorios"
        verbose_name_plural = "configuraciones de recordatorios"
        constraints = [
            models.UniqueConstraint(fields=["centro"],
                                    name="uq_configuracion_recordatorios_centro"),
        ]

    def __str__(self) -> str:
        estado = "activos" if self.activo else "desactivados"
        return f"Recordatorios {estado} por {self.get_canal_display()} a las {self.hora_envio}"


class Recordatorio(ModeloDeCentro):
    """Registro del recordatorio de una cita (RF07, CU15 y CU16 del informe).

    Uno por cita: la restricción única es la que garantiza que un reintento
    nunca duplica el mensaje. Se crea al intentar el primer envío y guarda el
    canal, el destino, los intentos y el resultado de cada uno.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADO = "ENVIADO", "Enviado"
        FALLIDO = "FALLIDO", "Fallido"
        CANCELADO = "CANCELADO", "Cancelado"

    cita = models.OneToOneField(Cita, on_delete=models.CASCADE, related_name="recordatorio")
    canal = models.CharField(max_length=16, choices=CanalDeRecordatorio.choices)
    # Un correo puede tener hasta 254 caracteres (RFC 5321).
    destino = models.CharField(max_length=254)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    id_externo = models.CharField(max_length=120, blank=True)
    ultimo_error = models.CharField(max_length=300, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recordatorio"
        verbose_name_plural = "recordatorios"
        constraints = [
            models.CheckConstraint(condition=models.Q(intentos__lte=3),
                                   name="ck_recordatorio_maximo_tres_intentos"),
        ]
