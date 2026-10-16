"""Entidades transversales: el centro cliente y la bitácora de auditoría."""
from django.db import models

from .modelos_base import SelloDeTiempo


class Centro(SelloDeTiempo):
    """Centro de podología que arrienda el sistema (inquilino del SaaS)."""

    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"
        DEMO = "DEMO", "Demostración"

    razon_social = models.CharField(max_length=150)
    ruc = models.CharField(max_length=11, unique=True)
    subdominio = models.SlugField(max_length=40, unique=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ACTIVO)

    class Meta:
        db_table = "centro"
        verbose_name_plural = "centros"
        ordering = ["razon_social"]

    def __str__(self) -> str:
        return f"{self.razon_social} ({self.subdominio})"

    @property
    def esta_operativo(self) -> bool:
        return self.estado in {self.Estado.ACTIVO, self.Estado.DEMO}


class RegistroAuditoria(models.Model):
    """Traza de los accesos y cambios sobre datos sensibles (Ley N.° 29733).

    Se escribe siempre desde `apps.core.auditoria.registrar`, nunca desde las
    vistas, para que ningún módulo pueda olvidarla.
    """

    class Accion(models.TextChoices):
        CONSULTA = "CONSULTA", "Consulta"
        ALTA = "ALTA", "Alta"
        EDICION = "EDICION", "Edición"
        BAJA = "BAJA", "Baja"
        ACCESO_DENEGADO = "ACCESO_DENEGADO", "Acceso denegado"

    centro = models.ForeignKey(Centro, on_delete=models.PROTECT, related_name="auditoria")
    usuario_id = models.BigIntegerField(null=True, blank=True)
    accion = models.CharField(max_length=16, choices=Accion.choices)
    entidad = models.CharField(max_length=60)
    entidad_id = models.CharField(max_length=40, blank=True)
    datos = models.JSONField(default=dict, blank=True)
    direccion_ip = models.GenericIPAddressField(null=True, blank=True)
    ocurrido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registro_auditoria"
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        indexes = [
            models.Index(fields=["centro", "entidad", "entidad_id"], name="idx_audit_entidad"),
            models.Index(fields=["ocurrido_en"], name="idx_audit_fecha"),
        ]

    def __str__(self) -> str:
        return f"{self.ocurrido_en:%Y-%m-%d %H:%M} {self.accion} {self.entidad}"
