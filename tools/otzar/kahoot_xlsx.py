"""Arma el Excel para importar en Kahoot desde un examen en JSON.

Uso: python kahoot_xlsx.py examenes/kahoot_tawil.json
Deja el .xlsx junto al .json, con el formato de la plantilla de Kahoot
(encabezados en la fila 8, preguntas desde la fila 9; pregunta máx. 120
caracteres, respuestas máx. 75, tiempo 5/10/20/30/60/90/120/240 s).
"""
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

TIEMPOS = {5, 10, 20, 30, 60, 90, 120, 240}


def armar(ruta_json):
    ruta = Path(ruta_json)
    examen = json.loads(ruta.read_text(encoding='utf-8'))
    wb = Workbook()
    ws = wb.active
    ws.title = 'Sheet1'
    ws['B2'] = examen['titulo']
    ws['B2'].font = Font(bold=True, size=14)
    ws['B3'] = 'Plantilla de Kahoot: no cambiar las columnas ni la fila 8.'
    encabezados = ['Question - max 120 characters', 'Answer 1 - max 75 characters',
                   'Answer 2 - max 75 characters', 'Answer 3 - max 75 characters',
                   'Answer 4 - max 75 characters',
                   'Time limit (sec) – 5, 10, 20, 30, 60, 90, 120, or 240 secs',
                   'Correct answer(s) - choose at least one']
    for col, texto in enumerate(encabezados, start=2):
        c = ws.cell(row=8, column=col, value=texto)
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True)
    for i, p in enumerate(examen['preguntas'], start=1):
        assert len(p['pregunta']) <= 120, (i, len(p['pregunta']))
        assert len(p['opciones']) == 4 and all(len(o) <= 75 for o in p['opciones']), i
        assert p['tiempo'] in TIEMPOS and 1 <= p['correcta'] <= 4, i
        fila = 8 + i
        ws.cell(row=fila, column=1, value=i)
        ws.cell(row=fila, column=2, value=p['pregunta'])
        for j, o in enumerate(p['opciones']):
            ws.cell(row=fila, column=3 + j, value=o)
        ws.cell(row=fila, column=7, value=p['tiempo'])
        ws.cell(row=fila, column=8, value=p['correcta'])
    for col, ancho in zip('ABCDEFGH', (4, 60, 35, 35, 35, 35, 14, 14)):
        ws.column_dimensions[col].width = ancho
    salida = ruta.with_suffix('.xlsx')
    wb.save(salida)
    return salida


if __name__ == '__main__':
    print(armar(sys.argv[1]))
