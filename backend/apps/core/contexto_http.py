"""Resolución del centro y la sede activa a partir de la petición.

Se aisló en este módulo porque hace falta en dos momentos distintos del
ciclo de la petición: en el middleware, para las vistas de Django, y en
`initial()` de las vistas de DRF, porque DRF autentica después de que ha
corrido todo el middleware. Antes vivía solo en el middleware y las
vistas de la API se quedaban sin centro (hallazgo del sprint 2).
"""
import logging

from django.db import connection

from .contexto import fijar_contexto

logger = logging.getLogger(__name__)


def sede_solicitada(request, usuario) -> int | None:
    """Sede pedida en la cabecera X-Sede, solo si el usuario la tiene asignada."""
    cabecera = request.headers.get("X-Sede")
    if not cabecera or not getattr(usuario, "is_authenticated", False):
        return None
    try:
        sede_id = int(cabecera)
    except ValueError:
        logger.warning("Cabecera X-Sede no numérica: %r", cabecera)
        return None
    return sede_id if usuario.puede_usar_sede(sede_id) else None


def fijar_centro_en_la_sesion(centro_id: int) -> None:
    """Deja el centro en la sesión de PostgreSQL para que actúe el RLS."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.centro_id', %s, false)", [str(centro_id)])


def aplicar_contexto(request) -> None:
    """Fija centro, sede y usuario en el contexto y en la sesión de la base."""
    usuario = getattr(request, "user", None)
    autenticado = getattr(usuario, "is_authenticated", False)
    centro_id = getattr(usuario, "centro_id", None) if autenticado else None
    sede_id = sede_solicitada(request, usuario)
    fijar_contexto(centro_id=centro_id, sede_id=sede_id,
                   usuario_id=getattr(usuario, "pk", None) if autenticado else None)
    if centro_id is not None:
        fijar_centro_en_la_sesion(centro_id)
    request.centro_id = centro_id
    request.sede_id = sede_id
