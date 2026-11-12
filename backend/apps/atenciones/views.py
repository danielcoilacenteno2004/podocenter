"""API de atenciones (RF10, CU10).

Solo se crea, se lista y se consulta. No hay edición ni borrado: la
atención es un hecho clínico ya ocurrido.
"""
from datetime import date

from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errores import ReglaDeNegocio
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Atencion
from .serializers import AtencionResumenSerializer, AtencionSerializer
from .servicios import atencion_con_auditoria, registrar_atencion, registro_del_dia


class AtencionViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["sede", "paciente", "profesional"]

    def get_queryset(self):
        return Atencion.objects.filter(centro_id=self.request.centro_id).select_related(
            "sede", "paciente", "profesional", "servicio"
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
            monto_cobrado=datos["monto_cobrado"],
            observaciones_clinicas=datos.get("observaciones_clinicas", ""),
            insumos=datos.get("insumos", []),
        )

    def retrieve(self, request, *args, **kwargs):
        atencion = atencion_con_auditoria(self.get_object())
        return Response(self.get_serializer(atencion).data)


class RegistroDiario(ContextoDeCentro, APIView):
    """P16 — atenciones e ingresos del día en la sede activa.

    GET /api/v1/reportes/registro-diario/?fecha=AAAA-MM-DD, la ruta que
    declara el Informe (Tabla 38). Sin fecha, el día de hoy.
    """

    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}

    def get(self, request):
        if request.sede_id is None:
            raise ReglaDeNegocio(
                "sin-sede-activa", "Elija la sede de la que quiere ver el registro."
            )
        texto = request.query_params.get("fecha")
        try:
            fecha = date.fromisoformat(texto) if texto else date.today()
        except ValueError as error:
            raise ReglaDeNegocio(
                "fecha-invalida", "La fecha debe tener el formato AAAA-MM-DD."
            ) from error
        registro = registro_del_dia(centro_id=request.centro_id, sede_id=request.sede_id,
                                    fecha=fecha)
        filas = AtencionResumenSerializer(registro["atenciones"], many=True).data
        return Response({
            "fecha": fecha,
            "atenciones": filas,
            "cantidad": len(filas),
            "total": f"{registro['total']:.2f}",
            "sin_monto": registro["sin_monto"],
        })

