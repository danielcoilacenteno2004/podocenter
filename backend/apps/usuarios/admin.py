"""Administración de usuarios y de su asignación a sedes.

También pone el segundo factor (RF18) en la puerta del admin de Django: sin
esto, el administrador de plataforma entraría a `/admin/` solo con la
contraseña, y el factor de la aplicación no serviría de nada.
"""
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError

from apps.core.errores import ReglaDeNegocio

from . import segundo_factor
from .models import AsignacionSede, Usuario


class IngresoAdminConSegundoFactor(AdminAuthenticationForm):
    """Formulario de ingreso del admin con el código de la aplicación."""

    codigo = forms.CharField(
        label="Código de verificación", required=False, max_length=16,
        help_text="Los seis dígitos de su aplicación, o uno de sus códigos de recuperación.",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.segundo_factor_activo:
            codigo = (self.cleaned_data.get("codigo") or "").strip()
            es_de_la_aplicacion = codigo.replace(" ", "").isdigit()
            try:
                segundo_factor.verificar_en_el_ingreso(
                    user,
                    codigo=codigo if es_de_la_aplicacion else "",
                    codigo_recuperacion="" if es_de_la_aplicacion else codigo,
                )
            except ReglaDeNegocio as error:
                raise ValidationError(error.detalle, code=error.codigo) from error
        elif user.requiere_segundo_factor:
            raise ValidationError(
                "Active primero la verificación en dos pasos desde la aplicación.",
                code="segundo-factor-pendiente",
            )


admin.site.login_form = IngresoAdminConSegundoFactor
admin.site.login_template = "usuarios/admin_login.html"
_permiso_del_admin = admin.site.has_permission


def _tiene_permiso_con_segundo_factor(request) -> bool:
    # Una sesión abierta desde la aplicación por un rol administrativo que aún
    # no da de alta su factor tampoco entra al admin.
    usuario = request.user
    if getattr(usuario, "requiere_segundo_factor", False) and not usuario.segundo_factor_activo:
        return False
    return _permiso_del_admin(request)


admin.site.has_permission = _tiene_permiso_con_segundo_factor


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
    # El factor no se marca a mano: activarlo sin secreto dejaría la cuenta
    # fuera, y quitarlo con la casilla no pasaría por la auditoría. Se quita
    # con la acción de abajo; el secreto no se muestra en ninguna parte.
    readonly_fields = ("ultimo_acceso_en", "segundo_factor_activo")
    actions = ["reiniciar_segundo_factor"]

    @admin.action(description="Reiniciar la verificación en dos pasos")
    def reiniciar_segundo_factor(self, request, queryset):
        reiniciados = 0
        for usuario in queryset:
            try:
                segundo_factor.reiniciar_segundo_factor(usuario, por=request.user,
                                                        motivo="desde el admin")
                reiniciados += 1
            except ReglaDeNegocio as error:
                self.message_user(request, f"{usuario.correo}: {error.detalle}", messages.ERROR)
        if reiniciados:
            self.message_user(request, f"Verificación en dos pasos reiniciada en {reiniciados} "
                                       "cuenta(s).", messages.SUCCESS)
