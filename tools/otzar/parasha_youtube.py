#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PARASHA SEMANAL desde YouTube · Otzar HaTorah (p. ej. el show de CHAZAQ)

Lo corre mantenimiento.py en cada ANUNCIAR (o a mano):
    python parasha_youtube.py             todos los shows con "parasha_semanal": true en su config.json
    python parasha_youtube.py chazaq      solo ese show
    --ver                                 prueba en seco: dice qué haría, no baja ni publica
    --forzar                              ignora el candado semanal
    --fecha=YYYY-MM-DD                    calcular la parasha como si hoy fuera esa fecha

Qué hace por show, una vez por semana:
 1. Calcula la parasha del Shabat que viene (diáspora) con @hebcal/core del robot
    (node, en C:\\robotwhats); si no hay node, pyluach; si no, la API de hebcal.
 2. Busca en los canales de YouTube del show (canales_youtube / canal_youtube del
    config.json) videos cuyo título nombre ESA parasha, con cualquier grafía
    (Ki Tavo / Ki Savo / כי תבוא): primero entre los últimos subidos (el shiur de
    esta semana) y, si no alcanza, buscando en el canal (otros años).
 3. Baja los mejores (parasha_max, 2 por defecto; mínimo parasha_min_minutos, 2: los de "Chazaq on the Parsha" duran 3)
    a episodios/, los sube a archive.org y publica el feed con podcast_bot.py.
    Spotify lee el feed y el robot los anuncia en el grupo del show en ese mismo
    ANUNCIAR (título + link exacto de Spotify + link del grupo, como siempre).
 4. Candado semanal parasha_ultimo.json en la carpeta del show. Si no encontró
    nada, vuelve a intentar en el siguiente ANUNCIAR (con 3 horas de calma).
