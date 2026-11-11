from rest_framework import serializers

from apps.citas.models import Cita

from .models import Atencion

_COPIADOS_DE_LA_CITA = ["sede", "paciente", "profesional", "servicio"]


class AtencionResumenSerializer(serializers.ModelSerializer):
    """Fila del listado: sin las observaciones clínicas, que solo da la ficha auditada."""

    paciente_nombre = serializers.CharField(source="paciente.nombre_completo", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre_completo", read_only=True)
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)

    class Meta:
        model = Atencion
        fields = [
            "id", "cita", "sede", "paciente", "paciente_nombre", "profesional",
            "profesional_nombre", "servicio", "servicio_nombre", "registrada_por",
            "registrada_en",
        ]
        read_only_fields = fields


class AtencionSerializer(AtencionResumenSerializer):
    # Declarado a mano para que no se añada el validador de unicidad del uno a
    # uno: una cita ya atendida la rechaza el servicio con su código estable.
    cita = serializers.PrimaryKeyRelatedField(queryset=Cita.objects.all())
    # Límite fijado en la especificación de P11 (Práctica N.° 7, Tabla 10).
    observaciones_clinicas = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )

    class Meta(AtencionResumenSerializer.Meta):
        fields = [*AtencionResumenSerializer.Meta.fields, "observaciones_clinicas"]
        read_only_fields = [
            *_COPIADOS_DE_LA_CITA, "id", "registrada_por", "registrada_en",
        ]
