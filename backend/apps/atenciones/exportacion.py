"""Exportación del registro diario a PDF y Excel (RF16, P22).

Capa de aplicación: arma el archivo desde `registro_del_rango`, la misma
consulta que pinta la pantalla P16, así que el total exportado no puede
diferir del que se ve. El archivo se genera en memoria y se entrega en la
respuesta; no se guarda en el servidor.

Cada exportación queda en la bitácora: es una salida de datos personales
(nombres de pacientes) fuera del sistema, y la Ley N.° 29733 obliga a poder
decir quién la hizo.
"""
import io
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.core.auditoria import registrar
from apps.core.errores import ReglaDeNegocio
from apps.sedes.models import Sede

from .servicios import registro_del_rango

FORMATOS = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
# Un mes de atenciones cabe en un archivo legible; más que eso es un
# respaldo, no un registro diario, y haría esperar a la persona.
MAXIMO_DE_DIAS = 31

# OWASP, «CSV Injection»: una celda de texto que empieza con uno de estos
# caracteres la hoja de cálculo la interpreta como fórmula. Un nombre de
# paciente como «=HYPERLINK(...)» se ejecutaría al abrir el archivo.
_INICIOS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")
_COLUMNAS = ["Fecha", "Hora", "Paciente", "Servicio", "Profesional", "Monto (S/)"]
_COLOR_MARCA = "3C5154"  # paleta oficial de Artemisa (docs/ESTADO.md)


@dataclass(frozen=True)
class Encabezado:
    centro: str
    sede: str
    desde: date
    hasta: date
    exportado_por: str
    exportado_en: datetime

    @property
    def periodo(self) -> str:
        if self.desde == self.hasta:
            return f"{self.desde:%d/%m/%Y}"
        return f"del {self.desde:%d/%m/%Y} al {self.hasta:%d/%m/%Y}"


def celda_segura(valor):
    """Neutraliza la inyección de fórmulas anteponiendo un apóstrofo.

    Solo afecta al texto: un monto es un número y no puede ser fórmula.
    """
    if isinstance(valor, str) and valor.startswith(_INICIOS_DE_FORMULA):
        return "'" + valor
    return valor


