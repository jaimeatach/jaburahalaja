#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Examen semanal de Rab Yosef Tawil (nov/2026).

    python examen_tawil.py            muestra el examen de esta semana y lo deja copiado
                                      (Ctrl+V en WhatsApp); también lo guarda en C:\\OTZAR\\tawil\\
    python examen_tawil.py respuestas  las respuestas (para ti, no para el grupo)

Cada jueves se arma solo (en el repo, tools/otzar/examenes/tawil_<viernes>.txt):
6 preguntas de las clases que salieron esa semana, sacadas de lo que dice el Rab en cada audio:
3 fáciles, 1 media, 1 medio difícil y 1 muy difícil. Las respuestas van en tawil_<viernes>_respuestas.txt.
"""
import datetime as dt
import subprocess
import sys
import urllib.request
from pathlib import Path

RAMAS = ("claude/shiurim-halachot-shabbat-vriig5", "main")
RAW = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/{}/tools/otzar/examenes/{}"
API = "https://api.github.com/repos/jaimeatach/jaburahalaja/contents/tools/otzar/examenes/{}?ref={}"
CARPETA = Path(r"C:\OTZAR\tawil")


def bajar(nombre):
    for rama in RAMAS:
        for url, cab in ((API.format(nombre, rama), {"Accept": "application/vnd.github.raw"}),
                         (RAW.format(rama, nombre), {})):
            try:
                req = urllib.request.Request(url, headers=dict(cab, **{"User-Agent": "otzar-examen"}))
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.read().decode("utf-8")
            except Exception:
                continue
    return None


def main():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    resp = len(sys.argv) > 1 and sys.argv[1].lower().startswith("resp")
    hoy = dt.date.today()
    # el del viernes que viene (si ya está) o el del último viernes (Motzaei Shabat = el de ayer)
    proximo = hoy + dt.timedelta(days=(4 - hoy.weekday()) % 7)
    viernes = hoy - dt.timedelta(days=(hoy.weekday() - 4) % 7)
    texto, cual = None, None
    # lleva la fecha del viernes; se acepta también la del jueves (el examen se arma el jueves)
    for f in (proximo, proximo - dt.timedelta(days=1), viernes, viernes - dt.timedelta(days=1), viernes - dt.timedelta(days=7)):
        nombre = f"tawil_{f:%Y-%m-%d}{'_respuestas' if resp else ''}.txt"
        texto = bajar(nombre)
        if texto:
            cual = nombre
            break
    if not texto:
        print("Todavía no está el examen de esta semana (se arma el jueves en la mañana).")
        return 1
    esta = {f"tawil_{x:%Y-%m-%d}" for x in (proximo, proximo - dt.timedelta(days=1), viernes, viernes - dt.timedelta(days=1))}
    if cual and not any(cual.startswith(x) for x in esta):
        print(f"(OJO: el de esta semana aún no está; este es {cual})\n")
    print(texto)
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        (CARPETA / cual).write_text(texto, encoding="utf-8")
    except Exception:
        pass
    try:   # al portapapeles de Windows (clip entiende UTF-16)
        subprocess.run("clip", input=b"\xff\xfe" + texto.encode("utf-16-le"), shell=True, check=True)
        print("\n✓ Copiado: pégalo en WhatsApp con Ctrl+V")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
