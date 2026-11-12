"""API del catálogo de servicios (RF09, CU17)."""
from rest_framework import mixins, viewsets

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Servicio
from .serializers import ServicioSerializer
from .servicios import actualizar_servicio, crear_servicio


class ServicioViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                      viewsets.GenericViewSet):
    """Catálogo de servicios.

    No hay DELETE: un servicio con citas o atenciones no se puede borrar sin
    perder historia (respondía 500); la baja es desmarcar `esta_activo`.
    """

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
        serializer.instance = crear_servicio(centro=self.request.user.centro,
                                             datos=dict(serializer.validated_data))

    def perform_update(self, serializer):
        serializer.instance = actualizar_servicio(serializer.instance,
                                                  datos=dict(serializer.validated_data))
