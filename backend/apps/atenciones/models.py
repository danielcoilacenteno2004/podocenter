"""Atención: constancia de lo que se hizo en una cita (RF10, CU10).

La cita es una promesa en la agenda; la atención es el hecho clínico. Por
eso guarda su propia copia de paciente, profesional y servicio tomada al
registrarla: si después alguien edita la cita, la ficha clínica no puede
cambiar con ella.
"""
from django.db import models

from apps.core.campos import TextoCifrado
from apps.core.modelos_base import ModeloDeCentro


class Atencion(ModeloDeCentro):
    sede = models.ForeignKey("sedes.Sede", on_delete=models.PROTECT, related_name="atenciones")
    cita = models.OneToOneField("citas.Cita", on_delete=models.PROTECT, related_name="atencion")
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT,
                                 related_name="atenciones")
    profesional = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                    related_name="atenciones")
    servicio = models.ForeignKey("catalogo.Servicio", on_delete=models.PROTECT,
                                 related_name="atenciones")
    observaciones_clinicas = TextoCifrado(blank=True, default="")
    registrada_por = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                       related_name="atenciones_registradas")
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "atencion"
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ["-registrada_en"]
        indexes = [
            models.Index(fields=["paciente", "-registrada_en"], name="idx_atencion_paciente"),
        ]

    def __str__(self) -> str:
        return f"{self.paciente} · {self.registrada_en:%d/%m/%Y %H:%M}"
