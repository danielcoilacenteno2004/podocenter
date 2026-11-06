"""Filtros de la agenda y segmentos del panel (observaciones de la P7)."""
from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.catalogo.models import Servicio
from apps.citas.models import Cita
from apps.citas.servicios import programar_cita
from apps.core.soporte_pruebas import activar_centro

AGENDA = "/api/v1/citas/agenda/"
PANEL = "/api/v1/panel/"


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


@pytest.fixture
def otro_servicio(centro):
    return Servicio.objects.create(
        centro=centro, nombre="Reflexología podal", duracion_minutos=30, precio="55.00"
    )


@pytest.fixture
def jornada(centro, sede, podologa, servicio, otro_servicio, paciente,
            proximo_lunes_a_las_nueve):
    """Tres citas el mismo día: dos servicios distintos y una cancelada."""
    base = proximo_lunes_a_las_nueve
    primera = programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=base,
    )
    segunda = programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=otro_servicio,
        inicio=base + timedelta(hours=2),
    )
    tercera = programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio,
        inicio=base + timedelta(hours=4),
    )
    tercera.estado = Cita.Estado.CANCELADA
    tercera.save(update_fields=["estado", "periodo", "actualizado_en"])
    activar_centro(centro.pk)
    return {"fecha": base.date().isoformat(), "primera": primera,
            "segunda": segunda, "tercera": tercera}


# ------------------------------------------------------------------ filtros
@pytest.mark.django_db
def test_sin_filtros_devuelve_toda_la_jornada(cliente, jornada):
    # Punto de partida de la pantalla P05: sin filtros se ve el día completo, y
    # la respuesta declara explícitamente que no se aplicó ninguno.
    respuesta = cliente.get(AGENDA, {"fecha": jornada["fecha"]})

    assert respuesta.status_code == 200
    assert respuesta.data["total"] == 3
    assert respuesta.data["filtros_aplicados"] == {}


@pytest.mark.django_db
def test_el_filtro_por_estado_acota_la_jornada(cliente, jornada):
    # Primera observación del asesor sobre la P7. El filtro lo resuelve la base:
    # la tabla no esconde filas que ya viajaron al navegador.
    respuesta = cliente.get(AGENDA, {"fecha": jornada["fecha"], "estado": "CANCELADA"})

    assert respuesta.data["total"] == 1
    assert respuesta.data["citas"][0]["id"] == jornada["tercera"].pk
    assert respuesta.data["filtros_aplicados"] == {"estado": "CANCELADA"}


@pytest.mark.django_db
def test_el_filtro_por_servicio_acota_la_jornada(cliente, jornada, otro_servicio):
    # Sirve para revisar de un vistazo cuántas sesiones de un mismo tratamiento
    # hay en el día, que es como la podóloga prepara su material.
    respuesta = cliente.get(
        AGENDA, {"fecha": jornada["fecha"], "servicio": otro_servicio.pk}
    )

    assert respuesta.data["total"] == 1
    assert respuesta.data["citas"][0]["id"] == jornada["segunda"].pk


@pytest.mark.django_db
def test_el_filtro_por_profesional_acota_la_jornada(cliente, jornada, podologa,
                                                    administradora):
    # En una sede con dos podólogas, cada una necesita aislar su propia columna;
    # se comprueba también que una profesional sin citas devuelva vacío y no
    # error.
    propias = cliente.get(AGENDA, {"fecha": jornada["fecha"], "profesional": podologa.pk})
    ajenas = cliente.get(
        AGENDA, {"fecha": jornada["fecha"], "profesional": administradora.pk}
    )

    assert propias.data["total"] == 3
    assert ajenas.data["total"] == 0


@pytest.mark.django_db
def test_los_filtros_se_combinan(cliente, jornada, podologa, otro_servicio):
    # Los tres filtros son acumulativos, no excluyentes: se aplican en la misma
    # consulta.
    respuesta = cliente.get(AGENDA, {
        "fecha": jornada["fecha"], "profesional": podologa.pk,
        "servicio": otro_servicio.pk, "estado": "PROGRAMADA",
    })

    assert respuesta.data["total"] == 1


@pytest.mark.django_db
def test_un_filtro_sin_sentido_se_ignora_en_lugar_de_romper(cliente, jornada):
    # Un parámetro manipulado en la barra de direcciones no puede tumbar la
    # pantalla; se descarta y se devuelve la jornada completa.
    respuesta = cliente.get(AGENDA, {"fecha": jornada["fecha"], "profesional": "abc"})

    assert respuesta.status_code == 200
    assert respuesta.data["total"] == 3


@pytest.mark.django_db
def test_un_estado_inexistente_se_rechaza_con_su_codigo(cliente, jornada):
    # A diferencia del caso anterior, un estado inventado sí se rechaza: si se
    # ignorara en silencio, la usuaria creería estar viendo un filtro que no
    # existe.
    respuesta = cliente.get(AGENDA, {"fecha": jornada["fecha"], "estado": "INVENTADO"})

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "estado-desconocido"


