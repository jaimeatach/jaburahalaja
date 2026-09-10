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
import urllib.error
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
RAW_REPO = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/otzar/"


def gh(cab, metodo, url, cuerpo=None):
    """Una llamada a la API de GitHub. Devuelve (status, json) y no revienta."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            texto = r.read().decode()
            return r.status, (json.loads(texto) if texto.strip() else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:                              # noqa: BLE001
        return 0, {"message": str(e)}


def subir_archivo(cab, base, ruta, contenido, mensaje):
    """Crea o actualiza un archivo del repo (PUT contents)."""
    st, j = gh(cab, "GET", f"{base}/contents/{ruta}")
    cuerpo = {"message": mensaje, "content": base64.b64encode(contenido).decode()}
    if st == 200 and j.get("sha"):
        cuerpo["sha"] = j["sha"]
    st, j = gh(cab, "PUT", f"{base}/contents/{ruta}", cuerpo)
    return st in (200, 201), j.get("message", "")


def asegurar_repo(cfg, cab):
    """Si el repo del feed no existe, lo crea y le prende GitHub Pages (main, raíz),
    igual que los otros shows de Otzar. Devuelve True si el repo está listo."""
    base = f"https://api.github.com/repos/{cfg['github_user']}/{cfg['github_repo']}"
    st, _ = gh(cab, "GET", base)
    if st == 200:
        return True
    if st != 404:
        log(f"No pude ver el repo ({st}): revisa github_token.txt")
        return False
    log(f"El repo {cfg['github_user']}/{cfg['github_repo']} no existe: lo creo.")
    cuerpo = {"name": cfg["github_repo"], "description": cfg.get("titulo", ""), "private": False,
              "has_issues": False, "has_wiki": False, "auto_init": False}
    st, j = gh(cab, "POST", "https://api.github.com/user/repos", cuerpo)
    if st not in (200, 201):
        log(f"ERROR creando el repo: {st} {j.get('message', '')}")
        log("   (el token tiene que ser de la cuenta " + cfg["github_user"] + " y tener permiso 'repo')")
        return False
    log("Repo creado.")
    # README y portada: con el primer archivo nace la rama main
    ok_, msg = subir_archivo(cab, base, "README.md",
                             f"# {cfg['github_repo']}\n{cfg.get('titulo', '')}\n\nFeed: https://{cfg['github_user']}.github.io/{cfg['github_repo']}/feed.xml\n".encode(),
                             "readme")
    if not ok_:
        log(f"ERROR subiendo README: {msg}")
        return False
    portada = Path("portada.jpg")
    if not portada.exists():
        try:
            with urllib.request.urlopen(RAW_REPO + "portada.jpg", timeout=60) as r:
                portada.write_bytes(r.read())
        except Exception:                               # noqa: BLE001
            pass
    if portada.exists():
        ok_, msg = subir_archivo(cab, base, "portada.jpg", portada.read_bytes(), "portada")
        log("Portada subida." if ok_ else f"No subí la portada: {msg}")
    for intento in range(3):
        st, j = gh(cab, "POST", f"{base}/pages", {"source": {"branch": "main", "path": "/"}})
        if st in (200, 201):
            log(f"GitHub Pages prendido: https://{cfg['github_user']}.github.io/{cfg['github_repo']}/")
            break
        if st == 409:                                   # ya estaba prendido
            break
        time.sleep(4)
    else:
        log(f"No pude prender Pages ({st} {j.get('message', '')}); préndelo a mano en Settings → Pages (main, /root).")
    return True


def subir_feed(cfg, xml):
    tok = Path("github_token.txt")
    if not tok.exists():
        log("Falta github_token.txt: el feed quedó en feed.xml pero no se publicó.")
        return False
    token = tok.read_text(encoding="utf-8").strip()
    cab = {"Authorization": f"token {token}", "User-Agent": "jabura-publicar", "Accept": "application/vnd.github+json"}
    if not asegurar_repo(cfg, cab):
        return False
    base = f"https://api.github.com/repos/{cfg['github_user']}/{cfg['github_repo']}"
    ok_, msg = subir_archivo(cab, base, "feed.xml", xml.encode("utf-8"),
                             f"feed jabura {datetime.now():%d/%m/%Y %H:%M}")
    if ok_:
        log(f"feed.xml publicado: https://{cfg['github_user']}.github.io/{cfg['github_repo']}/feed.xml")
        return True
    log(f"ERROR publicando el feed: {msg}")
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
