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


# ── 2. publicar ──────────────────────────────────────────────────────────────
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
        previos = e.get(show) or []
        memorizar = [g for g in guids if g not in ultimos and g not in previos]
        if memorizar or show not in e:
            e[show] = (previos + memorizar)[-2000:]
            cambio = True
            log(f"{show}: {len(memorizar)} viejo(s) memorizados sin anunciar; quedan por salir solo los últimos {n}")
    if cambio:
        estado_p.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    cfgw = leer_json(ROBOT / "config_whatsapp.json")
    if not cfgw:
        log(f"no encuentro {ROBOT / 'config_whatsapp.json'}")
        return 1
    alinear_y_marcar(cfgw)
    publicar()
    espejo()
    sin_atrasos(cfgw)
    log("mantenimiento listo; ahora el robot anuncia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
