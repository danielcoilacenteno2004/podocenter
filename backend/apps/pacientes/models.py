"""Paciente, consentimiento informado e historial (RF04, RF05, RNF06)."""
from django.db import models

from apps.core.campos import TextoCifrado
from apps.core.modelos_base import ModeloDeCentro, SelloDeTiempo


class Paciente(ModeloDeCentro):
    """Persona atendida en el centro.

    Los antecedentes son dato clínico y viajan cifrados; los datos de
    contacto no, porque la pantalla P08 busca por nombre y por documento.
    """

    class TipoDocumento(models.TextChoices):
        DNI = "DNI", "DNI"
        CE = "CE", "Carné de extranjería"
        PASAPORTE = "PAS", "Pasaporte"

    tipo_documento = models.CharField(max_length=3, choices=TipoDocumento.choices,
                                      default=TipoDocumento.DNI)
    documento = models.CharField(max_length=20)
    nombres = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=80)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(blank=True)
    domicilio = models.CharField(max_length=200, blank=True)
    antecedentes = TextoCifrado(blank=True, default="")
    esta_activo = models.BooleanField(default=True)

    class Meta:
        db_table = "paciente"
        verbose_name_plural = "pacientes"
        ordering = ["apellidos", "nombres"]
        constraints = [
            models.UniqueConstraint(
                fields=["centro", "tipo_documento", "documento"],
                name="uq_paciente_centro_documento",
            )
        ]
        indexes = [
            models.Index(fields=["centro", "apellidos", "nombres"], name="idx_paciente_nombre")
        ]

    def __str__(self) -> str:
        return f"{self.apellidos}, {self.nombres}"

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    @property
    def consentimiento_vigente(self):
        return self.consentimientos.filter(fue_revocado=False).order_by("-otorgado_en").first()


class Consentimiento(SelloDeTiempo):
    """Consentimiento informado versionado (RNF06, riesgo R12).

    Se guarda qué versión del texto aceptó el paciente y cuándo, porque la
    Ley N.° 29733 obliga a poder demostrarlo, no solo a declararlo.
    """

    class Canal(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Firmado en el centro"
        DIGITAL = "DIGITAL", "Aceptado en línea"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE,
                                 related_name="consentimientos")
    version_texto = models.CharField(max_length=20)
    acepta_tratamiento_datos = models.BooleanField(default=True)
    acepta_recordatorios = models.BooleanField(default=False)
    canal = models.CharField(max_length=12, choices=Canal.choices, default=Canal.PRESENCIAL)
    otorgado_en = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey("usuarios.Usuario", on_delete=models.PROTECT,
                                       related_name="consentimientos_registrados")
    fue_revocado = models.BooleanField(default=False)
    revocado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "consentimiento"
        verbose_name_plural = "consentimientos"
        ordering = ["-otorgado_en"]

    def __str__(self) -> str:
        return f"{self.paciente} v{self.version_texto}"
