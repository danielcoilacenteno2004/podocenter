from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .sesion import CambiarContrasena, CerrarSesion, EstadoDeSesion, IniciarSesion
from .views import ProfesionalesDeLaSede, SedesDeLaSesion, UsuarioViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("sesion/actual/", EstadoDeSesion.as_view(), name="sesion-actual"),
    path("sesion/ingresar/", IniciarSesion.as_view(), name="sesion-ingresar"),
    path("sesion/salir/", CerrarSesion.as_view(), name="sesion-salir"),
    path("sesion/contrasena/", CambiarContrasena.as_view(), name="sesion-contrasena"),
    path("sesion/sedes/", SedesDeLaSesion.as_view(), name="sesion-sedes"),
    path("sesion/profesionales/", ProfesionalesDeLaSede.as_view(), name="sesion-profesionales"),
    path("", include(router.urls)),
]
