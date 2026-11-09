#!/usr/bin/env python3
"""Mensaje para el grupo con el link de Spotify de CADA shiur de un show.

    python mensaje_links.py davidsohn

Lee nuestro feed (del más viejo al más nuevo), busca cada episodio en Spotify (API oficial
con C:\\robotwhats\\spotify_keys.txt) y arma el mensaje: título + link de cada uno, el link
del show y el del grupo de WhatsApp. Lo deja en <show>\\mensaje_links.txt y en el
portapapeles. Si a Spotify le falta alguno, lo dice y NO lo pone (no se manda sin link).
No cambia nada.
"""
import base64
import html
import json
import re
import subprocess
import sys
import unicodedata
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
RABS = {"davidsohn": "Rab Tzvi Jaim Davidsohn"}

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def leer_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def bajar(url, cab=None, datos=None):
    req = urllib.request.Request(url, data=datos, headers=dict(UA, **(cab or {})))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]+", " ", t).strip()


def main():
    show = (sys.argv[1] if len(sys.argv) > 1 else "davidsohn").lower()
    an = (leer_json(ROBOT / "config_whatsapp.json").get("anunciar") or {}).get(show) or {}
    c = leer_json(BASE / show / "config.json")
    sp_show = an.get("spotify", "") or c.get("spotify", "")
    sid = (re.search(r"show/([A-Za-z0-9]+)", sp_show) or [None, None])[1]
    if not sid and show == "davidsohn":
        sid = "2rhmdVO0e4Mw5WlXpmpYOA"
    grupo = an.get("whatsapp_link") or ""
    if not grupo:
        inv = an.get("invite")
        inv = inv[0] if isinstance(inv, list) and inv else inv
        if inv:
            grupo = inv if str(inv).startswith("http") else f"https://chat.whatsapp.com/{inv}"
    feed_url = an.get("feed") if str(an.get("feed", "")).startswith("http") else \
        f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}/feed.xml"

    xml = bajar(feed_url)
    eps = []
    for it in re.findall(r"<item>([\s\S]*?)</item>", xml):
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        d = re.search(r"<pubDate>([\s\S]*?)</pubDate>", it)
        if t:
            try:
                f = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
            except Exception:
                f = 0
            eps.append((f, html.unescape(t.group(1).strip())))
    eps.sort()
    print(f"{show}: {len(eps)} shiurim en nuestro feed")

    l = [x.strip() for x in (ROBOT / "spotify_keys.txt").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    auth = base64.b64encode(f"{l[0]}:{l[1]}".encode()).decode()
    tok = json.loads(bajar("https://accounts.spotify.com/api/token",
                           {"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"},
                           b"grant_type=client_credentials"))["access_token"]
    spot = {}
    url = f"https://api.spotify.com/v1/shows/{sid}/episodes?market=MX&limit=50"
    while url:
        j = json.loads(bajar(url, {"Authorization": "Bearer " + tok}))
        for ep in j.get("items") or []:
            if ep:
                spot[norm(ep.get("name"))] = ep["external_urls"]["spotify"].split("?")[0]
        url = j.get("next")
    print(f"Spotify: {len(spot)} episodios")

    lineas, faltan = [], []
    for _, t in eps:
        link = spot.get(norm(t))
        if not link:
            for k, v in spot.items():
                if norm(t) in k or k in norm(t):
                    link = v
                    break
        if link:
            lineas.append(f"🎧 *{t}*\n{link}")
        else:
            faltan.append(t)

    rab = RABS.get(show, c.get("title", show))
    msg = (f"Shalom! 🙌\nYa quedaron subidos todos los shiurim del *{rab}* que se mandaron al grupo.\n"
           f"Aquí está cada uno:\n\n" + "\n\n".join(lineas) +
           f"\n\n🎵 Todos en Spotify:\n{sp_show or 'https://open.spotify.com/show/' + sid}")
    if grupo:
        msg += f"\n\n📲 Grupo de WhatsApp:\n{grupo}"
    msg += "\n\nDe aquí en adelante, cada shiur nuevo que llegue se sube y se comparte solo."

    print("\n" + "=" * 60 + "\n" + msg + "\n" + "=" * 60)
    if faltan:
        print(f"\n✖ A Spotify todavía le faltan {len(faltan)} (no van en el mensaje; vuelve a correrlo en unas horas):")
        for t in faltan:
            print("   · " + t)
    else:
        print(f"\n✔ Los {len(lineas)} ya están en Spotify: el mensaje está completo.")
    salida = BASE / show / "mensaje_links.txt"
    try:
        salida.write_text(msg, encoding="utf-8")
        print(f"Guardado en {salida}")
    except Exception:
        pass
    try:
        subprocess.run("clip", input=b"\xff\xfe" + msg.encode("utf-16-le"), shell=True, check=True)
        print("Ya está copiado: pégalo en el grupo con Ctrl+V.")
    except Exception:
        pass


if __name__ == "__main__":
    main()
