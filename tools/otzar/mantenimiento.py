#!/usr/bin/env python3
"""
Mantenimiento de Otzar: lo corre ANUNCIAR.bat antes de mandar la orden al robot,
sin flags ni intervención. Deja todo listo para que el anuncio salga bien:

  1. Cada show que sube desde WhatsApp (config.json con "modo_whatsapp") lee la
     misma carpeta donde el robot guarda (config_whatsapp.json → escuchar), y lo
     que ya está en su feed queda marcado como publicado (no se resube).
  2. Publica la jabura (jabura_publicar.py) y cada show de WhatsApp (podcast_bot.py).
  3. Espeja el feed de Nacach al repo viejo (nacash), el que lee Spotify.
  4. Sin atrasos: en cada show con "solo_ultimos": N en anunciar, todo lo del feed
     salvo los últimos N queda memorizado en el robot, así el anuncio manda solo
     los N más nuevos y nunca se arrastra un rezago.

    python mantenimiento.py            (desde donde sea; rutas fijas abajo)
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
    if a.startswith("--robot="):
        ROBOT = Path(a.split("=", 1)[1])
AUDIO = (".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".amr")
FEED_JABURA = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/feed.xml"

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(msg):
    print(f"[{time.strftime('%d/%m %H:%M')}] {msg}", flush=True)


def leer_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto if defecto is not None else {}


def bajar(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "otzar-mantenimiento"}), timeout=40) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return ""


def feed_de(show, datos, cfg_show):
    if datos.get("feed", "").startswith("http"):
        return datos["feed"]
    if show == "jabura":
        return FEED_JABURA
    return f"https://{cfg_show.get('github_user', 'rabmeireliyahu')}.github.io/{cfg_show.get('github_repo', show)}/feed.xml"


def carpetas_del_robot(cfgw):
    out = {}
    for show, datos in (cfgw.get("escuchar") or {}).items():
        if isinstance(datos, dict) and datos.get("carpetaDestino"):
            out[show] = datos["carpetaDestino"]
    for e in cfgw.get("escuchar_directo") or []:
        if e.get("show") and e.get("carpetaDestino"):
            out.setdefault(e["show"], e["carpetaDestino"])
    return out


# ── 1. carpetas alineadas y publicados marcados ───────────────────────────────
def alinear_y_marcar(cfgw):
    for show, carpeta in sorted(carpetas_del_robot(cfgw).items()):
        d = BASE / show
        cfgp = d / "config.json"
        if not (d.is_dir() and cfgp.exists()):
            continue
        c = leer_json(cfgp)
        if not c.get("modo_whatsapp"):
            continue
        if str(c.get("carpeta_whatsapp", "")).rstrip("\\").lower() != str(carpeta).rstrip("\\").lower():
            c["carpeta_whatsapp"] = carpeta
            cfgp.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            log(f"{show}: bot apuntado a la carpeta del robot ({carpeta})")
        feed = bajar(feed_de(show, {}, c))
        if not feed:
            continue
        procesados = d / "procesados_whatsapp.txt"
        lista = procesados.read_text(encoding="utf-8").splitlines() if procesados.exists() else []
        marcados = 0
        try:
            audios = [f for f in Path(carpeta).iterdir() if f.is_file() and f.suffix.lower() in AUDIO]
        except Exception:
            audios = []
        for f in audios:
            if f.name in lista:
                continue
            titulo = re.sub(r"\s+", " ", f.stem).strip()
            if f"<title>{titulo}</title>" in feed:
                lista.append(f.name)
                marcados += 1
                mp3 = d / "episodios" / (re.sub(r'[<>:"/\\|?*]', "", f.stem).strip()[:120] + ".mp3")
                if mp3.exists():
                    try:
                        mp3.unlink()
                    except OSError:
                        pass
        if marcados:
            procesados.write_text("\n".join(lista) + "\n", encoding="utf-8")
            log(f"{show}: {marcados} audio(s) ya estaban en el feed, marcados")


# ── 1b. audios apartados "sin título" de shows con titulo_defecto: vuelven con nombre
def rescatar_sin_titulo(cfgw):
    for show, datos in (cfgw.get("escuchar") or {}).items():
        titulo = isinstance(datos, dict) and datos.get("titulo_defecto")
        if not titulo:
            continue
        d = BASE / show
        c = leer_json(d / "config.json")
        carpeta = Path(c.get("carpeta_whatsapp") or (d / "audios_whatsapp"))
        apart = carpeta / "_SIN_TITULO_renombrar"
        if not apart.is_dir():
            continue
        for f in sorted(apart.glob("*")):
            if not (f.is_file() and f.suffix.lower() in AUDIO):
                continue
            m = re.search(r"(\d{1,2}-\d{1,2}-\d{4})", f.stem)
            nuevo = f"{titulo} {m.group(1) if m else time.strftime('%d-%m-%Y', time.localtime(f.stat().st_mtime))}"
            destino = carpeta / (nuevo + f.suffix.lower())
            k = 2
            while destino.exists():
                destino = carpeta / f"{nuevo} ({k}){f.suffix.lower()}"
                k += 1
            f.rename(destino)
            log(f"{show}: '{f.name}' → '{destino.name}'")


# ── 2. publicar ──────────────────────────────────────────────────────────────
# ── 2b. "mp3" que en realidad son video (mp4/mov) o vienen en otro contenedor: archive.org
#        los rechaza ("video file has improper extension"). Se les saca el audio con
#        ffmpeg y quedan como mp3 de verdad, con el mismo nombre. ──────────────────────
def es_mp3_de_verdad(ruta):
    try:
        cab = ruta.read_bytes()[:16]
    except OSError:
        return True
    if cab[:3] == b"ID3" or (len(cab) > 1 and cab[0] == 0xFF and (cab[1] & 0xE0) == 0xE0):
        return True
    return False


def arreglar_mp3_falsos(show):
    carpetas = [show / "episodios", show / "audios_whatsapp", show / "convertidos"]
    c = leer_json(show / "config.json")
    if c.get("carpeta_whatsapp"):
        carpetas.append(Path(c["carpeta_whatsapp"]))
    for carpeta in carpetas:
        if not carpeta.is_dir():
            continue
        for f in sorted(carpeta.glob("*.mp3")):
            if es_mp3_de_verdad(f):
                continue
            tmp = f.with_name(f.stem + ".__real.mp3")
            try:
                r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(f), "-vn",
                                    "-codec:a", "libmp3lame", "-b:a", "96k", str(tmp)])
                ok_ = r.returncode == 0
            except OSError:
                ok_ = False
            if ok_ and tmp.exists() and tmp.stat().st_size > 1000:
                try:
                    f.unlink()
                    tmp.rename(f)
                    log(f"{show.name}: '{f.name}' era video/otro formato; ya es mp3 de verdad")
                except OSError as e:
                    log(f"{show.name}: no pude reemplazar {f.name}: {e}")
            else:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                log(f"{show.name}: no pude convertir {f.name} (¿ffmpeg?)")


def publicar():
    jab = BASE / "jabura"
    if (jab / "jabura_publicar.py").exists():
        log("--- Jabura: subiendo shiurim nuevos ---")
        subprocess.run([sys.executable, "jabura_publicar.py"], cwd=str(jab))
    for show in sorted(BASE.iterdir()):
        cfgp, bot = show / "config.json", show / "podcast_bot.py"
        if not (show.is_dir() and cfgp.exists() and bot.exists()):
            continue
        c = leer_json(cfgp)
        if not c.get("modo_whatsapp") or c.get("manual") or c.get("pausado"):
            continue
        if (show / "PAUSADO.txt").exists() or (show / "PAUSADOS.txt").exists():
            continue
        log(f"--- {show.name}: publicando lo que dejó el robot ---")
        arreglar_mp3_falsos(show)
        subprocess.run([sys.executable, "podcast_bot.py"], cwd=str(show))


# ── 3. espejo nacash ─────────────────────────────────────────────────────────
def espejo():
    nac = BASE / "nacach"
    if (nac / "espejo_nacash.py").exists():
        subprocess.run([sys.executable, "espejo_nacash.py"], cwd=str(nac))


# ── 4. sin atrasos ───────────────────────────────────────────────────────────
def sin_atrasos(cfgw):
    estado_p = ROBOT / "estado_anuncios.json"
    e = leer_json(estado_p)
    cambio = False
    for show, datos in (cfgw.get("anunciar") or {}).items():
        n = datos.get("solo_ultimos")
        if not isinstance(n, int) or n < 1 or datos.get("pausado"):
            continue
        if datos.get("sin_filtro_fecha") or datos.get("curso"):
            continue                      # curso en orden desde el 1: NUNCA se memoriza nada
        feed = bajar(feed_de(show, datos, leer_json(BASE / show / "config.json")))
        if not feed:
            continue
        items = re.findall(r"<item>([\s\S]*?)</item>", feed)
        pares = []
        for it in items:
            g = re.search(r"<guid[^>]*>(.*?)</guid>", it)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not g:
                continue
            try:
                cuando = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
            except Exception:
                cuando = 0
            pares.append((cuando, g.group(1).replace("&amp;", "&")))
        if not pares:
            continue
        guids = [g for _, g in pares]
        ultimos = [g for _, g in sorted(pares)[-n:]]     # los N más nuevos por fecha
        # lo publicado en los últimos 2 días sale completo (varios shiurim del mismo
        # día no son rezago); si son más de 30, se aplica el tope de siempre
        hace2d = time.time() - 2 * 86400
        recientes = [g for c, g in pares if c >= hace2d]
        if len(recientes) <= 30:
            ultimos = list(dict.fromkeys(ultimos + recientes))
        previos = e.get(show) or []
        memorizar = [g for g in guids if g not in ultimos and g not in previos]
        if memorizar or show not in e:
            e[show] = (previos + memorizar)[-2000:]
            cambio = True
            log(f"{show}: {len(memorizar)} viejo(s) memorizados sin anunciar; quedan por salir solo los últimos {n}")
    if cambio:
        try:
            estado_p.with_name(estado_p.name + ".bak_" + time.strftime("%Y%m%d%H%M%S")).write_bytes(estado_p.read_bytes())
        except Exception:
            pass
        estado_p.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 4. parasha semanal ───────────────────────────────────────────────────────
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def parasha_semanal(cfgw):
    """Los dos salen con el ANUNCIAR del lunes ("parasha": {"dia": 0} en el robot;
    si ese día no se aprieta, con el primer ANUNCIAR de la semana hasta el viernes;
    nunca sábado ni domingo, que ya cuentan para la parashá siguiente):
    a) shows con "parasha_semanal": true en su config.json (chazaq): baja de su
       canal de YouTube el shiur de la parasha de la semana y lo publica; el robot
       lo anuncia en este mismo ANUNCIAR. Candado semanal por show.
    b) Rav Asher Weiss (módulo parasha_semanal.js del robot, "parasha": {"auto": true}):
       se deja la orden parasha.ahora; el módulo tiene su candado semanal, no repite."""
    pc = cfgw.get("parasha") or {}
    try:
        dia = int(pc.get("dia", 0))
    except (TypeError, ValueError):
        dia = 0
    hoy = time.localtime().tm_wday
    if not (dia <= hoy <= 4):
        log(f"parasha de la semana: sale con el ANUNCIAR del {DIAS[dia]} (hoy es {DIAS[hoy]}); hoy no")
        return
    script = BASE / "jabura" / "parasha_youtube.py"
    if script.exists():
        log("--- parasha de la semana: shows de YouTube (parasha_semanal) ---")
        subprocess.run([sys.executable, str(script), f"--base={BASE}", f"--robot={ROBOT}"])
    if pc.get("auto") and (ROBOT / "parasha_semanal.js").exists():
        flag = ROBOT / "parasha.ahora"
        if not flag.exists():
            try:
                flag.write_text("ahora", encoding="utf-8")
                log("parasha de Rav Asher Weiss: orden dejada al robot (parasha.ahora); si ya salió esta semana, el módulo no repite")
            except Exception as ex:
                log(f"no pude dejar parasha.ahora: {ex}")


def main():
    cfgw = leer_json(ROBOT / "config_whatsapp.json")
    if not cfgw:
        log(f"no encuentro {ROBOT / 'config_whatsapp.json'}")
        return 1
    alinear_y_marcar(cfgw)
    rescatar_sin_titulo(cfgw)
    publicar()
    espejo()
    parasha_semanal(cfgw)
    sin_atrasos(cfgw)
    log("mantenimiento listo; ahora el robot anuncia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
