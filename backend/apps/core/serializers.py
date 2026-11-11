from rest_framework import serializers

from .models import Centro


class CentroSerializer(serializers.ModelSerializer):
    class Meta:
        model = Centro
        fields = ["id", "razon_social", "nombre_comercial", "ruc", "subdominio",
                  "correo_contacto", "estado", "motivo_suspension", "creado_en"]
        read_only_fields = ["id", "creado_en"]

    def validate_ruc(self, valor: str) -> str:
        if not valor.isdigit() or len(valor) != 11:
            raise serializers.ValidationError("El RUC debe tener 11 dígitos.")
        return valor

    def validate(self, datos):
        # Práctica N.° 7, Tabla 31: suspender «pide confirmación y motivo».
        estado = datos.get("estado", getattr(self.instance, "estado", None))
        motivo = datos.get("motivo_suspension", getattr(self.instance, "motivo_suspension", ""))
        if estado == Centro.Estado.SUSPENDIDO and not (motivo or "").strip():
            raise serializers.ValidationError(
                {"motivo_suspension": ["Indique el motivo de la suspensión."]}
            )
        return datos


class AdministradorInicialSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=80)
    apellidos = serializers.CharField(max_length=80)
    correo = serializers.EmailField(max_length=254)


class AltaDeCentroSerializer(CentroSerializer):
    """Alta (P29): los datos del centro y los de su administrador inicial."""

    administrador = AdministradorInicialSerializer(write_only=True)

    class Meta(CentroSerializer.Meta):
        fields = [*CentroSerializer.Meta.fields, "administrador"]
