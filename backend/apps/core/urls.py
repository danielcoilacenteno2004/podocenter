from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CentroViewSet, EstadoDelServicio

router = DefaultRouter()
router.register("centros", CentroViewSet, basename="centro")

urlpatterns = [
    path("estado/", EstadoDelServicio.as_view(), name="estado"),
    path("", include(router.urls)),
]
