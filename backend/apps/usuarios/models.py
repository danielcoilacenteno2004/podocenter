"""Usuario del sistema y su asignación a sedes (RF01, RF02, RF18)."""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from apps.core.campos import TextoCifrado
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
    # Verificación en dos pasos (RF18). El secreto se guarda cifrado, como los
    # datos clínicos: con una copia de la base y el secreto en claro, alguien
    # podría generar los códigos de cualquier administradora. Mientras el
    # factor no está activo, el secreto es el del alta en curso.
    segundo_factor_activo = models.BooleanField(default=False)
    secreto_totp = TextoCifrado(blank=True, default="")
    # Último intervalo de 30 s aceptado: un código ya usado no vale otra vez
    # dentro de su ventana (RFC 6238, sección 5.2).
    ultimo_paso_totp = models.BigIntegerField(null=True, blank=True)
    intentos_fallidos_segundo_factor = models.PositiveSmallIntegerField(default=0)
    segundo_factor_bloqueado_hasta = models.DateTimeField(null=True, blank=True)
    # Bloqueo tras cinco contraseñas erradas seguidas (bloqueo_de_ingreso.py).
    intentos_fallidos_ingreso = models.PositiveSmallIntegerField(default=0)
    ingreso_bloqueado_hasta = models.DateTimeField(null=True, blank=True)
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


class CodigoRecuperacion(SelloDeTiempo):
    """Código de un solo uso para entrar sin el teléfono (RF18).

    Se guarda solo su resumen, nunca el código: se muestra una vez, al
    confirmar el alta del factor. La tabla no lleva política de seguridad por
    fila por la misma razón que `usuario`: se consulta antes de saber el
    centro, durante el ingreso, y el administrador de plataforma no tiene
    centro. Solo la tocan los servicios de `segundo_factor.py`.
    """

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE,
                                related_name="codigos_recuperacion")
    resumen = models.CharField(max_length=100)
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "codigo_recuperacion"
        verbose_name = "código de recuperación"
        verbose_name_plural = "códigos de recuperación"

    def __str__(self) -> str:
        return f"Código de {self.usuario} ({'usado' if self.usado_en else 'vigente'})"


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
