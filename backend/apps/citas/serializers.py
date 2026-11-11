from rest_framework import serializers

from .models import Cita


class CitaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source="paciente.nombre_completo", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre_completo", read_only=True)
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)
    # P11 precarga con él el monto cobrado (Práctica 7, Tabla 10).
    servicio_precio = serializers.DecimalField(source="servicio.precio", max_digits=8,
                                               decimal_places=2, read_only=True)
    tiene_atencion = serializers.SerializerMethodField()

    class Meta:
        model = Cita
        fields = [
            "id", "sede", "paciente", "paciente_nombre", "profesional", "profesional_nombre",
            "servicio", "servicio_nombre", "servicio_precio", "inicio", "fin", "estado",
            "observaciones",
            "motivo_cancelacion", "tiene_atencion", "creado_en",
        ]
        read_only_fields = ["id", "fin", "estado", "motivo_cancelacion", "creado_en"]


    def get_tiene_atencion(self, cita) -> bool:
        """Usa la anotación de la consulta; una cita recién creada o recién
        cancelada no la trae y se comprueba con la relación."""
        marca = getattr(cita, "tiene_atencion", None)
        return hasattr(cita, "atencion") if marca is None else marca


class CancelacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=200)
    crear_reemplazo = serializers.BooleanField(default=False)
