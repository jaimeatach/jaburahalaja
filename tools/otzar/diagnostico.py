#!/usr/bin/env python3
"""Por qué no salió un shiur: qué vio el robot de ese show en los últimos días.

    python diagnostico.py hilu [dias]

Muestra (sin tocar nada): las líneas del log del robot que hablan del show o de
su grupo fuente, los arranques y caídas del robot, los audios en su carpeta, los
que quedaron esperando título y lo último que tiene su feed.
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROBOT = Path(r"C:\robotwhats")
BASE = Path(r"C:\OTZAR")


def leer_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    show = sys.argv[1].lower()
    dias = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    cfg = leer_json(ROBOT / "config_whatsapp.json")
    reg = leer_json(ROBOT / "grupos_registrados.json")
    fuente = (reg.get("escucha:" + show) or {}).get("nombre", "")
    carpeta = ((cfg.get("escuchar") or {}).get(show) or {}).get("carpetaDestino") or str(BASE / show / "audios_whatsapp")
    print(f"=== {show}: grupo fuente = {fuente or '(sin registrar)'} · carpeta = {carpeta}")

    # días en el formato del log del robot (es-MX): [10/10/2026, ...]
    fechas = []
    for i in range(dias):
        d = date.today() - timedelta(days=i)
        fechas.append(f"[{d.day}/{d.month}/{d.year},")
    claves = [show, "SIN AUDIO", "IGNORADO", "Audio recibido", "No pude", "descarga intento",
              "ERROR mensaje", "Reconectando", "ROBOT LISTO", "rechazo la sesion",
              "Conexion cerrada", "OTRA VENTANA", "OTRO ROBOT",
              "Error guardando", "No pude guardar", "no pude respaldar"]
    if fuente:
        claves.append(fuente[:20])
    for g in ((reg.get(show) or {}).get("grupos") or [reg.get(show) or {}]):   # sus grupos de anuncio
        if g.get("nombre"):
            claves.append(g["nombre"][:20])
    claves = [c.lower() for c in claves]
    print(f"\n--- log del robot, últimos {dias} días ---")
    try:
        lineas = (ROBOT / "robot_whatsapp.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as ex:
        lineas = []
        print(f"no pude leer el log: {ex}")
    vistas = [l for l in lineas if l.startswith(tuple(fechas)) and any(c in l.lower() for c in claves)
              and "ya identificado" not in l]
    salida, repetidas = [], 0
    for l in vistas:
        if "ROBOT LISTO" in l and salida and "ROBOT LISTO" in salida[-1]:
            repetidas += 1
            continue
        if repetidas:
            salida.append(f"   (... y {repetidas} arranques más seguidos: ¿dos ventanas del robot?)")
            repetidas = 0
        salida.append(l)
    if repetidas:
        salida.append(f"   (... y {repetidas} arranques más seguidos: ¿dos ventanas del robot?)")
    for l in salida[-120:]:
        print(l[:220])
    if not vistas:
        print("(nada)")

    print("\n--- últimos audios en su carpeta ---")
    try:
        arch = sorted(Path(carpeta).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:6]
        for a in arch:
            print(time.strftime("%d/%m %H:%M", time.localtime(a.stat().st_mtime)), a.name[:110])
        if not arch:
            print("(vacía)")
    except Exception as ex:
        print(f"no pude leer la carpeta: {ex}")

    print("\n--- esperando título ---")
    esp = [p for p in (ROBOT / "audios_esperando_titulo").glob(show + "__*")] if (ROBOT / "audios_esperando_titulo").exists() else []
    print("\n".join(p.name for p in esp) or "(ninguno)")

    print("\n--- lo último del feed ---")
    c = leer_json(BASE / show / "config.json")
    datos = (cfg.get("anunciar") or {}).get(show) or {}
    url = datos.get("feed") if str(datos.get("feed", "")).startswith("http") else \
        f"https://raw.githubusercontent.com/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}/main/feed.xml"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "otzar"}), timeout=30) as r:
            x = r.read().decode("utf-8", "replace")
        its = re.findall(r"<item>([\s\S]*?)</item>", x)
        for it in its[-3:]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            print((d.group(1)[:22] if d else "-"), "|", (t.group(1)[:100] if t else "-"))
    except Exception as ex:
        print(f"no pude leer el feed ({url}): {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
