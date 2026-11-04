"""Administración del catálogo de servicios del centro."""
from django.contrib import admin

from .models import Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "centro", "duracion_minutos", "precio", "esta_activo")
    list_filter = ("esta_activo", "centro")
    search_fields = ("nombre", "descripcion")
    ordering = ("centro", "nombre")
