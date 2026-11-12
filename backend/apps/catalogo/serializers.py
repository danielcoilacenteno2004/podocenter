from rest_framework import serializers

from .models import Servicio


class InsumoHabitualSerializer(serializers.Serializer):
    # Enteros sin validar aquí: producto, centro y cantidad los decide el
    # servicio con su código estable.
    producto = serializers.IntegerField(allow_null=True)
    cantidad = serializers.IntegerField(allow_null=True)


class ServicioSerializer(serializers.ModelSerializer):
    # El rango de la duración lo valida el servicio, con su código de negocio
    # (duracion-fuera-de-rango); declarado así, DRF no lo rechaza antes con
    # un 400 genérico tomado de los validadores del modelo.
    duracion_minutos = serializers.IntegerField()
    # CC-14: se escribe como [{producto, cantidad}] y se lee con el nombre,
    # el código y la unidad, que P26 y P11 muestran.
    insumos_habituales = InsumoHabitualSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Servicio
        fields = ["id", "nombre", "descripcion", "duracion_minutos", "precio",
                  "esta_activo", "insumos_habituales", "creado_en"]
        read_only_fields = ["id", "creado_en"]

    def to_representation(self, servicio):
        datos = super().to_representation(servicio)
        datos["insumos_habituales"] = [
            {"producto": i.producto_id, "codigo": i.producto.codigo, "nombre": i.producto.nombre,
             "unidad": i.producto.unidad, "esta_activo": i.producto.esta_activo,
             "cantidad": i.cantidad}
            # .all() aprovecha el prefetch del listado; se ordena aquí.
            for i in sorted(servicio.insumos_habituales.all(), key=lambda i: i.producto.nombre)
        ]
        return datos
