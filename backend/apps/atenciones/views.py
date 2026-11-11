"""API de atenciones (RF10, CU10).

Solo se crea, se lista y se consulta. No hay edición ni borrado: la
atención es un hecho clínico ya ocurrido.
"""
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Atencion
from .serializers import AtencionResumenSerializer, AtencionSerializer
from .servicios import atencion_con_auditoria, registrar_atencion


class AtencionViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["sede", "paciente", "profesional"]

    def get_queryset(self):
        return Atencion.objects.filter(centro_id=self.request.centro_id).select_related(
            "paciente", "profesional", "servicio"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return AtencionResumenSerializer
        return AtencionSerializer

    def perform_create(self, serializer):
        datos = serializer.validated_data
        serializer.instance = registrar_atencion(
            centro=self.request.user.centro,
            usuario=self.request.user,
            sede_id=self.request.sede_id,
            cita_id=datos["cita_id"],
            observaciones_clinicas=datos.get("observaciones_clinicas", ""),
        )

    def retrieve(self, request, *args, **kwargs):
        atencion = atencion_con_auditoria(self.get_object())
        return Response(self.get_serializer(atencion).data)
