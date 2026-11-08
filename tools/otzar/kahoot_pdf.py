"""PDF del Kahoot para revisar con el Rab: cada pregunta con sus 4 opciones,
la correcta marcada en verde y la explicación de lo que dijo en la clase.

Uso: python kahoot_pdf.py examenes/kahoot_tawil.json  (deja el .pdf al lado)
"""
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FUENTES = '/usr/share/fonts/truetype/dejavu/'
pdfmetrics.registerFont(TTFont('DV', FUENTES + 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DVB', FUENTES + 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFontFamily('DV', normal='DV', bold='DVB', italic='DV', boldItalic='DVB')

VERDE = colors.HexColor('#1e7b3a')
FONDO_VERDE = colors.HexColor('#e3f4e8')
GRIS = colors.HexColor('#555555')
NIVELES = {'facil': 'Fácil', 'media': 'Intermedia', 'medio_dificil': 'Medio difícil',
           'dificil': 'Difícil', 'muy_dificil': 'Muy difícil'}

titulo = ParagraphStyle('t', fontName='DVB', fontSize=17, leading=21, spaceAfter=4)
sub = ParagraphStyle('s', fontName='DV', fontSize=10, leading=13, textColor=GRIS, spaceAfter=10)
preg = ParagraphStyle('p', fontName='DVB', fontSize=11, leading=14, spaceAfter=4)
meta = ParagraphStyle('m', fontName='DV', fontSize=8.5, leading=11, textColor=GRIS)
op = ParagraphStyle('o', fontName='DV', fontSize=10, leading=13)
op_ok = ParagraphStyle('ok', parent=op, fontName='DVB', textColor=VERDE)
expl = ParagraphStyle('e', fontName='DV', fontSize=9, leading=12, textColor=GRIS, spaceBefore=4)


def armar(ruta_json):
    ruta = Path(ruta_json)
    examen = json.loads(ruta.read_text(encoding='utf-8'))
    salida = ruta.with_suffix('.pdf')
    doc = SimpleDocTemplate(str(salida), pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=examen['titulo'])
    hist = [Paragraph(escape(examen['titulo']), titulo),
            Paragraph(escape(examen['descripcion']) + '<br/>La respuesta correcta está en verde con ✔.', sub)]
    for i, p in enumerate(examen['preguntas'], 1):
        filas = []
        for j, o in enumerate(p['opciones']):
            ok = j + 1 == p['correcta']
            marca = '✔' if ok else '○'
            filas.append([Paragraph(marca, op_ok if ok else op),
                          Paragraph(f"{'ABCD'[j]}) {escape(o)}", op_ok if ok else op)])
        tabla = Table(filas, colWidths=[0.7 * cm, 16.3 * cm])
        estilo = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 2),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
        estilo.append(('BACKGROUND', (0, p['correcta'] - 1), (-1, p['correcta'] - 1), FONDO_VERDE))
        tabla.setStyle(TableStyle(estilo))
        bloque = [Paragraph(f"{i}. {escape(p['pregunta'])}", preg),
                  Paragraph(f"Shiur #{p['shiur']} · {NIVELES.get(p['nivel'], p['nivel'])} · {p['tiempo']} s", meta),
                  Spacer(1, 3), tabla,
                  Paragraph('<b>Lo que dijo el Rab:</b> ' + escape(p['explicacion']), expl),
                  Spacer(1, 12)]
        hist.append(KeepTogether(bloque))
    doc.build(hist)
    return salida


if __name__ == '__main__':
    print(armar(sys.argv[1]))
