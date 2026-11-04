"""Administración de Django para la plataforma.

El admin es la consola del administrador de plataforma: permite dar de alta
centros clientes (RF17) y revisar la bitácora de auditoría sin pasar por la
aplicación del centro.
"""
from django.contrib import admin

from .models import Centro, RegistroAuditoria


@admin.register(Centro)
class CentroAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "ruc", "subdominio", "estado", "creado_en")
    list_filter = ("estado",)
    search_fields = ("razon_social", "ruc", "subdominio")
    ordering = ("razon_social",)


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("ocurrido_en", "centro", "accion", "entidad", "entidad_id", "usuario_id")
    list_filter = ("accion", "entidad", "centro")
    search_fields = ("entidad", "entidad_id")
    date_hierarchy = "ocurrido_en"
    ordering = ("-ocurrido_en",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # La bitácora es append-only: borrarla desde el admin anularía su valor
        # como evidencia (RNF06).
        return False
