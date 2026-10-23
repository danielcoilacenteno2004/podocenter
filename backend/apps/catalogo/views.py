"""API del catálogo de servicios (RF09, CU17)."""
from rest_framework import viewsets

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Servicio
from .serializers import ServicioSerializer


class ServicioViewSet(ContextoDeCentro, viewsets.ModelViewSet):
    serializer_class = ServicioSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["esta_activo"]

    def get_queryset(self):
        return Servicio.objects.filter(centro_id=self.request.centro_id)

    def get_permissions(self):
        """La podóloga consulta el catálogo, pero no lo modifica."""
        if self.action not in {"list", "retrieve"}:
            self.roles_permitidos = {Rol.ADMIN_CENTRO}
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(centro=self.request.user.centro)
