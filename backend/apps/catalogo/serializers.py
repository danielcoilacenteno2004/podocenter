from rest_framework import serializers

from .models import Servicio


class ServicioSerializer(serializers.ModelSerializer):
    # El rango de la duración lo valida el servicio, con su código de negocio
    # (duracion-fuera-de-rango); declarado así, DRF no lo rechaza antes con
    # un 400 genérico tomado de los validadores del modelo.
    duracion_minutos = serializers.IntegerField()

    class Meta:
        model = Servicio
        fields = ["id", "nombre", "descripcion", "duracion_minutos", "precio",
                  "esta_activo", "creado_en"]
        read_only_fields = ["id", "creado_en"]
