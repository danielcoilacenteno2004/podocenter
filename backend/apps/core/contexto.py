"""Contexto de la petición en curso: centro y sede activa.

Se guarda en una variable de contexto en lugar de pasarlo por parámetro a
cada función, porque lo necesitan capas que no reciben el `request`
(señales, servicios y el conector de base de datos que fija el RLS).
"""
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = ["ContextoPeticion", "fijar_contexto", "contexto_actual", "limpiar_contexto"]


@dataclass(frozen=True)
class ContextoPeticion:
    centro_id: int | None = None
    sede_id: int | None = None
    usuario_id: int | None = None


_contexto: ContextVar[ContextoPeticion] = ContextVar(
    "contexto_peticion", default=ContextoPeticion()
)


def fijar_contexto(centro_id=None, sede_id=None, usuario_id=None) -> None:
    _contexto.set(ContextoPeticion(centro_id, sede_id, usuario_id))


def contexto_actual() -> ContextoPeticion:
    return _contexto.get()


def limpiar_contexto() -> None:
    _contexto.set(ContextoPeticion())
