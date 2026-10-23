#!/usr/bin/env python3
"""Dónde está cada show: grupos de WhatsApp, Spotify, Apple Podcasts, Amazon, SoundCloud.

    python plataformas.py            # revisa todo y lo muestra
    python plataformas.py --rapido   # lo mismo, pero si ya se revisó hace menos de 3 h no hace nada
                                     # (así lo corre mantenimiento.py en cada ANUNCIAR)

Apple Podcasts se revisa solo (API pública de iTunes, sin llaves): se busca el show
por el nombre de su feed y se confirma por la URL del feed. Lo que encuentra queda
en C:\\robotwhats\\plataformas.json y el robot pone el link del EPISODIO en Apple en
cada anuncio. Amazon Music y SoundCloud no tienen API pública: se ponen a mano una
vez (instalar_otzar.py --amazon=show:LINK / --soundcloud=show:LINK) y va el link del show.
"""
import base64
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
    # (oct/2026) Apple guardó el de dafyomi como ".../dafyomi/feed", sin ".xml": se comparan igual
    return re.sub(r"(/feed)\.xml$", r"\1", re.sub(r"^https?://|/+$", "", str(u or "").strip().lower()))


# Shows que ya sabemos que están en Apple (oct/2026): si la búsqueda de Apple no los trae
# (pasa con los recién aprobados), se usa este id. El de anunciar.<show>.apple manda sobre todo.
APPLE_FIJOS = {
    "tawil": "https://podcasts.apple.com/us/podcast/harav-yosef-tawil-shlit-a/id6824121409",
    "dafyomi": "https://podcasts.apple.com/us/podcast/daf-yomi-espa%C3%B1ol-jabrutouch/id6824132852",
}


def norm(t):
    return re.sub(r"[^\w]+", " ", str(t or "").lower()).strip()


def buscar_apple(titulo, feeds):
    """(collectionId, url del show) si el show está en Apple Podcasts."""
    validos = {plano(f) for f in feeds if f}
    # (oct/2026) "Harav Yosef Tawil Shlit”a" no salía: las comillas raras rompen la búsqueda de
    # Apple. Se prueba el título tal cual, sin comillas y con sus primeras palabras; solo se acepta
    # un resultado con NUESTRO feed o con el mismo nombre, así que probar más no trae otro show.
    limpio = re.sub(r"[\"”“״׳'`’]", "", titulo).strip()
    palabras = [w for w in re.split(r"\s+", limpio) if w]
    terminos = []
    for t in (titulo[:80], limpio[:80], " ".join(palabras[:3]), " ".join(palabras[1:3])):
        if t and t not in terminos:
            terminos.append(t)
    for i, t in enumerate(terminos):
        if i:
            time.sleep(3)                          # Apple: máximo ~20 consultas por minuto
        q = urllib.parse.quote(t)
        j = json.loads(bajar(f"https://itunes.apple.com/search?media=podcast&entity=podcast&limit=25&term={q}"))
        res = j.get("results") or []
        for r in res:
            if plano(r.get("feedUrl")) in validos:
                return str(r.get("collectionId")), (r.get("collectionViewUrl") or "").split("?")[0]
        for r in res:
            if norm(r.get("collectionName")) in (norm(titulo), norm(limpio)):
                return str(r.get("collectionId")), (r.get("collectionViewUrl") or "").split("?")[0]
    return "", ""


