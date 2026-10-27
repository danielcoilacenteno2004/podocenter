"""API de la agenda (RF06, RF08)."""
from datetime import date

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Cita
from .serializers import CancelacionSerializer, CitaSerializer
from .servicios import agenda_del_dia, cancelar_cita, programar_cita


class CitaViewSet(ContextoDeCentro, viewsets.ModelViewSet):
    serializer_class = CitaSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["estado", "sede", "profesional", "paciente"]

    def get_queryset(self):
        return Cita.objects.filter(centro_id=self.request.centro_id).select_related(
            "paciente", "profesional", "servicio", "sede"
        )

    def perform_create(self, serializer):
        datos = serializer.validated_data
        serializer.instance = programar_cita(
            centro=self.request.user.centro,
            usuario=self.request.user,
            sede=datos["sede"],
            paciente=datos["paciente"],
            profesional=datos["profesional"],
            servicio=datos["servicio"],
            inicio=datos["inicio"],
            observaciones=datos.get("observaciones", ""),
        )

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        formulario = CancelacionSerializer(data=request.data)
        formulario.is_valid(raise_exception=True)
        cita = cancelar_cita(cita=self.get_object(), motivo=formulario.validated_data["motivo"])
        respuesta = {"cita": self.get_serializer(cita).data}
        if formulario.validated_data["crear_reemplazo"]:
            # CC-16: la pantalla P07 ofrece crear la cita de reemplazo con los
            # mismos datos; el servidor devuelve la plantilla ya preparada.
            respuesta["plantilla_reemplazo"] = {
                "paciente": cita.paciente_id,
                "profesional": cita.profesional_id,
                "servicio": cita.servicio_id,
                "sede": cita.sede_id,
            }
        return Response(respuesta)

    @action(detail=False, methods=["get"])
    def agenda(self, request):
        fecha = request.query_params.get("fecha")
        fecha = date.fromisoformat(fecha) if fecha else date.today()
        sede_id = request.sede_id or request.query_params.get("sede")
        citas = agenda_del_dia(centro_id=request.centro_id, sede_id=sede_id, fecha=fecha)
        return Response({"fecha": fecha, "citas": self.get_serializer(citas, many=True).data})
