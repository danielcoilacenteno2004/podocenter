from rest_framework import serializers

from .models import HorarioSede, Sede


class HorarioSedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HorarioSede
        fields = ["id", "dia_semana", "hora_apertura", "hora_cierre", "esta_abierta"]

    def validate(self, datos):
        if datos["hora_cierre"] <= datos["hora_apertura"]:
            raise serializers.ValidationError("La hora de cierre debe ser posterior a la de apertura.")
        return datos


class SedeSerializer(serializers.ModelSerializer):
    horarios = HorarioSedeSerializer(many=True, read_only=True)

    class Meta:
        model = Sede
        fields = ["id", "nombre", "direccion", "telefono", "esta_activa", "horarios", "creado_en"]
        read_only_fields = ["id", "creado_en"]
