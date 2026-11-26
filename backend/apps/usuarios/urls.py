from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .sesion import (
    AltaDeSegundoFactor,
    CambiarContrasena,
    CerrarSesion,
    ConfirmarSegundoFactor,
    EstadoDeSesion,
    IniciarSesion,
    VerificarSegundoFactor,
)
from .views import (
    ProfesionalesDeLaSede,
    ReiniciarSegundoFactor,
    SedesDeLaSesion,
    UsuarioViewSet,
)

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("sesion/actual/", EstadoDeSesion.as_view(), name="sesion-actual"),
    path("sesion/ingresar/", IniciarSesion.as_view(), name="sesion-ingresar"),
    path("sesion/segundo-factor/verificar/", VerificarSegundoFactor.as_view(),
         name="segundo-factor-verificar"),
    path("sesion/segundo-factor/alta/", AltaDeSegundoFactor.as_view(), name="segundo-factor-alta"),
    path("sesion/segundo-factor/confirmar/", ConfirmarSegundoFactor.as_view(),
         name="segundo-factor-confirmar"),
    path("plataforma/usuarios/<int:pk>/reiniciar-segundo-factor/",
         ReiniciarSegundoFactor.as_view(), name="segundo-factor-reiniciar"),
    path("sesion/salir/", CerrarSesion.as_view(), name="sesion-salir"),
    path("sesion/contrasena/", CambiarContrasena.as_view(), name="sesion-contrasena"),
    path("sesion/sedes/", SedesDeLaSesion.as_view(), name="sesion-sedes"),
    path("sesion/profesionales/", ProfesionalesDeLaSede.as_view(), name="sesion-profesionales"),
    path("", include(router.urls)),
]
