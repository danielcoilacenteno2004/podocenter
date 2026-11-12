"""API de la agenda (RF06, RF08)."""
from datetime import date

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.errores import ReglaDeNegocio
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.usuarios.roles import Rol

from .models import Cita
from .serializers import CancelacionSerializer, CitaSerializer
from .servicios import (
    agenda_del_dia,
    cancelar_cita,
    con_datos_de_recordatorio,
    con_marca_de_atencion,
    horario_de_la_jornada,
    programar_cita,
)


def _entero(valor):
    """Convierte un parámetro de consulta a entero; ignora lo que no lo sea."""
    try:
        return int(valor) if valor else None
    except (TypeError, ValueError):
        return None


class CitaViewSet(ContextoDeCentro, mixins.CreateModelMixin, mixins.ListModelMixin,
                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Agenda: crear, consultar y cancelar.

    No hay PUT, PATCH ni DELETE. Escribían en el modelo sin pasar por
    `servicios.py`, de modo que por ahí se podía solapar una cita o sacarla
    del horario de la sede. Una cita no se borra, se cancela con motivo
    (`cancelar`); y reprogramarla quedó fuera por el recorte CC-12.
    """

    serializer_class = CitaSerializer
    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
    filterset_fields = ["estado", "sede", "profesional", "paciente"]

    def get_queryset(self):
        return con_datos_de_recordatorio(con_marca_de_atencion(
            Cita.objects.filter(centro_id=self.request.centro_id).select_related(
                "paciente", "profesional", "servicio", "sede"
            )
        ))

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
        """P05 — jornada de una sede, con los filtros opcionales de la P7."""
        parametros = request.query_params
        try:
            fecha = date.fromisoformat(parametros["fecha"]) if parametros.get("fecha") \
                else date.today()
        except ValueError as error:
            raise ReglaDeNegocio(
                "fecha-invalida", "La fecha debe tener el formato AAAA-MM-DD."
            ) from error

        estado = parametros.get("estado") or None
        if estado and estado not in Cita.Estado.values:
            raise ReglaDeNegocio("estado-desconocido", "Ese estado de cita no existe.")

        sede_id = request.sede_id or parametros.get("sede")
        citas = agenda_del_dia(
            centro_id=request.centro_id,
            sede_id=sede_id,
            fecha=fecha,
            estado=estado,
            profesional_id=_entero(parametros.get("profesional")),
            servicio_id=_entero(parametros.get("servicio")),
        )
        datos = self.get_serializer(citas, many=True).data
        return Response({
            "fecha": fecha,
            "horario": horario_de_la_jornada(
                centro_id=request.centro_id, sede_id=_entero(sede_id), fecha=fecha
            ),
            "total": len(datos),
            "filtros_aplicados": {
                clave: parametros[clave]
                for clave in ("estado", "profesional", "servicio")
                if parametros.get(clave)
            },
            "citas": datos,
        })
