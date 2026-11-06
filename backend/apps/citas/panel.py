"""Panel del día segmentado (pantalla P04).

La Práctica N.° 7 observó que un panel con indicadores sueltos no dice
nada: hay que separarlo por lo que la dueña del centro decide con cada
cosa. De ahí los cuatro segmentos de esta respuesta.

  · Citas      — cómo va la jornada y qué viene ahora.
  · Ingresos   — cuánto se espera facturar y cuánto ya está confirmado.
  · Ocupación  — cuánto de la jornada está vendido; es lo que decide si
                 conviene abrir más cupos o cerrar antes.

El cuarto segmento del diseño, Inventario, no se construye en esta fase: el
recorte CC-12 lo dejó fuera y la entrega por etapas lo movió a la segunda
entrega. Queda dibujado como diferido en el wireframe de la Práctica N.° 7,
que es donde corresponde dejar constancia de una decisión de alcance; el
panel en funcionamiento no muestra un recuadro vacío.

El panel vive en este módulo y no en `core` porque todo lo que calcula sale
de la agenda; `core` es la capa base y no debe depender de los módulos.
"""
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count, F, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errores import ReglaDeNegocio
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.sedes.models import Sede
from apps.usuarios.roles import Rol

from .models import Cita

# Estados que cuentan como ingreso esperado: la cita sigue en pie.
EN_PIE = (Cita.Estado.PROGRAMADA, Cita.Estado.ATENDIDA)


def _soles(valor) -> str:
    return f"{(valor or Decimal('0')).quantize(Decimal('0.01'))}"


class PanelDelDia(ContextoDeCentro, APIView):
    """Indicadores de la jornada, agrupados por decisión (CU04)."""

    permission_classes = [TieneRol]
    roles_permitidos = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}

    def get(self, request):
        parametro = request.query_params.get("fecha")
        try:
            fecha = date.fromisoformat(parametro) if parametro else date.today()
        except ValueError as error:
            raise ReglaDeNegocio(
                "fecha-invalida", "La fecha debe tener el formato AAAA-MM-DD."
            ) from error

        sede_id = request.sede_id or request.query_params.get("sede")
        if not sede_id:
            raise ReglaDeNegocio(
                "sede-no-elegida", "Elija una sede para ver el panel del día."
            )

        citas = list(
            Cita.objects.filter(
                centro_id=request.centro_id,
                sede_id=sede_id,
                inicio__date=fecha,
            )
            .select_related("servicio", "paciente", "profesional")
            .order_by("inicio")
        )
        sede = Sede.objects.filter(pk=sede_id).first()

        return Response({
            "fecha": fecha,
            "sede": {"id": sede.pk, "nombre": sede.nombre} if sede else None,
            "citas": self._segmento_citas(citas),
            "ingresos": self._segmento_ingresos(request.centro_id, sede_id, fecha),
            "ocupacion": self._segmento_ocupacion(citas, sede, fecha),
        })

    # ------------------------------------------------------------- segmentos
    def _segmento_citas(self, citas):
        por_estado = {estado: 0 for estado in Cita.Estado.values}
        for cita in citas:
            por_estado[cita.estado] += 1

        ahora = datetime.now().astimezone()
        siguiente = next(
            (c for c in citas if c.estado == Cita.Estado.PROGRAMADA and c.inicio >= ahora),
            None,
        )
        return {
            "titulo": "Citas",
            "disponible": True,
            "total": len(citas),
            "por_estado": [
                {"estado": estado, "etiqueta": Cita.Estado(estado).label,
                 "cantidad": cantidad}
                for estado, cantidad in por_estado.items()
            ],
            "proxima": {
                "cita_id": siguiente.pk,
                "hora": siguiente.inicio,
                "paciente": siguiente.paciente.nombre_completo,
                "servicio": siguiente.servicio.nombre,
                "profesional": siguiente.profesional.nombre_completo,
            } if siguiente else None,
            "pendientes": por_estado[Cita.Estado.PROGRAMADA],
        }

    def _segmento_ingresos(self, centro_id, sede_id, fecha):
        """Se calcula en la base para no traer la jornada entera a memoria."""
        base = Cita.objects.filter(
            centro_id=centro_id, sede_id=sede_id, inicio__date=fecha
        )
        esperado = base.filter(estado__in=EN_PIE).aggregate(
            total=Sum("servicio__precio")
        )["total"]
        confirmado = base.filter(estado=Cita.Estado.ATENDIDA).aggregate(
            total=Sum("servicio__precio")
        )["total"]
        perdido = base.filter(
            estado__in=(Cita.Estado.CANCELADA, Cita.Estado.NO_ASISTIO)
        ).aggregate(total=Sum("servicio__precio"))["total"]

        en_pie = base.filter(estado__in=EN_PIE).count()
        por_servicio = (
            base.filter(estado__in=EN_PIE)
            .values("servicio_id", nombre=F("servicio__nombre"))
            .annotate(citas=Count("id"), monto=Sum("servicio__precio"))
            .order_by("-monto")
        )
        return {
            "titulo": "Ingresos",
            "disponible": True,
            "moneda": "PEN",
            "esperado": _soles(esperado),
            "confirmado": _soles(confirmado),
            "perdido": _soles(perdido),
            "ticket_promedio": _soles(
                (esperado / en_pie) if en_pie and esperado else Decimal("0")
            ),
            "por_servicio": [
                {"servicio_id": fila["servicio_id"], "servicio": fila["nombre"],
                 "citas": fila["citas"], "monto": _soles(fila["monto"])}
                for fila in por_servicio
            ],
            "nota": (
                "El ingreso confirmado corresponde a las citas ya atendidas. "
                "El cobro efectivo se registra en el módulo de la segunda entrega."
            ),
        }

    def _segmento_ocupacion(self, citas, sede, fecha):
        horario = sede.horario_de(fecha.weekday()) if sede else None
        if horario is None:
            return {
                "titulo": "Ocupación",
                "disponible": False,
                "estado": "sede-cerrada",
                "detalle": "La sede no atiende ese día.",
            }
        apertura = datetime.combine(fecha, horario.hora_apertura)
        cierre = datetime.combine(fecha, horario.hora_cierre)
        disponibles = int((cierre - apertura).total_seconds() // 60)
        agendados = sum(
            int((c.fin - c.inicio).total_seconds() // 60)
            for c in citas if c.estado in EN_PIE
        )
        return {
            "titulo": "Ocupación",
            "disponible": True,
            "minutos_agendados": agendados,
            "minutos_disponibles": disponibles,
            "porcentaje": round(agendados * 100 / disponibles, 1) if disponibles else 0.0,
            "horario": f"{horario.hora_apertura:%H:%M} a {horario.hora_cierre:%H:%M}",
            "libres": max(disponibles - agendados, 0),
        }
