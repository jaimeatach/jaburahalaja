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
Vigila al robot (si se cierra lo vuelve a abrir), deja cada mañana un reporte para el chat que
mandó "!reporte" al robot y avisa si algo falla (disco lleno, mantenimiento que falla...).
Nunca en Shabat ni en Yom Tov (desde la víspera a las 16:00 hasta que sale: puesta del sol
+ 50 min) y nunca de noche (anuncios solo de 5:30 a 22:00). Para pausarlo: crea el archivo
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
REPORTE = BASE / "piloto_reporte.txt"      # lo lee el robot con "!estado"
AVISOS = ROBOT / "avisos"                  # el robot los manda al chat de "!reporte"
AUDIO = (".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".amr", ".pdf", ".doc", ".docx")
AJUSTES = {"cada_min": 5, "mantenimiento_min": 60, "youtube_min": 30, "anuncio_min": 15,
           "desde": "05:30", "hasta": "22:00", "youtube": True, "timeout_show_min": 20,
           "vigilar_robot": True, "reporte_hora": "07:00", "disco_minimo_gb": 5}
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


def puesta_sol(dia, lat=19.4326, lon=-99.1332):
    """Puesta del sol en CDMX (fórmula de la NOAA, la misma del robot), como datetime local."""
    import math
    n = dia.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1 + (18 - 12) / 24)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    de = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
          + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    r = math.pi / 180
    ha = math.acos(math.cos(90.833 * r) / (math.cos(lat * r) * math.cos(de)) - math.tan(lat * r) * math.tan(de)) / r
    utc = dt.datetime(dia.year, dia.month, dia.day, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=720 - 4 * (lon - ha) - eq)
    return utc.astimezone().replace(tzinfo=None)


def dia_sagrado(d):
    return d.weekday() == 5 or d.isoformat() in YOM_TOV


def bloqueo(ahora):
    """Shabat / Yom Tov: desde las 16:00 de la víspera hasta 50 min después de la puesta del
    sol del último día (Motzaei Shabat ya se anuncia). None = se puede."""
    d = ahora.date()
    manana = d + dt.timedelta(days=1)
    if dia_sagrado(d) and (dia_sagrado(manana) or ahora < puesta_sol(d) + dt.timedelta(minutes=50)):
        return "Shabat" if d.weekday() == 5 else "Yom Tov"
    if not dia_sagrado(d) and dia_sagrado(manana) and ahora.hour >= 16:
        return "Erev Shabat" if manana.weekday() == 5 else "Erev Yom Tov"
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


# ── vigilancia, reporte y avisos (para cuando nadie está frente a la PC) ──────────
_ultimo_aviso = {}


def avisar(clave, texto, cada_horas=3):
    """Deja un aviso para el chat de "!reporte" (el robot lo manda). Uno por tipo cada 3 h."""
    if time.time() - _ultimo_aviso.get(clave, 0) < cada_horas * 3600:
        return
    _ultimo_aviso[clave] = time.time()
    try:
        AVISOS.mkdir(parents=True, exist_ok=True)
        (AVISOS / f"{time.strftime('%Y%m%d%H%M%S')}_{clave}.txt").write_text(texto, encoding="utf-8")
    except Exception:
        pass
    log("AVISO: " + texto.replace("\n", " · "))


def robot_vivo():
    try:
        return time.time() - (ROBOT / "robot.lock").stat().st_mtime < 180
    except Exception:
        return False


def bat_del_robot():
    for nombre in ("ROBOT_WHATSAPP.bat", "ROBOT.bat", "INICIAR_ROBOT.bat"):
        if (ROBOT / nombre).exists():
            return ROBOT / nombre
    otros = sorted(ROBOT.glob("ROBOT*.bat"))
    return otros[0] if otros else None


_ult_relanzo = 0.0


def vigilar_robot(a):
    """Si la ventana del robot se cerró o se colgó, la vuelve a abrir (máximo una vez cada 10 min)."""
    global _ult_relanzo
    if not a.get("vigilar_robot", True) or robot_vivo():
        return
    if time.time() - _ult_relanzo < 600:
        return
    _ult_relanzo = time.time()
    bat = bat_del_robot()
    if not bat:
        log("robot: no está abierto y no encuentro ROBOT_WHATSAPP.bat para abrirlo")
        return
    try:
        subprocess.Popen(["cmd", "/c", "start", "ROBOT", "/d", str(ROBOT), str(bat)], cwd=str(ROBOT))
        log("robot: estaba cerrado o colgado; lo volví a abrir")
        avisar("robot", "⚠️ El robot de WhatsApp se había cerrado y el piloto lo volvió a abrir. Si vuelve a pasar seguido, revisa la PC.")
    except Exception as ex:
        log(f"robot: no pude abrirlo ({ex})")


def disco_libre_gb():
    try:
        import shutil
        return shutil.disk_usage(str(BASE)).free / 1e9
    except Exception:
        return -1


