"""Permisos por rol (RBAC). Tres roles, definidos en la Práctica N.° 5."""
from rest_framework.permissions import BasePermission

from apps.usuarios.roles import Rol


class TieneRol(BasePermission):
    """Permite el acceso solo a los roles declarados en la vista."""

    message = "Su rol no tiene permiso para esta acción."

    def has_permission(self, request, view) -> bool:
        roles = getattr(view, "roles_permitidos", None)
        if roles is None:
            return True
        return bool(request.user.is_authenticated and request.user.rol in roles)


class EsAdministradorDePlataforma(BasePermission):
    message = "Solo el administrador de plataforma puede realizar esta acción."

    def has_permission(self, request, view) -> bool:
        return bool(request.user.is_authenticated and request.user.rol == Rol.ADMIN_PLATAFORMA)
