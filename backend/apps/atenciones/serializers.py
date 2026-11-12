from rest_framework import serializers

from .models import Atencion

_COPIADOS_DE_LA_CITA = ["sede", "paciente", "profesional", "servicio"]


class AtencionResumenSerializer(serializers.ModelSerializer):
    """Fila del listado: sin las observaciones clínicas, que solo da la ficha auditada."""

    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)
    paciente_nombre = serializers.CharField(source="paciente.nombre_completo", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre_completo", read_only=True)
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)

    class Meta:
        model = Atencion
        fields = [
            "id", "cita", "sede", "sede_nombre", "paciente", "paciente_nombre", "profesional",
            "profesional_nombre", "servicio", "servicio_nombre", "monto_cobrado",
            "registrada_por", "registrada_en",
        ]
        read_only_fields = fields


class InsumoPedidoSerializer(serializers.Serializer):
    # Enteros y no relaciones: el producto, su centro y el stock los decide el
    # servicio con su código estable.
    producto = serializers.IntegerField(allow_null=True)
    cantidad = serializers.IntegerField(allow_null=True)


class AtencionSerializer(AtencionResumenSerializer):
    # Entero y no relación: así la existencia, el centro y la unicidad de la
    # cita los decide el servicio, con su código estable, y no un 400 genérico
    # del serializador.
    cita = serializers.IntegerField(source="cita_id")
    # Tabla 10 de la Práctica 7: obligatorio, mayor o igual a 0, dos decimales.
    monto_cobrado = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=0)
    # Límite fijado en la especificación de P11 (Práctica N.° 7, Tabla 10).
    observaciones_clinicas = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )
    # Tabla 10: insumos consumidos; cada uno genera su salida de stock.
    insumos = InsumoPedidoSerializer(many=True, required=False, write_only=True)
    insumos_consumidos = serializers.SerializerMethodField()

    class Meta(AtencionResumenSerializer.Meta):
        fields = [*AtencionResumenSerializer.Meta.fields, "observaciones_clinicas", "insumos",
                  "insumos_consumidos"]
        read_only_fields = [
            *_COPIADOS_DE_LA_CITA, "id", "registrada_por", "registrada_en",
        ]

    def get_insumos_consumidos(self, atencion) -> list[dict]:
        return [
            {"producto": m.producto_id, "codigo": m.producto.codigo, "nombre": m.producto.nombre,
             "unidad": m.producto.unidad, "cantidad": -m.cantidad}
            for m in atencion.insumos.select_related("producto").order_by("producto__nombre")
        ]