Semana de jag (Sukot, Pesaj…): no hay parasha, no hace nada.
"""
import json, os, re, subprocess, sys, time, urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
VER = "--ver" in sys.argv
FORZAR = "--forzar" in sys.argv
FECHA = None
SHOWS_PEDIDOS = []
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
    elif a.startswith("--robot="):
        ROBOT = Path(a.split("=", 1)[1])
    elif a.startswith("--fecha="):
        FECHA = a.split("=", 1)[1].strip()
    elif not a.startswith("--"):
        SHOWS_PEDIDOS.append(a.strip().lower())

YT_CLIENT = ["--extractor-args", "youtube:player_client=web_embedded"]
CALMA_SEG = 3 * 3600          # si no encontró nada, no vuelve a buscar antes de esto

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(m):
    print("[%s] PARASHA %s" % (time.strftime("%d/%m %H:%M"), m), flush=True)


# ─────────── nombres de las parashiot: clave hebcal → grafías (inglés) + hebreo ───────────
PARASHIOT = {
    "Bereshit":         (["Bereshit", "Bereishit", "Bereishis", "Beraishis", "Bereshis", "Breishit"], "בראשית"),
    "Noach":            (["Noach", "Noaj"], "נח"),
    "Lech-Lecha":       (["Lech Lecha", "Lech-Lecha", "Lech L'cha"], "לך לך"),
    "Vayera":           (["Vayera", "Vayeira", "Vayeirah"], "וירא"),
    "Chayei Sara":      (["Chayei Sara", "Chayei Sarah", "Chaye Sara", "Chayei Soroh"], "חיי שרה"),
    "Toldot":           (["Toldot", "Toldos", "Toledot"], "תולדות"),
    "Vayetzei":         (["Vayetzei", "Vayeitzei", "Vayetze", "Vayeitze"], "ויצא"),
    "Vayishlach":       (["Vayishlach", "Vayishlaj"], "וישלח"),
    "Vayeshev":         (["Vayeshev", "Vayeishev"], "וישב"),
    "Miketz":           (["Miketz", "Mikeitz", "Mikketz"], "מקץ"),
    "Vayigash":         (["Vayigash"], "ויגש"),
    "Vayechi":          (["Vayechi", "Vayeji"], "ויחי"),
    "Shemot":           (["Shemot", "Shemos", "Shmot", "Shmos"], "שמות"),
    "Vaera":            (["Vaera", "Va'era", "Va'eira", "Vaeira"], "וארא"),
    "Bo":               (["Bo"], "בא"),
    "Beshalach":        (["Beshalach", "Beshalaj", "B'shalach"], "בשלח"),
    "Yitro":            (["Yitro", "Yisro", "Jethro"], "יתרו"),
    "Mishpatim":        (["Mishpatim"], "משפטים"),
    "Terumah":          (["Terumah", "Teruma", "Trumah"], "תרומה"),
    "Tetzaveh":         (["Tetzaveh", "Tetzave", "Tetzavé"], "תצוה"),
    "Ki Tisa":          (["Ki Tisa", "Ki Sisa", "Ki Tissa"], "כי תשא"),
    "Vayakhel":         (["Vayakhel", "Vayakheil"], "ויקהל"),
    "Pekudei":          (["Pekudei", "Pekude", "Pikudei"], "פקודי"),
    "Vayikra":          (["Vayikra"], "ויקרא"),
    "Tzav":             (["Tzav"], "צו"),
    "Shmini":           (["Shmini", "Shemini"], "שמיני"),
    "Tazria":           (["Tazria"], "תזריע"),
    "Metzora":          (["Metzora", "Metzorah"], "מצורע"),
    "Achrei Mot":       (["Achrei Mot", "Acharei Mot", "Acharei Mos", "Achrei Mos", "Achare Mot"], "אחרי מות"),
    "Kedoshim":         (["Kedoshim"], "קדושים"),
    "Emor":             (["Emor"], "אמור"),
    "Behar":            (["Behar", "B'har"], "בהר"),
    "Bechukotai":       (["Bechukotai", "Bechukosai", "Bechukotay", "Behukotai"], "בחוקותי"),
    "Bamidbar":         (["Bamidbar", "Bamidbor"], "במדבר"),
    "Nasso":            (["Nasso", "Naso"], "נשא"),
    "Beha'alotcha":     (["Beha'alotcha", "Behaalotcha", "Beha'aloscha", "Behaaloscha", "Behaalotecha", "Beha'alosecha"], "בהעלותך"),
    "Sh'lach":          (["Sh'lach", "Shlach", "Shelach", "Shelach Lecha", "Shlach Lecha"], "שלח"),
    "Korach":           (["Korach", "Koraj", "Korah"], "קרח"),
    "Chukat":           (["Chukat", "Chukas", "Chukkat", "Jukat"], "חוקת"),
    "Balak":            (["Balak"], "בלק"),
    "Pinchas":          (["Pinchas", "Pinjas", "Pinehas", "Phinehas"], "פנחס"),
    "Matot":            (["Matot", "Mattot", "Mattos", "Matos"], "מטות"),
    "Masei":            (["Masei", "Massei", "Mas'ei"], "מסעי"),
    "Devarim":          (["Devarim", "Dvarim"], "דברים"),
    "Vaetchanan":       (["Vaetchanan", "Va'etchanan", "Va'eschanan", "Vaeschanan"], "ואתחנן"),
    "Eikev":            (["Eikev", "Ekev", "Eikav"], "עקב"),
    "Re'eh":            (["Re'eh", "Reeh", "Re'e"], "ראה"),
    "Shoftim":          (["Shoftim", "Shofetim"], "שופטים"),
    "Ki Teitzei":       (["Ki Teitzei", "Ki Seitzei", "Ki Tetze", "Ki Tetzei", "Ki Tetzé", "Ki Teze", "Ki Setzei"], "כי תצא"),
    "Ki Tavo":          (["Ki Tavo", "Ki Savo", "Ki Tabo"], "כי תבוא"),
    "Nitzavim":         (["Nitzavim", "Netzavim"], "נצבים"),
    "Vayeilech":        (["Vayeilech", "Vayelech", "Vayelej"], "וילך"),
    "Ha'azinu":         (["Ha'azinu", "Haazinu", "Ha'Azinu"], "האזינו"),
    "Vezot Haberakhah": (["Vezot Haberakhah", "V'zot Habracha", "Vezot Habracha", "Vezos Habrocho", "V'zos Habracha", "Zot Habracha"], "וזאת הברכה"),
}
PALABRAS_PARASHA = ["parsha", "parshas", "parshat", "parasha", "parashat", "parashas", "perasha", "פרשת", "פרשה"]


def _norm(t):
    """minúsculas, sin nikud, sin apóstrofos; lo que no es letra/número es espacio."""
    t = re.sub(r"[\u0591-\u05C7]", "", str(t or "")).lower()
    t = t.replace("'", "").replace("’", "").replace("׳", "")
    return " " + re.sub(r"[^\w\u05D0-\u05EA]+", " ", t).strip() + " "


def canonica(nombre):
    """'Ki Savo' / 'Bereishis' / 'כי תבוא' → clave hebcal ('Ki Tavo', 'Bereshit')."""
    n = _norm(nombre).strip()
    for clave, (grafias, heb) in PARASHIOT.items():
        if n == _norm(clave).strip() or n == _norm(heb).strip():
            return clave
        if any(n == _norm(g).strip() for g in grafias):
            return clave
    return None


def claves_de(nombres):
    """['Vayakhel', 'Pekudei'] o ['Vayakhel-Pekudei'] o ['Ki Savo'] → claves hebcal."""
    out = []
    for n in nombres:
        c = canonica(n)
        if not c and "-" in str(n):
            partes = [canonica(x) for x in str(n).split("-")]
            if all(partes):
                out += partes
                continue
        if c:
            out.append(c)
    return out


def nombra_parasha(titulo, claves):
    """True si el título nombra alguna de las parashiot (palabra completa)."""
    t = _norm(titulo)
    for clave in claves:
        grafias, heb = PARASHIOT[clave]
        for g in list(grafias) + [heb]:
            g = _norm(g).strip()
            if g and (" " + g + " ") in t:
                return True
    return False


def dice_parasha(titulo):
    t = _norm(titulo)
    return any((" " + _norm(p).strip() + " ") in t for p in PALABRAS_PARASHA)


# ─────────── la parasha de la semana ───────────
NODE_JS = r"""
import('@hebcal/core').then(({ HDate, Sedra }) => {
  const arg = process.argv[1];
  const d = arg ? new Date(arg + 'T12:00:00') : new Date();
  const hoy = new HDate(d);
  const shabat = hoy.onOrAfter(6);
  const sedra = new Sedra(shabat.getFullYear(), false);
  const r = sedra.lookup(shabat);
  const g = shabat.greg();
  const iso = g.getFullYear() + '-' + String(g.getMonth() + 1).padStart(2, '0') + '-' + String(g.getDate()).padStart(2, '0');
  console.log(JSON.stringify({ parsha: r.parsha || [], chag: !!r.chag, shabat: iso, anio: shabat.getFullYear() }));
}).catch(e => { console.error(String(e)); process.exit(1); });
"""


def _shabat_que_viene(hoy):
    return hoy + timedelta(days=(5 - hoy.weekday()) % 7)      # weekday: lunes=0 … sábado=5


def parasha_por_node(hoy):
    if not (ROBOT / "node_modules" / "@hebcal" / "core").exists():
        return None
    r = subprocess.run(["node", "-e", NODE_JS, hoy.isoformat()], cwd=str(ROBOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0 or not r.stdout.strip():
        raise Exception((r.stderr or "node sin salida")[:200])
    j = json.loads(r.stdout.strip().splitlines()[-1])
    return {"nombres": j.get("parsha") or [], "chag": bool(j.get("chag")), "shabat": j.get("shabat"), "anio": j.get("anio")}


def parasha_por_pyluach(hoy):
    from pyluach import dates, parshios            # noqa: F401  (pip install pyluach)
    sh = _shabat_que_viene(hoy)
    g = dates.GregorianDate(sh.year, sh.month, sh.day)
    s = parshios.getparsha_string(g, israel=False)
    anio = g.to_heb().year
    if not s:
        return {"nombres": [], "chag": True, "shabat": sh.isoformat(), "anio": anio}
    return {"nombres": [x.strip() for x in s.split(",")], "chag": False, "shabat": sh.isoformat(), "anio": anio}


def parasha_por_hebcal_api(hoy):
    sh = _shabat_que_viene(hoy)
    url = ("https://www.hebcal.com/hebcal?v=1&cfg=json&s=on&maj=on&min=off&mod=off&nx=off&mf=off&ss=off&i=off"
           "&start=%s&end=%s" % (sh.isoformat(), sh.isoformat()))
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "otzar-parasha"}), timeout=40) as r:
        j = json.loads(r.read().decode("utf-8"))
    anio = None
    for it in j.get("items") or []:
        if it.get("category") == "parashat":
            nombre = re.sub(r"^Parashat\s+", "", it.get("title") or "")
            m = re.search(r"(\d{4})", it.get("hdate") or "")
            anio = int(m.group(1)) if m else None
            return {"nombres": [x.strip() for x in nombre.split("-")], "chag": False, "shabat": sh.isoformat(), "anio": anio}
    return {"nombres": [], "chag": True, "shabat": sh.isoformat(), "anio": anio}


def parasha_de_la_semana():
    hoy = date.fromisoformat(FECHA) if FECHA else date.today()
    ultimo = None
    for nombre, fn in (("@hebcal/core del robot", parasha_por_node), ("pyluach", parasha_por_pyluach),
                       ("API de hebcal", parasha_por_hebcal_api)):
        try:
            p = fn(hoy)
            if p is None:
                continue
            p["fuente"] = nombre
            return p
        except Exception as ex:
            ultimo = "%s: %s" % (nombre, str(ex)[:120])
    log("no pude calcular la parasha (%s)" % ultimo)
    return None


# ─────────── yt-dlp ───────────
def ytj(args, timeout=120):
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "-J", "--no-warnings"] + YT_CLIENT + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise Exception((r.stderr or "sin salida")[:150])
    return json.loads(r.stdout)


def _base_canal(url):
    return re.sub(r"/(videos|shorts|streams|live)/?$", "", (url or "").strip().rstrip("/"))


def ultimos_del_canal(url, n):
    """(id, título) de los últimos n videos, sin bajar nada."""
    base = _base_canal(url)
    objetivo = base if "playlist?list=" in base else base + "/videos"
    data = ytj(["--flat-playlist", "--playlist-end", str(n), objetivo])
    return [(e.get("id"), e.get("title") or "") for e in (data.get("entries") or []) if e.get("id")]


def buscar_en_canal(url, consultas, tope):
    base = _base_canal(url)
    if "playlist?list=" in base:
        return []
    vistos = {}
    for q in consultas:
        try:
            data = ytj(["--flat-playlist", "--playlist-end", "12", "%s/search?query=%s" % (base, quote(q))])
        except Exception as ex:
            log("    búsqueda '%s' falló: %s" % (q, str(ex)[:100]))
            continue
        for e in (data.get("entries") or []):
            if e.get("id") and e["id"] not in vistos:
                vistos[e["id"]] = e.get("title") or ""
        if len(vistos) >= tope:
            break
    return list(vistos.items())


def ids_ya_bajados(carpeta):
    ya = set()
    try:
        for l in (carpeta / "ya_descargados.txt").read_text(encoding="utf-8", errors="replace").splitlines():
            partes = l.split()
            if len(partes) >= 2:
                ya.add(partes[1].strip())
    except Exception:
        pass
    return ya


def bajar(carpeta, vid):
    subprocess.run([sys.executable, "-m", "yt_dlp",
        "-x", "--audio-format", "mp3", "--audio-quality", "128K",
        "--embed-metadata", "--windows-filenames", "--no-mtime",
        "--download-archive", "ya_descargados.txt", "--ignore-errors"] + YT_CLIENT + [
        "-o", "episodios/%(title)s.%(ext)s",
        "https://www.youtube.com/watch?v=%s" % vid], cwd=str(carpeta))


def correr_bot(carpeta, comando):
    return subprocess.run([sys.executable, "podcast_bot.py", comando], cwd=str(carpeta)).returncode


# ─────────── por show ───────────
def canales_de(cfg):
    canales = cfg.get("parasha_canales") or cfg.get("canales_youtube") or \
        ([{"url": cfg["canal_youtube"]}] if cfg.get("canal_youtube") else [])
    out = []
    for c in canales:
        u = (c.get("url") if isinstance(c, dict) else c) or ""
        if u.strip():
            out.append(u.strip())
    return out


def procesar_show(carpeta, cfg, p):
    claves = claves_de(p["nombres"])
    if not claves:
        log("[%s] no reconozco la parasha %s; avísale a Claude." % (carpeta.name, p["nombres"]))
        return
    etiqueta = "-".join(claves) + " " + str(p.get("anio") or "")
    lock_p = carpeta / "parasha_ultimo.json"
    try:
        lock = json.loads(lock_p.read_text(encoding="utf-8"))
    except Exception:
        lock = {}
    if not FORZAR and lock.get("parasha") == etiqueta:
        log("[%s] %s ya se publicó esta semana (%s). Nada que hacer." % (carpeta.name, etiqueta, ", ".join(lock.get("shiurim") or [])[:80]))
        return
    if not FORZAR and lock.get("parasha_intento") == etiqueta and time.time() - float(lock.get("intento") or 0) < CALMA_SEG:
        log("[%s] %s: ya busqué hace poco y no había nada; vuelvo a buscar en el próximo ANUNCIAR." % (carpeta.name, etiqueta))
        return

    maximo = int(cfg.get("parasha_max") or 2)
    min_seg = int(cfg.get("parasha_min_minutos") or 2) * 60
    revisar = int(cfg.get("parasha_revisar") or 40)
    canales = canales_de(cfg)
    if not canales:
        log("[%s] no tiene canales_youtube en config.json; nada que buscar." % carpeta.name)
        return
    ya = ids_ya_bajados(carpeta)
    log("[%s] buscando %s en %d canal(es)..." % (carpeta.name, etiqueta, len(canales)))

    vistos = set()
    elegidos, ya_publicados = [], []

    def evaluar(candidatos, tope):
        """mira duración y vistas de cada candidato; los ya publicados cuentan pero no se bajan."""
        for c in candidatos:
            if len(elegidos) + len(ya_publicados) >= tope:
                return
            prio, _v, vid, tit = c
            if vid in ya:
                if prio >= 2:                 # el de esta semana ya lo publicó ACTUALIZAR: cuenta
                    ya_publicados.append(tit)
                else:
                    log("    ya publicado en otra ocasión, no lo repito: %s" % tit[:60])
                continue
            try:
                m = ytj(["https://www.youtube.com/watch?v=%s" % vid], timeout=90)
            except Exception as ex:
                log("    no pude leer '%s': %s" % (tit[:50], str(ex)[:80]))
                continue
            dur = m.get("duration") or 0
            if dur < min_seg:
                log("    corto (%d min), lo salto: %s" % (dur // 60, tit[:60]))
                continue
            c[1] = m.get("view_count") or 0
            c[3] = m.get("title") or tit
            elegidos.append(c)

    def faltan():
        return len(elegidos) + len(ya_publicados) < maximo

    # 1) lo último que subió cada canal: el shiur de ESTA semana
    for url in canales:
        recientes = []
        try:
            for vid, tit in ultimos_del_canal(url, revisar):
                if vid in vistos or not nombra_parasha(tit, claves):
                    continue
                vistos.add(vid)
                recientes.append([2 + (1 if dice_parasha(tit) else 0), 0, vid, tit])
        except Exception as ex:
            log("    no pude listar %s: %s" % (url[:60], str(ex)[:100]))
            if "Failed to resolve" in str(ex) or "getaddrinfo" in str(ex):
                log("    (sin internet o DNS caído; lo intento en el próximo ANUNCIAR)")
                return
        recientes.sort(key=lambda c: c[0], reverse=True)
        evaluar(recientes, maximo)
    # 2) si no alcanza, buscar en el canal (shiurim de esta parasha de otros años): los más vistos
    if faltan():
        consultas = []
        for clave in claves:
            grafias, heb = PARASHIOT[clave]
            consultas += ["Parshas " + grafias[0], "Parashat " + grafias[0], heb] + \
                         ["Parshas " + g for g in grafias[1:3]]
        for url in canales:
            buscados = []
            for vid, tit in buscar_en_canal(url, consultas, 24):
                if vid in vistos or not nombra_parasha(tit, claves):
                    continue
                vistos.add(vid)
                buscados.append([0 + (1 if dice_parasha(tit) else 0), 0, vid, tit])
            # para elegir los más vistos hay que leer las vistas de todos antes de cortar
            evaluar(buscados, 10 ** 6)
    # los recientes primero; entre iguales, los más vistos
    elegidos.sort(key=lambda c: (c[0], c[1]), reverse=True)
    elegidos = elegidos[:max(0, maximo - len(ya_publicados))]
    if not vistos and not ya_publicados:
        log("[%s] no hay ningún video de %s en el canal (todavía). Vuelvo a buscar en el próximo ANUNCIAR." % (carpeta.name, etiqueta))
        lock.update({"parasha_intento": etiqueta, "intento": time.time()})
        if not VER:
            lock_p.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for tit in ya_publicados:
        log("    ya estaba publicado: %s" % tit[:70])
    if not elegidos and not ya_publicados:
        log("[%s] había candidatos pero ninguno sirvió; vuelvo a intentar en el próximo ANUNCIAR." % carpeta.name)
        lock.update({"parasha_intento": etiqueta, "intento": time.time()})
        if not VER:
            lock_p.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    for prio, vistas, vid, tit in elegidos:
        log("    %s (%s vistas%s): %s" % ("bajaría" if VER else "bajando", format(vistas, ","),
                                          ", reciente" if prio >= 2 else "", tit[:70]))
        if not VER:
            bajar(carpeta, vid)

    epi = carpeta / "episodios"
    nuevos = list(epi.glob("*.mp3")) if epi.exists() else []
    if VER:
        log("[%s] (prueba en seco) no bajé ni publiqué nada." % carpeta.name)
        return
    if nuevos:
        log("[%s] subiendo a Archive y publicando el feed (%d mp3)..." % (carpeta.name, len(nuevos)))
        correr_bot(carpeta, "apartar")
        if correr_bot(carpeta, "subir") != 0 or correr_bot(carpeta, "feed") != 0:
            log("[%s] *** algo falló al publicar; lo reintento en el próximo ANUNCIAR ***" % carpeta.name)
            return
    elif elegidos:
        log("[%s] yt-dlp no dejó ningún mp3; lo reintento en el próximo ANUNCIAR." % carpeta.name)
        lock.update({"parasha_intento": etiqueta, "intento": time.time()})
        lock_p.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    lock = {"parasha": etiqueta, "cuando": datetime.now().isoformat(timespec="minutes"),
            "shiurim": [c[3] for c in elegidos] + ya_publicados}
    lock_p.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    log("[%s] listo: %d shiur(im) de %s. El robot los anuncia en su grupo." % (carpeta.name, len(lock["shiurim"]), etiqueta))


def main():
    shows = []
    for carpeta in sorted(BASE.iterdir()):
        cfgp = carpeta / "config.json"
        if not (carpeta.is_dir() and cfgp.exists() and (carpeta / "podcast_bot.py").exists()):
            continue
        if SHOWS_PEDIDOS and carpeta.name.lower() not in SHOWS_PEDIDOS:
            continue
        try:
            cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not SHOWS_PEDIDOS and not cfg.get("parasha_semanal"):
            continue
        if cfg.get("pausado") or (carpeta / "PAUSADO.txt").exists():
            continue
        shows.append((carpeta, cfg))
    if not shows:
        if SHOWS_PEDIDOS:
            log("no encontré el show %s en %s" % (", ".join(SHOWS_PEDIDOS), BASE))
        return 0
    p = parasha_de_la_semana()
    if not p:
        return 1
    if p.get("chag") or not p.get("nombres"):
        log("este Shabat (%s) es jag (%s): no hay parasha, nada que hacer." % (p.get("shabat"), ", ".join(p.get("nombres") or [])))
        return 0
    log("la parasha de este Shabat (%s) es %s · vía %s" % (p.get("shabat"), " - ".join(p["nombres"]), p.get("fuente")))
    for carpeta, cfg in shows:
        try:
            procesar_show(carpeta, cfg, p)
        except Exception as ex:
            log("[%s] ERROR: %s" % (carpeta.name, str(ex)[:200]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
