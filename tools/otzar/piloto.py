#!/usr/bin/env python3
"""PILOTO AUTOMÁTICO de Otzar HaTorah: hace solo lo de los botones, sin que nadie apriete.

Se abre con PILOTO.bat (junto al robot) y se deja la ventana abierta, igual que el robot.
Cada 5 minutos:
  1. ¿El robot guardó un audio nuevo (WhatsApp, cualquier show)? → corre el mantenimiento
     (lo mismo que ANUNCIAR.bat: sube a archive.org, arma el feed, Spotify lo toma de ahí).
     Aunque no haya nada nuevo, el mantenimiento corre una vez por hora (correo, parashá...).
  2. Cada 30 minutos: los shows de YouTube (lo del botón ACTUALIZAR): baja y publica lo nuevo.
  3. Después de publicar, y cada 15 minutos, le da la orden "anunciar" al robot. El robot
     solo manda lo que ya tiene su link exacto de Spotify (si todavía no, lo reintenta en la
     siguiente vuelta), y nunca repite.
Nunca en Shabat ni en Yom Tov (desde el viernes / la víspera a las 16:00 hasta la medianoche
del día) y nunca de noche (anuncios solo de 5:30 a 22:00). Para pausarlo: crea el archivo
C:\\OTZAR\\PILOTO_PAUSA.txt (o cierra la ventana). Ajustes en C:\\OTZAR\\jabura\\piloto.json.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
    if a.startswith("--robot="):
        ROBOT = Path(a.split("=", 1)[1])
JAB = BASE / "jabura"
LOG = BASE / "piloto.log"
LOCK = BASE / "piloto.lock"
PAUSA = BASE / "PILOTO_PAUSA.txt"
ESTADO = JAB / "piloto_estado.json"
AUDIO = (".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".amr", ".pdf", ".doc", ".docx")
AJUSTES = {"cada_min": 5, "mantenimiento_min": 60, "youtube_min": 30, "anuncio_min": 15,
           "desde": "05:30", "hasta": "22:00", "youtube": True, "timeout_show_min": 20}
# Yom Tov de la diáspora (sale de @hebcal/core; lo mismo que usa el robot)
YOM_TOV = {"2026-10-03", "2026-10-04", "2027-04-22", "2027-04-23", "2027-04-28", "2027-04-29",
           "2027-06-11", "2027-06-12", "2027-10-02", "2027-10-03", "2027-10-11", "2027-10-16",
           "2027-10-17", "2027-10-23", "2027-10-24", "2028-04-11", "2028-04-12", "2028-04-17",
           "2028-04-18", "2028-05-31", "2028-06-01", "2028-09-21", "2028-09-22", "2028-09-30"}

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(m):
    linea = f"[{time.strftime('%d/%m %H:%M:%S')}] {m}"
    print(linea, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {} if defecto is None else defecto


def ajustes():
    a = dict(AJUSTES)
    a.update(leer_json(JAB / "piloto.json"))
    return a


def bloqueo(ahora):
    """Shabat / Yom Tov: desde las 16:00 de la víspera hasta la medianoche del día."""
    d = ahora.date()
    if d.weekday() == 5:
        return "Shabat"
    if d.isoformat() in YOM_TOV:
        return "Yom Tov"
    manana = (d + dt.timedelta(days=1))
    if ahora.hour >= 16 and (d.weekday() == 4 or manana.isoformat() in YOM_TOV):
        return "Erev Shabat" if d.weekday() == 4 else "Erev Yom Tov"
    return None


def en_horario(ahora, a):
    h = ahora.strftime("%H:%M")
    return a["desde"] <= h < a["hasta"]


def carpetas_robot():
    cfg = leer_json(ROBOT / "config_whatsapp.json")
    out = []
    for d in (cfg.get("escuchar") or {}).values():
        if isinstance(d, dict) and d.get("carpetaDestino"):
            out.append(Path(d["carpetaDestino"]))
    for e in cfg.get("escuchar_directo") or []:
        if isinstance(e, dict) and e.get("carpetaDestino"):
            out.append(Path(e["carpetaDestino"]))
    for show in BASE.iterdir():
        if show.is_dir():
            out += [show / "audios_whatsapp"]
            c = leer_json(show / "config.json")
            if c.get("correo_carpeta"):
                out.append(Path(c["correo_carpeta"]))
    vistas, unicas = set(), []
    for p in out:
        k = str(p).lower()
        if k not in vistas:
            vistas.add(k)
            unicas.append(p)
    return unicas


def lo_mas_nuevo():
    """La fecha del archivo más nuevo que dejó el robot (o el correo) en cualquier show."""
    mayor, cual = 0.0, ""
    for c in carpetas_robot():
        try:
            for f in c.iterdir():
                if f.is_file() and f.suffix.lower() in AUDIO:
                    m = f.stat().st_mtime
                    if m > mayor:
                        mayor, cual = m, f"{c.name}\\{f.name}"
        except Exception:
            continue
    return mayor, cual


def correr(cmd, cwd, minutos, etiqueta):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(cwd), timeout=minutos * 60,
                           env=dict(os.environ, PYTHONUTF8="1"))
        log(f"{etiqueta}: listo en {int(time.time() - t0)} s" + ("" if r.returncode == 0 else f" (salió con código {r.returncode})"))
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"{etiqueta}: tardó más de {minutos} min, lo corto y sigo")
    except Exception as ex:
        log(f"{etiqueta}: no pude correrlo ({ex})")
    return False


def mantenimiento():
    if not (JAB / "mantenimiento.py").exists():
        log("no está C:\\OTZAR\\jabura\\mantenimiento.py (corre el instalador)")
        return False
    log("=== MANTENIMIENTO: subir a archive.org y armar los feeds ===")
    return correr([sys.executable, "mantenimiento.py"], JAB, 45, "mantenimiento")


def shows_youtube():
    out = []
    for show in sorted(BASE.iterdir()):
        bot, cfgp = show / "podcast_bot.py", show / "config.json"
        if not (show.is_dir() and bot.exists() and cfgp.exists()):
            continue
        c = leer_json(cfgp)
        if not (c.get("canales_youtube") or c.get("canal_youtube")):
            continue
        if c.get("modo_whatsapp") or c.get("manual") or c.get("pausado"):
            continue
        if (show / "PAUSADO.txt").exists() or (show / "PAUSADOS.txt").exists():
            continue
        try:
            if "PAUSADO por instalar_otzar" in bot.read_text(encoding="utf-8", errors="replace")[:200]:
                continue
        except Exception:
            continue
        out.append(show)
    return out


def youtube(a):
    shows = shows_youtube()
    log(f"=== YOUTUBE (lo del botón ACTUALIZAR): {len(shows)} shows ===")
    for show in shows:
        if PAUSA.exists() or bloqueo(dt.datetime.now()):
            log("youtube: pausa o Shabat/Yom Tov; lo que falta sigue en la próxima vuelta")
            return
        correr([sys.executable, "podcast_bot.py"], show, a["timeout_show_min"], f"youtube {show.name}")


def anunciar():
    daf = ROBOT / "dafyomi_calendario.py"
    if daf.exists():
        correr([sys.executable, str(daf)], ROBOT, 5, "daf yomi de hoy")
    cmd = ROBOT / "comando.txt"
    if cmd.exists():
        log("anunciar: el robot todavía no recogió la orden anterior (¿está abierta su ventana?)")
        return False
    cmd.write_text("anunciar", encoding="utf-8")
    for _ in range(15):
        time.sleep(2)
        if not cmd.exists():
            log("anunciar: el robot recogió la orden (mira su ventana)")
            return True
    log("anunciar: el robot NO recogió la orden en 30 s. ¿Está abierta la ventana del robot?")
    try:
        cmd.unlink()
    except Exception:
        pass
    return False


def otro_piloto_vivo():
    try:
        if time.time() - LOCK.stat().st_mtime < 120:
            return True
    except Exception:
        pass
    return False


def main():
    if otro_piloto_vivo():
        print("Ya hay otro PILOTO abierto (piloto.lock reciente). Cierra esta ventana.")
        time.sleep(15)
        return 1
    log("=== PILOTO AUTOMÁTICO encendido. Deja esta ventana abierta junto al robot. ===")
    e = leer_json(ESTADO)
    ultimo_audio = float(e.get("ultimo_audio", 0))
    ult_mant = float(e.get("ult_mant", 0))
    ult_yt = float(e.get("ult_yt", 0))
    ult_anuncio = float(e.get("ult_anuncio", 0))
    avisado = ""
    while True:
        try:
            LOCK.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass
        a = ajustes()
        ahora = dt.datetime.now()
        motivo = "pausa (existe PILOTO_PAUSA.txt)" if PAUSA.exists() else bloqueo(ahora)
        if motivo:
            if motivo != avisado:
                log(f"EN ESPERA: {motivo}. No se publica ni se anuncia nada hasta que termine.")
                avisado = motivo
            time.sleep(60)
            continue
        if avisado:
            log("de vuelta: sigo con lo de siempre")
            avisado = ""
        hubo = False
        nuevo, cual = lo_mas_nuevo()
        if nuevo > ultimo_audio + 1:
            log(f"audio nuevo del robot: {cual}")
            # que el robot termine de escribirlo
            time.sleep(20)
            if mantenimiento():
                hubo = True
            ultimo_audio, ult_mant = nuevo, time.time()
        elif time.time() - ult_mant > a["mantenimiento_min"] * 60:
            mantenimiento()
            ult_mant, hubo = time.time(), True
        if a.get("youtube", True) and time.time() - ult_yt > a["youtube_min"] * 60:
            youtube(a)
            ult_yt, hubo = time.time(), True
        if en_horario(dt.datetime.now(), a) and (hubo or time.time() - ult_anuncio > a["anuncio_min"] * 60):
            anunciar()
            ult_anuncio = time.time()
        try:
            ESTADO.write_text(json.dumps({"ultimo_audio": ultimo_audio, "ult_mant": ult_mant, "ult_yt": ult_yt,
                                          "ult_anuncio": ult_anuncio}), encoding="utf-8")
        except Exception:
            pass
        espera = max(60, int(a["cada_min"] * 60))
        for _ in range(espera // 10):
            time.sleep(10)
            try:
                LOCK.write_text(str(os.getpid()), encoding="utf-8")
            except Exception:
                pass
            n2, _c = lo_mas_nuevo()
            if n2 > ultimo_audio + 1:          # llegó algo: no espera los 5 minutos
                break


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        log("PILOTO apagado (Ctrl+C)")
