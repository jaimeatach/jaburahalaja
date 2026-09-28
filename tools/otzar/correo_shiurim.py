#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORREO → SHOW · Otzar HaTorah
Baja los audios que llegan por correo (adjuntos o links de Google Drive) y los
deja en la carpeta de WhatsApp del show, ORDENADOS, para que ANUNCIAR los
publique (podcast_bot.py en modo_whatsapp) y Spotify los lea en ese orden.

Lo corre mantenimiento.py en cada ANUNCIAR (o a mano):
    python correo_shiurim.py            todos los shows con "correo" en su config.json
    python correo_shiurim.py taamim     solo ese show
    --ver      prueba en seco: dice qué bajaría, no guarda nada
    --todos    revisa también los correos ya procesados (por si se borró algo)

config.json del show:
    "correo": {
        "usuario": "bamiga@autentafoods.com",        # buzón donde llegan
        "de": ["credi71@gmail.com"],                 # remitente(s) que cuentan
        "servidor": "imap.gmail.com",                # opcional: se adivina
        "desde": "2026-09-01",                       # opcional: correos desde esa fecha
        "orden": "tanaj"                             # parashá → Tehilim → Rut → Ester → resto
    }
La clave (contraseña de aplicación, no la normal) va en correo_clave.txt en la
carpeta del show (o en C:\\OTZAR\\correo_clave.txt para todos). Nunca en el config.