@pytest.mark.django_db
def test_una_fecha_mal_escrita_se_rechaza_con_su_codigo(cliente):
    # El formato dd/mm/aaaa es el que escribiría una persona; el error tiene que
    # decirlo con un código que la pantalla sepa traducir.
    respuesta = cliente.get(AGENDA, {"fecha": "13/11/2026"})

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "fecha-invalida"


# ------------------------------------------------------------------- panel
@pytest.mark.django_db
def test_el_panel_trae_los_tres_segmentos_construidos(cliente, jornada):
    # Segunda observación del asesor: el panel se entrega segmentado por
    # decisión —citas, ingresos y ocupación— y no como indicadores sueltos.
    respuesta = cliente.get(PANEL, {"fecha": jornada["fecha"]})

    assert respuesta.status_code == 200
    assert set(respuesta.data) >= {"citas", "ingresos", "ocupacion"}


@pytest.mark.django_db
def test_el_panel_no_devuelve_el_segmento_de_inventario(cliente, jornada):
    # El cuarto segmento del diseño quedó fuera de esta fase por el recorte
    # CC-12. El panel no lo anuncia ni lo dibuja vacío: la constancia de esa
    # decisión vive en el wireframe de la Práctica N.° 7, que es donde se
    # documenta el alcance, y no en el sistema en funcionamiento.
    respuesta = cliente.get(PANEL, {"fecha": jornada["fecha"]})

    assert "inventario" not in respuesta.data


@pytest.mark.django_db
def test_el_segmento_de_citas_cuenta_por_estado(cliente, jornada):
    # El desglose por estado es lo que convierte un número en información: «doce
    # citas» no dice lo mismo que «doce, de las cuales tres canceladas».
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["citas"]
    por_estado = {fila["estado"]: fila["cantidad"] for fila in datos["por_estado"]}

    assert datos["total"] == 3
    assert por_estado["PROGRAMADA"] == 2
    assert por_estado["CANCELADA"] == 1


@pytest.mark.django_db
def test_el_ingreso_esperado_excluye_las_citas_canceladas(cliente, jornada):
    # Una cita cancelada no es ingreso esperado; contarla inflaría la previsión
    # del día, que es justo lo que la dueña usa para decidir.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]

    # 60.00 de la primera y 55.00 de la segunda; la tercera está cancelada.
    assert datos["esperado"] == "115.00"
    assert datos["perdido"] == "60.00"
    assert datos["ticket_promedio"] == "57.50"


@pytest.mark.django_db
def test_el_ingreso_confirmado_solo_cuenta_lo_atendido(cliente, jornada):
    # Separar lo esperado de lo confirmado evita el error de leer una previsión
    # como si fuera caja.
    jornada["primera"].estado = Cita.Estado.ATENDIDA
    jornada["primera"].save(update_fields=["estado", "periodo", "actualizado_en"])

    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]

    assert datos["confirmado"] == "60.00"


@pytest.mark.django_db
def test_el_ingreso_se_desglosa_por_servicio(cliente, jornada):
    # Ordenado por monto: muestra qué tratamiento sostiene la jornada, que es el
    # dato con el que se decide qué promocionar.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]
    nombres = [fila["servicio"] for fila in datos["por_servicio"]]

    assert len(datos["por_servicio"]) == 2
    assert nombres[0] == "Quiropodia general"      # ordenado por monto


@pytest.mark.django_db
def test_la_ocupacion_se_mide_contra_el_horario_de_la_sede(cliente, jornada):
    # La ocupación se calcula contra el horario real de la sede, no contra un
    # día teórico de ocho horas; de otro modo el porcentaje no significaría
    # nada.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ocupacion"]

    # La sede abre de 08:00 a 20:00 y hay 45 + 30 minutos vendidos.
    assert datos["minutos_disponibles"] == 720
    assert datos["minutos_agendados"] == 75
    assert datos["porcentaje"] == pytest.approx(10.4, abs=0.1)


@pytest.mark.django_db
def test_el_desglose_trae_el_identificador_del_servicio(cliente, jornada, otro_servicio):
    # Cada fila del desglose enlaza a la agenda filtrada por ese servicio, así
    # que el nombre no basta: hace falta el identificador con el que se arma el
    # filtro.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]
    ids = {fila["servicio_id"] for fila in datos["por_servicio"]}

    assert otro_servicio.pk in ids


@pytest.mark.django_db
def test_la_proxima_cita_trae_su_identificador(cliente, jornada):
    # La tarjeta de «próxima cita» es un enlace; necesita saber a qué cita apunta.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["citas"]

    assert datos["proxima"] is None or "cita_id" in datos["proxima"]


@pytest.mark.django_db
def test_un_dia_vacio_no_rompe_el_panel(cliente, sede):
    # Un domingo o un día sin citas debe devolver ceros, no una división por
    # cero ni un `null` que la pantalla no sepa pintar.
    respuesta = cliente.get(PANEL, {"fecha": "2027-01-04"})

    assert respuesta.status_code == 200
    assert respuesta.data["citas"]["total"] == 0
    assert respuesta.data["ingresos"]["esperado"] == "0.00"
    assert respuesta.data["ingresos"]["ticket_promedio"] == "0.00"
