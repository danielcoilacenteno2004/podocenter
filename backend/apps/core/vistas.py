"""Piezas comunes a las vistas de la API."""
from .contexto_http import aplicar_contexto
from .errores import ReglaDeNegocio


class ContextoDeCentro:
    """Vuelve a fijar el contexto una vez que DRF ya autenticó al usuario.

    Toda vista que lea o escriba datos de un centro hereda de esta clase.
    Sin ella, `request.centro_id` queda en None y las consultas no
    devuelven nada, porque el middleware corre antes de la autenticación
    de DRF.
    """

    # Las pocas vistas que una cuenta con contraseña temporal sí puede usar.
    permite_contrasena_pendiente = False
    # Las pocas que puede usar un rol administrativo sin segundo factor: las
    # del alta del factor, el cambio de contraseña y sus propias sedes.
    permite_segundo_factor_pendiente = False

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        aplicar_contexto(request)
        # Una contraseña temporal la conoce también quien la entregó: hasta
        # que el titular la cambie, la cuenta no lee ni escribe datos.
        usuario = request.user
        if (getattr(usuario, "debe_cambiar_contrasena", False)
                and not self.permite_contrasena_pendiente):
            raise ReglaDeNegocio(
                "cambio-de-contrasena-pendiente",
                "Cambie la contraseña temporal antes de continuar.",
            )
        # RF18: el segundo factor es obligatorio para los roles administrativos.
        # Mientras no lo den de alta, la sesión solo sirve para darlo de alta.
        if (getattr(usuario, "requiere_segundo_factor", False)
                and not usuario.segundo_factor_activo
                and not self.permite_segundo_factor_pendiente):
            raise ReglaDeNegocio(
                "segundo-factor-pendiente",
                "Active la verificación en dos pasos antes de continuar.",
            )