def _escapar(texto: str) -> str:
    """Paragraph de ReportLab interpreta etiquetas tipo XML: un nombre con «<»
    o «&» rompería el PDF o le cambiaría el formato. Se escapan esos tres."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def soles(monto) -> str:
    """Mismo formato que la pantalla P16 (`S/ 150.00`)."""
    return "—" if monto is None else f"S/ {monto:.2f}"


def exportar_registro(*, usuario, centro_id: int, sede_id: int, desde: date, hasta: date,
                      formato: str) -> tuple[bytes, str, str]:
    """Genera el archivo y devuelve (contenido, tipo MIME, nombre de archivo)."""
    if formato not in FORMATOS:
        raise ReglaDeNegocio("formato-no-soportado", "Elija exportar en PDF o en Excel.")
    if hasta < desde:
        raise ReglaDeNegocio("rango-invalido",
                             "La fecha final no puede ser anterior a la inicial.")
    if (hasta - desde).days + 1 > MAXIMO_DE_DIAS:
        raise ReglaDeNegocio("rango-demasiado-largo",
                             f"Exporte como máximo {MAXIMO_DE_DIAS} días a la vez.")

    # La sede llega de la cabecera X-Sede ya validada contra las asignaciones
    # del usuario; el filtro por centro es el segundo cerrojo, junto al RLS.
    sede = Sede.objects.select_related("centro").get(pk=sede_id, centro_id=centro_id)
    registro = registro_del_rango(centro_id=centro_id, sede_id=sede_id, desde=desde, hasta=hasta)
    atenciones = list(registro["atenciones"])
    encabezado = Encabezado(
        centro=sede.centro.nombre_comercial or sede.centro.razon_social,
        sede=sede.nombre, desde=desde, hasta=hasta,
        exportado_por=usuario.nombre_completo, exportado_en=timezone.localtime(),
    )
    generar = _pdf if formato == "pdf" else _xlsx
    contenido = generar(encabezado, atenciones, registro["total"], registro["sin_monto"])

    registrar("EXPORTACION", "registro_diario", sede_id, {
        "formato": formato, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "atenciones": len(atenciones), "total": f"{registro['total']:.2f}",
    })
    sufijo = desde.isoformat() if desde == hasta else f"{desde.isoformat()}_{hasta.isoformat()}"
    nombre = f"registro-diario_{slugify(sede.nombre) or 'sede'}_{sufijo}.{formato}"
    return contenido, FORMATOS[formato], nombre


def _filas(atenciones) -> list[list]:
    filas = []
    for atencion in atenciones:
        local = timezone.localtime(atencion.registrada_en)
        filas.append([local.date(), local.strftime("%H:%M"), atencion.paciente.nombre_completo,
                      atencion.servicio.nombre, atencion.profesional.nombre_completo,
                      atencion.monto_cobrado])
    return filas


def _por_dia(filas) -> "OrderedDict[date, tuple[int, Decimal]]":
    """Cantidad y total de cada día, desde las mismas filas del detalle."""
    dias: OrderedDict[date, tuple[int, Decimal]] = OrderedDict()
    for fila in filas:
        cantidad, total = dias.get(fila[0], (0, Decimal("0.00")))
        dias[fila[0]] = (cantidad + 1, total + (fila[5] or Decimal("0.00")))
    return dias


def _nota_sin_monto(sin_monto: int) -> str:
    return (f"{sin_monto} atención(es) registrada(s) antes de existir el monto cobrado no "
            "suman al total.")


# --- Excel ---------------------------------------------------------------------

def _xlsx(encabezado: Encabezado, atenciones, total: Decimal, sin_monto: int) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Registro diario"
    negrita = Font(bold=True)

    def fila_de_texto(*valores):
        hoja.append([celda_segura(v) for v in valores])

    fila_de_texto("Registro diario")
    hoja["A1"].font = Font(bold=True, size=14)
    fila_de_texto("Centro", encabezado.centro)
    fila_de_texto("Sede", encabezado.sede)
    fila_de_texto("Periodo", encabezado.periodo)
    fila_de_texto("Exportado por", encabezado.exportado_por)
    fila_de_texto("Exportado el", f"{encabezado.exportado_en:%d/%m/%Y %H:%M}")
    hoja.append([])

    hoja.append(_COLUMNAS)
    fila_titulos = hoja.max_row
    for celda in hoja[fila_titulos]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=_COLOR_MARCA)
    filas = _filas(atenciones)
    for fila in filas:
        hoja.append([celda_segura(v) for v in fila])
        hoja.cell(row=hoja.max_row, column=1).number_format = "dd/mm/yyyy"
        hoja.cell(row=hoja.max_row, column=6).number_format = "#,##0.00"

    # El total es la cifra del servidor, no una fórmula: así es idéntico al de
    # la pantalla aunque alguien ordene o filtre la hoja.
    hoja.append(["Total", None, f"{len(filas)} atención(es)", None, None, total])
    for celda in hoja[hoja.max_row]:
        celda.font = negrita
    hoja.cell(row=hoja.max_row, column=6).number_format = "#,##0.00"
    if sin_monto:
        fila_de_texto(_nota_sin_monto(sin_monto))

    if encabezado.desde != encabezado.hasta and filas:
        resumen = libro.create_sheet("Por día")
        resumen.append(["Fecha", "Atenciones", "Total (S/)"])
        for celda in resumen[1]:
            celda.font = negrita
        for dia, (cantidad, subtotal) in _por_dia(filas).items():
            resumen.append([dia, cantidad, subtotal])
            resumen.cell(row=resumen.max_row, column=1).number_format = "dd/mm/yyyy"
            resumen.cell(row=resumen.max_row, column=3).number_format = "#,##0.00"

    for letra, ancho in zip("ABCDEF", [12, 8, 32, 28, 28, 12], strict=True):
        hoja.column_dimensions[letra].width = ancho
    hoja.cell(row=fila_titulos, column=6).alignment = Alignment(horizontal="right")
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


# --- PDF -----------------------------------------------------------------------

def _pdf(encabezado: Encabezado, atenciones, total: Decimal, sin_monto: int) -> bytes:
    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"Registro diario {encabezado.sede} {encabezado.periodo}",
        author=encabezado.centro,
    )
    estilos = getSampleStyleSheet()
    normal, celda = estilos["Normal"], estilos["BodyText"]
    celda.fontSize, celda.leading = 8.5, 10.5

    def texto(valor, estilo=celda):
        # Paragraph interpreta etiquetas: el texto de los datos se escapa.
        return Paragraph(_escapar(str(valor)), estilo)

    contenido = [
        Paragraph("Registro diario", estilos["Title"]),
        texto(f"Centro: {encabezado.centro}", normal),
        texto(f"Sede: {encabezado.sede}", normal),
        texto(f"Periodo: {encabezado.periodo}", normal),
        texto(f"Exportado por {encabezado.exportado_por} el "
              f"{encabezado.exportado_en:%d/%m/%Y %H:%M}", normal),
        Spacer(1, 6 * mm),
    ]
    filas = _filas(atenciones)
    datos = [_COLUMNAS]
    for fila in filas:
        datos.append([f"{fila[0]:%d/%m/%Y}", fila[1], texto(fila[2]), texto(fila[3]),
                      texto(fila[4]), soles(fila[5])])
    if not filas:
        datos.append(["No hay atenciones registradas en esta sede para el periodo.",
                      "", "", "", "", ""])
    datos.append(["Total", "", f"{len(filas)} atención(es)", "", "", soles(total)])

    tabla = Table(datos, repeatRows=1,
                  colWidths=[20 * mm, 13 * mm, 45 * mm, 42 * mm, 38 * mm, 22 * mm])
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{_COLOR_MARCA}")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#EEF2F0")]),
    ]
    if not filas:
        estilo.append(("SPAN", (0, 1), (-1, 1)))
    tabla.setStyle(TableStyle(estilo))
    contenido.append(tabla)
    if sin_monto:
        contenido += [Spacer(1, 3 * mm), texto(_nota_sin_monto(sin_monto), normal)]

    if encabezado.desde != encabezado.hasta and filas:
        resumen = [["Fecha", "Atenciones", "Total"]] + [
            [f"{dia:%d/%m/%Y}", str(cantidad), soles(subtotal)]
            for dia, (cantidad, subtotal) in _por_dia(filas).items()
        ]
        por_dia = Table(resumen, colWidths=[30 * mm, 25 * mm, 30 * mm], hAlign="LEFT")
        por_dia.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ]))
        contenido += [Spacer(1, 6 * mm), Paragraph("Por día", estilos["Heading3"]), por_dia]

    def numerar(lienzo, doc):
        lienzo.setFont("Helvetica", 8)
        lienzo.drawRightString(A4[0] - 15 * mm, 8 * mm, f"Página {doc.page}")

    documento.build(contenido, onFirstPage=numerar, onLaterPages=numerar)
    return salida.getvalue()
