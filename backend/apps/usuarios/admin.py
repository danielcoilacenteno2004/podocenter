"""Administración de usuarios y de su asignación a sedes."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AsignacionSede, Usuario


class AsignacionEnLinea(admin.TabularInline):
    model = AsignacionSede
    extra = 1
    autocomplete_fields = ("sede",)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    inlines = [AsignacionEnLinea]
    list_display = ("correo", "nombres", "apellidos", "rol", "centro", "esta_activo")
    list_filter = ("rol", "esta_activo", "centro")
    search_fields = ("correo", "nombres", "apellidos", "documento")
    ordering = ("apellidos", "nombres")
    filter_horizontal = ()
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Datos personales", {"fields": ("nombres", "apellidos", "documento")}),
        ("Pertenencia", {"fields": ("centro", "rol", "esta_activo")}),
        ("Seguridad", {"fields": ("segundo_factor_activo", "ultimo_acceso_en")}),
        ("Permisos de Django", {"fields": ("is_staff", "is_superuser", "groups",
                                           "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("correo", "nombres", "apellidos", "centro", "rol",
                       "password1", "password2"),
        }),
    )
    readonly_fields = ("ultimo_acceso_en",)
