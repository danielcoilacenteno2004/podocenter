from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AtencionViewSet, RegistroDiario

router = DefaultRouter()
router.register("atenciones", AtencionViewSet, basename="atencion")
urlpatterns = [
    path("reportes/registro-diario/", RegistroDiario.as_view(), name="registro-diario"),
    path("", include(router.urls)),
]
