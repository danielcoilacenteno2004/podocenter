"""API del módulo Sedes (RF03, CU02)."""
from rest_framework import mixins, viewsets

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Sede
from .serializers import SedeSerializer
from .servicios import actualizar_sede, crear_sede


class SedeViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                  mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """Sedes del centro con su horario.

    No hay DELETE: una sede con citas, atenciones o stock no se puede borrar
    sin perder historia (respondía 500), y la baja es desmarcar `esta_activa`.
    """

    serializer_class = SedeSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO}
    filterset_fields = ["esta_activa"]

    def get_queryset(self):
        return Sede.objects.filter(centro_id=self.request.centro_id).prefetch_related("horarios")

    def perform_create(self, serializer):
        datos = dict(serializer.validated_data)
        horario = datos.pop("horario", None)
        serializer.instance = crear_sede(centro=self.request.user.centro, datos=datos,
                                         horario=horario)

    def perform_update(self, serializer):
        datos = dict(serializer.validated_data)
        horario = datos.pop("horario", None)
        serializer.instance = actualizar_sede(serializer.instance, datos=datos, horario=horario)
