#!/usr/bin/env python3
"""PILOTO AUTOMÁTICO de Otzar HaTorah: hace solo lo de los botones, sin que nadie apriete.

Se abre con PILOTO.bat (junto al robot) y se deja la ventana abierta, igual que el robot.
Cada 5 minutos:
  1. ¿El robot guardó un audio nuevo (WhatsApp, cualquier show)? → corre el mantenimiento
     (lo mismo que ANUNCIAR.bat: sube a archive.org, arma el feed, Spotify lo toma de ahí).
     Aunque no haya nada nuevo, el mantenimiento corre una vez por hora (correo, parashá...).
  2. Cada 30 minutos: los shows de YouTube (lo del botón ACTUALIZAR): baja y publica lo nuevo.
  3. Después de publicar, y cada 5 minutos, le da la orden "anunciar" al robot. El robot
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
import threading
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
AJUSTES = {"cada_min": 5, "mantenimiento_min": 60, "youtube_min": 30, "anuncio_min": 5,
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


def mantenimiento(rapido=False):
    """rapido: solo el show al que le llegó algo (lo decide mantenimiento.py; aquí se fuerza mientras
    YouTube corre en paralelo, para no tocar a la vez los feeds de los shows de YouTube)."""
    if not (JAB / "mantenimiento.py").exists():
        log("no está C:\\OTZAR\\jabura\\mantenimiento.py (corre el instalador)")
        return False
    log("=== MANTENIMIENTO: subir a archive.org y armar los feeds ===")
    return correr([sys.executable, "mantenimiento.py"] + (["--rapido"] if rapido else []), JAB, 45, "mantenimiento")


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


# ── se actualiza solo (20/11/2026; el usuario: "si yo le muevo de esta compu se mueva ahí") ──
#   Cada hora baja de la rama los scripts de Python que ya tiene la PC; si alguno cambió y compila,
#   lo pone (con respaldo .antes_auto). Si cambió el propio piloto, se cierra y PILOTO.bat lo vuelve
#   a abrir en 30 s con el nuevo. El robot (JavaScript) NO: eso sigue con el instalador.
RAMA_RAW = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/claude/shiurim-halachot-shabbat-vriig5/tools/otzar/"
AUTO = ["mantenimiento.py", "piloto.py", "diagnostico.py", "plataformas.py", "parasha_youtube.py",
        "revisar_spotify.py", "espacio.py", "soundcloud_subir.py", "carga_youtube.py",
        "mudanza.py", "examen_tawil.py", "drive_a_show.py", "drive_sammy.py", "shas_unido.py",
        "estadisticas_op3.py", "mensaje_links.py"]


def actualizarse():
    """Devuelve True si cambió piloto.py (hay que reiniciar)."""
    import urllib.request
    import py_compile
    import tempfile
    cambiados = []
    for nombre in AUTO:
        local = JAB / nombre
        if not local.exists():
            continue
        try:
            with urllib.request.urlopen(RAMA_RAW + nombre + f"?t={int(time.time())}", timeout=60) as r:
                nuevo = r.read()
        except Exception:
            continue
        if len(nuevo) < 200 or nuevo == local.read_bytes():
            continue
        tmp = None
        try:
            with tempfile.NamedTemporaryFile("wb", suffix=".py", delete=False) as t:
                tmp = t.name
                t.write(nuevo)
            py_compile.compile(tmp, doraise=True)
        except Exception as e:
            log(f"actualizar: {nombre} nuevo no compila; me quedo con el de antes ({e})")
            continue
        finally:
            try:
                if tmp:
                    os.unlink(tmp)
            except Exception:
                pass
        try:
            (JAB / (nombre + ".antes_auto")).write_bytes(local.read_bytes())
            local.write_bytes(nuevo)
            cambiados.append(nombre)
        except Exception as e:
            log(f"actualizar: no pude escribir {nombre} ({e})")
    if cambiados:
        log("actualizado desde el repo: " + ", ".join(cambiados))
    return "piloto.py" in cambiados


# ── control a distancia (23/11/2026; el usuario: "algo de reporte de errores y poderlo arreglar a distancia") ──
#   Cada 20 min el piloto sube a un repo PRIVADO de GitHub (otzar-estado, lo crea solo con el
#   github_token.txt de la PC) un estado.txt: procesos, robot vivo, disco, unidades (G:), claves de
#   archive.org, y lo último del log del piloto y del robot. Así Claude ve qué pasa sin estar en la PC.
#   En el mismo repo, ordenes.json (lo escribe Claude) = [{"id": "...", "accion": ..., "args": [...]}];
#   cada orden corre UNA vez y su salida queda en resultados/<id>.txt. Acciones: instalar (el instalador
#   de la rama con esos argumentos), mantenimiento, reiniciar_robot, reiniciar_piloto, script (un .py de
#   tools/otzar de la rama, con argumentos). Nada en Shabat/Yom Tov.
REPO_ESTADO = "otzar-estado"
_gh = {"user": None, "listo": False}


def _token():
    for p in (JAB / "github_token.txt", BASE / "github_token.txt"):
        try:
            t = p.read_text(encoding="utf-8").strip()
            if t:
                return t
        except Exception:
            pass
    return ""


def _api(metodo, ruta, datos=None):
    import urllib.request
    import urllib.error
    req = urllib.request.Request("https://api.github.com" + ruta, method=metodo,
                                 data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"Authorization": "token " + _token(), "Accept": "application/vnd.github+json",
                                          "User-Agent": "otzar-piloto"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            cuerpo = r.read()
            return r.status, (json.loads(cuerpo) if cuerpo else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def _repo_estado():
    if _gh["listo"]:
        return _gh["user"]
    if not _token():
        return None
    st, yo = _api("GET", "/user")
    if st != 200:
        log(f"distancia: el token de GitHub no sirve ({st})")
        return None
    _gh["user"] = yo.get("login")
    st, _ = _api("GET", f"/repos/{_gh['user']}/{REPO_ESTADO}")
    if st == 404:
        st, r = _api("POST", "/user/repos", {"name": REPO_ESTADO, "private": True, "auto_init": True,
                                              "description": "Estado de la PC de Otzar (lo escribe el piloto)"})
        log(f"distancia: repo privado {REPO_ESTADO} " + ("creado" if st in (200, 201) else f"NO se pudo crear ({st} {r.get('message')})"))
        if st not in (200, 201):
            avisar("distancia", f"⚠️ No pude crear el repo privado {REPO_ESTADO} para el reporte a distancia ({r.get('message')}).", 24)
            return None
        time.sleep(3)
    _gh["listo"] = True
    return _gh["user"]


def _subir(ruta, texto, mensaje):
    import base64
    u = _repo_estado()
    if not u:
        return False
    st, viejo = _api("GET", f"/repos/{u}/{REPO_ESTADO}/contents/{ruta}")
    datos = {"message": mensaje, "content": base64.b64encode(texto.encode("utf-8")).decode()}
    if st == 200 and viejo.get("sha"):
        datos["sha"] = viejo["sha"]
    st, _ = _api("PUT", f"/repos/{u}/{REPO_ESTADO}/contents/{ruta}", datos)
    return st in (200, 201)


def _cola(p, n):
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            lineas = f.read().decode("utf-8", "replace").splitlines()
        return "\n".join(lineas[-n:])
    except Exception as e:
        return f"(no pude leer {p}: {e})"


def _sal(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60).stdout.strip()
    except Exception as e:
        return f"({e})"


def estado_texto(est):
    import shutil
    partes = [f"Estado de la PC de Otzar · {dt.datetime.now():%d/%m/%Y %H:%M:%S}",
              f"robot vivo (robot.lock < 3 min): {robot_vivo()}",
              f"en espera: {bloqueo(dt.datetime.now()) or 'no'} · pausa: {PAUSA.exists()}"]
    for u in "CDEFGH":
        if os.path.exists(f"{u}:\\"):
            try:
                partes.append(f"unidad {u}: libre {shutil.disk_usage(f'{u}:/').free / 1e9:.0f} GB")
            except Exception:
                partes.append(f"unidad {u}: existe")
    ia = [Path.home() / ".config" / "internetarchive" / "ia.ini", Path.home() / ".ia"]
    partes.append(f"claves de archive.org: {any(x.exists() for x in ia)}")
    partes.append("ajustes: " + json.dumps(ajustes(), ensure_ascii=False))
    partes.append("estado del piloto: " + json.dumps(est, ensure_ascii=False, default=str)[:3000])
    partes.append("\n===== PROCESOS\n" + _sal('tasklist /fo csv /nh | findstr /i "node python"'))
    partes.append("\n===== PILOTO (últimas 200)\n" + _cola(LOG, 200))
    partes.append("\n===== ROBOT (últimas 250)\n" + _cola(ROBOT / "robot_whatsapp.log", 250))
    return "\n".join(partes)


def _correr_orden(o):
    import urllib.request
    acc, args = o.get("accion"), [str(x) for x in (o.get("args") or [])]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    def py(cmd, cwd, minutos=60):
        r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=minutos * 60)
        return f"código {r.returncode}\n{r.stdout[-60000:]}\n{r.stderr[-20000:]}"
    if acc in ("instalar", "script"):
        nombre = "instalar_otzar.py" if acc == "instalar" else os.path.basename(o.get("script", ""))
        if not nombre.endswith(".py"):
            return "script inválido"
        destino = (ROBOT if acc == "instalar" else JAB) / nombre
        with urllib.request.urlopen(RAMA_RAW + nombre + f"?t={int(time.time())}", timeout=120) as r:
            destino.write_bytes(r.read())
        return py([sys.executable, str(destino)] + args, destino.parent, int(o.get("minutos", 60)))
    if acc == "py":                     # un .py que ya está en la PC (p. ej. C:\\OTZAR\\efshar\\shalom_bait.py)
        f = Path(str(o.get("archivo", "")))
        if not f.is_file() or not str(f.resolve()).lower().startswith((str(BASE).lower(), str(ROBOT).lower())):
            return f"archivo inválido: {f}"
        return py([sys.executable, str(f)] + args, f.parent, int(o.get("minutos", 60)))
    if acc == "mantenimiento":
        return py([sys.executable, str(JAB / "mantenimiento.py")] + args, JAB, 90)
    if acc == "reiniciar_robot":
        matar_robot_colgado()
        time.sleep(5)
        global _ult_relanzo
        _ult_relanzo = 0
        try:
            (ROBOT / "robot.lock").unlink()
        except Exception:
            pass
        vigilar_robot(dict(ajustes(), vigilar_robot=True))
        return "robot reiniciado"
    if acc == "reiniciar_piloto":
        return "REINICIAR"
    return f"acción desconocida: {acc}"


def distancia(a, est):
    """Sube el estado (cada 20 min) y corre las órdenes nuevas. Devuelve True si hay que reiniciar el piloto."""
    if not a.get("distancia", True) or not _token():
        return False
    d = est.setdefault("distancia", {})
    if time.time() - d.get("ult_estado", 0) > 20 * 60:
        d["ult_estado"] = time.time()
        try:
            _subir("estado.txt", estado_texto(est), f"estado {dt.datetime.now():%d/%m %H:%M}")
        except Exception as e:
            log(f"distancia: no pude subir el estado ({e})")
    if time.time() - d.get("ult_ordenes", 0) < 120:
        return False
    d["ult_ordenes"] = time.time()
    u = _repo_estado()
    if not u:
        return False
    import base64
    st, f = _api("GET", f"/repos/{u}/{REPO_ESTADO}/contents/ordenes.json")
    if st != 200:
        return False
    try:
        ordenes = json.loads(base64.b64decode(f.get("content", "")).decode("utf-8") or "[]")
    except Exception as e:
        log(f"distancia: ordenes.json no se entiende ({e})")
        return False
    hechas = d.setdefault("hechas", [])
    reiniciar = False
    for o in ordenes if isinstance(ordenes, list) else []:
        oid = str(o.get("id", ""))
        if not oid or oid in hechas:
            continue
        hechas.append(oid)
        d["hechas"] = hechas[-200:]
        ESTADO.write_text(json.dumps(est), encoding="utf-8")       # que no se repita si algo truena
        log(f"distancia: orden {oid}: {o.get('accion')} {o.get('args') or ''}")
        try:
            res = _correr_orden(o)
        except Exception as e:
            res = f"ERROR: {e}"
        if res == "REINICIAR":
            reiniciar, res = True, "el piloto se reinicia"
        _subir(f"resultados/{oid}.txt", f"{dt.datetime.now():%d/%m/%Y %H:%M:%S}\n{json.dumps(o, ensure_ascii=False)}\n\n{res}",
               f"resultado {oid}")
        d["ult_estado"] = 0                                          # estado nuevo enseguida
    return reiniciar


# ── examen de Tawil en Motzaei Shabat (nov/2026) ──────────────────────────────
#   El sábado, 30 min después de Rabenu Tam (puesta del sol + 72 min), le pide al Apps Script
#   del usuario (aplicación web, "examen_url" en jabura\piloto.json) el link del examen de la
#   semana, deja el mensaje en <robot>\salida\ (el robot lo manda a los grupos propios de
#   Tawil) y, cuando el robot lo mandó, le avisa al script para que mande UN correo de
#   confirmación con el link de resultados. Una vez por semana (candado en piloto_estado).
SALIDA = ROBOT / "salida"


def _pedir_json(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "otzar-piloto"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def mensaje_examen(dias, link):
    return ("Shavua Tov! 🌟\n\n"
            f"📝 Examen de los días {dias} del Rab Yosef Tawil.\n\n"
            "Es una autoevaluación para repasar lo que aprendimos; el examen con premio es mensual.\n\n"
            f"👉 {link}\n\n"
            "¡Hatzlajá! 🙌")


def examen_revisar(a, est):
    """(20/11) El viernes en la mañana le manda al chat de "!reporte" el link del examen ya armado,
    para revisarlo antes de que salga el sábado. Una vez por semana."""
    url = str(a.get("examen_url") or "").strip()
    ahora = dt.datetime.now()
    if not url or ahora.weekday() != 4 or not ("09:00" <= ahora.strftime("%H:%M") < "15:45") or bloqueo(ahora):
        return
    ex = est.setdefault("examen_tawil", {})
    if ex.get("revisar") == ahora.date().isoformat():
        return
    try:
        r = _pedir_json(url)
    except Exception as e:
        log(f"examen Tawil (revisar): no pude pedir el link ({e})")
        return
    if r.get("ok") and int(r.get("preguntas") or 0) < 10 and ahora.strftime("%H:%M") < "14:30":
        return                      # todavía no subo las 10 preguntas: espera un rato
    ex["revisar"] = ahora.date().isoformat()
    if not r.get("ok"):
        avisar("examen_rev", f"⚠️ El examen de Tawil de esta semana todavía no está ({r.get('error')}). Avísale a Claude.", 6)
        return
    sab = ahora.date() + dt.timedelta(days=1)
    hora = puesta_sol(sab) + dt.timedelta(minutes=72 + int(a.get("examen_despues_min", 30)))
    avisar("examen_rev", f"📝 Examen de Tawil de esta semana, para que lo revises (días {r.get('dias')}, "
                         f"{r.get('preguntas')} preguntas):\n{r.get('link')}\n\nSale solo al grupo el sábado a las "
                         f"{hora.strftime('%H:%M')}. Si algo está mal, díselo a Claude antes.", 1)


def examen_tawil(a, est):
    url = str(a.get("examen_url") or "").strip()
    if not url:
        return
    ahora = dt.datetime.now()
    # el sábado de esta semana (o el de ayer, si ya es domingo de madrugada)
    sab = ahora.date() - dt.timedelta(days=(ahora.weekday() - 5) % 7)
    hora = puesta_sol(sab) + dt.timedelta(minutes=72 + int(a.get("examen_despues_min", 30)))
    if not (hora <= ahora < hora + dt.timedelta(hours=6)) or bloqueo(ahora):
        return
    clave = sab.isoformat()
    ex = est.setdefault("examen_tawil", {})
    if ex.get("enviado") == clave:
        return
    archivo = SALIDA / f"examen_tawil_{clave}.json"
    hecho = SALIDA / "enviados" / archivo.name
    if hecho.exists():
        try:
            r = _pedir_json(url + ("&" if "?" in url else "?") + "enviado=1")
            log(f"examen Tawil: mandado al grupo; correo de confirmación: {r.get('correo') or r.get('error')}")
        except Exception as e:
            log(f"examen Tawil: mandado al grupo, pero no pude pedir el correo ({e})")
        ex["enviado"] = clave
        return
    if archivo.exists():
        if time.time() - archivo.stat().st_mtime > 15 * 60:
            avisar("examen", "⚠️ El examen de Tawil está listo pero el robot no lo ha mandado en 15 min. ¿Está abierto?", 1)
        return
    try:
        r = _pedir_json(url)
    except Exception as e:
        log(f"examen Tawil: no pude pedir el link ({e}); reintento en la próxima vuelta")
        if ahora > hora + dt.timedelta(minutes=30):
            avisar("examen", f"⚠️ No pude sacar el link del examen de Tawil ({e}). Sigo intentando.", 2)
        return
    if not r.get("ok") or not r.get("link"):
        log(f"examen Tawil: el script dice {r.get('error') or r}")
        avisar("examen", f"⚠️ Examen de Tawil: {r.get('error') or 'el script no dio el link'}. Avísale a Claude.", 6)
        return
    SALIDA.mkdir(parents=True, exist_ok=True)
    datos = {"show": a.get("examen_show", "tawil"), "solo_propios": True,
             "texto": mensaje_examen(r.get("dias", ""), r["link"])}
    archivo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"examen Tawil (días {r.get('dias')}): mensaje listo para el robot → {r['link']}")


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


def mantener_despierta():
    """(nov/2026) La HP no se duerme ni apaga la pantalla mientras el piloto esté abierto.
    En las laptops con "Modern Standby", al apagarse la pantalla Windows corta el internet
    y deja los programas casi congelados: el 19-20/11 nada salió hasta que alguien abrió la
    compu. SetThreadExecutionState vale mientras el piloto viva, sin tocar la configuración."""
    if os.name != "nt":
        return
    try:
        import ctypes
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED | ES_AWAYMODE_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x1 | 0x2 | 0x40)
    except Exception:
        pass


def sin_quickedit():
    """Un clic en la ventana negra (modo "Edición rápida") congela al programa hasta que se
    aprieta una tecla. Se apaga en esta ventana y, en el registro, para las que se abran después
    (la del robot)."""
    if os.name != "nt":
        return
    try:
        import winreg
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Console")
        winreg.SetValueEx(k, "QuickEdit", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(k)
    except Exception:
        pass
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)
        modo = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(modo)):
            # sin ENABLE_QUICK_EDIT_MODE (0x40), con ENABLE_EXTENDED_FLAGS (0x80)
            k32.SetConsoleMode(h, (modo.value & ~0x40) | 0x80)
    except Exception:
        pass


def matar_robot_colgado():
    """Cierra TODAS las ventanas del robot (el .bat que lo relanza y su node) antes de abrir una nueva.
    (23/11) Antes solo mataba el node de robot.lock: el .bat viejo lo volvía a abrir, el piloto abría
    otra ventana y quedaban dos peleándose ("Deja abierta solo una ventana del robot" cada 30 s).
    No toca otros node (enviar_daf.js, etc.)."""
    if os.name != "nt":
        return
    ps = ("Get-CimInstance Win32_Process | Where-Object { "
          "($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'ROBOT[^\\\\]*\\.bat') -or "
          "($_.Name -eq 'node.exe' -and $_.CommandLine -match 'robot_whatsapp') } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    try:
        pid = int((ROBOT / "robot.lock").read_text(encoding="utf-8").strip() or 0)
        if pid > 0:
            subprocess.run(f"taskkill /PID {pid} /T /F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


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
    matar_robot_colgado()
    time.sleep(3)
    try:
        # (nov/2026) el título de "start" va ENTRE COMILLAS: sin ellas Windows buscaba un programa "ROBOT"
        subprocess.Popen(f'start "ROBOT" /d "{ROBOT}" "{bat}"', cwd=str(ROBOT), shell=True)
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


_yt = {"hilo": None}


def main():
    if otro_piloto_vivo():
        print("Ya hay otro PILOTO abierto (piloto.lock reciente). Cierra esta ventana.")
        time.sleep(15)
        return 1
    log("=== PILOTO AUTOMÁTICO encendido. Deja esta ventana abierta junto al robot. ===")
    sin_quickedit()
    mantener_despierta()
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
        mantener_despierta()
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
        if a.get("auto_actualizar", True) and time.time() - est.get("ult_actualizar", 0) > 3600 \
                and not (_yt["hilo"] is not None and _yt["hilo"].is_alive()):
            est["ult_actualizar"] = time.time()
            try:
                if actualizarse():
                    log("el piloto cambió: me reinicio con el nuevo")
                    ESTADO.write_text(json.dumps(est), encoding="utf-8")
                    LOCK.unlink(missing_ok=True)
                    return 0
            except Exception as e:
                log(f"actualizar: {e}")
        try:
            if distancia(a, est):
                log("distancia: me reinicio por orden remota")
                ESTADO.write_text(json.dumps(est), encoding="utf-8")
                LOCK.unlink(missing_ok=True)
                return 0
        except Exception as e:
            log(f"distancia: {e}")
        hubo = False
        # (nov/2026) YouTube corre en paralelo (antes, mientras bajaba YouTube, un audio de WhatsApp
        # esperaba hasta media hora). Al terminar, se anuncia lo que bajó.
        yt_vivo = _yt["hilo"] is not None and _yt["hilo"].is_alive()
        if _yt["hilo"] is not None and not yt_vivo:
            _yt["hilo"], hubo = None, True
        nuevo, cual = lo_mas_nuevo()
        if nuevo > ultimo_audio + 1:
            log(f"audio nuevo del robot: {cual}")
            # que el robot termine de escribirlo
            time.sleep(10)
            nuevo = max(nuevo, lo_mas_nuevo()[0])
            bien = mantenimiento(rapido=yt_vivo)
            est["mant_ok"], est["mant_fallos"] = bien, (0 if bien else est.get("mant_fallos", 0) + 1)
            hubo = hubo or bien
            ultimo_audio = nuevo
            if not yt_vivo:
                ult_mant = time.time()
        elif time.time() - ult_mant > a["mantenimiento_min"] * 60 and not yt_vivo:
            bien = mantenimiento()
            est["mant_ok"], est["mant_fallos"] = bien, (0 if bien else est.get("mant_fallos", 0) + 1)
            ult_mant, hubo = time.time(), True
        if a.get("youtube", True) and time.time() - ult_yt > a["youtube_min"] * 60 and not yt_vivo:
            _yt["hilo"] = threading.Thread(target=youtube, args=(a,), daemon=True)
            _yt["hilo"].start()
            ult_yt = time.time()
        try:
            examen_revisar(a, est)
            examen_tawil(a, est)
        except Exception as e:
            log(f"examen Tawil: {e}")
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
            antes = time.time()
            time.sleep(10)
            hueco = time.time() - antes
            if hueco > 300:                    # 10 s de espera que duraron minutos: la PC se durmió
                log(f"la PC estuvo dormida o congelada {hueco / 60:.0f} min (nada corría)")
                avisar("dormida", f"⚠️ La PC estuvo dormida o congelada {hueco / 60:.0f} minutos y no mandó nada "
                                  "en ese rato. Ya volvió. Revisa que esté conectada a la luz y con internet.", 1)
                break
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
