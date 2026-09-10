#!/usr/bin/env python3
"""
Espejo del feed de Nacach: el show de Spotify se dio de alta con el RSS del repo
viejo (rabmeireliyahu/nacash) y el subidor publica en el nuevo (nacach), así que
desde el 18/8 Spotify no veía nada nuevo. Esto copia feed.xml de nacach a nacash
cada vez que corre (ANUNCIAR.bat lo llama), y así da igual cuál lea Spotify.

    python espejo_nacash.py        # corre en C:\\OTZAR\\nacach (usa su github_token.txt)
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

AQUI = Path(__file__).resolve().parent
USUARIO, ORIGEN, ESPEJO = "rabmeireliyahu", "nacach", "nacash"


def gh(cab, metodo, url, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read().decode()
            return r.status, (json.loads(t) if t.strip() else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:                                  # noqa: BLE001
        return 0, {"message": str(e)}


def main():
    tok = AQUI / "github_token.txt"
    if not tok.exists():
        print("espejo nacash: falta github_token.txt junto a este script.")
        return 1
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "espejo-nacash", "Accept": "application/vnd.github+json"}
    st, j = gh(cab, "GET", f"https://api.github.com/repos/{USUARIO}/{ORIGEN}/contents/feed.xml")
    if st != 200 or not j.get("content"):
        print(f"espejo nacash: no pude leer el feed de {ORIGEN} ({st} {j.get('message', '')})")
        return 1
    feed = base64.b64decode(j["content"])
    st, e = gh(cab, "GET", f"https://api.github.com/repos/{USUARIO}/{ESPEJO}/contents/feed.xml")
    if st == 200 and e.get("sha") == j.get("sha"):
        print(f"espejo nacash: ya es igual ({feed.count(b'<item>')} episodios).")
        return 0
    cuerpo = {"message": "feed espejo de " + ORIGEN, "content": base64.b64encode(feed).decode()}
    if st == 200 and e.get("sha"):
        cuerpo["sha"] = e["sha"]
    st, r = gh(cab, "PUT", f"https://api.github.com/repos/{USUARIO}/{ESPEJO}/contents/feed.xml", cuerpo)
    if st in (200, 201):
        print(f"espejo nacash: feed copiado a {ESPEJO} ({feed.count(b'<item>')} episodios). "
              f"Spotify lo toma en unas horas.")
        return 0
    print(f"espejo nacash: ERROR {st} {r.get('message', '')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
