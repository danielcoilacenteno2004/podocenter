from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SedesDeLaSesion, UsuarioViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("sesion/sedes/", SedesDeLaSesion.as_view(), name="sesion-sedes"),
    path("", include(router.urls)),
]
