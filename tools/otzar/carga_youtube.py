#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carga inicial de un show de YouTube (nov/2026; Rab Biderman, los últimos 300).

    python carga_youtube.py biderman

Corre el podcast_bot.py del show una y otra vez, sin parar, hasta que ya no queda nada
por bajar. Cada vuelta baja unos 15 min de videos (del más nuevo al más viejo), los sube a
archive.org y al feed. Si se apaga o se reinicia la PC, sigue sola al prender: el
instalador deja OTZAR_carga_<show>.cmd en la carpeta Inicio de Windows; al terminar, este
script lo quita, baja la revisión a los últimos 20 (para que ACTUALIZAR sea ligero) y deja
CARGA_TERMINADA.txt en la carpeta del show.
Nada en Shabat ni Yom Tov (el mismo candado del piloto). Log en <show>\\carga.log.
"""
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(r"C:\OTZAR")
SHOW = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
D = BASE / SHOW
LOG = D / "carga.log"
LOCK = D / "carga.lock"
INICIO = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
FINAL_ULTIMOS = 20


def log(m):
    linea = f"[{dt.datetime.now():%d/%m %H:%M}] {m}"
    print(linea, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def _bloqueo_piloto():
    """bloqueo() del piloto (Shabat/Yom Tov con la puesta del sol de CDMX)."""
    p = BASE / "jabura" / "piloto.py"
    if p.exists():
        try:
            argv = sys.argv
            sys.argv = [str(p)]
            spec = importlib.util.spec_from_file_location("piloto_otzar", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            sys.argv = argv
            return m.bloqueo
        except Exception as e:                       # noqa: BLE001
            sys.argv = argv
            log(f"no pude usar el candado del piloto ({e}); uso uno sencillo")

    def sencillo(ahora):                             # viernes 16:00 → sábado 21:00
        if ahora.weekday() == 4 and ahora.hour >= 16:
            return "Erev Shabat"
        if ahora.weekday() == 5 and ahora.hour < 21:
            return "Shabat"
        return None
    return sencillo


def otra_carga_viva():
    try:
        return LOCK.exists() and time.time() - LOCK.stat().st_mtime < 5 * 60
    except OSError:
        return False


def refrescar_lock():
    while True:
        try:
            LOCK.write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            pass
        time.sleep(60)


def una_vuelta():
    """Corre podcast_bot.py una vez. Devuelve (por_bajar, bajados, otra_ventana)."""
    por_bajar = bajados = None
    otra = False
    try:
        proc = subprocess.Popen([sys.executable, "podcast_bot.py"], cwd=str(D), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for ln in proc.stdout:
            ln = ln.rstrip()
            print(ln, flush=True)
            m = re.search(r"(\d+) en el canal, (\d+) por bajar", ln)
            if m and int(m.group(1)) > 0:           # 0 en el canal = YouTube no contestó, no "ya terminé"
                por_bajar = int(m.group(2))
            m = re.search(r"Videos nuevos bajados: (\d+)", ln)
            if m:
                bajados = int(m.group(1))
            if "Ya hay otra ventana" in ln:
                otra = True
            if any(x in ln for x in ("bajando:", "publicado(s)", "ERROR", "Fallo", "TOPE")):
                try:
                    with open(LOG, "a", encoding="utf-8") as f:
                        f.write(ln + "\n")
                except OSError:
                    pass
        proc.wait(timeout=60)
    except Exception as e:                           # noqa: BLE001
        log(f"podcast_bot.py: {e}")
    return por_bajar, bajados, otra


def terminar():
    cfgp = D / "config.json"
    try:
        c = json.loads(cfgp.read_text(encoding="utf-8"))
        for ch in c.get("canales_youtube") or []:
            if isinstance(ch, dict):
                ch["revisar_ultimos"] = FINAL_ULTIMOS
        c["revisar_ultimos"] = FINAL_ULTIMOS
        cfgp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:                           # noqa: BLE001
        log(f"no pude bajar la revisión a {FINAL_ULTIMOS} ({e})")
    try:
        (INICIO / f"OTZAR_carga_{SHOW}.cmd").unlink()
    except OSError:
        pass
    (D / "CARGA_TERMINADA.txt").write_text(f"Carga inicial terminada {dt.datetime.now():%d/%m/%Y %H:%M}\n", encoding="utf-8")
    log(f"=== CARGA TERMINADA: ya no queda nada por bajar. Desde ahora lo nuevo lo baja ACTUALIZAR "
        f"(revisa los últimos {FINAL_ULTIMOS}). Ya no se abre al prender la PC. ===")


def main():
    if not SHOW or not (D / "podcast_bot.py").exists():
        print(f"no encuentro {D / 'podcast_bot.py'}")
        return
    if (D / "CARGA_TERMINADA.txt").exists():
        log("la carga ya había terminado")
        terminar()
        return
    if otra_carga_viva():
        print("ya hay otra ventana con la carga de este show; esta se cierra")
        return
    threading.Thread(target=refrescar_lock, daemon=True).start()
    bloqueo = _bloqueo_piloto()
    log(f"=== CARGA INICIAL de {SHOW}: no para hasta tener todo (puedes minimizar esta ventana) ===")
    sin_nada = 0
    while True:
        b = bloqueo(dt.datetime.now())
        if b:
            log(f"{b}: no se baja nada; sigo después")
            time.sleep(15 * 60)
            continue
        por_bajar, bajados, otra = una_vuelta()
        if otra:
            time.sleep(5 * 60)                       # el piloto lo está corriendo; espero
            continue
        if por_bajar == 0:
            terminar()
            return
        sin_nada = sin_nada + 1 if not bajados else 0
        if sin_nada >= 3 and por_bajar is not None:
            # 3 vueltas sin bajar nada: lo que queda no se puede (privado, en vivo, muy largo)
            log(f"3 vueltas sin bajar nada ({por_bajar} que YouTube no deja bajar); doy la carga por terminada")
            terminar()
            return
        log(f"vuelta lista: {bajados or 0} nuevo(s), faltan {por_bajar if por_bajar is not None else '?'}")
        time.sleep(60 if bajados else 5 * 60)        # sin internet o sin nada: espera un poco más


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            if LOCK.exists() and LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK.unlink()
        except OSError:
            pass
