from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AtencionViewSet

router = DefaultRouter()
router.register("atenciones", AtencionViewSet, basename="atencion")
urlpatterns = [
    path("", include(router.urls)),
]
