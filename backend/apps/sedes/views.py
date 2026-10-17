"""API del módulo Sedes (RF03, CU02)."""
from rest_framework import viewsets

from apps.core.auditoria import registrar
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Sede
from .serializers import SedeSerializer


class SedeViewSet(ContextoDeCentro, viewsets.ModelViewSet):
    serializer_class = SedeSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO}
    filterset_fields = ["esta_activa"]

    def get_queryset(self):
        return Sede.objects.filter(centro_id=self.request.centro_id).prefetch_related("horarios")

    def perform_create(self, serializer):
        sede = serializer.save(centro=self.request.user.centro)
        registrar("ALTA", "sede", sede.pk, {"nombre": sede.nombre})
