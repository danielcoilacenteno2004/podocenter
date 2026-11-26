from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AtencionViewSet, ExportarRegistroDiario, RegistroDiario

router = DefaultRouter()
router.register("atenciones", AtencionViewSet, basename="atencion")
urlpatterns = [
    path("reportes/registro-diario/", RegistroDiario.as_view(), name="registro-diario"),
    path("reportes/registro-diario/exportar/", ExportarRegistroDiario.as_view(),
         name="registro-diario-exportar"),
    path("", include(router.urls)),
]
