"""Punto único de escritura de la bitácora de auditoría."""
import logging

from .contexto import contexto_actual
from .models import RegistroAuditoria

logger = logging.getLogger(__name__)


def registrar(accion: str, entidad: str, entidad_id="", datos=None, ip=None) -> None:
    """Deja constancia de una acción sobre datos sensibles.

    No interrumpe nunca la operación del usuario: si la auditoría falla, se
    anota en el log del servidor y la petición continúa.
    """
    contexto = contexto_actual()
    if contexto.centro_id is None:
        logger.warning("Auditoría sin centro en contexto: %s %s", accion, entidad)
        return
    try:
        RegistroAuditoria.objects.create(
            centro_id=contexto.centro_id,
            usuario_id=contexto.usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id),
            datos=datos or {},
            direccion_ip=ip,
        )
    except Exception:  # noqa: BLE001 - la auditoría nunca tumba la petición
        logger.exception("No se pudo escribir la auditoría de %s %s", accion, entidad)
