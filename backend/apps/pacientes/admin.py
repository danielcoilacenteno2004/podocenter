"""Administración de pacientes y consentimientos.

Los antecedentes clínicos van cifrados en la base; aquí se muestran solo los
campos de identificación, que es lo que necesita una corrección de datos.
"""
from django.contrib import admin

from .models import Consentimiento, Paciente


class ConsentimientoEnLinea(admin.TabularInline):
    model = Consentimiento
    extra = 0
    readonly_fields = ("otorgado_en", "registrado_por")


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    inlines = [ConsentimientoEnLinea]
    list_display = ("documento", "apellidos", "nombres", "centro", "telefono", "esta_activo")
    list_filter = ("esta_activo", "tipo_documento", "centro")
    search_fields = ("documento", "nombres", "apellidos")
    ordering = ("apellidos", "nombres")
    exclude = ("antecedentes",)
