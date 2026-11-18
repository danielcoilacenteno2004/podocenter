"""Filtros de la agenda y segmentos del panel (observaciones de la P7)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.atenciones.servicios import registrar_atencion
from apps.catalogo.models import Servicio
from apps.citas.models import Cita
from apps.citas.servicios import programar_cita
from apps.core.soporte_pruebas import activar_centro, hacer_que_la_cita_ya_empezo

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
def test_el_ingreso_confirmado_es_lo_cobrado_y_cuadra_con_el_registro_diario(
        cliente, centro, sede, podologa, servicio, paciente, proximo_lunes_a_las_nueve):
    # Lo confirmado es caja: lo que se cobró en la atención, no el precio de
    # catálogo. Con un descuento (50 sobre un servicio de 60) el panel tiene
    # que dar la misma cifra que el registro diario (P16); si no, la dueña
    # vería dos ingresos distintos para el mismo día.
    cita = hacer_que_la_cita_ya_empezo(programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
    ))
    registrar_atencion(centro=centro, usuario=podologa, sede_id=sede.pk,
                       cita_id=cita.pk, monto_cobrado=Decimal("50.00"))
    fecha = timezone.localtime(cita.inicio).date().isoformat()

    ingresos = cliente.get(PANEL, {"fecha": fecha}).data["ingresos"]
    registro = cliente.get("/api/v1/reportes/registro-diario/", {"fecha": fecha}).data

    assert ingresos["confirmado"] == "50.00"
    assert Decimal(ingresos["confirmado"]) == Decimal(str(registro["total"]))


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
def test_la_ocupacion_cuenta_la_capacidad_de_cada_profesional(cliente, jornada, administradora):
    # Con dos profesionales asignadas, la sede vende el doble de minutos. Medir
    # contra el horario una sola vez daba la mitad de capacidad y porcentajes
    # que podían pasar de 100 %; la decisión de abrir cupos se tomaría sobre
    # una cifra falsa.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ocupacion"]
    por_profesional = {p["nombre"]: p for p in datos["profesionales"]}

    assert datos["minutos_jornada"] == 720
    assert datos["minutos_disponibles"] == 1440
    assert datos["porcentaje"] == pytest.approx(5.2, abs=0.1)
    assert por_profesional["Rosa Quispe"]["minutos_agendados"] == 75
    assert por_profesional["Lucía Ramos"]["libres"] == 720


@pytest.mark.django_db
def test_una_cita_terminada_queda_sin_registrar_y_una_empezada_sigue_en_curso(
        cliente, centro, sede, podologa, servicio, paciente, proximo_lunes_a_las_nueve):
    # Una cita programada que ya terminó no está «por atender»: falta registrar
    # su atención, y la pantalla la ofrece para registrarla, porque cada una
    # que falta deja mal el ingreso y el stock del día. La que empezó y no ha
    # terminado sí está por atender, marcada como en curso.
    def cita_que_empezo_hace(minutos, desfase_en_horas):
        return hacer_que_la_cita_ya_empezo(programar_cita(
            centro=centro, usuario=podologa, sede=sede, paciente=paciente,
            profesional=podologa, servicio=servicio,
            inicio=proximo_lunes_a_las_nueve + timedelta(hours=desfase_en_horas),
        ), hace_minutos=minutos)

    terminada = cita_que_empezo_hace(60, 0)       # 45 minutos de duración
    en_curso = cita_que_empezo_hace(10, 2)
    fecha = timezone.localtime(en_curso.inicio).date().isoformat()

    datos = cliente.get(PANEL, {"fecha": fecha}).data["citas"]

    assert [fila["cita_id"] for fila in datos["sin_registrar"]] == [terminada.pk]
    assert datos["por_atender"] == 1
    assert datos["siguientes"][0]["cita_id"] == en_curso.pk
    assert datos["siguientes"][0]["momento"] == "en-curso"


@pytest.mark.django_db
def test_el_desglose_trae_el_identificador_del_servicio(cliente, jornada, otro_servicio):
    # Cada fila del desglose enlaza a la agenda filtrada por ese servicio, así
    # que el nombre no basta: hace falta el identificador con el que se arma el
    # filtro.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]
    ids = {fila["servicio_id"] for fila in datos["por_servicio"]}

    assert otro_servicio.pk in ids


@pytest.mark.django_db
def test_las_siguientes_citas_vienen_en_orden_y_la_primera_es_la_proxima(cliente, jornada):
    # La lista de lo que viene es lo que se mira para saber a quién toca: va
    # por hora y sin las canceladas, y la primera que falta empezar es la
    # «próxima cita» que la Tabla 7 pide destacar. Cada fila enlaza a su cita
    # y a la ficha del paciente, así que trae los dos identificadores.
    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["citas"]
    filas = datos["siguientes"]

    assert [fila["cita_id"] for fila in filas] == [jornada["primera"].pk, jornada["segunda"].pk]
    assert [fila["momento"] for fila in filas] == ["proxima", "despues"]
    assert filas[0]["paciente_id"] == jornada["primera"].paciente_id


@pytest.mark.django_db
def test_una_cancelacion_reprogramada_no_cuenta_como_no_concretada(
        cliente, jornada, centro, sede, podologa, servicio, paciente):
    # Una cita cancelada que tiene reemplazo no es ingreso perdido: cambió de
    # hora. Contarla inflaba el «no concretado» con dinero que sí llegará.
    programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio,
        inicio=jornada["tercera"].inicio + timedelta(hours=2), reemplaza=jornada["tercera"],
    )

    datos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ingresos"]

    assert datos["perdido"] == "0.00"


@pytest.mark.django_db
def test_la_referencia_promedia_los_mismos_dias_de_las_semanas_anteriores(
        cliente, centro, sede, podologa, servicio, paciente, proximo_lunes_a_las_nueve):
    # Sin referencia una cifra no dice si el día va bien o mal. Se compara con
    # los cuatro lunes anteriores en que la sede abrió: dos con una cita de
    # 60.00 y dos vacíos dan 0.5 citas y 30.00 de ingreso esperado.
    lunes = proximo_lunes_a_las_nueve + timedelta(weeks=3)
    for semanas in (1, 2):
        programar_cita(
            centro=centro, usuario=podologa, sede=sede, paciente=paciente,
            profesional=podologa, servicio=servicio, inicio=lunes - timedelta(weeks=semanas),
        )

    datos = cliente.get(PANEL, {"fecha": lunes.date().isoformat()}).data

    assert datos["citas"]["referencia"] == {"dias": 4, "total": 0.5}
    assert datos["ingresos"]["referencia"] == {"dias": 4, "esperado": "30.00", "confirmado": "0.00"}


@pytest.mark.django_db
def test_la_ocupacion_anticipa_los_siete_dias_siguientes(
        cliente, jornada, centro, sede, podologa, servicio, paciente):
    # Lo que se puede llenar todavía son los días que vienen. Un martes con
    # una cita de 45 minutos sobre 720 de capacidad da 6.2 %; el domingo la
    # sede no abre y se dice, en lugar de dar un cero que parezca un día vacío.
    lunes = jornada["primera"].inicio
    programar_cita(
        centro=centro, usuario=podologa, sede=sede, paciente=paciente,
        profesional=podologa, servicio=servicio, inicio=lunes + timedelta(days=1),
    )

    proximos = cliente.get(PANEL, {"fecha": jornada["fecha"]}).data["ocupacion"]["proximos"]

    assert len(proximos) == 7
    assert proximos[0]["porcentaje"] == pytest.approx(6.2, abs=0.1)
    assert proximos[5]["abierta"] is False and proximos[5]["porcentaje"] is None


@pytest.mark.django_db
def test_un_dia_vacio_no_rompe_el_panel(cliente, sede):
    # Un domingo o un día sin citas debe devolver ceros, no una división por
    # cero ni un `null` que la pantalla no sepa pintar.
    respuesta = cliente.get(PANEL, {"fecha": "2027-01-04"})

    assert respuesta.status_code == 200
    assert respuesta.data["citas"]["total"] == 0
    assert respuesta.data["ingresos"]["esperado"] == "0.00"
    assert respuesta.data["ingresos"]["ticket_promedio"] == "0.00"


# ------------------------------------------------------------- cuadrícula
@pytest.mark.django_db
def test_la_agenda_trae_el_horario_de_la_sede_ese_dia(cliente, sede):
    # La cuadrícula de P05 traza sus filas con este horario. Debe ser el mismo
    # que exige `programar_cita`: si no, la pantalla ofrecería huecos que el
    # servidor rechaza por fuera-de-horario. 2027-01-04 es lunes.
    respuesta = cliente.get(AGENDA, {"fecha": "2027-01-04"})

    assert respuesta.data["horario"] == {"apertura": "08:00", "cierre": "20:00"}


@pytest.mark.django_db
def test_un_dia_en_que_la_sede_no_abre_trae_horario_nulo(cliente, sede):
    # El domingo la sede del ejemplo no tiene horario: la pantalla debe saber
    # que está cerrada en vez de dibujar una cuadrícula vacía con horas
    # inventadas. 2027-01-03 es domingo.
    respuesta = cliente.get(AGENDA, {"fecha": "2027-01-03"})

    assert respuesta.status_code == 200
    assert respuesta.data["horario"] is None
