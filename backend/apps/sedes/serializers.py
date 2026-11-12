from rest_framework import serializers

from .models import HorarioSede, Sede


class HorarioSedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HorarioSede
        fields = ["id", "dia_semana", "hora_apertura", "hora_cierre", "esta_abierta"]


class DiaDeHorarioSerializer(serializers.Serializer):
    """Un día abierto de la semana al escribir el horario. Los que no vienen
    quedan cerrados. Cierre posterior a apertura lo decide el servicio."""

    dia_semana = serializers.IntegerField(min_value=0, max_value=6)
    hora_apertura = serializers.TimeField()
    hora_cierre = serializers.TimeField()


class SedeSerializer(serializers.ModelSerializer):
    horarios = HorarioSedeSerializer(many=True, read_only=True)
    # Escritura del horario (CC-15): la semana completa de una vez, en la
    # misma petición que los datos de la sede.
    horario = DiaDeHorarioSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Sede
        fields = ["id", "nombre", "direccion", "telefono", "esta_activa", "horarios", "horario",
                  "creado_en"]
        read_only_fields = ["id", "creado_en"]
