"""Traducción de las excepciones de la API al formato RFC 9457.

La Práctica N.° 7 definió un mensaje de usuario por cada error; este módulo
es el único lugar donde se construye la respuesta, para que las 29 pantallas
reciban siempre la misma forma.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class ReglaDeNegocio(Exception):
    """Error esperado de negocio; se traduce a 422 con un código estable."""

    def __init__(self, codigo: str, detalle: str):
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(detalle)


def manejador_de_errores(exc, context):
    if isinstance(exc, ReglaDeNegocio):
        return Response(
            {
                "type": f"https://podocenter.pe/errores/{exc.codigo}",
                "title": "La operación no cumple una regla del negocio",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "detail": exc.detalle,
                "codigo": exc.codigo,
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content_type="application/problem+json",
        )
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        return None
    respuesta.data = {
        "type": "https://podocenter.pe/errores/generico",
        "title": respuesta.status_text,
        "status": respuesta.status_code,
        "detail": respuesta.data,
    }
    respuesta.content_type = "application/problem+json"
    return respuesta
