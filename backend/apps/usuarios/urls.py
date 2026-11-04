from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .sesion import CerrarSesion, EstadoDeSesion, IniciarSesion
from .views import SedesDeLaSesion, UsuarioViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("sesion/actual/", EstadoDeSesion.as_view(), name="sesion-actual"),
    path("sesion/ingresar/", IniciarSesion.as_view(), name="sesion-ingresar"),
    path("sesion/salir/", CerrarSesion.as_view(), name="sesion-salir"),
    path("sesion/sedes/", SedesDeLaSesion.as_view(), name="sesion-sedes"),
    path("", include(router.urls)),
]
