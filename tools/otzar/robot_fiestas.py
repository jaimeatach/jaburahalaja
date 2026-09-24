#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================================
#  ROBOT DE FIESTAS - Otzar HaTorah  (version C:\OTZAR, sep 2026)
#  4 dias antes de cada fiesta:
#   - busca en TODOS los canales de TODOS los shows
#     shiurim de esa fiesta (TODOS los nombres he/en/es)
#   - elige los N MAS VISTOS de cada canal (minimo 10 minutos); N = 2, o el
#     segundo argumento ("sukot2026 5" = 5 por canal)
#   - los baja, los sube a Archive y publica el feed
#  Uso:
#    python robot_fiestas.py                 (modo automatico diario)
#    python robot_fiestas.py probar          (fiesta mas cercana, no marca)
#    python robot_fiestas.py roshhashana2026 (fuerza esa fiesta y marca)
#    python robot_fiestas.py sukot2026 5     (fuerza, 5 por canal)
# ================================================================
import json, os, re, subprocess, sys, time
from datetime import date
from pathlib import Path
from urllib.parse import quote

BASE = Path(r"C:\OTZAR")
ESTADO = BASE / "fiestas_hechas.json"
LOG = BASE / "fiestas.log"
DIAS_ANTES = 4
POR_CANAL = 2
if len(sys.argv) > 2 and sys.argv[2].isdigit():
    POR_CANAL = max(1, int(sys.argv[2]))
CANDIDATOS = max(6, POR_CANAL * 2)
MIN_SEG = 600
YT_CLIENT = ["--extractor-args", "youtube:player_client=web_embedded"]

