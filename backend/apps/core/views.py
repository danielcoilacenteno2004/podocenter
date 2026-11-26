"""Vistas transversales: estado del servicio y centros clientes (RF17)."""
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Centro
from .permisos import EsAdministradorDePlataforma
from .serializers import AltaDeCentroSerializer, CentroSerializer
from .servicios import crear_centro, registrar_cambio_de_centro
from .vistas import ContextoDeCentro


class EstadoDelServicio(APIView):
    """Sonda que usan el balanceador y el pipeline de despliegue."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"estado": "operativo", "version": "0.4.0"})


class CentroViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """RF17 — alta y mantenimiento de los centros clientes (P19 y P29).

    No hay DELETE: un centro cliente no se borra, se suspende con motivo; y
    borrar uno con datos fallaba con un 500. Hereda `ContextoDeCentro` por sus
    dos cerrojos de cuenta (contraseña temporal y segundo factor), que valen
    también para la plataforma; el centro queda vacío, como antes.
    """

    queryset = Centro.objects.all()
    permission_classes = [EsAdministradorDePlataforma]
    filterset_fields = ["estado"]

    def get_serializer_class(self):
        return AltaDeCentroSerializer if self.action == "create" else CentroSerializer

    def create(self, request, *args, **kwargs):
        entrada = AltaDeCentroSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        administrador = datos.pop("administrador")
        centro, admin, temporal = crear_centro(datos=datos, administrador=administrador,
                                               usuario=request.user)
        respuesta = dict(CentroSerializer(centro).data)
        respuesta["administrador"] = {
            "id": admin.pk, "correo": admin.correo, "nombre_completo": admin.nombre_completo,
        }
        # Única vez que sale: no se guarda en claro ni se puede volver a pedir.
        respuesta["contrasena_temporal"] = temporal
        return Response(respuesta, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        centro = serializer.save()
        registrar_cambio_de_centro(centro, self.request.user, {
            "estado": centro.estado, "motivo_suspension": centro.motivo_suspension,
        })
