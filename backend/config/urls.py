"""Rutas raíz del proyecto. Toda la API cuelga de /api/v1/."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.usuarios.urls")),
    path("api/v1/", include("apps.sedes.urls")),
    path("api/v1/", include("apps.catalogo.urls")),
    path("api/v1/", include("apps.pacientes.urls")),
    path("api/v1/", include("apps.citas.urls")),
]
