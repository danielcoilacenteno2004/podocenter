"""Consulta de atenciones desde el admin (solo lectura).

Las atenciones se registran desde la API, que es donde se copia la cita y
se cierra en la misma transacción. Las observaciones clínicas no se
muestran aquí: su lectura solo queda auditada a través de la ficha.
"""
from django.contrib import admin

from .models import Atencion


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    list_display = ("registrada_en", "sede", "paciente", "profesional", "servicio")
    list_filter = ("sede", "centro")
    search_fields = ("paciente__nombres", "paciente__apellidos", "paciente__documento")
    date_hierarchy = "registrada_en"
    exclude = ("observaciones_clinicas",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
