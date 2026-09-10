#!/usr/bin/env python3
"""
Publica los shiurim nuevos de la jabura: Drive → archive.org → feed.xml → GitHub.
Es el equivalente de "podcast_bot.py robot" para la jabura, con dos diferencias
que importan:

  - NUNCA borra nada del Drive: esa carpeta es la fuente, la lee también la app.
  - Sube conservando las subcarpetas (שיעורים בהלכה/בורר/…), que es de donde la
    app y el feed sacan el orden y el siman.

Lee config.json de la carpeta donde se corre (mismo formato que los otros shows):
  archive_id, github_user, github_repo, titulo, descripcion, autor, email, idioma
  y "carpeta": la ruta del Drive de la jabura.

    python jabura_publicar.py          # sube lo nuevo, arma el feed y lo publica
    python jabura_publicar.py --ver    # solo muestra qué haría

Credenciales, igual que siempre: IA_ACCESS_KEY / IA_SECRET_KEY (o `ia configure`)
y github_token.txt en esta carpeta.
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subir_a_archive as SA   # noqa: E402  (listar, extension, humano)

for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

AUDIO = {".m4a", ".mp3", ".mp4", ".m4v", ".mov", ".wav", ".ogg", ".opus", ".aac", ".wma", ".aif", ".aiff", ".3gp"}


def log(msg):
    print(f"[{datetime.now():%d/%m %H:%M}] {msg}")


def cargar_config():
    ruta = Path("config.json")
    if not ruta.exists():
        sys.exit("Falta config.json en esta carpeta.")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# ── 1. subir lo nuevo a archive.org, conservando la ruta ─────────────────────
def subir_nuevos(cfg, archivos, ver):
    from internetarchive import get_item
    claves = {}
    if os.environ.get("IA_ACCESS_KEY") and os.environ.get("IA_SECRET_KEY"):
        claves = {"access_key": os.environ["IA_ACCESS_KEY"], "secret_key": os.environ["IA_SECRET_KEY"]}
    item = get_item(cfg["archive_id"])
    ya = {f["name"] for f in (item.files or [])}
    pendientes = [(l, r) for l, r in archivos if r not in ya]
    log(f"En el Drive: {len(archivos)} · ya en archive.org: {len(archivos) - len(pendientes)} · por subir: {len(pendientes)}")
    if ver or not pendientes:
        for _, r in pendientes[:10]:
            print("    (subiría)", r)
        return ya | {r for _, r in pendientes} if ver else ya
    subidos = 0
    for i, (local, remoto) in enumerate(pendientes, 1):
        for intento in range(1, 4):
            try:
                item.upload({remoto: local}, retries=3, retries_sleep=5, verbose=False, **claves)
                log(f"  ok  [{i}/{len(pendientes)}] {remoto}")
                subidos += 1
                ya.add(remoto)
                break
            except Exception as e:                      # noqa: BLE001
                if intento == 3:
                    log(f"  FALLA {remoto}: {e}")
                else:
                    time.sleep(5 * intento)
    log(f"Subidos {subidos} de {len(pendientes)}.")
    return ya


# ── 2. el feed: todos los audios del ítem, en orden ──────────────────────────
def titulo_de(remoto):
    """'שיעורים בהלכה/בורר/05. הקדמה.m4a' → 'בורר · הקדמה'. El módulo (la carpeta)
    va adelante salvo que el nombre ya lo diga, para que en Spotify se entienda
    de qué siman es cada episodio."""
    partes = remoto.split("/")
    base = re.sub(r"\.[^.]+$", "", partes[-1])
    base = re.sub(r"^\s*\[?\d{1,3}\]?[.\-_\s]*", "", base)     # "05. titulo" → "titulo"
    base = re.sub(r"\s+", " ", base).strip() or Path(remoto).stem
    modulo = partes[-2] if len(partes) >= 2 else ""
    if modulo in ("שיעורים", "audios", "audio"):                 # subcarpeta genérica
        modulo = partes[-3] if len(partes) >= 3 else ""
    if modulo and not re.match(r"^שיעורים", modulo) and modulo not in base:
        return f"{modulo} · {base}"
    return base


MIME = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac",
        ".ogg": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav"}


def armar_feed(cfg, archivos, remotos_en_archive):
    """archivos: [(local, remoto)] del Drive; solo entran los que ya están arriba."""
    base_url = f"https://archive.org/download/{cfg['archive_id']}"
    feed_url = f"https://{cfg['github_user']}.github.io/{cfg['github_repo']}"
    entradas = []
    for local, remoto in archivos:
        if SA.extension(Path(remoto).name) not in AUDIO and Path(remoto).suffix.lower() not in AUDIO:
            continue
        if remoto not in remotos_en_archive:
            continue
        try:
            st = os.stat(local)
            cuando, peso = st.st_mtime, st.st_size
        except OSError:
            cuando, peso = time.time(), 0
        entradas.append((cuando, remoto, peso))
    entradas.sort()                                     # del más viejo al más nuevo
    items = []
    for cuando, remoto, peso in entradas:
        url = base_url + "/" + "/".join(quote(p) for p in remoto.split("/"))
        items.append(f"""    <item>
      <title>{escape(titulo_de(remoto))}</title>
      <description>{escape(titulo_de(remoto))}</description>
      <enclosure url="{url}" length="{peso}" type="{MIME.get(Path(remoto).suffix.lower(), 'audio/mpeg')}"/>
      <guid isPermaLink="false">{escape(remoto)}</guid>
      <pubDate>{format_datetime(datetime.fromtimestamp(cuando))}</pubDate>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(cfg["titulo"])}</title>
    <description>{escape(cfg["descripcion"])}</description>
    <link>{feed_url}</link>
    <language>{cfg.get("idioma", "es")}</language>
    <itunes:author>{escape(cfg["autor"])}</itunes:author>
    <itunes:owner><itunes:name>{escape(cfg["autor"])}</itunes:name><itunes:email>{cfg["email"]}</itunes:email></itunes:owner>
    <itunes:image href="{feed_url}/portada.jpg"/>
    <itunes:category text="Religion &amp; Spirituality"/>
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
""", len(items)


# ── 3. publicar el feed en GitHub (mismo método que podcast_bot) ─────────────
def subir_feed(cfg, xml):
    tok = Path("github_token.txt")
    if not tok.exists():
        log("Falta github_token.txt: el feed quedó en feed.xml pero no se publicó.")
        return False
    token = tok.read_text(encoding="utf-8").strip()
    api = f"https://api.github.com/repos/{cfg['github_user']}/{cfg['github_repo']}/contents/feed.xml"
    cab = {"Authorization": f"token {token}", "User-Agent": "jabura-publicar", "Accept": "application/vnd.github+json"}
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=cab)) as r:
            sha = json.loads(r.read().decode())["sha"]
    except Exception:
        pass
    cuerpo = {"message": f"feed jabura {datetime.now():%d/%m/%Y %H:%M}",
              "content": base64.b64encode(xml.encode("utf-8")).decode()}
    if sha:
        cuerpo["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
    try:
        with urllib.request.urlopen(req) as r:
            if r.status in (200, 201):
                log("feed.xml publicado en GitHub.")
                return True
    except Exception as e:                              # noqa: BLE001
        log(f"ERROR publicando el feed: {e}")
    return False


def main():
    ver = "--ver" in sys.argv
    cfg = cargar_config()
    carpeta = cfg.get("carpeta") or SA.CARPETA
    if not os.path.isdir(carpeta):
        sys.exit(f"No encuentro la carpeta del Drive:\n  {carpeta}")
    archivos, dudosos = SA.listar(carpeta)
    if dudosos:
        log(f"OJO: {len(dudosos)} archivos sin extensión que no identifiqué; se saltean.")
    arriba = subir_nuevos(cfg, archivos, ver)
    xml, n = armar_feed(cfg, archivos, arriba)
    Path("feed.xml").write_text(xml, encoding="utf-8")
    log(f"feed.xml con {n} episodios.")
    if ver:
        log("Prueba en seco: no se subió ni se publicó nada.")
        return
    subir_feed(cfg, xml)
    log("Listo. En la app, los nuevos aparecen solos al entrar como admin.")


if __name__ == "__main__":
    main()
