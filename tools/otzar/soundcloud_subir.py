#!/usr/bin/env python3
"""Sube a SoundCloud, solos, los shiurim nuevos de cada show (API oficial).

Una vez, en la PC de Otzar:
  1. En soundcloud.com/you/apps registra una app ("Register a new application").
     Redirect URI:  http://localhost:8721/callback
  2. Guarda sus llaves en C:\\OTZAR\\jabura\\soundcloud_app.txt
        línea 1: Client ID
        línea 2: Client Secret
     (ese archivo NUNCA va al repo)
  3. python soundcloud_subir.py autorizar <show>
     Se abre el navegador: entra con la cuenta de SoundCloud de ESE show y acepta.
     Queda C:\\OTZAR\\<show>\\soundcloud_token.json.
Luego cada ANUNCIAR (mantenimiento.py) corre:  python soundcloud_subir.py subir
y sube lo nuevo del feed de cada show autorizado. La primera vez solo memoriza lo
que ya existe (la cuenta gratis de SoundCloud permite ~3 horas en total); con
--todo sube también lo viejo.

Deja en C:\\robotwhats\\soundcloud_episodios.json el link de cada episodio, y el
robot lo pone en el anuncio ("SoundCloud").
"""
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
APP = BASE / "jabura" / "soundcloud_app.txt"
REDIRECT = "http://localhost:8721/callback"
AUTORIZAR = "https://secure.soundcloud.com/authorize"
TOKENS = ["https://secure.soundcloud.com/oauth/token", "https://api.soundcloud.com/oauth2/token"]
API = "https://api.soundcloud.com"
POR_CORRIDA = 4          # máximo de audios por ANUNCIAR (para no tardar ni gastar cuota de golpe)


def log(m):
    print(f"[{time.strftime('%d/%m %H:%M')}] SOUNDCLOUD {m}", flush=True)


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {} if defecto is None else defecto


def escribir_json(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def llaves():
    try:
        l = [x.strip() for x in APP.read_text(encoding="utf-8").splitlines() if x.strip()]
        return l[0], l[1]
    except Exception:
        return None, None


def pedir_token(datos):
    ultimo = None
    for url in TOKENS:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(datos).encode(),
                                     headers={"Accept": "application/json; charset=utf-8",
                                              "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            ultimo = f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}"
        except Exception as e:
            ultimo = str(e)
    raise RuntimeError(f"SoundCloud no dio el token: {ultimo}")


def autorizar(show):
    cid, secreto = llaves()
    if not cid:
        sys.exit(f"Falta {APP} (línea 1 Client ID, línea 2 Client Secret)")
    verificador = secrets.token_urlsafe(48)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    estado = secrets.token_urlsafe(16)
    url = AUTORIZAR + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
        "code_challenge": reto, "code_challenge_method": "S256", "state": estado})
    recibido = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            recibido.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Listo. Ya puedes cerrar esta ventana.</h2>".encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 8721), H)
    print("Abriendo el navegador. Entra con la cuenta de SoundCloud de", show, "y acepta.")
    print("Si no se abre, copia este link en el navegador:\n", url)
    webbrowser.open(url)
    while "code" not in recibido and "error" not in recibido:
        srv.handle_request()
    if recibido.get("error") or recibido.get("state") != estado:
        sys.exit(f"SoundCloud no autorizó: {recibido}")
    tok = pedir_token({"grant_type": "authorization_code", "client_id": cid, "client_secret": secreto,
                       "redirect_uri": REDIRECT, "code_verifier": verificador, "code": recibido["code"]})
    tok["vence"] = time.time() + int(tok.get("expires_in") or 3600) - 120
    escribir_json(BASE / show / "soundcloud_token.json", tok)
    yo = api_get("/me", tok["access_token"])
    print(f"Autorizado: {show} → {yo.get('permalink_url', '?')}")
    c = leer_json(BASE / show / "config.json")
    c["soundcloud_perfil"] = yo.get("permalink_url", "")
    escribir_json(BASE / show / "config.json", c)


def token_vigente(show):
    p = BASE / show / "soundcloud_token.json"
    tok = leer_json(p)
    if not tok.get("access_token"):
        return None
    if time.time() < float(tok.get("vence", 0)):
        return tok["access_token"]
    cid, secreto = llaves()
    nuevo = pedir_token({"grant_type": "refresh_token", "client_id": cid, "client_secret": secreto,
                         "refresh_token": tok.get("refresh_token", "")})
    nuevo.setdefault("refresh_token", tok.get("refresh_token"))
    nuevo["vence"] = time.time() + int(nuevo.get("expires_in") or 3600) - 120
    escribir_json(p, nuevo)
    return nuevo["access_token"]


