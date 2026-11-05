#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Todo el Shas de Rav Naftali Vasserman (מחוברים לתורה) en UN solo podcast (nov/2026).

    python shas_unido.py                 busca en C:\\OTZAR los podcasts de una masejet cada uno,
                                         junta sus episodios en orden (masejet por masejet, daf por
                                         daf) y publica rabmeireliyahu.github.io/shas/feed.xml
    python shas_unido.py --ver           solo dice qué encontró y en qué orden, sin publicar
    python shas_unido.py --rss=archivo   usa los RSS de ese archivo (uno por línea) en vez de buscar
    Si no encuentra nada en C:\\OTZAR (los de Anchor), pide pegar el RSS o el link de Apple de cada masejet
    y los guarda en shas_rss.txt para la próxima vez.

No borra ni cambia los podcasts de cada masejet: el nuevo feed apunta a los MISMOS mp3 (archive.org).
Volver a correrlo agrega lo nuevo que haya salido en cada masejet.
"""
import base64
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(r"C:\OTZAR")
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
VER = "--ver" in sys.argv
USUARIO, REPO = "rabmeireliyahu", "shas"
PAGES = f"https://{USUARIO}.github.io/{REPO}"
TITULO = "ש״ס בבלי · הרב נפתלי וסרמן · מחוברים לתורה"
DESCRIPCION = ("כל הש״ס בבלי, מסכת אחר מסכת ודף אחר דף, בשיעורים של הרב נפתלי וסרמן (מחוברים לתורה). "
               "Otzar HaTorah - אוצר התורה.")
AUTOR = "הרב נפתלי וסרמן"

# orden del Shas (Bavli) con las grafías que se usan en los títulos
MASEJTOT = [
    ("ברכות", "Berajot|Brachot|Berachot|Berakhot|Brajot"),
    ("שבת", "Shabbat|Shabat|Shabbos"), ("עירובין", "Eruvin|Eiruvin"), ("פסחים", "Pesachim|Pesajim"),
    ("שקלים", "Shekalim"), ("יומא", "Yoma"), ("סוכה", "Sukkah|Sukka|Suca|Sukah"), ("ביצה", "Beitzah|Beitza|Beitsa|Betza"),
    ("ראש השנה", "Rosh Hashana|Rosh Hashanah|Rosh HaShana"), ("תענית", "Taanit|Ta'anit"),
    ("מגילה", "Megillah|Megila|Meguila|Megilla"), ("מועד קטן", "Moed Katan|Mo'ed Katan"),
    ("חגיגה", "Chagigah|Jaguiga|Chagiga|Hagiga"), ("יבמות", "Yevamot|Yevamos"), ("כתובות", "Ketubot|Ketuvot|Kesubos"),
    ("נדרים", "Nedarim"), ("נזיר", "Nazir"), ("סוטה", "Sotah|Sota"), ("גיטין", "Gittin|Guitin|Gitin"),
    ("קידושין", "Kiddushin|Kidushin"), ("בבא קמא", "Bava Kamma|Bava Kama|Baba Kama"),
    ("בבא מציעא", "Bava Metzia|Baba Metzia|Bava Metsia"), ("בבא בתרא", "Bava Batra|Baba Batra"),
    ("סנהדרין", "Sanhedrin"), ("מכות", "Makkot|Makot"), ("שבועות", "Shevuot|Shevuos"),
    ("עבודה זרה", "Avodah Zarah|Avoda Zara"), ("הוריות", "Horayot|Horiyot"), ("זבחים", "Zevachim|Zevajim"),
    ("מנחות", "Menachot|Menajot"), ("חולין", "Chullin|Julin|Chulin|Hulin"), ("בכורות", "Bechorot|Bejorot|Bekhorot"),
    ("ערכין", "Arachin|Arajin|Arakhin"), ("תמורה", "Temurah|Temura"), ("כריתות", "Keritot|Kritot|Kerisus"),
    ("מעילה", "Meilah|Meila|Me'ila"), ("קינים", "Kinnim|Kinim"), ("תמיד", "Tamid"), ("מידות", "Middot|Midot"),
    ("נדה", "Niddah|Nida|Nidah"),
]
GEM = dict(zip("אבגדהוזחטיכלמנסעפצקרשתךםןףץ", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                                                200, 300, 400, 20, 40, 50, 80, 90]))
NO_SON = r"משנה ברורה|ילקוט יוסף|התנ[\"״]?ך|תנ[\"״]ך המבואר"


def log(m):
    print(m, flush=True)


def leer(url, crudo=False):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        import subprocess   # Spotify le cierra la puerta a Python; con curl (viene en Windows) sí abre
        b = subprocess.run(["curl", "-sL", "--ssl-no-revoke", url], capture_output=True, timeout=120).stdout
        if not b:
            raise
    return b if crudo else b.decode("utf-8", "replace")


def masejet_de(texto):
    """Índice en el Shas de la masejet que nombra el texto (o None). Las más largas primero
    ("בבא קמא" antes que "קמא"; "ראש השנה" antes que "שנה")."""
    t = re.sub(r"[\u0591-\u05C7]", "", texto or "")
    orden = sorted(range(len(MASEJTOT)), key=lambda i: -len(MASEJTOT[i][0]))
    for i in orden:
        heb, lat = MASEJTOT[i]
        if re.search(rf"(?<![א-ת]){heb}(?![א-ת])", t) or re.search(rf"\b(?:{lat})\b", t, re.I):
            return i
    return None


def daf_de(titulo):
    """(daf, amud) del título: "דף ב" / "דף כ"ג ע"ב" / "Daf 23b" / "23". Sin número: (None, 0)."""
    t = re.sub(r"[\u0591-\u05C7]", "", titulo or "")
    m = re.search(r"דף\s+([א-ת][א-ת\"״׳']{0,4})(?:\s*(?:ע[\"״׳']?|עמוד)\s*([אב]))?", t)
    if m:
        n = sum(GEM.get(c, 0) for c in m.group(1))
        return (n or None), (2 if m.group(2) == "ב" else 1)
    m = re.search(r"\b(?:daf|dapim|page)\s*(\d{1,3})\s*([ab])?", t, re.I) or re.search(r"(?<!\d)(\d{1,3})\s*([ab])?(?!\d)", t)
    if m:
        return int(m.group(1)), (2 if (m.group(2) or "").lower() == "b" else 1)
    return None, 0


def items_de(feed):
    out = []
    for it in re.findall(r"<item>([\s\S]*?)</item>", feed):
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        e = re.search(r'<enclosure\s+[^>]*url="([^"]+)"[^>]*>', it)
        if not (t and e):
            continue
        ln = re.search(r'length="(\d+)"', e.group(0))
        ty = re.search(r'type="([^"]+)"', e.group(0))
        g = re.search(r"<guid[^>]*>([\s\S]*?)</guid>", it)
        d = re.search(r"<pubDate>([\s\S]*?)</pubDate>", it)
        du = re.search(r"<itunes:duration>([\s\S]*?)</itunes:duration>", it)
        try:
            fecha = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
        except Exception:
            fecha = 0
        out.append({"t": html.unescape(t.group(1).strip()), "u": html.unescape(e.group(1)),
                    "len": ln.group(1) if ln else "0", "type": ty.group(1) if ty else "audio/mpeg",
                    "g": html.unescape(g.group(1).strip()) if g else e.group(1), "f": fecha,
                    "dur": du.group(1).strip() if du else ""})
    return out


def candidatos():
    """Feeds de una masejet cada uno: --rss=archivo, o los shows de C:\\OTZAR de Rav Vasserman."""
    for a in sys.argv[1:]:
        if a.startswith("--rss="):
            return [x.strip() for x in Path(a.split("=", 1)[1]).read_text(encoding="utf-8").splitlines()
                    if x.strip().startswith("http")]
    feeds = []
    for d in sorted(BASE.iterdir()) if BASE.is_dir() else []:
        try:
            c = json.loads((d / "config.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        texto = " ".join(str(c.get(k, "")) for k in ("titulo", "autor", "descripcion"))
        if d.name == REPO or re.search(NO_SON, texto):
            continue
        if not re.search(r"וסרמן|מחוברים לתורה|Vasserman|Wasserman", texto, re.I):
            continue
        if masejet_de(c.get("titulo", "")) is None and masejet_de(d.name) is None:
            continue
        feeds.append(c.get("feed_url") or f"https://{c.get('github_user', USUARIO)}.github.io/{c.get('github_repo', d.name)}/feed.xml")
    return feeds


def rss_de(link):
    """RSS de Anchor/Spotify for Creators tal cual; un link de Apple Podcasts → su RSS (API de iTunes)."""
    link = link.strip().strip('"')
    m = re.search(r"podcasts\.apple\.com/.*?id(\d{6,})", link)
    if m:
        try:
            j = json.loads(leer(f"https://itunes.apple.com/lookup?id={m.group(1)}"))
            return (j.get("results") or [{}])[0].get("feedUrl")
        except Exception:
            return None
    if "open.spotify.com/show/" in link:
        # Spotify no da el RSS: se toma el nombre del podcast y se busca ese mismo nombre en Apple
        try:
            pag = leer(link.split("?")[0])
            nombre = html.unescape(re.search(r"<title>([^<|]+)", pag).group(1)).strip()
            j = json.loads(leer("https://itunes.apple.com/search?media=podcast&limit=50&term="
                                + urllib.parse.quote(nombre)))
            for r in j.get("results") or []:
                if (r.get("collectionName") or "").strip() == nombre and r.get("feedUrl"):
                    log(f"  ✓ {nombre}: RSS encontrado por Apple")
                    return r["feedUrl"]
            log(f"  ✗ {nombre}: no está en Apple, así que no veo su RSS. Pega su RSS de Spotify for Creators\n"
                "    (creators.spotify.com → el podcast → Configuración → Disponibilidad → RSS → Copiar).")
        except Exception as e:
            log(f"  ✗ no pude leer {link}: {e}")
        return None
    return link if link.startswith("http") else None


def pedir_links():
    """Pega los links (RSS de Anchor o link de Apple), uno por renglón; se guardan en shas_rss.txt."""
    guardado = Path("shas_rss.txt")
    if guardado.exists():
        prev = [x.strip() for x in guardado.read_text(encoding="utf-8").splitlines() if x.strip()]
        if prev:
            log(f"Uso los {len(prev)} links guardados en {guardado.resolve()} (bórralo para pegar otros).")
            return [r for r in (rss_de(x) for x in prev) if r]
    log("Pega el link de Spotify de cada masejet (o su RSS anchor.fm/s/…/podcast/rss, o su link de Apple),\n"
        "uno por renglón, en el orden que sea. Cuando termines, deja un renglón vacío y Enter.")
    links = []
    while True:
        try:
            x = input("> ").strip()
        except EOFError:
            break
        if not x:
            break
        links += [y for y in re.split(r"\s+", x) if y]
    if links:
        guardado.write_text("\n".join(links) + "\n", encoding="utf-8")
    return [r for r in (rss_de(x) for x in links) if r]


def armar(feeds):
    porm, imagen, sin_masejet = {}, "", []
    for url in feeds:
        try:
            x = leer(url)
        except Exception as e:
            log(f"  ✗ no pude leer {url}: {e}")
            continue
        cab = x.split("<item>")[0]
        ct = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", cab)
        nombre = html.unescape(ct.group(1).strip()) if ct else url
        i = masejet_de(nombre)
        if i is None:
            sin_masejet.append(f"{nombre} ({url})")
            continue
        im = re.search(r'<itunes:image href="([^"]+)"', cab)
        if im and not imagen:
            imagen = im.group(1)
        its = items_de(x)
        porm.setdefault(i, []).extend(its)
        log(f"  ✓ {MASEJTOT[i][0]:<10} {len(its):>4} shiurim · {nombre}")
    for s in sin_masejet:
        log(f"  ? sin masejet en el nombre, NO entra: {s}")
    total, lista = 0, []
    for i in sorted(porm):
        vistos, its = set(), []
        for it in porm[i]:
            if it["u"] in vistos:
                continue
            vistos.add(it["u"])
            its.append(it)
        # daf por daf; lo que no dice daf, por fecha
        def clave(it):
            n, amud = daf_de(it["t"])
            if n is None:   # la הקדמה va antes del daf ב; lo demás sin daf, al final
                n = 0 if re.search(r"הקדמה|פתיחה|מבוא|intro", it["t"], re.I) else 10 ** 4
            return n, amud, it["f"]
        its.sort(key=clave)
        for it in its:
            it["m"] = i
        lista += its
        total += len(its)
    return lista, imagen


def feed_xml(lista, imagen):
    # serial: el primero (ברכות דף ב) es el más viejo; así Spotify y Apple los muestran en orden
    inicio = datetime(2015, 1, 1, 12, 0, tzinfo=timezone.utc)
    partes = [f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(TITULO)}</title>
    <description>{escape(DESCRIPCION)}</description>
    <link>{PAGES}</link>
    <language>he</language>
    <itunes:author>{escape(AUTOR)}</itunes:author>
    <itunes:owner><itunes:name>Otzar HaTorah</itunes:name><itunes:email>rabmeireliyahu@gmail.com</itunes:email></itunes:owner>
    <itunes:image href="{escape(imagen or PAGES + '/portada.jpg')}"/>
    <itunes:category text="Religion &amp; Spirituality"><itunes:category text="Judaism"/></itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>serial</itunes:type>"""]
    items = []
    for n, it in enumerate(lista, 1):
        heb = MASEJTOT[it["m"]][0]
        t = it["t"] if masejet_de(it["t"]) is not None else f"מסכת {heb} · {it['t']}"
        fecha = format_datetime(inicio + timedelta(hours=n))
        items.append(f"""    <item>
      <title>{escape(t)}</title>
      <description>{escape(t)} · {escape(AUTOR)}</description>
      <enclosure url="{escape(it['u'])}" length="{it['len']}" type="{escape(it['type'])}"/>
      <guid isPermaLink="false">shas-{escape(it['g'])}</guid>
      <pubDate>{fecha}</pubDate>
      <itunes:season>{it['m'] + 1}</itunes:season>
      <itunes:episode>{n}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>{f'''
      <itunes:duration>{escape(it['dur'])}</itunes:duration>''' if it['dur'] else ''}
    </item>""")
    # el más nuevo arriba (como los demás feeds), la fecha manda el orden
    partes += reversed(items)
    partes.append("  </channel>\n</rss>\n")
    return "\n".join(partes)


