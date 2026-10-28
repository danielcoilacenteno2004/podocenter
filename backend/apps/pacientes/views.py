"""API del módulo Pacientes (RF04, RF05)."""
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Paciente
from .serializers import PacienteSerializer
from .servicios import ficha_con_auditoria, registrar_paciente, revocar_consentimiento


class PacienteViewSet(ContextoDeCentro, viewsets.ModelViewSet):
    """CU06 y CU07 — búsqueda, alta y ficha del paciente."""

    serializer_class = PacienteSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["esta_activo", "tipo_documento"]

    def get_queryset(self):
        consulta = Paciente.objects.filter(centro_id=self.request.centro_id)
        texto = self.request.query_params.get("buscar")
        if texto:
            consulta = consulta.filter(
                Q(nombres__icontains=texto)
                | Q(apellidos__icontains=texto)
                | Q(documento__startswith=texto)
            )
        return consulta.prefetch_related("consentimientos")

    def perform_create(self, serializer):
        datos = dict(serializer.validated_data)
        consentimiento = datos.pop("consentimiento", {})
        serializer.instance = registrar_paciente(
            centro=self.request.user.centro,
            usuario=self.request.user,
            datos=datos,
            consentimiento=consentimiento,
        )

    def retrieve(self, request, *args, **kwargs):
        paciente = ficha_con_auditoria(self.get_object())
        return Response(self.get_serializer(paciente).data)

    @action(detail=True, methods=["post"], url_path="revocar-consentimiento")
    def revocar(self, request, pk=None):
        revocar_consentimiento(self.get_object())
        return Response({"revocado": True})