def buscar_spotify(titulo):
    """Link del show en Spotify con EXACTAMENTE este nombre (llaves del robot), o ""."""
    l = [x.strip() for x in (ROBOT / "spotify_keys.txt").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    auth = base64.b64encode(f"{l[0]}:{l[1]}".encode()).decode()
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=b"grant_type=client_credentials",
                                 headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read().decode())["access_token"]
    q = urllib.parse.quote(titulo[:100])
    req = urllib.request.Request(f"https://api.spotify.com/v1/search?type=show&market=MX&limit=10&q={q}",
                                 headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = (json.loads(r.read().decode()).get("shows") or {}).get("items") or []
    for sh in res:
        if sh and norm(sh.get("name")) == norm(titulo):
            return "https://open.spotify.com/show/" + sh["id"]
    return ""


def activar_spotify(cfgw, show, link, guids):
    """El show recién apareció en Spotify: se pone el link, se quita la pausa y lo que ya
    estaba en el feed queda como anunciado salvo el último (así no salen los viejos en tropel)."""
    datos = cfgw["anunciar"][show]
    datos.update({"spotify": link, "sin_spotify": False, "pausado": False})
    datos.pop("buscar_spotify", None)
    rw = ROBOT / "config_whatsapp.json"
    rw.with_name(rw.name + ".bak_" + time.strftime("%Y%m%d%H%M%S")).write_bytes(rw.read_bytes())
    rw.write_text(json.dumps(cfgw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estado_p = ROBOT / "estado_anuncios.json"
    e = leer_json(estado_p)
    previos = e.get(show) or []
    e[show] = (previos + [g for g in guids[:-1] if g not in previos])[-2000:]
    if estado_p.exists():
        estado_p.with_name(estado_p.name + ".bak_" + time.strftime("%Y%m%d%H%M%S")).write_bytes(estado_p.read_bytes())
    estado_p.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        (ROBOT / "avisos").mkdir(exist_ok=True)
        (ROBOT / "avisos" / f"{time.strftime('%Y%m%d%H%M%S')}_spotify_{show}.txt").write_text(
            f"✅ Otzar: {show} ya está en Spotify ({link}); el robot empieza a anunciarlo.", encoding="utf-8")
    except OSError:
        pass


def main():
    rapido = "--rapido" in sys.argv
    destino = ROBOT / "plataformas.json"
    previo = leer_json(destino)
    # (oct/2026) cada 3 h (antes 20): en modo rápido solo pregunta por los shows que AÚN no
    # tiene ubicados en Apple, así un show recién aprobado sale en el siguiente ANUNCIAR
    if rapido and time.time() - float(previo.get("_revisado", 0) or 0) < 3 * 3600:
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
        guids = []
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
            pares = []
            for it in items:
                g = re.search(r"<guid[^>]*>(.*?)</guid>", it)
                d = re.search(r"<pubDate>(.*?)</pubDate>", it)
                try:
                    cuando = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
                except Exception:
                    cuando = 0
                if g:
                    pares.append((cuando, g.group(1).replace("&amp;", "&")))
            guids = [g for _, g in sorted(pares)]          # del más viejo al más nuevo
        except Exception as ex:
            problemas.append(f"{show}: no pude leer su feed ({ex})")
        # (oct/2026) show nuevo que aún no está en Spotify ("buscar_spotify", p. ej. grilak):
        # se busca por el nombre de su feed; al aparecer se activa solo
        if datos.get("buscar_spotify") and not str(datos.get("spotify", "")).startswith("http") and n_items:
            try:
                link = buscar_spotify(titulo)
                if link:
                    activar_spotify(cfgw, show, link, guids)
                    problemas.append(f"{show}: apareció en Spotify ({link}); anuncio activado")
            except Exception as ex:
                problemas.append(f"{show}: no pude buscarlo en Spotify ({ex})")
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
        if not apple_id and APPLE_FIJOS.get(show):
            apple_url = APPLE_FIJOS[show]
            apple_id = re.search(r"id(\d{5,})", apple_url).group(1)
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
        inv = datos.get("invite")
        links = [x for x in (inv if isinstance(inv, list) else [inv]) if isinstance(x, str) and x.startswith("http")]
        if not datos.get("pausado") and not links:
            problemas.append(f"{show}: NO tiene grupo de WhatsApp donde anunciar")
        elif not datos.get("pausado") and len(grupos) < len(links):
            problemas.append(f"{show}: {len(links) - len(grupos)} grupo(s) del config sin identificar "
                             "(¿el robot es miembro? se ubican al reiniciar el robot)")
        if dias is not None and dias > 14 and not datos.get("pausado"):
            problemas.append(f"{show}: su feed no tiene nada nuevo hace {dias} días")
    for k, v in previo.items():                 # shows que ya no están: se conserva lo puesto a mano
        if k not in out and isinstance(v, dict):
            out[k] = v
    # (oct/2026) un grupo de anuncio que usan SOLO dos shows suele ser el grupo de un Rab metido
    # por error en otro show (Ofir Malka salía en el grupo de Pinto). Los generales ("Solo Shiurim")
    # los usan muchos y no cuentan. Se avisa una vez al chat del "!reporte".
    uso = {}
    for sh, r in reg.items():
        if sh.startswith(("escucha:", "admin:")) or not isinstance(r, dict):
            continue
        for g in (r.get("grupos") or ([r] if r.get("id") else [])):
            if g.get("id"):
                uso.setdefault(g["id"], {"nombre": g.get("nombre", "?"), "shows": set()})["shows"].add(sh)
    avisados = set(previo.get("_grupos_avisados") or [])
    for gid, u in uso.items():
        if len(u["shows"]) == 2:
            txt = f"grupo «{u['nombre']}» lo usan {' y '.join(sorted(u['shows']))}: ¿uno anuncia en el grupo del otro? (quitar: instalar_otzar.py --quitar-grupo=show:nombre)"
            problemas.append(txt)
            clave = gid + "|" + ",".join(sorted(u["shows"]))
            if clave not in avisados:
                avisados.add(clave)
                try:
                    (ROBOT / "avisos").mkdir(exist_ok=True)
                    (ROBOT / "avisos" / f"{time.strftime('%Y%m%d%H%M%S')}_grupo.txt").write_text("⚠️ Otzar: " + txt, encoding="utf-8")
                except OSError:
                    pass
    out["_grupos_avisados"] = sorted(avisados)
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
