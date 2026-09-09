#!/usr/bin/env python3
"""
Saca la lista de episodios del canal de Spotify a partir de su RSS, para poder
poner el botón de Spotify al lado de cada shiur en la app.

    python spotify_lista.py "https://anchor.fm/s/XXXXXXX/podcast/rss"

El RSS se consigue en Spotify for Podcasters → el show → Settings →
Availability → "RSS distribution" (o "Feed RSS"). No baja audio: solo lee
títulos y enlaces, y los deja en spotify_episodios.json.

Es la parte de "rescatar" de podcast_bot.py que hace falta acá, sin el resto.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def directo(url):
    """Sigue la redirección de podcasters.spotify.com hasta open.spotify.com/episode/…

    Ese es el link que abre el episodio directo en la app de Spotify.
    """
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            final = r.geturl()
            m = re.search(r"open\.spotify\.com/episode/[A-Za-z0-9]+", final)
            if m:
                return "https://" + m.group(0)
            # a veces la página final trae el id adentro aunque la URL no lo diga
            cuerpo = r.read(200000).decode("utf-8", "replace")
            m = re.search(r"open\.spotify\.com/episode/([A-Za-z0-9]{22})", cuerpo)
            if m:
                return "https://open.spotify.com/episode/" + m.group(1)
            return final
    except Exception:
        return url


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso:  python spotify_lista.py "URL-del-RSS"')
    url = sys.argv[1].strip()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raiz = ET.fromstring(r.read())
    canal = raiz.find("channel")
    if canal is None:
        sys.exit("Eso no parece un RSS de podcast.")
    print("Show:", (canal.findtext("title") or "").strip())
    salida = []
    for it in canal.findall("item"):
        titulo = (it.findtext("title") or "").strip()
        enlace = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or "").strip()
        # Spotify for Podcasters pone el enlace del episodio en <link>; si no,
        # el guid suele ser una URL utilizable.
        if not enlace.startswith("http") and guid.startswith("http"):
            enlace = guid
        print("   resolviendo:", titulo[:60])
        salida.append({"titulo": titulo, "enlace": directo(enlace), "enlace_rss": enlace})
    with open("spotify_episodios.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"{len(salida)} episodios → spotify_episodios.json")
    for e in salida[:8]:
        print("   ·", e["titulo"][:70])
    if len(salida) > 8:
        print(f"   … y {len(salida) - 8} más")
    print("\nMandá el archivo spotify_episodios.json y con eso emparejo cada uno con su shiur.")


if __name__ == "__main__":
    main()