def log(m):
    linea = "[%s] %s" % (time.strftime("%d/%m %H:%M"), m)
    print(linea, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(linea + "\n")
    except Exception: pass

# ─────────── CALENDARIO 2026-2027 (dia principal) ───────────
FIESTAS = [
 {"clave":"roshhashana2026","nombre":"Rosh HaShana","fecha":date(2026,9,12),
  "kw":{"he":["ראש השנה","ר\"ה","אלול","הכנה לראש השנה","ימים נוראים","תשובה","סליחות","שופר","מלכויות"],
        "en":["Rosh Hashanah","Rosh Hashana","Yamim Noraim","High Holidays","Days of Awe","teshuva","shofar","Elul","selichot"],
        "es":["Rosh Hashana","Rosh Hashaná","Año Nuevo judio","teshuva","teshuvá","shofar","Elul","selijot","dias temibles"]}},
 {"clave":"yomkipur2026","nombre":"Yom Kipur","fecha":date(2026,9,21),
  "kw":{"he":["יום כיפור","יום הכיפורים","יוה\"כ","כיפור","נעילה","וידוי","עשרת ימי תשובה","כפרות"],
        "en":["Yom Kippur","Yom Kipur","Day of Atonement","Neilah","Aseret Yemei Teshuva","Kol Nidre","viduy"],
        "es":["Yom Kipur","Kipur","Kippur","Dia del Perdon","Día del Perdón","Neila","Kol Nidrei","kaparot"]}},
 {"clave":"sukot2026","nombre":"Sukot","fecha":date(2026,9,26),
  "kw":{"he":["סוכות","חג הסוכות","ארבעת המינים","לולב","אתרוג","סוכה","הושענא רבה","אושפיזין","חול המועד","שמחת בית השואבה","הדס","ערבה","סכך"],
        "en":["Sukkot","Sukot","Succos","Sukkos","Succot","Sukkah","Four Species","lulav","esrog","etrog","sukkah","Hoshana Rabba","Hoshana Raba","ushpizin","Simchat Beit Hashoeva","Chol Hamoed","Chol Hamoed","arba minim","arbaat haminim","hadas","schach"],
        "es":["Sucot","Sukot","arba minim","arbaat haminim","cuatro especies","lulav","etrog","suka","sucá","Hoshana Raba","ushpizin","Jol Hamoed","Jol Amoed","simjat bet hashoeva"]}},
 {"clave":"simjatora2026","nombre":"Simjat Tora","fecha":date(2026,10,3),
  "kw":{"he":["שמחת תורה","שמיני עצרת","הקפות"],"en":["Simchat Torah","Shemini Atzeret","hakafot"],"es":["Simjat Tora","Simjat Torá","Shemini Atzeret","hakafot"]}},
 {"clave":"januca2026","nombre":"Januca","fecha":date(2026,12,5),
  "kw":{"he":["חנוכה","נס חנוכה","נרות חנוכה","חשמונאים"],"en":["Chanukah","Hanukkah","Chanuka","menorah","Maccabees"],"es":["Januca","Janucá","Jánuca","januquia","macabeos"]}},
 {"clave":"tubishvat2027","nombre":"Tu BiShvat","fecha":date(2027,1,22),
  "kw":{"he":["טו בשבט","ט\"ו בשבט","ראש השנה לאילנות"],"en":["Tu BiShvat","Tu B'Shvat","new year trees"],"es":["Tu BiShvat","Tu Bishvat","año nuevo de los arboles"]}},
 {"clave":"purim2027","nombre":"Purim","fecha":date(2027,3,23),
  "kw":{"he":["פורים","מגילת אסתר","מרדכי","המן","משלוח מנות"],"en":["Purim","Megillah","Esther","Mordechai","Haman"],"es":["Purim","Meguila","Ester","Mordejai","Haman"]}},
 {"clave":"pesaj2027","nombre":"Pesaj","fecha":date(2027,4,22),
  "kw":{"he":["פסח","ליל הסדר","הגדה של פסח","יציאת מצרים","חמץ","מצה"],"en":["Pesach","Passover","Seder","Haggadah","chametz","matzah"],"es":["Pesaj","Pésaj","Seder","Hagada","jametz","matza"]}},
 {"clave":"lagbaomer2027","nombre":"Lag BaOmer","fecha":date(2027,5,25),
  "kw":{"he":["לג בעומר","ל\"ג בעומר","רבי שמעון בר יוחאי","רשב\"י","מירון"],"en":["Lag BaOmer","Lag B'Omer","Rashbi","Meron"],"es":["Lag BaOmer","Lag Baomer","Rashbi","Meron"]}},
 {"clave":"shavuot2027","nombre":"Shavuot","fecha":date(2027,6,11),
  "kw":{"he":["שבועות","חג השבועות","מתן תורה","מגילת רות"],"en":["Shavuos","Shavuot","Matan Torah","Ruth"],"es":["Shavuot","Shabuot","Matan Tora","Rut"]}},
 {"clave":"tishabeav2027","nombre":"Tisha BeAv","fecha":date(2027,8,12),
  "kw":{"he":["תשעה באב","ט' באב","ט׳ באב","חורבן","בין המצרים","בית המקדש"],"en":["Tisha B'Av","Tisha BAv","9th of Av","Three Weeks","Churban"],"es":["Tisha BeAv","9 de Av","destruccion del Templo","Bet Hamikdash"]}},
]

def leer_estado():
    try: return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception: return {}

def marcar(clave):
    e = leer_estado(); e[clave] = str(date.today())
    ESTADO.write_text(json.dumps(e, indent=2), encoding="utf-8")

def fiesta_activa(arg):
    hoy = date.today()
    hechas = leer_estado()
    if arg and not arg.startswith("prob"):
        for f in FIESTAS:
            if f["clave"] == arg:
                return f, (f["fecha"] - hoy).days, True
        log("*** no conozco la fiesta '%s'. Claves: %s" % (arg, ", ".join(x["clave"] for x in FIESTAS)))
        return None, None, False
    for f in FIESTAS:
        dias = (f["fecha"] - hoy).days
        if arg:  # probar
            if 0 <= dias <= 30: return f, dias, False
        else:
            if 0 <= dias <= DIAS_ANTES and f["clave"] not in hechas: return f, dias, True
    return None, None, False

# ─────────── yt-dlp ───────────
def ytj(args, timeout=120):
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-J", "--no-warnings"] + YT_CLIENT + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise Exception((r.stderr or "sin salida")[:150])
    return json.loads(r.stdout)

class SinInternet(Exception):
    pass

def _norm(t):
    t = re.sub(r"[\u0591-\u05C7]", "", str(t or "")).lower()
    return re.sub(r"[^\w\u05D0-\u05EA ]+", " ", t)

def es_de_fiesta(titulo, palabras):
    """True si el titulo del video nombra la fiesta (cualquier idioma). YouTube
    devuelve cualquier cosa cuando un canal tiene poco: sin esto entraban Pesaj
    y programas infantiles como 'shiurim de Sukot'."""
    t = _norm(titulo)
    for kw in palabras:
        k = _norm(kw).strip()
        if len(k) >= 3 and k in t:
            return True
    return False

def buscar_en_canal(url_canal, palabras):
    base = re.sub(r"/(videos|shorts|streams|live)/?$", "", url_canal.rstrip("/"))
    if "playlist?list=" in base:
        return []
    encontrados = {}
    fallos_red = 0
    for kw in palabras:
        try:
            data = ytj(["--flat-playlist", "--playlist-end", "12", "%s/search?query=%s" % (base, quote(kw))])
            for e in (data.get("entries") or []):
                vid = e.get("id")
                if vid and vid not in encontrados:
                    encontrados[vid] = e.get("title") or ""
        except Exception as ex:
            log("    busqueda '%s' fallo: %s" % (kw, ex))
            # sin internet / DNS caido: no tiene caso seguir con 20 shows x 25 palabras
            if "Failed to resolve" in str(ex) or "getaddrinfo" in str(ex) or "Name or service not known" in str(ex):
                fallos_red += 1
                if fallos_red >= 3:
                    raise SinInternet("no resuelve www.youtube.com (sin internet o DNS caido)")
        if len(encontrados) >= CANDIDATOS * 2:
            break
    resultado = []
    for vid in list(encontrados.keys())[:CANDIDATOS * 2]:
        try:
            if not es_de_fiesta(encontrados.get(vid) or "", palabras):
                continue                                  # no habla de la fiesta
            m = ytj(["https://www.youtube.com/watch?v=%s" % vid], timeout=90)
            dur = m.get("duration") or 0
            if dur < MIN_SEG: continue
            if not es_de_fiesta(m.get("title") or "", palabras):
                continue
            resultado.append((m.get("view_count") or 0, dur, vid, m.get("title") or ""))
        except Exception:
            continue
        if len(resultado) >= CANDIDATOS: break
    resultado.sort(reverse=True)
    return resultado[:POR_CANAL]

def bajar(carpeta, vid):
    subprocess.run([sys.executable, "-m", "yt_dlp",
        "-x", "--audio-format", "mp3", "--audio-quality", "128K",
        "--embed-metadata", "--windows-filenames",
        "--download-archive", "ya_descargados.txt", "--ignore-errors"] + YT_CLIENT + [
        "-o", "episodios/%(title)s.%(ext)s",
        "https://www.youtube.com/watch?v=%s" % vid], cwd=str(carpeta))

def apartar_no_fiesta(f, palabras, shows):
    """Una corrida anterior (sin el filtro de titulo) pudo bajar videos que no son de
    la fiesta. Se leen sus lineas 'bajando (...): titulo' del log y, si el titulo no
    nombra la fiesta, el mp3 se borra para que no se suba."""
    try:
        lineas = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return
    inicio = None
    for i, l in enumerate(lineas):
        if "FIESTA: %s" % f["nombre"] in l:
            inicio = i
    if inicio is None:
        return
    show = None
    movidos = 0
    for l in lineas[inicio:]:
        m = re.search(r"\] \[([^\]]+)\] buscando", l)
        if m:
            show = m.group(1); continue
        m = re.search(r"bajando \([^)]*\): (.+)$", l)
        if not (m and show):
            continue
        tit = m.group(1).strip()
        if es_de_fiesta(tit, palabras):
            continue
        epi = BASE / show / "episodios"
        if not epi.is_dir():
            continue
        clave = _norm(tit)[:35].strip()
        for mp3 in epi.glob("*.mp3"):
            if clave and _norm(mp3.stem).startswith(clave):
                # candado: solo lo bajado en estos dias (nunca un archivo viejo del show)
                try:
                    if time.time() - mp3.stat().st_mtime > 10 * 86400:
                        continue
                except OSError:
                    continue
                try:
                    mp3.unlink()
                    movidos += 1
                    log("    borrado (no es de %s): [%s] %s" % (f["nombre"], show, mp3.name[:60]))
                except Exception as ex:
                    log("    no pude borrar %s: %s" % (mp3.name[:50], ex))
    if movidos:
        log("Borrados %d archivo(s) que no eran de la fiesta." % movidos)

def correr_bot(carpeta, comando):
    return subprocess.run([sys.executable, "podcast_bot.py", comando], cwd=str(carpeta)).returncode

def main():
    arg = sys.argv[1].lower().strip() if len(sys.argv) > 1 else ""
    f, dias, marca = fiesta_activa(arg)
    if not f:
        log("No hay fiesta en ventana. Nada que hacer hoy.")
        return
    log("====== FIESTA: %s (en %s dias) · %d por canal ======" % (f["nombre"], dias, POR_CANAL))
    # antes de recorrer 20 shows: hay internet?
    try:
        import socket
        socket.gethostbyname("www.youtube.com")
    except Exception:
        log("*** No hay internet o el DNS no responde (www.youtube.com). No hago nada; vuelve a correr cuando haya red. ***")
        sys.exit(2)
    todas = f["kw"]["he"] + f["kw"]["en"] + f["kw"]["es"]

    shows = []
    for carpeta in sorted(BASE.iterdir()):
        cfgp = carpeta / "config.json"
        if not (carpeta.is_dir() and (carpeta / "podcast_bot.py").exists() and cfgp.exists()):
            continue
        try: cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception: continue
        if cfg.get("modo_whatsapp") or cfg.get("carpeta_whatsapp") or cfg.get("modo") == "whatsapp": continue
        canales = cfg.get("canales_youtube") or ([{"url": cfg["canal_youtube"]}] if cfg.get("canal_youtube") else [])
        canales = [c if isinstance(c, dict) else {"url": c} for c in canales]
        if not canales: continue
        shows.append((carpeta, cfg, canales))

    log("Shows a revisar: %d" % len(shows))
    apartar_no_fiesta(f, todas, shows)
    con_nuevos = []
    for carpeta, cfg, canales in shows:
        idioma = (cfg.get("idioma") or "he")[:2]
        # primero los nombres del idioma del show, luego todos los demas
        palabras = (f["kw"].get(idioma) or []) + [k for k in todas if k not in (f["kw"].get(idioma) or [])]
        log("[%s] buscando: %s ..." % (carpeta.name, palabras[0]))
        elegidos = []
        try:
            for canal in canales:
                url = (canal.get("url") or "").strip()
                if not url: continue
                for (views, dur, vid, tit) in buscar_en_canal(url, palabras):
                    elegidos.append((views, vid, tit))
        except SinInternet as ex:
            log("*** %s. Me detengo; vuelve a correr cuando haya red. ***" % ex)
            sys.exit(2)
        if not elegidos:
            log("    nada encontrado."); continue
        elegidos.sort(reverse=True)
        epi = carpeta / "episodios"
        antes = len(list(epi.glob("*.mp3"))) if epi.exists() else 0
        for views, vid, tit in elegidos[:POR_CANAL * max(1, len(canales))]:
            log("    bajando (%s vistas): %s" % (format(views, ","), tit[:60]))
            bajar(carpeta, vid)
        despues = len(list(epi.glob("*.mp3"))) if epi.exists() else 0
        if despues > antes:
            con_nuevos.append(carpeta)
            log("    %d shiur(im) nuevos de %s." % (despues - antes, f["nombre"]))
        else:
            log("    (ya los tenia todos)")

    ok = 0
    # se sube lo pendiente de TODOS los shows revisados: si una corrida anterior se
    # corto a la mitad, lo que bajo quedo en episodios/ sin subir
    for carpeta, _cfg, _c in shows:
        if carpeta not in con_nuevos:
            con_nuevos.append(carpeta)
    for carpeta in con_nuevos:
        log("[%s] subiendo a Archive y publicando feed..." % carpeta.name)
        correr_bot(carpeta, "apartar")
        if correr_bot(carpeta, "subir") == 0 and correr_bot(carpeta, "feed") == 0:
            ok += 1
        else:
            log("    *** algo fallo en %s, revisa ***" % carpeta.name)

    if marca:
        marcar(f["clave"])
    log("====== FIN %s: %d shows con shiurim nuevos, %d publicados ======" % (f["nombre"], len(con_nuevos), ok))

if __name__ == "__main__":
    main()
