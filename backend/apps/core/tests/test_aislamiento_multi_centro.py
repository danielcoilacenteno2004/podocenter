"""El aislamiento entre centros clientes es el requisito que sostiene el SaaS."""
import pytest
from django.db import InternalError, ProgrammingError, transaction

from apps.core.models import Centro
from apps.core.soporte_pruebas import activar_centro
from apps.sedes.models import Sede


@pytest.mark.django_db
def test_una_consulta_sin_filtro_solo_devuelve_las_sedes_del_centro_activo(
    centro, sede, otro_centro
):
    activar_centro(otro_centro.pk)
    ajena = Sede.objects.create(centro=otro_centro, nombre="San Isidro", direccion="Av. Arequipa 1")

    activar_centro(centro.pk)
    visibles = list(Sede.objects.all())

    assert sede in visibles
    assert ajena not in visibles
    assert len(visibles) == 1


@pytest.mark.django_db
def test_no_se_puede_leer_una_sede_de_otro_centro_ni_pidiendola_por_su_identificador(
    centro, otro_centro
):
    activar_centro(otro_centro.pk)
    ajena = Sede.objects.create(centro=otro_centro, nombre="Miraflores", direccion="Av. Larco 2")

    activar_centro(centro.pk)

    assert not Sede.objects.filter(pk=ajena.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_la_base_rechaza_escribir_una_fila_con_el_centro_de_otro_inquilino(centro, otro_centro):
    activar_centro(centro.pk)

    with pytest.raises((InternalError, ProgrammingError)), transaction.atomic():
        Sede.objects.create(centro=otro_centro, nombre="Intrusa", direccion="x")


@pytest.mark.django_db
def test_la_tabla_de_centros_no_esta_sujeta_al_aislamiento(centro, otro_centro):
    """El administrador de plataforma necesita verlos todos (RF17)."""
    assert Centro.objects.count() == 2
