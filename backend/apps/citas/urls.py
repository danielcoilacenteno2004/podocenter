from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .panel import PanelDelDia
from .views import CitaViewSet, ConfiguracionDeRecordatorios

router = DefaultRouter()
router.register("citas", CitaViewSet, basename="cita")
urlpatterns = [
    path("panel/", PanelDelDia.as_view(), name="panel-del-dia"),
    path("recordatorios/configuracion/", ConfiguracionDeRecordatorios.as_view(),
         name="recordatorios-configuracion"),
    path("", include(router.urls)),
]
