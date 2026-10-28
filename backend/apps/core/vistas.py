"""Piezas comunes a las vistas de la API."""
from .contexto_http import aplicar_contexto


class ContextoDeCentro:
    """Vuelve a fijar el contexto una vez que DRF ya autenticó al usuario.

    Toda vista que lea o escriba datos de un centro hereda de esta clase.
    Sin ella, `request.centro_id` queda en None y las consultas no
    devuelven nada, porque el middleware corre antes de la autenticación
    de DRF.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        aplicar_contexto(request)
