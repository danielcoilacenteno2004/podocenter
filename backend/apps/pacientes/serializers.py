from rest_framework import serializers

from .models import Consentimiento, Paciente


class ConsentimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consentimiento
        fields = ["id", "version_texto", "acepta_tratamiento_datos", "acepta_recordatorios",
                  "canal", "otorgado_en", "fue_revocado"]
        read_only_fields = fields


class PacienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    consentimiento = serializers.DictField(write_only=True, required=False, default=dict)
    consentimiento_vigente = ConsentimientoSerializer(read_only=True)

    class Meta:
        model = Paciente
        fields = [
            "id", "tipo_documento", "documento", "nombres", "apellidos", "nombre_completo",
            "fecha_nacimiento", "telefono", "correo", "domicilio", "antecedentes",
            "esta_activo", "consentimiento", "consentimiento_vigente", "creado_en",
        ]
        read_only_fields = ["id", "creado_en"]

    def validate_documento(self, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El documento es obligatorio.")
        return valor
