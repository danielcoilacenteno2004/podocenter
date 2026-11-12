"""Reglas de aplicación de las sedes (RF03, CU02, CC-15).

Las vistas no escriben la sede ni su horario directamente: pasan por aquí,
que es donde se comprueba el nombre repetido y la forma del horario y donde
queda la auditoría.
"""
from django.db import IntegrityError, transaction

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio

from .models import HorarioSede, Sede

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _nombre_libre(centro_id: int, nombre: str, excepto=None) -> None:
    repetida = Sede.objects.filter(centro_id=centro_id, nombre__iexact=nombre.strip())
    if excepto is not None:
        repetida = repetida.exclude(pk=excepto)
    if repetida.exists():
        raise ReglaDeNegocio("sede-duplicada", "Ya existe una sede con ese nombre.")


def _validar_horario(dias: list[dict]) -> None:
    vistos = set()
    for dia in dias:
        numero = dia["dia_semana"]
        if numero in vistos:
            raise ReglaDeNegocio("dia-repetido", f"El {DIAS[numero]} aparece dos veces.")
        vistos.add(numero)
        if dia["hora_cierre"] <= dia["hora_apertura"]:
            raise ReglaDeNegocio(
                "horario-invalido",
                f"El {DIAS[numero]}, la hora de cierre debe ser posterior a la de apertura.",
            )


def _guardar_horario(sede: Sede, dias: list[dict]) -> None:
    """Reemplaza la semana completa. Un día que no viene queda cerrado, que
    es como la agenda ya entiende la ausencia de horario (`Sede.horario_de`)."""
    _validar_horario(dias)
    sede.horarios.all().delete()
    HorarioSede.objects.bulk_create([
        HorarioSede(sede=sede, dia_semana=d["dia_semana"], hora_apertura=d["hora_apertura"],
                    hora_cierre=d["hora_cierre"])
        for d in sorted(dias, key=lambda d: d["dia_semana"])
    ])


def _horario_para_bitacora(dias: list[dict]) -> dict:
    return {DIAS[d["dia_semana"]]: f"{d['hora_apertura']:%H:%M}-{d['hora_cierre']:%H:%M}"
            for d in sorted(dias, key=lambda d: d["dia_semana"])}


def _guardar(sede: Sede) -> None:
    """El nombre se comprobó antes; si otra petición lo tomó entre medias,
    la restricción única de la base responde y se traduce igual."""
    try:
        with transaction.atomic():
            sede.save()
    except IntegrityError as error:
        if "uq_sede_centro_nombre" in str(error):
            raise ReglaDeNegocio("sede-duplicada", "Ya existe una sede con ese nombre.") from error
        raise


@transaction.atomic
def crear_sede(*, centro, datos: dict, horario: list[dict] | None = None) -> Sede:
    """Alta de sede (P28), con su horario en la misma transacción.

    Sin horario la sede existe, pero la agenda la trata como cerrada.
    """
    _nombre_libre(centro.pk, datos["nombre"])
    sede = Sede(centro=centro, **datos)
    _guardar(sede)
    if horario is not None:
        _guardar_horario(sede, horario)
    registrar("ALTA", "sede", sede.pk, {
        "nombre": sede.nombre,
        **({"horario": _horario_para_bitacora(horario)} if horario is not None else {}),
    })
    return sede


@transaction.atomic
def actualizar_sede(sede: Sede, *, datos: dict, horario: list[dict] | None = None) -> Sede:
    """Edición de sede (P28). La baja es `esta_activa = False`: una sede no se
    borra, porque sus citas, atenciones y stock siguen siendo historia.

    Cambiar el horario no toca las citas ya programadas: siguen en pie y la
    administradora decide qué hacer con las que queden fuera.
    """
    if "nombre" in datos:
        _nombre_libre(sede.centro_id, datos["nombre"], excepto=sede.pk)
    for campo, valor in datos.items():
        setattr(sede, campo, valor)
    _guardar(sede)
    if horario is not None:
        _guardar_horario(sede, horario)
    cambios = {campo: str(valor) for campo, valor in datos.items()}
    if horario is not None:
        cambios["horario"] = _horario_para_bitacora(horario)
    registrar("EDICION", "sede", sede.pk, cambios)
    return sede
