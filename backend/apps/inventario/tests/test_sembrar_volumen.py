"""Pruebas del comando `sembrar_volumen`.

Las pruebas de carga de la Práctica N.° 9 miden el sistema con el volumen de
la Tabla 51. Si el comando sembrara un libro de inventario incoherente o
cambiara el stock de la demostración, la medición se haría sobre datos que el
sistema real nunca produciría.
"""
from collections import defaultdict

import pytest
from django.core.management import CommandError, call_command

from apps.core.models import Centro
from apps.core.soporte_pruebas import activar_centro
from apps.inventario.management.commands.sembrar_volumen import MARCA
from apps.inventario.models import MovimientoInventario, Stock


@pytest.fixture
def demo(db):
    call_command("cargar_demo", verbosity=0)
    centro = Centro.objects.get(subdominio="piessanos")
    activar_centro(centro.pk)
    return centro


@pytest.mark.django_db
def test_siembra_exactamente_la_cantidad_pedida(demo):
    # La cifra es la que se declara en el informe de pruebas: si el comando
    # sembrara otra, el volumen citado no sería el medido.
    call_command("sembrar_volumen", cantidad=240, dias=30, verbosity=0)

    assert MovimientoInventario.objects.filter(centro=demo, motivo=MARCA).count() == 240


@pytest.mark.django_db
def test_cada_historia_encadena_existencias_y_cierra_en_cero(demo):
    # Un libro que no cuadra no es un volumen representativo: cada movimiento
    # debe partir de la existencia que dejó el anterior, sin bajar de cero, y
    # cerrar en cero para que el inventario inicial de la demo siga siendo cierto.
    call_command("sembrar_volumen", cantidad=240, dias=30, verbosity=0)

    historias = defaultdict(list)
    for m in (MovimientoInventario.objects.filter(centro=demo, motivo=MARCA)
              .order_by("creado_en", "pk")):
        historias[(m.sede_id, m.producto_id)].append(m)
    for movimientos in historias.values():
        existencia = 0
        for m in movimientos:
            existencia += m.cantidad
            assert m.existencia_resultante == existencia >= 0
        assert existencia == 0


@pytest.mark.django_db
def test_no_cambia_el_stock_ni_siembra_salidas(demo):
    # El stock solo cambia por un movimiento real, y la salida exige una
    # atención: sembrar cualquiera de las dos cosas falsearía la demostración.
    antes = dict(Stock.objects.filter(centro=demo).values_list("pk", "cantidad"))

    call_command("sembrar_volumen", cantidad=240, dias=30, verbosity=0)

    assert dict(Stock.objects.filter(centro=demo).values_list("pk", "cantidad")) == antes
    assert not MovimientoInventario.objects.filter(motivo=MARCA, tipo="SALIDA").exists()


@pytest.mark.django_db
def test_correrlo_dos_veces_no_duplica(demo):
    # Si cada corrida sumara sus movimientos, el volumen medido dependería de
    # cuántas veces se preparó el entorno.
    call_command("sembrar_volumen", cantidad=240, dias=30, verbosity=0)
    call_command("sembrar_volumen", cantidad=240, dias=30, verbosity=0)

    assert MovimientoInventario.objects.filter(centro=demo, motivo=MARCA).count() == 240


@pytest.mark.django_db
def test_sin_la_demostracion_falla_con_un_mensaje_claro(db):
    # El comando no inventa un centro: sin cargar_demo, se detiene y dice qué falta.
    with pytest.raises(CommandError, match="cargar_demo"):
        call_command("sembrar_volumen", verbosity=0)


@pytest.mark.django_db
def test_rechaza_una_cantidad_que_no_alcanza_para_cerrar_cada_historia(demo):
    # Con menos de dos movimientos por producto y sede, alguna historia no
    # podría cerrar en cero: mejor un error que un libro descuadrado.
    with pytest.raises(CommandError, match="mínima"):
        call_command("sembrar_volumen", cantidad=10, verbosity=0)
