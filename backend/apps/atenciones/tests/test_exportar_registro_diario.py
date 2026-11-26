"""Pruebas de la exportación del registro diario a PDF y Excel (RF16, P22).

Lo que se garantiza: que los dos archivos se abren, que su total es el
mismo que el de la pantalla para el mismo conjunto de atenciones, que una
sede no exporta datos de otra, que un nombre malicioso no se ejecuta como
fórmula en la hoja de cálculo y que cada exportación queda auditada.
"""
import base64
import io
import re
import zlib
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.atenciones.exportacion import celda_segura
from apps.atenciones.models import Atencion
from apps.atenciones.servicios import registrar_atencion
from apps.citas.servicios import programar_cita
from apps.core.models import RegistroAuditoria
from apps.core.soporte_pruebas import hacer_que_la_cita_ya_empezo
from apps.pacientes.servicios import registrar_paciente
from apps.sedes.models import HorarioSede, Sede
from apps.usuarios.models import AsignacionSede

EXPORTAR = "/api/v1/reportes/registro-diario/exportar/"
REGISTRO = "/api/v1/reportes/registro-diario/"


@pytest.fixture
def atender(centro, podologa, servicio, paciente, proximo_lunes_a_las_nueve):
    """Programa, adelanta y atiende una cita; devuelve la atención."""
    def _atender(sede, monto, quien=None):
        cita = hacer_que_la_cita_ya_empezo(programar_cita(
            centro=centro, usuario=podologa, sede=sede, paciente=quien or paciente,
            profesional=podologa, servicio=servicio, inicio=proximo_lunes_a_las_nueve,
        ))
        return registrar_atencion(centro=centro, usuario=podologa, sede_id=sede.pk,
                                  cita_id=cita.pk, monto_cobrado=Decimal(monto))
    return _atender


@pytest.fixture
def otra_sede(centro):
    sede = Sede.objects.create(centro=centro, nombre="Yanahuara", direccion="Av. Lima 456")
    for dia in range(0, 6):
        HorarioSede.objects.create(sede=sede, dia_semana=dia,
                                   hora_apertura="08:00", hora_cierre="20:00")
    return sede


@pytest.fixture
def cliente(podologa, sede):
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(sede.pk))
    return cliente


def _texto_del_pdf(contenido: bytes) -> str:
    """Texto de las secuencias de contenido del PDF.

    ReportLab las codifica en ASCII85 y luego las comprime (filtros
    /ASCII85Decode /FlateDecode): se deshacen los dos pasos.
    """
    partes = []
    for flujo in re.findall(rb"stream\r?\n(.*?)~>\s*endstream", contenido, re.S):
        try:
            partes.append(zlib.decompress(base64.a85decode(flujo)).decode("latin-1"))
        except (ValueError, zlib.error):
            continue  # una imagen u otro flujo que no es texto
    return "\n".join(partes)


def _hoja(contenido: bytes):
    return load_workbook(io.BytesIO(contenido))["Registro diario"]


def _total_de_la_hoja(hoja):
    fila_total = next(f for f in hoja.iter_rows() if f[0].value == "Total")
    return Decimal(str(fila_total[5].value))


@pytest.mark.django_db
def test_el_pdf_es_un_archivo_pdf_valido_con_el_encabezado(cliente, sede, atender, centro,
                                                           podologa):
    # El archivo tiene que abrirse en cualquier visor y decir de qué centro,
    # sede y día es, y quién lo sacó: impreso, no hay otra forma de saberlo.
    atender(sede, "60.00")

    respuesta = cliente.get(EXPORTAR, {"formato": "pdf"})

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/pdf"
    assert respuesta["Content-Disposition"].startswith("attachment;")
    assert respuesta.content.startswith(b"%PDF-")
    assert respuesta.content.rstrip().endswith(b"%%EOF")
    texto = _texto_del_pdf(respuesta.content)
    for esperado in ["Registro diario", sede.nombre, f"{date.today():%d/%m/%Y}",
                     "Exportado por"]:
        assert esperado in texto


@pytest.mark.django_db
def test_el_excel_es_un_libro_valido_con_el_encabezado(cliente, sede, atender, centro, podologa):
    # Se comprueba abriéndolo con la misma biblioteca que leería cualquier
    # hoja de cálculo: si el archivo estuviera mal formado, fallaría aquí.
    atender(sede, "60.00")

    respuesta = cliente.get(EXPORTAR, {"formato": "xlsx"})

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"].startswith("application/vnd.openxmlformats")
    hoja = _hoja(respuesta.content)
    encabezado = {fila[0].value: fila[1].value for fila in hoja.iter_rows(max_row=6)}
    assert encabezado["Centro"] == centro.razon_social
    assert encabezado["Sede"] == sede.nombre
    assert encabezado["Periodo"] == f"{date.today():%d/%m/%Y}"
    assert encabezado["Exportado por"] == podologa.nombre_completo


