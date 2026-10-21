"""API del módulo Usuarios y roles (RF01) y de la sesión (RF02)."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.auditoria import registrar
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro

from .models import Usuario
from .roles import Rol
from .serializers import SedeAsignadaSerializer, UsuarioSerializer
from .servicios import crear_usuario, desactivar_usuario, sedes_disponibles


class UsuarioViewSet(ContextoDeCentro, viewsets.ModelViewSet):
    """CU01 — mantenimiento de usuarios del centro."""

    serializer_class = UsuarioSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO}
    filterset_fields = ["rol", "esta_activo"]
    search_fields = ["nombres", "apellidos", "correo"]

    def get_queryset(self):
        return (
            Usuario.objects.filter(centro_id=self.request.centro_id)
            .prefetch_related("asignaciones__sede")
            .order_by("apellidos", "nombres")
        )

    def perform_create(self, serializer):
        datos = serializer.validated_data
        usuario = crear_usuario(
            centro=self.request.user.centro,
            correo=datos["correo"],
            nombres=datos["nombres"],
            apellidos=datos["apellidos"],
            rol=datos["rol"],
            sedes_ids=datos.get("sedes_ids", []),
        )
        serializer.instance = usuario

    def perform_destroy(self, instance):
        desactivar_usuario(instance)

    @action(detail=True, methods=["post"])
    def reactivar(self, request, pk=None):
        usuario = self.get_object()
        usuario.esta_activo = True
        usuario.save(update_fields=["esta_activo", "actualizado_en"])
        registrar("EDICION", "usuario", usuario.pk, {"reactivado": True})
        return Response(self.get_serializer(usuario).data, status=status.HTTP_200_OK)


class SedesDeLaSesion(ContextoDeCentro, APIView):
    """Sedes entre las que el usuario elige al entrar (pantalla P03)."""

    def get(self, request):
        datos = SedeAsignadaSerializer(sedes_disponibles(request.user), many=True).data
        return Response({"sedes": datos, "requiere_eleccion": len(datos) > 1})
