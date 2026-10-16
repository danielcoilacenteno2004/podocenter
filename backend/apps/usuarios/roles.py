"""Catálogo de roles del sistema (RF01).

Se declara aparte de los modelos para que los permisos puedan importarlo
sin arrastrar la capa de datos.
"""
from django.db import models


class Rol(models.TextChoices):
    ADMIN_PLATAFORMA = "ADMIN_PLATAFORMA", "Administrador de plataforma"
    ADMIN_CENTRO = "ADMIN_CENTRO", "Administrador del centro"
    PODOLOGA = "PODOLOGA", "Podóloga"


ROLES_DE_CENTRO = {Rol.ADMIN_CENTRO, Rol.PODOLOGA}
ROLES_CON_SEGUNDO_FACTOR = {Rol.ADMIN_PLATAFORMA, Rol.ADMIN_CENTRO}