@pytest.mark.django_db
def test_el_total_exportado_es_el_mismo_que_el_de_la_pantalla(cliente, sede, atender):
    # Con las mismas atenciones, la pantalla P16, el Excel y el PDF dan la
    # misma cifra. Si el archivo calculara por su cuenta, la caja impresa
    # podría no cuadrar con la del sistema.
    for monto in ["60.00", "45.50", "120.25"]:
        atender(sede, monto)
    en_pantalla = cliente.get(REGISTRO).data

    excel = cliente.get(EXPORTAR, {"formato": "xlsx"}).content
    pdf = cliente.get(EXPORTAR, {"formato": "pdf"}).content

    assert en_pantalla["total"] == "225.75"
    assert _total_de_la_hoja(_hoja(excel)) == Decimal(en_pantalla["total"])
    assert f"S/ {en_pantalla['total']}" in _texto_del_pdf(pdf)
    filas_de_atencion = [f for f in _hoja(excel).iter_rows(min_row=9) if f[2].value
                         and f[0].value != "Total"]
    assert len(filas_de_atencion) == en_pantalla["cantidad"] == 3


@pytest.mark.django_db
def test_el_rango_suma_lo_mismo_que_los_dias_por_separado(cliente, sede, atender):
    # El total del rango es la suma de los registros diarios de cada día:
    # se mueve una atención a ayer y se compara contra las dos pantallas.
    atender(sede, "60.00")
    ayer = atender(sede, "40.00")
    Atencion.objects.filter(pk=ayer.pk).update(
        registrada_en=ayer.registrada_en - timedelta(days=1))
    hoy = timezone.localdate()
    por_dia = sum(Decimal(cliente.get(REGISTRO, {"fecha": d.isoformat()}).data["total"])
                  for d in (hoy - timedelta(days=1), hoy))

    excel = cliente.get(EXPORTAR, {"formato": "xlsx", "desde": (hoy - timedelta(days=1)),
                                   "hasta": hoy}).content

    assert _total_de_la_hoja(_hoja(excel)) == por_dia == Decimal("100.00")
    resumen = load_workbook(io.BytesIO(excel))["Por día"]
    assert [fila[1].value for fila in resumen.iter_rows(min_row=2)] == [1, 1]


@pytest.mark.django_db
@pytest.mark.parametrize("formato", ["pdf", "xlsx"])
def test_un_rango_sin_atenciones_exporta_un_archivo_con_total_cero(cliente, formato):
    # Un día sin atenciones también se exporta: es la constancia de que la
    # sede no cobró nada, no un error.
    respuesta = cliente.get(EXPORTAR, {"formato": formato, "desde": "2026-01-05",
                                       "hasta": "2026-01-09"})

    assert respuesta.status_code == 200
    if formato == "xlsx":
        assert _total_de_la_hoja(_hoja(respuesta.content)) == Decimal("0")
    else:
        assert "No hay atenciones" in _texto_del_pdf(respuesta.content)
        assert "S/ 0.00" in _texto_del_pdf(respuesta.content)


@pytest.mark.django_db
def test_solo_exporta_la_sede_activa(cliente, sede, otra_sede, podologa, atender):
    # Las atenciones de otra sede del mismo centro no entran en el archivo,
    # aunque la podóloga trabaje en las dos.
    AsignacionSede.objects.create(usuario=podologa, sede=otra_sede)
    atender(sede, "60.00")
    atender(otra_sede, "999.00")

    hoja = _hoja(cliente.get(EXPORTAR, {"formato": "xlsx"}).content)

    assert _total_de_la_hoja(hoja) == Decimal("60.00")


