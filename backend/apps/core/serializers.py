from rest_framework import serializers

from .models import Centro


class CentroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Centro
        fields = ["id", "razon_social", "ruc", "subdominio", "estado", "creado_en"]
        read_only_fields = ["id", "creado_en"]

    def validate_ruc(self, valor: str) -> str:
        if not valor.isdigit() or len(valor) != 11:
            raise serializers.ValidationError("El RUC debe tener 11 dígitos.")
        return valor
