"""Consulta de citas desde el admin (solo lectura).

Las citas se crean desde la agenda, que es donde viven las reglas de
horario y de solapamiento; permitir crearlas aquí las saltaría.
"""
from django.contrib import admin

from .models import Cita


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("inicio", "sede", "paciente", "profesional", "servicio", "estado")
    list_filter = ("estado", "sede", "centro")
    search_fields = ("paciente__nombres", "paciente__apellidos", "paciente__documento")
    date_hierarchy = "inicio"
    ordering = ("-inicio",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
