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

HUBO_NUEVOS = False          # True si esta corrida subió shiurim nuevos (sale con código 3)
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
    global HUBO_NUEVOS
    HUBO_NUEVOS = subidos > 0
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

# ── el orden del feed es el de la app ────────────────────────────────────────
# Lo más viejo es el musar, después חגים, y luego los simanim por número: מוקצה
# (ש״ח), שי״ג, שי״ד… hasta ש״מ, que queda al final como lo más nuevo. Los módulos
# que comparten siman (מעבד·טוחן·לש en שכ״א, גוזז·כותב ומוחק en ש״מ) van en ese
# orden. Una carpeta nueva que nombre su siman ("סימן שמא") se ubica por el número.
ORDEN = [
    ("שאול לניאדו", 0), ("רב יהודה חאסקי שליט א", 1), ("שיחות מוסר", 2), ("חגים", 3),
    ("מוקצה", 308), ("סימן שי ג בונה וסותר", 313), ("סימן שי ד בנין וסתירה בכלים", 314),
    ("סימן שט ו אוהל", 315), ("צידה", 316), ("קושר", 317), ("בורר", 319),
    ("מלאכת סחיטה - דש", 320), ("מלאכת מעבד", 321.0), ("טוחן", 321.1), ("לש", 321.2),
    ("גוזז", 340.0), ("כותב ומוחק", 340.1),
]
GEMATRIA = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10, "כ": 20, "ך": 20,
            "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50, "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90, "ץ": 90,
            "ק": 100, "ר": 200, "ש": 300, "ת": 400}


def norm(t):
    t = re.sub(r"[\u0591-\u05BD\u05BF-\u05C7]", "", str(t))
    t = re.sub(r"[׳״'\"]", "", t)
    return re.sub(r"\s+", " ", re.sub(r"[`.\-_·־–—\[\]()]", " ", t)).strip().lower()


ORDEN_N = [(norm(k), v) for k, v in ORDEN]


def siman_de_carpeta(nombre):
    m = re.match(r"^(?:סימן|סי)?\s*([\u05D0-\u05EA]{1,5}|\d{1,3})(?:\s|$)", norm(nombre))
    if not m:
        return 0
    v = m.group(1)
    n = int(v) if v.isdigit() else sum(GEMATRIA.get(c, 0) for c in v)
    return n if 242 <= n <= 365 else 0


def rango(remoto):
    """(módulo, número dentro del módulo, nombre) para ordenar como la app."""
    partes = remoto.split("/")
    dirs, base = partes[:-1], partes[-1]
    mod = 999.0
    for d in reversed(dirs):
        k = norm(d)
        hit = next((v for kk, v in ORDEN_N if kk == k), None)
        if hit is None:
            n = siman_de_carpeta(d)
            hit = float(n) if n else None
        if hit is not None:
            mod = float(hit)
            break
    m = re.match(r"^\s*\[?(\d{1,3})\]?", base)
    num = int(m.group(1)) if m else 900
    return (mod, num, norm(base))


FECHAS = Path("fechas.json")


def feed_url_de(cfg):
    """Dónde vive el feed: por defecto GitHub Pages del repo; "feed_url" en
    config.json lo cambia (la jabura lo sirve Netlify junto con la app)."""
    return (cfg.get("feed_url") or f"https://{cfg['github_user']}.github.io/{cfg['github_repo']}").rstrip("/")


def fechas_del_feed(entradas, cfg=None):
    """Cada episodio conserva su fecha entre corridas (fechas.json). La primera vez
    se reparten hacia atrás desde hoy, en el orden de la app, cada 12 horas; los
    que llegan después toman la fecha del archivo (o ahora), siempre más nueva
    que todo lo anterior, para que Spotify y el robot los vean como nuevos."""
    fechas = {}
    if FECHAS.exists():
        try:
            fechas = json.loads(FECHAS.read_text(encoding="utf-8"))
        except Exception:
            fechas = {}
    if not fechas and cfg:
        # sin copia local (PC nueva): las fechas ya publicadas mandan, para que
        # el orden y las fechas no cambien entre una máquina y otra
        try:
            with urllib.request.urlopen(feed_url_de(cfg) + "/fechas.json", timeout=30) as r:
                fechas = json.loads(r.read().decode("utf-8"))
            log(f"fechas.json tomado del feed publicado ({len(fechas)} fechas).")
        except Exception:
            fechas = {}
    ahora = time.time()
    nuevos = [e for e in entradas if e["guid"] not in fechas]
    if not fechas and nuevos:                           # primera vez: todos hacia atrás
        for i, e in enumerate(nuevos):
            fechas[e["guid"]] = ahora - (len(nuevos) - 1 - i) * 12 * 3600
    else:
        tope = max(fechas.values(), default=0)
        for e in nuevos:
            f = max(e["mtime"], tope + 60, ahora - 60)
            fechas[e["guid"]] = f
            tope = f
    FECHAS.write_text(json.dumps(fechas, ensure_ascii=False, indent=0), encoding="utf-8")
    return fechas


