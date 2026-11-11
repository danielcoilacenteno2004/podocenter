from rest_framework import serializers

from .models import Usuario
from .roles import Rol


class UsuarioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    sedes_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )
    # Columna «Sedes» de P17: lectura de las asignaciones vigentes. Escribirlas
    # sigue siendo solo cosa del alta (sedes_ids).
    sedes = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id", "correo", "nombres", "apellidos", "nombre_completo", "rol",
            "esta_activo", "segundo_factor_activo", "sedes_ids", "sedes", "creado_en",
        ]
        read_only_fields = ["id", "creado_en", "segundo_factor_activo"]

    def get_sedes(self, usuario) -> list[dict]:
        return [
            {"id": a.sede_id, "nombre": a.sede.nombre}
            for a in usuario.asignaciones.all() if a.esta_activa
        ]

    def validate_rol(self, valor: str) -> str:
        if valor == Rol.ADMIN_PLATAFORMA:
            raise serializers.ValidationError("Rol no disponible para un centro.")
        return valor


class SedeAsignadaSerializer(serializers.Serializer):
    """Respuesta de /sesion/sedes/, que alimenta la pantalla P03."""

    id = serializers.IntegerField(source="sede.id")
    nombre = serializers.CharField(source="sede.nombre")
    direccion = serializers.CharField(source="sede.direccion")
    es_predeterminada = serializers.BooleanField()
