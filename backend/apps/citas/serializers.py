from rest_framework import serializers

from .models import CanalDeRecordatorio, Cita, ConfiguracionRecordatorios


class CitaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source="paciente.nombre_completo", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre_completo", read_only=True)
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)
    # P11 precarga con él el monto cobrado (Práctica 7, Tabla 10).
    servicio_precio = serializers.DecimalField(source="servicio.precio", max_digits=8,
                                               decimal_places=2, read_only=True)
    tiene_atencion = serializers.SerializerMethodField()
    # Declarado a mano para que la regla la aplique programar_cita con su
    # código estable, y no el validador de unicidad genérico del OneToOne.
    reemplaza = serializers.PrimaryKeyRelatedField(
        queryset=Cita.objects.all(), required=False, allow_null=True
    )
    # RF07: enlace «Recordar por WhatsApp» (null si no corresponde) y estado
    # del recordatorio automático (null si todavía no hay).
    enlace_whatsapp = serializers.SerializerMethodField()
    recordatorio = serializers.SerializerMethodField()

    class Meta:
        model = Cita
        fields = [
            "id", "sede", "paciente", "paciente_nombre", "profesional", "profesional_nombre",
            "servicio", "servicio_nombre", "servicio_precio", "inicio", "fin", "estado",
            "observaciones",
            "motivo_cancelacion", "tiene_atencion", "enlace_whatsapp", "recordatorio", "creado_en",
            "reemplaza",
        ]
        read_only_fields = ["id", "fin", "estado", "motivo_cancelacion", "creado_en"]


    def get_enlace_whatsapp(self, cita) -> str | None:
        from .recordatorios import enlace_whatsapp

        return enlace_whatsapp(cita)

    def get_recordatorio(self, cita) -> dict | None:
        recordatorio = getattr(cita, "recordatorio", None)
        if recordatorio is None:
            return None
        return {"estado": recordatorio.estado, "enviado_en": recordatorio.enviado_en,
                "intentos": recordatorio.intentos, "canal": recordatorio.canal}

    def get_tiene_atencion(self, cita) -> bool:
        """Usa la anotación de la consulta; una cita recién creada o recién
        cancelada no la trae y se comprueba con la relación."""
        marca = getattr(cita, "tiene_atencion", None)
        return hasattr(cita, "atencion") if marca is None else marca


class CancelacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=200)
    crear_reemplazo = serializers.BooleanField(default=False)


class ConfiguracionRecordatoriosSerializer(serializers.ModelSerializer):
    """RF07 — activar los recordatorios, su hora y su canal (por centro)."""

    canal = serializers.ChoiceField(choices=CanalDeRecordatorio.choices, required=False)
    canales = serializers.SerializerMethodField()

    class Meta:
        model = ConfiguracionRecordatorios
        fields = ["activo", "hora_envio", "canal", "canales"]

    def get_canales(self, _configuracion) -> list[dict]:
        """Los canales que conoce el sistema y si hoy se pueden elegir."""
        from .canales import CANALES

        return [{"codigo": c.codigo, "nombre": c.nombre, "automatico": c.automatico,
                 "disponible": c.disponible} for c in CANALES.values()]
