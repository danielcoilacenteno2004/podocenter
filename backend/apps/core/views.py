"""Vistas transversales: estado del servicio y centros clientes (RF17)."""
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Centro
from .permisos import EsAdministradorDePlataforma
from .serializers import CentroSerializer


class EstadoDelServicio(APIView):
    """Sonda que usan el balanceador y el pipeline de despliegue."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"estado": "operativo", "version": "0.4.0"})


class CentroViewSet(viewsets.ModelViewSet):
    """RF17 — alta y mantenimiento de los centros clientes."""

    queryset = Centro.objects.all()
    serializer_class = CentroSerializer
    permission_classes = [EsAdministradorDePlataforma]
    filterset_fields = ["estado"]
