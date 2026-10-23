from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ServicioViewSet

router = DefaultRouter()
router.register("servicios", ServicioViewSet, basename="servicio")
urlpatterns = [path("", include(router.urls))]
