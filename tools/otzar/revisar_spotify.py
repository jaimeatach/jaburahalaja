#!/usr/bin/env python3
"""¿Por qué no se ve en Spotify? Compara lo que tiene Spotify con nuestro feed.

    python revisar_spotify.py tawil

1. El RSS viejo de Spotify for Creators (rss_original del config del show): si el redirect
   está hecho, tiene que llevar a nuestro feed.
2. Los últimos episodios que tiene Spotify (API oficial con las llaves del robot,
   C:\\robotwhats\\spotify_keys.txt).
3. Los últimos de nuestro feed, y cuáles le faltan a Spotify.
No cambia nada.
"""
import base64
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

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


def bajar(url, cab=None, datos=None, tiempo=60):
    req = urllib.request.Request(url, data=datos, headers=dict(UA, **(cab or {})))
    with urllib.request.urlopen(req, timeout=tiempo) as r:
        return r.geturl(), r.read().decode("utf-8", "replace")


def titulos(xml):
    out = []
    for it in re.findall(r"<item>([\s\S]*?)</item>", xml):
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        d = re.search(r"<pubDate>([\s\S]*?)</pubDate>", it)
        if t:
            out.append((html.unescape(t.group(1).strip()), d.group(1).strip() if d else ""))
    return out


def numero(t):
    m = re.match(r"\s*#\s*(\d+)", t or "")
    return int(m.group(1)) if m else None


def norm(t):
    return re.sub(r"[^\w]+", " ", (t or "").lower()).strip()


def main():
    show = (sys.argv[1] if len(sys.argv) > 1 else "tawil").lower()
    cfgw = leer_json(ROBOT / "config_whatsapp.json")
    an = (cfgw.get("anunciar") or {}).get(show) or {}
    c = leer_json(BASE / show / "config.json")
    sid = (re.search(r"show/([A-Za-z0-9]+)", an.get("spotify", "") or c.get("spotify", "")) or [None, None])[1]
    feed_url = an.get("feed") if str(an.get("feed", "")).startswith("http") else \
        f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}/feed.xml"
    print(f"=== {show} ===\nSpotify: {sid or '?'}\nNuestro feed: {feed_url}\n")

    print("1) ¿Redirect hecho?")
    rss = c.get("rss_original")
    if not rss:
        print("   (no hay rss_original en el config del show; no puedo revisar el RSS viejo)")
    else:
        try:
            final, xml = bajar(rss)
            if "github.io" in final or final.rstrip("/") == feed_url.rstrip("/"):
                print(f"   ✔ el RSS viejo de Spotify for Creators ya manda a nuestro feed ({final})")
            else:
                print(f"   ✖ el RSS viejo ({rss}) NO manda a nuestro feed: sigue sirviendo {len(titulos(xml))} episodios propios.")
                print("     → el redirect NO quedó hecho (o no se guardó). Spotify sigue leyendo lo que se sube en Creators.")
                print("       Lo más nuevo ahí: " + " | ".join(t for t, _ in titulos(xml)[:3]))
        except Exception as ex:
            print(f"   ? no pude abrir {rss} ({ex})")

    print("\n2) Lo que tiene Spotify")
    spot = []
    keys = ROBOT / "spotify_keys.txt"
    if not sid:
        print("   ✖ no encuentro el link del show de Spotify en el config")
    elif not keys.exists():
        print(f"   ✖ no está {keys}")
    else:
        try:
            l = [x.strip() for x in keys.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
            auth = base64.b64encode(f"{l[0]}:{l[1]}".encode()).decode()
            _, t = bajar("https://accounts.spotify.com/api/token", {"Authorization": "Basic " + auth,
                         "Content-Type": "application/x-www-form-urlencoded"}, b"grant_type=client_credentials")
            tok = json.loads(t)["access_token"]
            _, s = bajar(f"https://api.spotify.com/v1/shows/{sid}?market=MX", {"Authorization": "Bearer " + tok})
            sj = json.loads(s)
            print(f"   show: {sj.get('name')} · {sj.get('total_episodes')} episodios en Spotify")
            _, e = bajar(f"https://api.spotify.com/v1/shows/{sid}/episodes?market=MX&limit=15", {"Authorization": "Bearer " + tok})
            for ep in json.loads(e).get("items") or []:
                if ep:
                    spot.append(ep.get("name", ""))
                    print(f"   · {ep.get('release_date', '')}  {ep.get('name', '')}")
        except Exception as ex:
            print(f"   ? no pude preguntarle a Spotify ({ex})")

    print("\n3) Nuestro feed (lo último)")
    try:
        _, xml = bajar(feed_url + ("&" if "?" in feed_url else "?") + "x=1")
        nuestros = titulos(xml)
        def clave(par):
            return numero(par[0]) or 0
        ult = sorted(nuestros, key=clave)[-8:] if any(numero(t) for t, _ in nuestros) else nuestros[:8]
        nums_spot = {numero(x) for x in spot if numero(x)}
        norm_spot = {norm(x) for x in spot}
        faltan = []
        for t, d in ult:
            esta = (numero(t) in nums_spot) if numero(t) else (norm(t) in norm_spot)
            print(f"   {'✔' if esta else '✖'} {t}   ({d})")
            if not esta:
                faltan.append(t)
        if spot and faltan:
            print(f"\n   → A Spotify le faltan {len(faltan)} de estos. Si el punto 1 dice ✔, Spotify todavía no relee el feed:")
            print("     en Spotify for Creators → el show → 'Episodios' a veces hay un botón para actualizar; si no, tarda hasta 24 h.")
        elif spot:
            print("\n   ✔ Spotify ya tiene todo lo nuevo. Si no lo ves en la app, cierra y abre Spotify (caché del celular).")
    except Exception as ex:
        print(f"   ? no pude leer nuestro feed ({ex})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
