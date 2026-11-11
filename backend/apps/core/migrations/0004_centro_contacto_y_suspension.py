"""Datos de contacto y motivo de suspensión del centro cliente (P19 y P29).

Los centros que ya existen reciben una cadena vacía en el nombre comercial y
el correo de contacto (preserve_default=False): en adelante el alta los exige.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_registroauditoria_accion"),
    ]

    operations = [
        migrations.AddField(
            model_name="centro",
            name="nombre_comercial",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="centro",
            name="correo_contacto",
            field=models.EmailField(default="", max_length=150),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="centro",
            name="motivo_suspension",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
