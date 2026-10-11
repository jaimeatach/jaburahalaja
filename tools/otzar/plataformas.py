#!/usr/bin/env python3
"""Dónde está cada show: grupos de WhatsApp, Spotify, Apple Podcasts, Amazon, SoundCloud.

    python plataformas.py            # revisa todo y lo muestra
    python plataformas.py --rapido   # lo mismo, pero si ya se revisó hace menos de 20 h no hace nada
                                     # (así lo corre mantenimiento.py en cada ANUNCIAR)

Apple Podcasts se revisa solo (API pública de iTunes, sin llaves): se busca el show
por el nombre de su feed y se confirma por la URL del feed. Lo que encuentra queda
en C:\\robotwhats\\plataformas.json y el robot pone el link del EPISODIO en Apple en
cada anuncio. Amazon Music y SoundCloud no tienen API pública: se ponen a mano una
vez (instalar_otzar.py --amazon=show:LINK / --soundcloud=show:LINK) y va el link del show.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
FEED_JABURA = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/feed.xml"
PUBLICO_JABURA = "https://jaburahalajasaul.netlify.app/feed.xml"


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {} if defecto is None else defecto


def bajar(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (otzar-plataformas)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def feeds_de(show, datos, cfg_show):
    """(feed para leer, feed público para Apple/Amazon, otros feeds que pueden estar en Apple)."""
    if show == "jabura":
        return FEED_JABURA, PUBLICO_JABURA, [PUBLICO_JABURA, FEED_JABURA]
    user = cfg_show.get("github_user", "rabmeireliyahu")
    repo = cfg_show.get("github_repo", show)
    publico = f"https://{user}.github.io/{repo}/feed.xml"
    leer = f"https://raw.githubusercontent.com/{user}/{repo}/main/feed.xml"
    if str(datos.get("feed", "")).startswith("http"):
        leer = datos["feed"]
    otros = [publico, leer] + ([cfg_show["rss_original"]] if cfg_show.get("rss_original") else [])
    return leer, publico, otros


def plano(u):
    return re.sub(r"^https?://|/+$", "", str(u or "").strip().lower())


def norm(t):
    return re.sub(r"[^\w]+", " ", str(t or "").lower()).strip()


def buscar_apple(titulo, feeds):
    """(collectionId, url del show) si el show está en Apple Podcasts."""
    q = urllib.parse.quote(titulo[:80])
    j = json.loads(bajar(f"https://itunes.apple.com/search?media=podcast&entity=podcast&limit=15&term={q}"))
    validos = {plano(f) for f in feeds if f}
    res = j.get("results") or []
    for r in res:
        if plano(r.get("feedUrl")) in validos:
            return str(r.get("collectionId")), (r.get("collectionViewUrl") or "").split("?")[0]
    for r in res:
        if norm(r.get("collectionName")) == norm(titulo):
            return str(r.get("collectionId")), (r.get("collectionViewUrl") or "").split("?")[0]
    return "", ""


def main():
    rapido = "--rapido" in sys.argv
    destino = ROBOT / "plataformas.json"
    previo = leer_json(destino)
    if rapido and time.time() - float(previo.get("_revisado", 0) or 0) < 20 * 3600:
        return 0
    cfgw = leer_json(ROBOT / "config_whatsapp.json")
    reg = leer_json(ROBOT / "grupos_registrados.json")
    out = {"_revisado": time.time()}
    filas, faltan_apple, problemas = [], [], []
    for show, datos in (cfgw.get("anunciar") or {}).items():
        datos = datos or {}
        cfg_show = leer_json(BASE / show / "config.json")
        leer, publico, otros = feeds_de(show, datos, cfg_show)
        prev = previo.get(show) or {}
        info = {k: v for k, v in prev.items() if k in ("amazon", "soundcloud")}
        titulo, n_items, ultimo = cfg_show.get("titulo", show), 0, None
        try:
            x = bajar(leer)
            m = re.search(r"<channel>[\s\S]*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", x)
            if m:
                titulo = m.group(1).strip()
            items = re.findall(r"<item>([\s\S]*?)</item>", x)
            n_items = len(items)
            fechas = []
            for it in items:
                d = re.search(r"<pubDate>(.*?)</pubDate>", it)
                try:
                    f = parsedate_to_datetime(d.group(1).strip())
                    fechas.append(f if f.tzinfo else f.replace(tzinfo=timezone.utc))
                except Exception:
                    pass
            ultimo = max(fechas) if fechas else None
        except Exception as ex:
            problemas.append(f"{show}: no pude leer su feed ({ex})")
        apple_id, apple_url = "", ""
        if not rapido or not prev.get("apple_id"):
            try:
                apple_id, apple_url = buscar_apple(titulo, otros)
                time.sleep(3)                      # Apple: máximo ~20 consultas por minuto
            except Exception as ex:
                problemas.append(f"{show}: no pude consultar Apple ({ex})")
                apple_id, apple_url = prev.get("apple_id", ""), prev.get("apple", "")
        else:
            apple_id, apple_url = prev.get("apple_id", ""), prev.get("apple", "")
        if datos.get("apple"):
            apple_url = datos["apple"]
            apple_id = (re.search(r"id(\d{5,})", apple_url) or [None, apple_id])[1]
        info.update({"titulo": titulo, "feed": publico, "apple_id": apple_id, "apple": apple_url})
        out[show] = info
        grupos = (reg.get(show) or {}).get("grupos") or ([reg[show]] if (reg.get(show) or {}).get("id") else [])
        spot = str(datos.get("spotify", ""))
        amazon = datos.get("amazon") or info.get("amazon")
        sc = datos.get("soundcloud") or info.get("soundcloud")
        dias = (datetime.now(timezone.utc) - ultimo).days if ultimo else None
        filas.append((show, len(grupos), "PAUSA" if datos.get("pausado") else "", "sí" if spot.startswith("http") else "NO",
                      "sí" if apple_id or apple_url else "NO", "sí" if amazon else "NO", "sí" if sc else "-",
                      n_items, f"{dias} d" if dias is not None else "?"))
        if not (apple_id or apple_url) and not datos.get("pausado"):
            faltan_apple.append((show, titulo, publico))
        if not datos.get("pausado") and not grupos and (datos.get("invite") or "") != "":
            problemas.append(f"{show}: tiene grupo en el config pero el robot no lo identificó (¿el robot es miembro?)")
        if not datos.get("pausado") and not datos.get("invite"):
            problemas.append(f"{show}: NO tiene grupo de WhatsApp donde anunciar")
        if dias is not None and dias > 14 and not datos.get("pausado"):
            problemas.append(f"{show}: su feed no tiene nada nuevo hace {dias} días")
    for k, v in previo.items():                 # shows que ya no están: se conserva lo puesto a mano
        if k not in out and isinstance(v, dict):
            out[k] = v
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if rapido:
        print(f"plataformas: revisadas ({sum(1 for f in filas if f[4] == 'sí')} de {len(filas)} shows en Apple Podcasts)")
        return 0
    print(f"{'show':<18}{'grupos':>7}  {'':5} {'Spotify':>8} {'Apple':>6} {'Amazon':>7} {'SoundC':>7} {'episod':>7} {'último':>7}")
    for f in filas:
        print(f"{f[0]:<18}{f[1]:>7}  {f[2]:5} {f[3]:>8} {f[4]:>6} {f[5]:>7} {f[6]:>7} {f[7]:>7} {f[8]:>7}")
    if problemas:
        print("\nPROBLEMAS:")
        for p in problemas:
            print("  ·", p)
    if faltan_apple:
        print("\nFALTAN EN APPLE PODCASTS (dar de alta una vez en https://podcastsconnect.apple.com → + → Nuevo show → 'Agregar un show con un feed RSS'):")
        for show, titulo, feed in faltan_apple:
            print(f"  · {show:<16} {titulo[:40]:<40} {feed}")
    sin_amazon = [f[0] for f in filas if f[5] == "NO" and not f[2]]
    if sin_amazon:
        print("\nAMAZON MUSIC: dar de alta cada feed en https://podcasters.amazon.com (mismo link RSS de arriba),")
        print("  y luego pásame el link del show: instalar_otzar.py --amazon=show:LINK")
        print("  sin Amazon:", ", ".join(sin_amazon))
    print(f"\nGuardado en {destino}: el robot ya pone el link de Apple en los anuncios de los que están.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
