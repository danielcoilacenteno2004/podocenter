from rest_framework import serializers

from .models import Cita


class CitaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source="paciente.nombre_completo", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre_completo", read_only=True)
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)

    class Meta:
        model = Cita
        fields = [
            "id", "sede", "paciente", "paciente_nombre", "profesional", "profesional_nombre",
            "servicio", "servicio_nombre", "inicio", "fin", "estado", "observaciones",
            "motivo_cancelacion", "creado_en",
        ]
        read_only_fields = ["id", "fin", "estado", "motivo_cancelacion", "creado_en"]


class CancelacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=200)
    crear_reemplazo = serializers.BooleanField(default=False)
