"""Administración de sedes y sus horarios de atención."""
from django.contrib import admin

from .models import HorarioSede, Sede


class HorarioEnLinea(admin.TabularInline):
    model = HorarioSede
    extra = 0


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    inlines = [HorarioEnLinea]
    list_display = ("nombre", "centro", "direccion", "telefono", "esta_activa")
    list_filter = ("esta_activa", "centro")
    search_fields = ("nombre", "direccion")
    ordering = ("centro", "nombre")