Orden: dentro de cada tanda, primero las parashiot en el orden de la Torá (en
cualquier grafía: פרשת בראשית, Bereshit, Bereishis…), luego Tehilim por capítulo
(תהלים כ״ג / Tehilim 23), luego Rut, luego Ester, y al final lo demás. Las fechas
se asignan seguidas después de lo último que ya tiene el feed, así en Spotify
quedan en ese orden y siempre arriba de lo anterior. Lo que ya está en el feed
(por título) no se vuelve a subir. Candado: correo_procesados.json.
"""
import email, email.header, email.utils, imaplib, json, os, re, socket, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(r"C:\OTZAR")
VER = "--ver" in sys.argv
TODOS = "--todos" in sys.argv
SHOWS_PEDIDOS = []
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
    elif not a.startswith("--"):
        SHOWS_PEDIDOS.append(a.strip().lower())

AUDIO = (".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".wma", ".amr", ".flac")
GENERICO_RX = re.compile(r"^(audio|voice|ptt|rec|recording|whatsapp ?audio|aud|new recording|voz|grabaci[oó]n|msg|vn|voice ?note|nota de voz|audio track)\b", re.I)


def es_generico(stem):
    """'WhatsApp Audio 2026-09-20 at 10.00.01', 'PTT-20260921-WA0001', 'audio', '123' → sin título real."""
    if GENERICO_RX.match(stem or ""):
        return True
    return len(re.sub(r"[^A-Za-z\u05D0-\u05EA]", "", stem or "")) <= 3

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(m):
    print("[%s] CORREO %s" % (time.strftime("%d/%m %H:%M"), m), flush=True)


# ─────────── orden: parashá → Tehilim → Rut → Ester ───────────
PARASHIOT = [
    ("בראשית", ["Bereshit", "Bereishit", "Bereishis", "Beraishis", "Bereshis", "Breishit"]),
    ("נח", ["Noach", "Noaj"]), ("לך לך", ["Lech Lecha", "Lech-Lecha"]), ("וירא", ["Vayera", "Vayeira"]),
    ("חיי שרה", ["Chayei Sara", "Chayei Sarah", "Chaye Sara"]), ("תולדות", ["Toldot", "Toldos", "Toledot"]),
    ("ויצא", ["Vayetzei", "Vayeitzei", "Vayetze"]), ("וישלח", ["Vayishlach", "Vayishlaj"]),
    ("וישב", ["Vayeshev", "Vayeishev"]), ("מקץ", ["Miketz", "Mikeitz"]), ("ויגש", ["Vayigash"]),
    ("ויחי", ["Vayechi", "Vayeji"]), ("שמות", ["Shemot", "Shemos", "Shmot"]), ("וארא", ["Vaera", "Va'era", "Vaeira"]),
    ("בא", ["Bo"]), ("בשלח", ["Beshalach", "Beshalaj"]), ("יתרו", ["Yitro", "Yisro"]), ("משפטים", ["Mishpatim"]),
    ("תרומה", ["Terumah", "Teruma"]), ("תצוה", ["Tetzaveh", "Tetzave"]), ("כי תשא", ["Ki Tisa", "Ki Sisa"]),
    ("ויקהל", ["Vayakhel"]), ("פקודי", ["Pekudei", "Pekude"]), ("ויקרא", ["Vayikra"]), ("צו", ["Tzav"]),
    ("שמיני", ["Shmini", "Shemini"]), ("תזריע", ["Tazria"]), ("מצורע", ["Metzora"]),
    ("אחרי מות", ["Achrei Mot", "Acharei Mot", "Acharei Mos", "Ajarei Mot"]), ("קדושים", ["Kedoshim"]),
    ("אמור", ["Emor"]), ("בהר", ["Behar"]), ("בחוקותי", ["Bechukotai", "Bechukosai", "Bejukotai"]),
    ("במדבר", ["Bamidbar"]), ("נשא", ["Nasso", "Naso"]), ("בהעלותך", ["Beha'alotcha", "Behaalotcha", "Behaaloscha", "Behaalotja"]),
    ("שלח", ["Sh'lach", "Shlach", "Shelach", "Shelaj"]), ("קרח", ["Korach", "Koraj"]), ("חוקת", ["Chukat", "Chukas", "Jukat"]),
    ("בלק", ["Balak"]), ("פנחס", ["Pinchas", "Pinjas"]), ("מטות", ["Matot", "Mattos", "Matos"]), ("מסעי", ["Masei", "Massei"]),
    ("דברים", ["Devarim"]), ("ואתחנן", ["Vaetchanan", "Va'etchanan", "Vaetjanan"]), ("עקב", ["Eikev", "Ekev"]),
    ("ראה", ["Re'eh", "Reeh"]), ("שופטים", ["Shoftim"]), ("כי תצא", ["Ki Teitzei", "Ki Seitzei", "Ki Tetze", "Ki Tetzé"]),
    ("כי תבוא", ["Ki Tavo", "Ki Savo"]), ("נצבים", ["Nitzavim"]), ("וילך", ["Vayeilech", "Vayelech", "Vayelej"]),
    ("האזינו", ["Ha'azinu", "Haazinu"]), ("וזאת הברכה", ["Vezot Haberakhah", "V'zot Habracha", "Vezot Habracha", "Zot Habracha"]),
]
GEMATRIA = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10, "כ": 20, "ך": 20,
            "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50, "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90, "ץ": 90,
            "ק": 100, "ר": 200, "ש": 300, "ת": 400}


def _norm(t):
    t = re.sub(r"[\u0591-\u05C7]", "", str(t or "")).lower().replace("'", "").replace("’", "").replace("׳", "").replace("״", "")
    return " " + re.sub(r"[^\w\u05D0-\u05EA]+", " ", t).strip() + " "


def _numero(texto):
    """'23', 'כג', 'ק״נ' → número (después de la palabra Tehilim/perek)."""
    m = re.search(r"(\d{1,3})", texto)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:פרק|מזמור|תהלים|תהילים)\s*([\u05D0-\u05EA]{1,4})\b", texto)
    if m:
        return sum(GEMATRIA.get(c, 0) for c in m.group(1))
    return 0


def clasificar(titulo):
    """→ (categoria, indice): 0 parashá, 1 Tehilim, 2 Rut, 3 Ester, 4 otro."""
    t = _norm(titulo)
    for i, (heb, grafias) in enumerate(PARASHIOT):
        for g in [heb] + grafias:
            g = _norm(g).strip()
            if (" " + g + " ") in t:
                return 0, i + 1
    if re.search(r"תהל?ים|tehil+im|salmo|psalm|מזמור", titulo, re.I):
        return 1, _numero(titulo)
    if re.search(r"\bרות\b|\bruth?\b", titulo, re.I):
        return 2, _numero(titulo)
    if re.search(r"אסתר|est[h]?er", titulo, re.I):
        return 3, _numero(titulo)
    return 4, 0


# ─────────── correo ───────────
def decodificar(s):
    if not s:
        return ""
    partes = []
    for texto, cod in email.header.decode_header(s):
        if isinstance(texto, bytes):
            try:
                texto = texto.decode(cod or "utf-8", "replace")
            except Exception:
                texto = texto.decode("utf-8", "replace")
        partes.append(texto)
    return "".join(partes).strip()


def limpiar_titulo(s):
    s = re.sub(r"^\s*((fwd?|re|rv|fw)\s*:\s*)+", "", s, flags=re.I)
    s = s.replace("_", " ")
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    return re.sub(r"\s+", " ", s).strip()[:120]


def leer_clave(carpeta):
    for p in (carpeta / "correo_clave.txt", BASE / "correo_clave.txt"):
        if p.exists():
            c = p.read_text(encoding="utf-8", errors="replace").strip().replace(" ", "")
            if c:
                return c
    return None


def conectar(cfg, clave):
    usuario = cfg["usuario"]
    dominio = usuario.split("@")[-1].lower()
    candidatos = [cfg.get("servidor")] if cfg.get("servidor") else []
    if dominio in ("gmail.com", "googlemail.com"):
        candidatos.append("imap.gmail.com")
    candidatos += ["imap.gmail.com", "outlook.office365.com", "imap." + dominio, "mail." + dominio]
    ultimo = None
    for host in dict.fromkeys(c for c in candidatos if c):
        try:
            m = imaplib.IMAP4_SSL(host, 993, ssl_context=ssl.create_default_context(), timeout=15)
        except (socket.error, ssl.SSLError, OSError) as ex:
            ultimo = "%s: %s" % (host, str(ex)[:120])
            continue                                   # ese servidor no existe: probar otro
        try:
            m.login(usuario, clave)
            return m, host
        except imaplib.IMAP4.error as ex:
            # el servidor sí es, pero rechazó la contraseña: no tiene caso seguir probando
            raise Exception("%s rechazó la contraseña de %s (%s). Tiene que ser una contraseña de APLICACIÓN." % (host, usuario, str(ex)[:100]))
    raise Exception(ultimo or "sin servidor")


def buscar_ids(m, cfg):
    m.select(cfg.get("carpeta") or "INBOX", readonly=True)
    partes = []
    remitentes = cfg.get("de") or []
    if isinstance(remitentes, str):
        remitentes = [remitentes]
    crit = []
    for r in remitentes:
        crit.append('FROM "%s"' % r)
    if cfg.get("desde"):
        try:
            d = datetime.strptime(cfg["desde"], "%Y-%m-%d").strftime("%d-%b-%Y")
            partes.append("SINCE %s" % d)
        except ValueError:
            pass
    if crit:
        # IMAP: OR anidado para varios remitentes
        q = crit[0]
        for c in crit[1:]:
            q = "OR %s %s" % (c, q)
        partes.append(q)
    consulta = "(%s)" % " ".join(partes) if partes else "ALL"
    tip, datos = m.search(None, consulta)
    if tip != "OK":
        return []
    return [x for x in datos[0].split() if x]


DRIVE_RX = re.compile(r"https?://drive\.google\.com/(?:file/d/([-\w]{20,})|open\?id=([-\w]{20,})|uc\?[^\s\"'<>]*id=([-\w]{20,}))")


def bajar_drive(fid, destino_dir):
    """Baja un archivo compartido de Google Drive (link 'cualquiera con el link')."""
    url = "https://drive.google.com/uc?export=download&id=" + fid
    cab = {"User-Agent": "Mozilla/5.0"}
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    r = op.open(urllib.request.Request(url, headers=cab), timeout=120)
    ctype = r.headers.get("Content-Type", "")
    if "text/html" in ctype:
        html = r.read().decode("utf-8", "replace")
        m = re.search(r'confirm=([0-9A-Za-z_-]+)', html)
        uuid = re.search(r'name="uuid" value="([^"]+)"', html)
        url2 = "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=%s" % (fid, m.group(1) if m else "t")
        if uuid:
            url2 += "&uuid=" + uuid.group(1)
        r = op.open(urllib.request.Request(url2, headers=cab), timeout=300)
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            raise Exception("Drive no deja bajar el archivo (¿está compartido con link?)")
    nombre = ""
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="([^"]+)"', cd)
    if m:
        nombre = urllib.parse.unquote(m.group(1))
    datos = r.read()
    return nombre, datos


def titulos_del_feed(cfgshow):
    try:
        url = "https://%s.github.io/%s/feed.xml" % (cfgshow.get("github_user", "rabmeireliyahu"), cfgshow.get("github_repo"))
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "otzar-correo"}), timeout=40) as r:
            xml = r.read().decode("utf-8", "replace")
        return set(_norm(re.sub(r"<!\[CDATA\[|\]\]>", "", t)).strip() for t in re.findall(r"<title>(.*?)</title>", xml, re.S)), xml
    except Exception as ex:
        log("no pude leer el feed del show (%s); no descarto repetidos" % str(ex)[:80])
        return set(), ""


def fecha_max_feed(xml):
    mx = 0
    for d in re.findall(r"<pubDate>(.*?)</pubDate>", xml):
        try:
            mx = max(mx, email.utils.parsedate_to_datetime(d.strip()).timestamp())
        except Exception:
            pass
    return mx


def procesar_show(carpeta, cfgshow):
    cfg = cfgshow.get("correo") or {}
    if not cfg.get("usuario"):
        return
    clave = leer_clave(carpeta)
    if not clave:
        log("[%s] falta correo_clave.txt (contraseña de aplicación del buzón %s)" % (carpeta.name, cfg["usuario"]))
        return
    destino = Path(cfgshow.get("carpeta_whatsapp") or (carpeta / "audios_whatsapp"))
    destino.mkdir(parents=True, exist_ok=True)
    proc_p = carpeta / "correo_procesados.json"
    try:
        proc = json.loads(proc_p.read_text(encoding="utf-8"))
    except Exception:
        proc = {}
    try:
        m, host = conectar(cfg, clave)
    except Exception as ex:
        log("[%s] no pude entrar al buzón %s (%s)" % (carpeta.name, cfg["usuario"], ex))
        log("    si es Gmail/Google Workspace: contraseña de aplicación (Cuenta Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones)")
        return
    log("[%s] buzón %s en %s" % (carpeta.name, cfg["usuario"], host))
    ids = buscar_ids(m, cfg)
    log("    %d correo(s) de %s" % (len(ids), ", ".join(cfg.get("de") if isinstance(cfg.get("de"), list) else [cfg.get("de") or "cualquiera"])))
    ya_feed, xml = titulos_del_feed(cfgshow)
    ya_carpeta = set(_norm(p.stem).strip() for p in destino.iterdir() if p.is_file())
    nuevos = []           # (cat, idx, titulo, ext, bytes | None, fid | None, msgid)
    for i in ids:
        tip, datos = m.fetch(i, "(RFC822)")
        if tip != "OK" or not datos or not datos[0]:
            continue
        msg = email.message_from_bytes(datos[0][1])
        msgid = (msg.get("Message-ID") or "").strip() or ("uid-" + i.decode())
        if msgid in proc and not TODOS:
            continue
        asunto = limpiar_titulo(decodificar(msg.get("Subject")))
        adjuntos, cuerpo = [], ""
        for parte in msg.walk():
            if parte.get_content_maintype() == "multipart":
                continue
            nombre = decodificar(parte.get_filename() or "")
            ctype = parte.get_content_type()
            if nombre and Path(nombre).suffix.lower() in AUDIO or ctype.startswith("audio/"):
                ext = Path(nombre).suffix.lower() if nombre else "." + (ctype.split("/")[-1].replace("mpeg", "mp3").replace("x-m4a", "m4a"))
                adjuntos.append((limpiar_titulo(Path(nombre).stem) if nombre else "", ext if ext in AUDIO else ".mp3", parte.get_payload(decode=True)))
            elif ctype in ("text/plain", "text/html") and not parte.get_filename():
                try:
                    cuerpo += parte.get_payload(decode=True).decode(parte.get_content_charset() or "utf-8", "replace")
                except Exception:
                    pass
        links = [next(g for g in mm if g) for mm in DRIVE_RX.findall(cuerpo)]
        if not adjuntos and not links:
            log("    sin audio ni link de Drive: '%s' (se marca visto)" % asunto[:60])
            proc[msgid] = {"asunto": asunto, "cuando": time.strftime("%Y-%m-%d %H:%M"), "nada": True}
            continue
        varios = len(adjuntos) + len(links) > 1
        n = 0
        for nombre, ext, contenido in adjuntos:
            n += 1
            titulo = nombre if nombre and not es_generico(nombre) else (asunto + (" %d" % n if varios else ""))
            titulo = limpiar_titulo(titulo) or ("Shiur " + time.strftime("%Y-%m-%d"))
            nuevos.append([*clasificar(titulo), titulo, ext, contenido, None, msgid])
        for fid in dict.fromkeys(links):
            n += 1
            nuevos.append([4, 0, asunto + (" %d" % n if varios else ""), ".mp3", None, fid, msgid])
    m.logout()

    # links de Drive: hay que bajarlos para saber el nombre real
    for it in nuevos:
        if it[5]:
            try:
                log("    bajando de Drive: %s" % it[2][:50])
                nombre, datos = bajar_drive(it[5], destino)
                if nombre:
                    stem, ext = Path(nombre).stem, Path(nombre).suffix.lower()
                    if ext in AUDIO:
                        it[3] = ext
                    if not es_generico(stem):
                        it[2] = limpiar_titulo(stem)
                it[4] = datos
                it[0], it[1] = clasificar(it[2])
            except Exception as ex:
                log("    Drive falló (%s); lo reintento en el próximo ANUNCIAR" % str(ex)[:100])
                it[4] = None
    nuevos = [it for it in nuevos if it[4]]
    # repetidos: ya en el feed o ya en la carpeta
    listos = []
    for it in nuevos:
        k = _norm(it[2]).strip()
        if k in ya_feed:
            log("    ya está en Spotify, no lo repito: %s" % it[2][:60])
        elif k in ya_carpeta:
            log("    ya está esperando en la carpeta: %s" % it[2][:60])
        else:
            listos.append(it)
            ya_carpeta.add(k)
    if not listos:
        log("[%s] nada nuevo que bajar." % carpeta.name)
    else:
        # orden: parashá → Tehilim → Rut → Ester → resto; fechas seguidas después de lo último del feed
        listos.sort(key=lambda it: (it[0], it[1], it[2]))
        base = max(fecha_max_feed(xml) + 60, time.time() - 4 * 86400)
        for k, it in enumerate(listos):
            cat, idx, titulo, ext, datos, _f, _m = it
            ruta = destino / (titulo + ext)
            cuando = base + k * 60
            log("    %s [%s] %s%s" % ("guardaría" if VER else "guardado", ["parashá", "Tehilim", "Rut", "Ester", "otro"][cat],
                                    titulo[:60], " (%s)" % datetime.fromtimestamp(cuando).strftime("%d/%m %H:%M")))
            if VER:
                continue
            ruta.write_bytes(datos)
            os.utime(ruta, (cuando, cuando))
        log("[%s] %d audio(s) en %s; ANUNCIAR los publica en ese orden." % (carpeta.name, len(listos), destino))
    if not VER:
        for it in nuevos:
            proc.setdefault(it[6], {"cuando": time.strftime("%Y-%m-%d %H:%M"), "titulos": []})
            proc[it[6]].setdefault("titulos", []).append(it[2])
        proc_p.write_text(json.dumps(proc, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    shows = []
    for carpeta in sorted(BASE.iterdir()):
        cfgp = carpeta / "config.json"
        if not (carpeta.is_dir() and cfgp.exists()):
            continue
        if SHOWS_PEDIDOS and carpeta.name.lower() not in SHOWS_PEDIDOS:
            continue
        try:
            c = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not c.get("correo"):
            continue
        shows.append((carpeta, c))
    if not shows:
        if SHOWS_PEDIDOS:
            log("el show %s no tiene 'correo' en su config.json" % ", ".join(SHOWS_PEDIDOS))
        return 0
    for carpeta, c in shows:
        try:
            procesar_show(carpeta, c)
        except Exception as ex:
            log("[%s] ERROR: %s" % (carpeta.name, str(ex)[:200]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
