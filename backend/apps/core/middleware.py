"""Fija el centro y la sede activa de cada petición de Django.

El centro no se acepta nunca desde la petición: se toma del usuario
autenticado. Las vistas de DRF repiten la operación en `initial()` con
`ContextoDeCentro`, porque su autenticación ocurre después del middleware.
"""
from .contexto import limpiar_contexto
from .contexto_http import aplicar_contexto


class ContextoTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        aplicar_contexto(request)
        try:
            return self.get_response(request)
        finally:
            limpiar_contexto()
