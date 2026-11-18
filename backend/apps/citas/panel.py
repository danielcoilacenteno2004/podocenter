"""Panel del día segmentado (pantalla P04).

La Práctica N.° 7 observó que un panel con indicadores sueltos no dice
nada: hay que separarlo por lo que la dueña del centro decide con cada
cosa. De ahí los segmentos de esta respuesta.

  · Citas      — qué viene en la jornada y qué citas ya pasaron de hora
                 sin registrar su atención.
  · Ingresos   — cuánto se espera facturar y cuánto ya está cobrado.
  · Ocupación  — cuánto de la capacidad de la sede (sus profesionales por
                 su horario) está vendido, hoy y los siete días siguientes;
                 es lo que decide si conviene abrir más cupos o cerrar antes.

Cada segmento trae además su referencia: el promedio de los mismos días de
la semana anteriores en que la sede abrió. Sin ella, «3 citas» o «S/ 270»
no dicen si el día va bien o mal. Todo sale en una sola respuesta, como
pide la Tabla 7 de la Práctica N.° 7 para el selector de día.

El cuarto segmento del diseño, Inventario, no se construye en esta fase: el
recorte CC-12 lo dejó fuera y la entrega por etapas lo movió a la segunda
entrega. Queda dibujado como diferido en el wireframe de la Práctica N.° 7,
que es donde corresponde dejar constancia de una decisión de alcance; el
panel en funcionamiento no muestra un recuadro vacío.

El panel vive en este módulo y no en `core` porque todo lo que calcula sale
de la agenda; `core` es la capa base y no debe depender de los módulos.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.atenciones.servicios import registro_del_dia
from apps.core.errores import ReglaDeNegocio
from apps.core.permisos import TieneRol
from apps.core.vistas import ContextoDeCentro
from apps.sedes.models import Sede
from apps.usuarios.roles import Rol
from apps.usuarios.servicios import profesionales_de_la_sede

from .models import Cita

# Estados que ocupan agenda: la cita sigue en pie.
EN_PIE = (Cita.Estado.PROGRAMADA, Cita.Estado.ATENDIDA)
# Estados cuyo ingreso ya no llegará.
NO_CONCRETADOS = (Cita.Estado.CANCELADA, Cita.Estado.NO_ASISTIO)
# Cuántas de las citas que vienen devuelve el panel, además de las que están
# en curso: lo de la próxima hora o dos. El día completo está en la agenda.
SIGUIENTES = 5
# Días con que se compara la jornada: el mismo día de la semana, en las
# semanas anteriores. Uno solo es demasiado ruidoso; cuatro son un mes.
SEMANAS_DE_REFERENCIA = 4
# Días siguientes cuya ocupación se anticipa.
DIAS_POR_DELANTE = 7


def _soles(valor) -> str:
    return f"{(valor or Decimal('0')).quantize(Decimal('0.01'))}"


def _minutos(cita) -> int:
    return int((cita.fin - cita.inicio).total_seconds() // 60)


def _promedio(valores):
    valores = list(valores)
    return sum(valores) / len(valores) if valores else None


def _promedio_redondeado(valores):
    """Con un decimal, como el resto de las cifras de conteo y porcentaje."""
    media = _promedio(valores)
    return round(media, 1) if media is not None else None


def _cita_breve(cita) -> dict:
    """Lo que el panel muestra de una cita: la identifica para enlazarla."""
    return {
        "cita_id": cita.pk,
        "inicio": cita.inicio,
        "paciente_id": cita.paciente_id,
        "paciente": cita.paciente.nombre_completo,
        "servicio": cita.servicio.nombre,
        "profesional": cita.profesional.nombre_completo,
    }


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

        centro_id = request.centro_id
        sede = Sede.objects.filter(pk=sede_id).first()
        anteriores = [fecha - timedelta(weeks=n) for n in range(1, SEMANAS_DE_REFERENCIA + 1)]
        siguientes = [fecha + timedelta(days=n) for n in range(1, DIAS_POR_DELANTE + 1)]
        citas_de = self._citas_por_dia(centro_id, sede_id, [fecha, *anteriores, *siguientes])
        # Las mismas personas que la agenda muestra como columnas; se cargan
        # una vez para todos los días que se miden.
        plantel = {
            p.pk: p.nombre_completo
            for p in profesionales_de_la_sede(centro_id=centro_id, sede_id=sede_id)
        }

        def ingresos(dia):
            return self._segmento_ingresos(citas_de[dia], centro_id, sede_id, dia)

        def ocupacion(dia):
            return self._segmento_ocupacion(citas_de[dia], plantel, sede, dia)

        citas = self._segmento_citas(citas_de[fecha])
        ingresos_del_dia = ingresos(fecha)
        ocupacion_del_dia = ocupacion(fecha)

        # La referencia se mide con las mismas funciones que el día, para que
        # las dos cifras signifiquen lo mismo. Los días en que la sede no abrió
        # (un feriado, por ejemplo) se descartan: promediarlos como cero
        # hundiría la referencia.
        abiertos = [dia for dia in anteriores if sede and sede.horario_de(dia.weekday())]
        ocupaciones = [o for o in map(ocupacion, abiertos) if o["disponible"]]
        citas["referencia"] = {
            "dias": len(abiertos),
            "total": _promedio_redondeado(len(citas_de[dia]) for dia in abiertos),
        }
        # Lo esperado se compara en los días que vienen y lo cobrado en los que
        # ya pasaron; se devuelven los dos para que cada cifra tenga su par.
        ingresos_anteriores = [ingresos(dia) for dia in abiertos]
        referencia = {"dias": len(abiertos)}
        for clave in ("esperado", "confirmado"):
            media = _promedio(Decimal(i[clave]) for i in ingresos_anteriores)
            referencia[clave] = _soles(media) if media is not None else None
        ingresos_del_dia["referencia"] = referencia
        ocupacion_del_dia["referencia"] = {
            "dias": len(ocupaciones),
            "porcentaje": _promedio_redondeado(o["porcentaje"] for o in ocupaciones),
        }
        ocupacion_del_dia["proximos"] = [
            {"fecha": dia, "porcentaje": medida.get("porcentaje"), "abierta": medida["disponible"]}
            for dia, medida in ((dia, ocupacion(dia)) for dia in siguientes)
        ]

        return Response({
            "fecha": fecha,
            "sede": {"id": sede.pk, "nombre": sede.nombre} if sede else None,
            "citas": citas,
            "ingresos": ingresos_del_dia,
            "ocupacion": ocupacion_del_dia,
        })

    @staticmethod
    def _citas_por_dia(centro_id, sede_id, fechas):
        """Las citas de todas las fechas medidas, en una sola consulta."""
        por_dia = {dia: [] for dia in fechas}
        consulta = (
            Cita.objects.filter(centro_id=centro_id, sede_id=sede_id, inicio__date__in=fechas)
            .select_related("servicio", "paciente", "profesional", "reemplazo")
            .order_by("inicio")
        )
        for cita in consulta:
            por_dia.setdefault(timezone.localdate(cita.inicio), []).append(cita)
        return por_dia

    # ------------------------------------------------------------- segmentos
    def _segmento_citas(self, citas):
        por_estado = {estado: 0 for estado in Cita.Estado.values}
        for cita in citas:
            por_estado[cita.estado] += 1

        # Una cita programada cuya hora ya terminó no está «por atender»: se
        # atendió sin registrarlo o el paciente no vino. Se separa porque cada
        # una que falta deja mal el ingreso del día y sin descontar los
        # insumos del stock, y se devuelve una por una para poder actuar.
        # Las que vienen van en orden: todas las que están en curso y, detrás,
        # hasta SIGUIENTES de las que faltan empezar. La primera de estas es la
        # «próxima cita» que la Tabla 7 pide destacar.
        ahora = timezone.now()
        programadas = [c for c in citas if c.estado == Cita.Estado.PROGRAMADA]
        sin_registrar = [c for c in programadas if c.fin <= ahora]
        por_atender = [c for c in programadas if c.fin > ahora]
        en_curso = [c for c in por_atender if c.inicio <= ahora]
        despues = [c for c in por_atender if c.inicio > ahora][:SIGUIENTES]

        return {
            "titulo": "Citas",
            "disponible": True,
            "total": len(citas),
            "por_estado": [
                {"estado": estado, "etiqueta": Cita.Estado(estado).label,
                 "cantidad": cantidad}
                for estado, cantidad in por_estado.items()
            ],
            "por_atender": len(por_atender),
            "siguientes": [
                *({**_cita_breve(c), "momento": "en-curso"} for c in en_curso),
                *({**_cita_breve(c), "momento": "proxima" if i == 0 else "despues"}
                  for i, c in enumerate(despues)),
            ],
            "sin_registrar": [_cita_breve(c) for c in sin_registrar],
        }

    def _segmento_ingresos(self, citas, centro_id, sede_id, fecha):
        """Lo cobrado sale del mismo cálculo que el registro diario (P16).

        Así las dos pantallas dan la misma cifra por construcción: si el
        panel sumara precios de catálogo, un descuento las haría discrepar.
        Lo esperado es lo ya cobrado más el precio de las citas que faltan.
        """
        registro = registro_del_dia(centro_id=centro_id, sede_id=sede_id, fecha=fecha)
        cobradas = [a for a in registro["atenciones"] if a.monto_cobrado is not None]
        programadas = [c for c in citas if c.estado == Cita.Estado.PROGRAMADA]

        confirmado = registro["total"]
        esperado = confirmado + sum((c.servicio.precio for c in programadas), Decimal("0"))
        # Una cancelación con cita de reemplazo no es ingreso perdido: cambió
        # de día. Se cuenta en la fecha de su reemplazo, si llega a darse.
        perdido = sum(
            (c.servicio.precio for c in citas
             if c.estado in NO_CONCRETADOS and getattr(c, "reemplazo", None) is None),
            Decimal("0"),
        )
        cuantas = len(cobradas) + len(programadas)

        por_servicio = {}
        filas = [(a.servicio, a.monto_cobrado) for a in cobradas]
        filas += [(c.servicio, c.servicio.precio) for c in programadas]
        for servicio, monto in filas:
            fila = por_servicio.setdefault(servicio.pk, {
                "servicio_id": servicio.pk, "servicio": servicio.nombre,
                "citas": 0, "monto": Decimal("0"),
            })
            fila["citas"] += 1
            fila["monto"] += monto

        return {
            "titulo": "Ingresos",
            "disponible": True,
            "moneda": "PEN",
            "esperado": _soles(esperado),
            "confirmado": _soles(confirmado),
            "perdido": _soles(perdido),
            "ticket_promedio": _soles(esperado / cuantas if cuantas else Decimal("0")),
            "por_servicio": [
                {**fila, "monto": _soles(fila["monto"])}
                for fila in sorted(por_servicio.values(),
                                   key=lambda f: (-f["monto"], f["servicio"]))
            ],
            # Atenciones anteriores al campo monto_cobrado: no suman, como en P16.
            "sin_monto": registro["sin_monto"],
            "nota": (
                "Lo cobrado es la suma de las atenciones registradas en la sede, la "
                "misma cifra del registro diario; lo esperado le añade el precio de "
                "las citas que faltan."
            ),
        }

    def _segmento_ocupacion(self, citas, plantel_de_la_sede, sede, fecha):
        horario = sede.horario_de(fecha.weekday()) if sede else None
        if horario is None:
            return {
                "titulo": "Ocupación",
                "disponible": False,
                "estado": "sede-cerrada",
                "detalle": "La sede no atiende ese día.",
            }

        # La capacidad es la de cada profesional por el horario de la sede: con
        # dos profesionales, la sede vende el doble de minutos. Se cuenta a las
        # mismas personas que la agenda muestra como columnas: quien está
        # asignada a la sede y quien tiene citas ese día aunque ya no lo esté.
        # El sistema no guarda horarios por profesional; se supone que cada una
        # cubre la jornada completa.
        plantel = dict(plantel_de_la_sede)
        for cita in citas:
            plantel.setdefault(cita.profesional_id, cita.profesional.nombre_completo)
        if not plantel:
            return {
                "titulo": "Ocupación",
                "disponible": False,
                "estado": "sin-profesionales",
                "detalle": "No hay profesionales asignadas a la sede.",
            }

        apertura = datetime.combine(fecha, horario.hora_apertura)
        cierre = datetime.combine(fecha, horario.hora_cierre)
        jornada = int((cierre - apertura).total_seconds() // 60)

        agendado = dict.fromkeys(plantel, 0)
        for cita in citas:
            if cita.estado in EN_PIE:
                agendado[cita.profesional_id] += _minutos(cita)

        capacidad = jornada * len(plantel)
        total = sum(agendado.values())
        profesionales = sorted(
            ({"id": pk, "nombre": nombre,
              "minutos_agendados": agendado[pk],
              "porcentaje": round(agendado[pk] * 100 / jornada, 1) if jornada else 0.0,
              "libres": max(jornada - agendado[pk], 0)}
             for pk, nombre in plantel.items()),
            key=lambda p: p["nombre"],
        )
        return {
            "titulo": "Ocupación",
            "disponible": True,
            "minutos_agendados": total,
            "minutos_disponibles": capacidad,
            "minutos_jornada": jornada,
            "porcentaje": round(total * 100 / capacidad, 1) if capacidad else 0.0,
            "horario": f"{horario.hora_apertura:%H:%M} a {horario.hora_cierre:%H:%M}",
            "libres": sum(p["libres"] for p in profesionales),
            "profesionales": profesionales,
        }