@pytest.mark.django_db
def test_una_sede_no_asignada_no_se_puede_exportar(podologa, otra_sede, atender):
    # Poner en la cabecera el número de una sede ajena no sirve: el servidor
    # solo acepta las sedes asignadas al usuario y responde con el código
    # estable, sin generar ningún archivo.
    cliente = APIClient()
    cliente.force_authenticate(user=podologa)
    cliente.credentials(HTTP_X_SEDE=str(otra_sede.pk))

    respuesta = cliente.get(EXPORTAR, {"formato": "pdf"})

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == "sin-sede-activa"
    assert respuesta["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
def test_la_sede_de_otro_centro_tampoco(cliente, podologa, otro_centro):
    # Aislamiento entre inquilinos: la sede de otro centro no es asignable y
    # el RLS no la deja ver, así que el resultado es el mismo que arriba.
    from apps.core.soporte_pruebas import activar_centro

    activar_centro(otro_centro.pk)
    ajena = Sede.objects.create(centro=otro_centro, nombre="Norte", direccion="Av. Perú 1")
    activar_centro(podologa.centro_id)
    cliente.credentials(HTTP_X_SEDE=str(ajena.pk))

    respuesta = cliente.get(EXPORTAR, {"formato": "xlsx"})

    assert respuesta.data["codigo"] == "sin-sede-activa"


@pytest.mark.django_db
def test_un_nombre_con_formula_no_se_ejecuta_en_el_excel(cliente, centro, podologa, sede,
                                                         atender):
    # OWASP, «CSV Injection»: quien registre a un paciente con un nombre como
    # «=HYPERLINK(...)» no debe lograr que la hoja lo ejecute al abrirla. La
    # celda tiene que quedar como texto, con el apóstrofo delante.
    malicioso = registrar_paciente(
        centro=centro, usuario=podologa,
        datos={"tipo_documento": "DNI", "documento": "40999888",
               "nombres": '=HYPERLINK("http://ejemplo.invalid","x")', "apellidos": "Prueba",
               "telefono": "958000111"},
        consentimiento={"acepta_tratamiento_datos": True, "acepta_recordatorios": False},
    )
    atender(sede, "10.00", quien=malicioso)

    hoja = _hoja(cliente.get(EXPORTAR, {"formato": "xlsx"}).content)

    celda = next(f[2] for f in hoja.iter_rows() if f[2].value and "HYPERLINK" in f[2].value)
    assert celda.data_type == "s"
    assert celda.value.startswith("'=")


@pytest.mark.parametrize(("valor", "esperado"), [
    ("=1+1", "'=1+1"), ("+51 958", "'+51 958"), ("-2", "'-2"), ("@SUMA", "'@SUMA"),
    ("\tx", "'\tx"), ("Carmen", "Carmen"), (Decimal("-5.00"), Decimal("-5.00")),
])
def test_neutraliza_los_inicios_de_formula_y_deja_los_numeros(valor, esperado):
    # Los seis inicios que la hoja interpreta como fórmula. Un monto negativo
    # es un número y no se toca: anteponerle un apóstrofo lo volvería texto y
    # rompería las sumas de quien use el archivo.
    assert celda_segura(valor) == esperado


@pytest.mark.django_db
def test_cada_exportacion_queda_en_la_auditoria(cliente, sede, atender, podologa):
    # Sacar del sistema nombres de pacientes es un tratamiento de datos
    # personales: tiene que poder decirse quién lo hizo, cuándo y qué salió.
    atender(sede, "60.00")

    cliente.get(EXPORTAR, {"formato": "pdf"})
    cliente.get(EXPORTAR, {"formato": "xlsx"})

    registros = RegistroAuditoria.objects.filter(accion="EXPORTACION", entidad="registro_diario")
    assert [r.datos["formato"] for r in registros.order_by("ocurrido_en", "id")] == ["pdf", "xlsx"]
    assert {r.usuario_id for r in registros} == {podologa.pk}
    assert registros.first().datos["total"] == "60.00"


@pytest.mark.django_db
@pytest.mark.parametrize(("parametros", "codigo"), [
    ({"formato": "csv"}, "formato-no-soportado"),
    ({"formato": "pdf", "desde": "2026-03-10", "hasta": "2026-03-01"}, "rango-invalido"),
    ({"formato": "pdf", "desde": "2026-01-01", "hasta": "2026-03-01"}, "rango-demasiado-largo"),
    ({"formato": "pdf", "fecha": "10/03/2026"}, "fecha-invalida"),
])
def test_los_parametros_invalidos_se_rechazan_con_su_codigo(cliente, parametros, codigo):
    # Cada caso tiene su código estable para que la interfaz explique qué
    # corregir, en lugar de descargar un archivo vacío o fallar con un 500.
    respuesta = cliente.get(EXPORTAR, parametros)

    assert respuesta.status_code == 422
    assert respuesta.data["codigo"] == codigo


@pytest.mark.django_db
def test_un_nombre_con_marcas_no_rompe_el_pdf(cliente, centro, podologa, sede, atender):
    # El PDF interpreta «<» y «&» como etiquetas: sin escaparlos, un nombre
    # así haría fallar la exportación entera o cambiaría el formato del texto.
    raro = registrar_paciente(
        centro=centro, usuario=podologa,
        datos={"tipo_documento": "DNI", "documento": "40999777", "nombres": "Ana <b> & Co",
               "apellidos": "Prueba", "telefono": "958000222"},
        consentimiento={"acepta_tratamiento_datos": True, "acepta_recordatorios": False},
    )
    atender(sede, "10.00", quien=raro)

    respuesta = cliente.get(EXPORTAR, {"formato": "pdf"})

    assert respuesta.status_code == 200
    # Sin escapar, «<b>» sería una etiqueta de negrita y no aparecería escrito.
    # ReportLab parte la línea en varios trozos de texto: se juntan.
    trozos = re.findall(r"\(((?:\\.|[^\\)])*)\) Tj", _texto_del_pdf(respuesta.content))
    assert "Ana <b> &" in "".join(trozos)