def contar_log_robot(dia):
    """Audios guardados, anuncios y errores del robot en un día (lee la cola del log)."""
    import re
    p = ROBOT / "robot_whatsapp.log"
    g = an = er = 0
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 8_000_000))
            texto = f.read().decode("utf-8", "replace")
    except Exception:
        return g, an, er
    pref = re.compile(r"^\[0?%d/0?%d/%d," % (dia.day, dia.month, dia.year))
    for linea in texto.splitlines():
        if not pref.match(linea):
            continue
        if "GUARDADO" in linea:
            g += 1
        elif "ANUNCIADO en" in linea:
            an += 1
        elif "ERROR" in linea:
            er += 1
    return g, an, er


def escribir_reporte(est):
    ahora = dt.datetime.now()
    ayer = (ahora - dt.timedelta(days=1)).date()
    g, an, er = contar_log_robot(ayer)
    gh, anh, erh = contar_log_robot(ahora.date())
    hora = lambda t: dt.datetime.fromtimestamp(t).strftime("%d/%m %H:%M") if t else "nunca"
    libre = disco_libre_gb()
    lineas = [
        f"🤖 Otzar · {ahora.strftime('%d/%m %H:%M')}",
        ("✅ Robot conectado" if robot_vivo() else "❌ Robot NO responde"),
        ("⏸️ Piloto en PAUSA (!sigue para seguir)" if PAUSA.exists() else "✅ Piloto andando"),
        f"Ayer: {g} audios guardados · {an} anuncios · {er} errores",
        f"Hoy: {gh} audios · {anh} anuncios · {erh} errores",
        f"Mantenimiento: {hora(est.get('ult_mant'))}" + ("" if est.get("mant_ok", True) else " ⚠️ con errores"),
        f"YouTube: {hora(est.get('ult_yt'))} · Anuncio: {hora(est.get('ult_anuncio'))}",
        (f"Disco: {libre:.0f} GB libres" if libre >= 0 else ""),
    ]
    b = bloqueo(ahora)
    if b:
        lineas.append(f"🕯️ {b}: en espera hasta que termine")
    texto = "\n".join(x for x in lineas if x)
    try:
        REPORTE.write_text(texto, encoding="utf-8")
    except Exception:
        pass
    return texto


def revisar_salud(a, est):
    texto = escribir_reporte(est)
    hoy = dt.date.today().isoformat()
    if dt.datetime.now().strftime("%H:%M") >= a.get("reporte_hora", "07:00") and est.get("reporte_dia") != hoy:
        est["reporte_dia"] = hoy
        avisar("reporte", "☀️ Reporte de la mañana\n" + texto, cada_horas=0)
    libre = disco_libre_gb()
    if 0 <= libre < a.get("disco_minimo_gb", 5):
        avisar("disco", f"⚠️ Al disco de la PC le quedan {libre:.1f} GB. Hay que liberar espacio (audios viejos ya subidos).", 12)
    if est.get("mant_fallos", 0) >= 3:
        avisar("mant", "⚠️ El mantenimiento falló 3 veces seguidas (subir a archive.org / feeds). Revisa C:\\OTZAR\\piloto.log.")
    if est.get("anuncio_fallos", 0) >= 3:
        avisar("anuncio", "⚠️ El robot no recoge la orden de anunciar (3 veces). ¿Está abierta su ventana?")


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
    est = dict(e)
    avisado = ""
    while True:
        try:
            LOCK.write_text(str(os.getpid()), encoding="utf-8")
        except Exception:
            pass
        a = ajustes()
        ahora = dt.datetime.now()
        vigilar_robot(a)
        revisar_salud(a, est)
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
            bien = mantenimiento()
            est["mant_ok"], est["mant_fallos"] = bien, (0 if bien else est.get("mant_fallos", 0) + 1)
            hubo = hubo or bien
            ultimo_audio, ult_mant = nuevo, time.time()
        elif time.time() - ult_mant > a["mantenimiento_min"] * 60:
            bien = mantenimiento()
            est["mant_ok"], est["mant_fallos"] = bien, (0 if bien else est.get("mant_fallos", 0) + 1)
            ult_mant, hubo = time.time(), True
        if a.get("youtube", True) and time.time() - ult_yt > a["youtube_min"] * 60:
            youtube(a)
            ult_yt, hubo = time.time(), True
        if en_horario(dt.datetime.now(), a) and (hubo or time.time() - ult_anuncio > a["anuncio_min"] * 60):
            recogio = anunciar()
            est["anuncio_fallos"] = 0 if recogio else est.get("anuncio_fallos", 0) + 1
            ult_anuncio = time.time()
        est.update({"ultimo_audio": ultimo_audio, "ult_mant": ult_mant, "ult_yt": ult_yt, "ult_anuncio": ult_anuncio})
        escribir_reporte(est)
        try:
            ESTADO.write_text(json.dumps(est), encoding="utf-8")
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