def publicar(xml):
    tok = next((p for p in (BASE / "jabura" / "github_token.txt",) if p.exists()), None)
    if not tok:
        log("✗ falta C:\\OTZAR\\jabura\\github_token.txt")
        return False
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "otzar-shas", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{USUARIO}/{REPO}"

    def gh(metodo, url, cuerpo=None):
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                     headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                t = r.read().decode()
                return r.status, (json.loads(t) if t.strip() else {})
        except urllib.error.HTTPError as e:
            return e.code, {}
    st, _ = gh("GET", base)
    if st == 404:
        st, _ = gh("POST", "https://api.github.com/user/repos",
                   {"name": REPO, "description": TITULO, "private": False, "auto_init": True})
        log("✓ repo creado" if st in (200, 201) else f"✗ no pude crear el repo ({st})")
        time.sleep(5)
    st, j = gh("GET", f"{base}/contents/feed.xml")
    cuerpo = {"message": "shas unido", "content": base64.b64encode(xml.encode("utf-8")).decode()}
    if st == 200 and j.get("sha"):
        cuerpo["sha"] = j["sha"]
    st, _ = gh("PUT", f"{base}/contents/feed.xml", cuerpo)
    if st not in (200, 201):
        log(f"✗ no pude subir el feed ({st})")
        return False
    gh("POST", f"{base}/pages", {"source": {"branch": "main", "path": "/"}})
    log(f"✓ feed publicado: {PAGES}/feed.xml (Pages tarda unos minutos la primera vez)")
    return True


def main():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    feeds = candidatos()
    if not feeds:
        feeds = pedir_links()
    if not feeds:
        log("Sin links no hay nada que juntar.")
        return 1
    log(f"=== Shas unido: {len(feeds)} podcast(s) de masejet ===")
    lista, imagen = armar(feeds)
    if not lista:
        log("✗ no salió ningún shiur")
        return 1
    sin_daf = sum(1 for it in lista if daf_de(it["t"])[0] is None)
    log(f"Total: {len(lista)} shiurim en {len({it['m'] for it in lista})} masejtot "
        f"({sin_daf} sin número de daf: van al final de su masejet, por fecha).")
    log("  primero: " + lista[0]["t"][:70] + "\n  último:  " + lista[-1]["t"][:70])
    xml = feed_xml(lista, imagen)
    if VER:
        Path("shas_unido_prueba.xml").write_text(xml, encoding="utf-8")
        log("(prueba en seco: quedó shas_unido_prueba.xml, no se publicó nada)")
        return 0
    if publicar(xml):
        log("Para Spotify y Apple: agrega un podcast nuevo con ese RSS. Los de cada masejet siguen igual.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
