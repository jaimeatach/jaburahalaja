#!/usr/bin/env python3
"""
Saca la lista de episodios del canal de Spotify con el link EXACTO de cada uno
(open.spotify.com/episode/…), para poner el botón al lado de cada shiur.

Dos caminos, del más seguro al menos:

  1) API de Spotify — da el link exacto, siempre. Necesita una credencial gratis:
       developer.spotify.com/dashboard → Create app → copiar Client ID y Secret
     y ponerlas en variables de entorno antes de correr:
       set SPOTIFY_CLIENT_ID=...
       set SPOTIFY_CLIENT_SECRET=...
       python spotify_lista.py

  2) RSS del show + rascar la página de cada episodio. No necesita credencial,
     pero Spotify no siempre expone el ID ahí:
       python spotify_lista.py "https://anchor.fm/s/XXXXXXX/podcast/rss"

Deja spotify_episodios.json con titulo y enlace. No baja audio.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SHOW = "1tH0BEW6Aj5Y6jjgaLyLp5"     # Jabura Halaja
RSS = "https://anchor.fm/s/10984f8dc/podcast/rss"

for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def pedir(url, headers=None, datos=None, timeout=30):
    req = urllib.request.Request(url, data=datos, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


# ── Camino 1: la API ─────────────────────────────────────────────────────────
def por_api(cid, secreto, show):
    cred = base64.b64encode(f"{cid}:{secreto}".encode()).decode()
    cuerpo, _ = pedir("https://accounts.spotify.com/api/token",
                      headers={"Authorization": "Basic " + cred,
                               "Content-Type": "application/x-www-form-urlencoded"},
                      datos=b"grant_type=client_credentials")
    token = json.loads(cuerpo)["access_token"]
    salida, offset = [], 0
    while True:
        url = (f"https://api.spotify.com/v1/shows/{show}/episodes"
               f"?limit=50&offset={offset}&market=US")
        cuerpo, _ = pedir(url, headers={"Authorization": "Bearer " + token})
        pagina = json.loads(cuerpo)
        for ep in pagina.get("items") or []:
            if not ep:
                continue
            salida.append({"titulo": (ep.get("name") or "").strip(),
                           "enlace": (ep.get("external_urls") or {}).get("spotify", "")})
        if not pagina.get("next"):
            break
        offset += 50
    return salida


# ── Camino 2: RSS + rascar la página ─────────────────────────────────────────
ID22 = r"([A-Za-z0-9]{22})"
PATRONES = [r"open\.spotify\.com/episode/" + ID22, r"spotify:episode:" + ID22,
            r'"episodeUri":"spotify:episode:' + ID22, r'/episode/' + ID22 + r'["?]']


def rascar(url):
    """Busca el ID del episodio en la URL final y en toda la página."""
    if not url:
        return ""
    try:
        cuerpo, final = pedir(url, timeout=25)
        texto = final + "\n" + cuerpo.decode("utf-8", "replace")
        for pat in PATRONES:
            m = re.search(pat, texto)
            if m:
                return "https://open.spotify.com/episode/" + m.group(1)
        return final
    except Exception:
        return url


def por_rss(url):
    cuerpo, _ = pedir(url, timeout=60)
    canal = ET.fromstring(cuerpo).find("channel")
    if canal is None:
        sys.exit("Eso no parece un RSS de podcast.")
    print("Show:", (canal.findtext("title") or "").strip())
    salida = []
    for it in canal.findall("item"):
        titulo = (it.findtext("title") or "").strip()
        enlace = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or "").strip()
        if not enlace.startswith("http") and guid.startswith("http"):
            enlace = guid
        print("   resolviendo:", titulo[:60])
        salida.append({"titulo": titulo, "enlace": rascar(enlace), "enlace_rss": enlace})
    return salida


def main():
    cid, secreto = os.environ.get("SPOTIFY_CLIENT_ID", "").strip(), os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    show = SHOW
    m = re.search(r"open\.spotify\.com/show/([A-Za-z0-9]+)", arg)
    if m:
        show = m.group(1)

    if cid and secreto:
        print("Usando la API de Spotify (link exacto garantizado)…")
        salida = por_api(cid, secreto, show)
    else:
        rss = arg if arg.startswith("http") and "spotify.com/show" not in arg else RSS
        print("Sin credencial de la API: leo el RSS y rasco cada episodio.")
        print("(Para el link exacto seguro: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET)\n")
        salida = por_rss(rss)

    with open("spotify_episodios.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    exactos = sum(1 for e in salida if "open.spotify.com/episode/" in e["enlace"])
    print(f"\n{len(salida)} episodios → spotify_episodios.json · con link exacto: {exactos}")
    for e in salida[:6]:
        print("   ·", e["titulo"][:60])
    if exactos < len(salida):
        print("\nNo todos tienen link exacto. Con la credencial de la API salen todos:")
        print("  developer.spotify.com/dashboard → Create app → Client ID y Secret")
    print("\nMandá spotify_episodios.json y con eso emparejo.")


if __name__ == "__main__":
    main()
