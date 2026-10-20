"""Seguridad a nivel de fila (RLS) sobre las tablas con datos de un centro.

Es el segundo cerrojo del aislamiento multi-inquilino descrito en la
Práctica N.° 5: aunque una consulta olvide filtrar por centro, PostgreSQL
solo devuelve las filas del centro fijado en `app.centro_id` por el
middleware. El rol propietario de la base conserva BYPASSRLS para que las
migraciones y los respaldos sigan funcionando.
"""
from django.db import migrations

TABLAS = [
    "sede", "horario_sede", "servicio", "paciente", "cita",
    "registro_auditoria", "asignacion_sede",
]

POLITICA_POR_CENTRO = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pol_aislamiento_centro ON {tabla};
CREATE POLICY pol_aislamiento_centro ON {tabla}
    USING (centro_id = NULLIF(current_setting('app.centro_id', true), '')::bigint)
    WITH CHECK (centro_id = NULLIF(current_setting('app.centro_id', true), '')::bigint);
"""

REVERTIR = """
DROP POLICY IF EXISTS pol_aislamiento_centro ON {tabla};
ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY;
"""

# Estas dos tablas no llevan centro_id propio: heredan el del padre.
POLITICA_HEREDADA = {
    "horario_sede": "sede_id IN (SELECT id FROM sede)",
    "asignacion_sede": "sede_id IN (SELECT id FROM sede)",
}


def _sentencias():
    adelante, atras = [], []
    for tabla in TABLAS:
        if tabla in POLITICA_HEREDADA:
            condicion = POLITICA_HEREDADA[tabla]
            adelante.append(
                f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;"
                f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;"
                f"DROP POLICY IF EXISTS pol_aislamiento_centro ON {tabla};"
                f"CREATE POLICY pol_aislamiento_centro ON {tabla} "
                f"USING ({condicion}) WITH CHECK ({condicion});"
            )
        else:
            adelante.append(POLITICA_POR_CENTRO.format(tabla=tabla))
        atras.append(REVERTIR.format(tabla=tabla))
    return adelante, atras


ADELANTE, ATRAS = _sentencias()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("sedes", "0001_initial"),
        ("catalogo", "0001_initial"),
        ("pacientes", "0002_initial"),
        ("citas", "0002_initial"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        *[migrations.RunSQL(a, b) for a, b in zip(ADELANTE, ATRAS)],
    ]