def armar_feed(cfg, archivos, remotos_en_archive):
    """archivos: [(local, remoto)] del Drive; solo entran los que ya están arriba."""
    base_url = f"https://archive.org/download/{cfg['archive_id']}"
    feed_url = feed_url_de(cfg)
    entradas = []
    for local, remoto in archivos:
        if SA.extension(Path(remoto).name) not in AUDIO and Path(remoto).suffix.lower() not in AUDIO:
            continue
        if remoto not in remotos_en_archive:
            continue
        try:
            st = os.stat(local)
            mtime, peso = st.st_mtime, st.st_size
        except OSError:
            mtime, peso = time.time(), 0
        mod, num, nombre = rango(remoto)
        # sin número en el nombre (musar, ועדים): por fecha del archivo
        entradas.append({"guid": remoto, "mtime": mtime, "peso": peso,
                         "orden": (mod, num, mtime if num == 900 else 0, nombre)})
    entradas.sort(key=lambda e: e["orden"])             # el orden de la app
    fechas = fechas_del_feed(entradas, cfg)
    items = []
    for e in entradas:
        remoto, peso, cuando = e["guid"], e["peso"], fechas[e["guid"]]
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
    <link>{cfg.get("link") or feed_url}</link>
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


# ── 4. la lista de episodios de Spotify, para que la app enlace cada shiur ───
def llaves_spotify(cfg):
    """Client ID y secret de la API de Spotify: variables de entorno, o
    spotify_keys.txt (línea 1 = ID, línea 2 = secret) aquí o en la carpeta del
    robot, que ya las usa para anunciar."""
    cid, sec = os.environ.get("SPOTIFY_CLIENT_ID", "").strip(), os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if cid and sec:
        return cid, sec
    for ruta in [Path("spotify_keys.txt"), Path(cfg.get("robot", r"C:\robotwhats")) / "spotify_keys.txt"]:
        try:
            l = [x.strip() for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
            if len(l) >= 2:
                return l[0], l[1]
        except Exception:
            pass
    return "", ""


def episodios_spotify(cfg):
    show = cfg.get("spotify_show", "")
    m = re.search(r"show/([A-Za-z0-9]+)", show)
    if not m:
        return None
    cid, sec = llaves_spotify(cfg)
    if not cid:
        log("Sin llaves de Spotify (spotify_keys.txt): no actualizo la lista de episodios.")
        return None
    try:
        cred = base64.b64encode(f"{cid}:{sec}".encode()).decode()
        req = urllib.request.Request("https://accounts.spotify.com/api/token", data=b"grant_type=client_credentials",
                                     headers={"Authorization": "Basic " + cred,
                                              "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            token = json.loads(r.read().decode())["access_token"]
        salida, offset = [], 0
        while True:
            url = f"https://api.spotify.com/v1/shows/{m.group(1)}/episodes?limit=50&offset={offset}&market={cfg.get('market', 'MX')}"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer " + token}), timeout=30) as r:
                pagina = json.loads(r.read().decode())
            for ep in pagina.get("items") or []:
                if ep:
                    salida.append({"titulo": (ep.get("name") or "").strip(),
                                   "enlace": (ep.get("external_urls") or {}).get("spotify", ""),
                                   "fecha": ep.get("release_date", "")})
            if not pagina.get("next"):
                break
            offset += 50
        log(f"Spotify: {len(salida)} episodios en el show.")
        return salida
    except Exception as e:                              # noqa: BLE001
        log(f"Spotify: no pude leer los episodios ({e}).")
        return None


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
        log(f"feed.xml publicado: {feed_url_de(cfg)}/feed.xml")
        if FECHAS.exists():
            subir_archivo(cab, base, "fechas.json", FECHAS.read_bytes(), "fechas del feed")
        st, _ = gh(cab, "GET", f"{base}/contents/portada.jpg")
        if st == 404 and Path("portada.jpg").exists():
            subir_archivo(cab, base, "portada.jpg", Path("portada.jpg").read_bytes(), "portada")
        eps = episodios_spotify(cfg)
        if eps:
            datos = json.dumps(eps, ensure_ascii=False, indent=1).encode("utf-8")
            Path("spotify_episodios.json").write_bytes(datos)
            ok2, msg2 = subir_archivo(cab, base, "spotify_episodios.json", datos, "episodios de Spotify")
            log("Lista de Spotify publicada: la app enlaza cada shiur con su episodio." if ok2 else f"No subí la lista de Spotify: {msg2}")
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
    publicado = subir_feed(cfg, xml)
    log("Listo. En la app, los nuevos aparecen solos al entrar como admin.")
    if HUBO_NUEVOS and publicado:
        sys.exit(3)                  # aviso para auto_publicar.bat: hay que anunciar


if __name__ == "__main__":
    main()