def api_get(ruta, token):
    req = urllib.request.Request(API + ruta, headers={"Authorization": "OAuth " + token, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def subir_pista(token, titulo, descripcion, audio, nombre):
    limite = "----otzar" + secrets.token_hex(12)
    partes = []
    for k, v in (("track[title]", titulo[:100]), ("track[description]", descripcion[:3000]),
                 ("track[sharing]", "public"), ("track[downloadable]", "false")):
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
    partes.append((f'--{limite}\r\nContent-Disposition: form-data; name="track[asset_data]"; filename="{nombre}"\r\n'
                   f'Content-Type: application/octet-stream\r\n\r\n').encode("utf-8") + audio + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    req = urllib.request.Request(API + "/tracks", data=b"".join(partes), method="POST",
                                 headers={"Authorization": "OAuth " + token, "Accept": "application/json",
                                          "Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read().decode())


def feed_de(show, c):
    if show == "jabura":
        return "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/feed.xml"
    return f"https://raw.githubusercontent.com/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}/main/feed.xml"


def items(xml):
    out = []
    for it in re.findall(r"<item>([\s\S]*?)</item>", xml):
        g = re.search(r"<guid[^>]*>([\s\S]*?)</guid>", it)
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        e = re.search(r'<enclosure[^>]*url="([^"]+)"', it)
        d = re.search(r"<description>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</description>", it)
        f = re.search(r"<pubDate>([\s\S]*?)</pubDate>", it)
        if g and t and e:
            from email.utils import parsedate_to_datetime
            try:
                cuando = parsedate_to_datetime(f.group(1).strip()).timestamp() if f else 0
            except Exception:
                cuando = 0
            un = lambda s: s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').strip()
            out.append({"guid": un(g.group(1)), "titulo": un(t.group(1)), "audio": un(e.group(1)),
                        "desc": un(d.group(1)) if d else "", "cuando": cuando})
    return sorted(out, key=lambda x: x["cuando"])


def subir(shows, todo=False):
    cid, _ = llaves()
    if not cid:
        return
    links = leer_json(ROBOT / "soundcloud_episodios.json")
    for show in shows:
        c = leer_json(BASE / show / "config.json")
        if not (BASE / show / "soundcloud_token.json").exists():
            continue
        hechos_p = BASE / show / "soundcloud_subidos.json"
        hechos = leer_json(hechos_p)
        try:
            with urllib.request.urlopen(urllib.request.Request(feed_de(show, c), headers={"User-Agent": "otzar"}), timeout=60) as r:
                lista = items(r.read().decode("utf-8", "replace"))
        except Exception as ex:
            log(f"[{show}] no pude leer el feed ({ex})")
            continue
        if not hechos and not todo:                  # primera vez: lo que ya existe no se sube
            hechos = {i["guid"]: "" for i in lista}
            escribir_json(hechos_p, hechos)
            log(f"[{show}] primera vez: {len(hechos)} episodios viejos memorizados; desde ahora sube lo nuevo")
            continue
        nuevos = [i for i in lista if i["guid"] not in hechos][:POR_CORRIDA]
        if not nuevos:
            continue
        try:
            token = token_vigente(show)
        except Exception as ex:
            log(f"[{show}] {ex}  → vuelve a correr: python soundcloud_subir.py autorizar {show}")
            continue
        for i in nuevos:
            try:
                with urllib.request.urlopen(urllib.request.Request(i["audio"], headers={"User-Agent": "Mozilla/5.0"}), timeout=600) as r:
                    audio = r.read()
                nombre = re.sub(r"[^\w.\-]+", "_", Path(urllib.parse.urlparse(i["audio"]).path).name) or "shiur.mp3"
                pista = subir_pista(token, i["titulo"], i["desc"] or i["titulo"], audio, nombre)
                url = pista.get("permalink_url", "")
                hechos[i["guid"]] = url
                links.setdefault(show, {})[i["titulo"]] = url
                escribir_json(hechos_p, hechos)
                escribir_json(ROBOT / "soundcloud_episodios.json", links)
                log(f"[{show}] subido: {i['titulo'][:60]} → {url}")
            except urllib.error.HTTPError as e:
                cuerpo = e.read().decode("utf-8", "replace")[:200]
                log(f"[{show}] SoundCloud rechazó '{i['titulo'][:40]}' ({e.code}: {cuerpo})")
                if e.code in (401, 403, 422, 429):
                    break                            # sin permiso, sin cuota o castigo: se reintenta el próximo ANUNCIAR
            except Exception as ex:
                log(f"[{show}] no pude subir '{i['titulo'][:40]}' ({ex})")


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("autorizar", "subir"):
        print(__doc__)
        return 1
    if a[0] == "autorizar":
        if len(a) < 2:
            sys.exit("uso: python soundcloud_subir.py autorizar <show>")
        autorizar(a[1].lower())
        return 0
    shows = [x.lower() for x in a[1:] if not x.startswith("--")]
    if not shows:
        shows = [d.name for d in BASE.iterdir() if (d / "soundcloud_token.json").exists()]
    subir(shows, todo="--todo" in a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
