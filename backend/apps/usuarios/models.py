"""Usuario del sistema y su asignación a sedes (RF01, RF02, RF18)."""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.core.modelos_base import SelloDeTiempo

from .roles import ROLES_CON_SEGUNDO_FACTOR, Rol


class GestorDeUsuarios(BaseUserManager):
    """Crea usuarios normalizando el correo, que es la credencial de acceso."""

    use_in_migrations = True

    def create_user(self, correo: str, password: str | None = None, **extra):
        if not correo:
            raise ValueError("El usuario necesita un correo electrónico.")
        usuario = self.model(correo=self.normalize_email(correo), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo: str, password: str | None = None, **extra):
        extra.setdefault("rol", Rol.ADMIN_PLATAFORMA)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("esta_activo", True)
        return self.create_user(correo, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin, SelloDeTiempo):
    """Persona que entra al sistema.

    El administrador de plataforma no pertenece a ningún centro; por eso
    `centro` admite nulo. Cualquier otro rol lo tiene obligatoriamente, y es
    ese campo el que decide qué filas ve (RLS).
    """

    correo = models.EmailField(unique=True, max_length=254)
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    documento = models.CharField(max_length=12, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices)
    centro = models.ForeignKey(
        "core.Centro", on_delete=models.PROTECT, null=True, blank=True, related_name="usuarios"
    )
    sedes = models.ManyToManyField("sedes.Sede", through="AsignacionSede", related_name="usuarios")
    esta_activo = models.BooleanField(default=True)
    segundo_factor_activo = models.BooleanField(default=False)
    secreto_totp = models.CharField(max_length=64, blank=True)
    ultimo_acceso_en = models.DateTimeField(null=True, blank=True)
    # Encendido mientras la cuenta tenga una contraseña temporal (alta o
    # restablecimiento): hasta cambiarla, la API solo deja cambiarla.
    debe_cambiar_contrasena = models.BooleanField(default=False)

    is_staff = models.BooleanField(default=False)

    objects = GestorDeUsuarios()

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombres", "apellidos"]

    class Meta:
        db_table = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["apellidos", "nombres"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rol="ADMIN_PLATAFORMA", centro__isnull=True)
                | ~models.Q(rol="ADMIN_PLATAFORMA") & models.Q(centro__isnull=False),
                name="ck_usuario_centro_segun_rol",
            )
        ]

    def __str__(self) -> str:
        return f"{self.apellidos}, {self.nombres}"

    @property
    def is_active(self) -> bool:
        return self.esta_activo

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    @property
    def requiere_segundo_factor(self) -> bool:
        """El RNF01 exige segundo factor a los roles administrativos."""
        return self.rol in ROLES_CON_SEGUNDO_FACTOR

    def puede_usar_sede(self, sede_id: int) -> bool:
        return self.asignaciones.filter(sede_id=sede_id, esta_activa=True).exists()


class AsignacionSede(SelloDeTiempo):
    """Sedes en las que un usuario puede trabajar (pantalla P03)."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="asignaciones")
    sede = models.ForeignKey("sedes.Sede", on_delete=models.CASCADE, related_name="asignaciones")
    es_predeterminada = models.BooleanField(default=False)
    esta_activa = models.BooleanField(default=True)

    class Meta:
        db_table = "asignacion_sede"
        verbose_name = "asignación de sede"
        verbose_name_plural = "asignaciones de sede"
        constraints = [
            models.UniqueConstraint(fields=["usuario", "sede"], name="uq_asignacion_usuario_sede")
        ]

    def __str__(self) -> str:
        return f"{self.usuario} → {self.sede}"
