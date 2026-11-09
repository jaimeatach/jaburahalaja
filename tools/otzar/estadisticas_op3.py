#!/usr/bin/env python3
"""Estadísticas REALES de todos los podcasts (OP3) en un mes hebreo o un rango de fechas.

    python estadisticas_op3.py                      # Jeshván 5787 (12/10/2026 - 10/11/2026)
    python estadisticas_op3.py 2026-11-11 2026-12-10 # otro rango (el fin no se incluye +1 día)

Cada feed pasa sus mp3 por op3.dev (prefijo https://op3.dev/e/…): OP3 cuenta cada descarga /
reproducción que pide el mp3, con la app (Apple Podcasts, Spotify, Pocket Casts, navegador…),
el país y el episodio. Spotify guarda su propia copia del audio de los shows por RSS: sus
reproducciones NO llegan a OP3 (esas salen de Spotify for Creators).
Los robots (indexadores, "research", subtítulos…) NO se cuentan: van aparte en "por_tipo".
Horas = descargas × duración del episodio (lo que se bajó/escuchó como máximo; OP3 no ve si
se escuchó completo). Deja estadisticas_<inicio>.json y .csv junto al script.
Llave: OP3_TOKEN (variable o op3_token.txt); sin ella usa la de prueba pública de OP3.
"""
import base64, csv, json, os, re, sys, time, html, urllib.request, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FEEDS = {
 "jabura": "https://jaburahalajasaul.netlify.app/feed.xml",
 **{k: f"https://rabmeireliyahu.github.io/{k}/feed.xml" for k in (
  "tawil grillak davidsohn hilu credi isaaccredi nacash ofirmalka peretz tefila efshar taamim shawat "
  "abergel abuhatzeira ahavatjesed bensoussan biderman chazaq dafyomi davidpinto golan kavas krohn meital musar "
  "musayof podcast mishnaberura yalkutyosef ravasherweiss ravmeir ravmutzafi ravshmueli ravyitzchakyosef shaked "
  "torahanytime yakobov yechavedaat chicurel yitzchakcohen pinchastaylor yechezkelozer reuvenelbaz lugasi kachlon "
  "yarchi glazer turquie shas").split()},
}
INI = sys.argv[1] if len(sys.argv) > 2 else "2026-10-12"
FIN = sys.argv[2] if len(sys.argv) > 2 else "2026-11-11"
TOKEN = os.environ.get("OP3_TOKEN") or ((AQUI / "op3_token.txt").read_text().strip() if (AQUI / "op3_token.txt").exists() else "preview07ce")


ROBOT = re.compile(r"(?i)bot\b|bot/|crawl|spider|research|subtitl|fetch|biblestudy|python|curl|wget|validator|feedparser|go-http|okhttp/[0-9.]+$|java/|axios|node-fetch|scrapy|headless")
NAVEGADOR = re.compile(r"(?i)^(chrome|safari|firefox|edge|opera|samsung internet|mozilla/5\.0 \((windows|macintosh|x11))")


def tipo(r):
    """'app' (apps de podcast), 'web' (navegador) o 'robot' (indexadores, no son personas)."""
    nom = r.get("agentName") or ""
    if r.get("agentType") == "bot" or ROBOT.search(nom) or ROBOT.search(r.get("agentType") or ""):
        return "robot"
    if r.get("agentType") == "browser" or NAVEGADOR.search(nom):
        return "web"
    return "app"


def get(url, intentos=4):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "otzar-estadisticas"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 401, 403):
                raise
            time.sleep(3 * (i + 1))
        except Exception:
            time.sleep(3 * (i + 1))
    raise RuntimeError("sin respuesta: " + url)


def segs(d):
    d = (d or "").strip()
    if not d:
        return 0
    if d.isdigit():
        return int(d)
    p = [int(x) for x in d.split(":") if x.isdigit()]
    s = 0
    for x in p:
        s = s * 60 + x
    return s


def feed_info(url):
    x = get(url)
    tit = html.unescape((re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", x, re.S) or [None, "?"])[1].strip())
    dur, nom = {}, {}
    for it in re.findall(r"<item>([\s\S]*?)</item>", x):
        e = re.search(r'<enclosure[^>]*url="([^"]+)"', it)
        if not e:
            continue
        u = html.unescape(e.group(1))
        d = re.search(r"<itunes:duration>([^<]*)</itunes:duration>", it)
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        clave = urllib.parse.unquote(u.split("op3.dev/e/")[-1]).split("://")[-1]
        dur[clave] = segs(d.group(1) if d else "")
        nom[clave] = html.unescape(t.group(1).strip()) if t else ""
    return tit, dur, nom, x.count("op3.dev/e/")


def main():
    salida, filas = {"inicio": INI, "fin_exclusivo": FIN, "generado": time.strftime("%Y-%m-%d %H:%M"), "shows": []}, []
    for k, url in FEEDS.items():
        try:
            tit, dur, nom, con_op3 = feed_info(url)
        except Exception as e:
            print(f"{k:16} ✖ feed: {e}")
            continue
        if not con_op3:
            print(f"{k:16} (sin OP3 en el feed)")
            salida["shows"].append({"clave": k, "titulo": tit, "feed": url, "op3": False})
            continue
        b64 = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        try:
            uuid = json.loads(get(f"https://op3.dev/api/1/shows/{b64}?token={TOKEN}"))["showUuid"]
        except Exception as e:
            print(f"{k:16} ✖ OP3 no conoce el show ({e})")
            salida["shows"].append({"clave": k, "titulo": tit, "feed": url, "op3": False})
            continue
        n, segs_tot, apps, paises, eps, dias, oyentes = 0, 0, Counter(), Counter(), Counter(), Counter(), set()
        por_tipo = {t: {"descargas": 0, "segs": 0, "oyentes": set()} for t in ("app", "web", "robot")}
        cont = None
        while True:
            q = f"https://op3.dev/api/1/downloads/show/{uuid}?start={INI}&end={FIN}&format=json&limit=20000&token={TOKEN}"
            if cont:
                q += "&continuationToken=" + urllib.parse.quote(cont)
            j = json.loads(get(q))
            for r in j.get("rows", []):
                clave = urllib.parse.unquote(r.get("url", "").split("op3.dev/e/")[-1]).split("://")[-1]
                t = tipo(r)
                pt = por_tipo[t]
                pt["descargas"] += 1
                pt["segs"] += dur.get(clave, 0)
                pt["oyentes"].add(r.get("audienceId"))
                if t == "robot":
                    apps[r.get("agentName") or "robot"] += 1
                    continue
                n += 1
                segs_tot += dur.get(clave, 0)
                apps[r.get("agentName") or r.get("agentType") or "?"] += 1
                paises[r.get("countryCode") or "?"] += 1
                eps[nom.get(clave) or clave.rsplit("/", 1)[-1]] += 1
                dias[r.get("time", "")[:10]] += 1
                oyentes.add(r.get("audienceId"))
            cont = j.get("continuationToken")
            if not cont:
                break
        horas = round(segs_tot / 3600, 1)
        print(f"{k:16} {n:7} descargas (robots aparte: {por_tipo['robot']['descargas']}) · {horas:8} h · {len(oyentes):5} oyentes · {tit[:40]}")
        salida["shows"].append({"clave": k, "titulo": tit, "feed": url, "op3": True, "uuid": uuid,
                                "descargas": n, "horas": horas, "oyentes": len(oyentes),
                                "por_tipo": {t: {"descargas": v["descargas"], "horas": round(v["segs"] / 3600, 1),
                                                 "oyentes": len(v["oyentes"])} for t, v in por_tipo.items()},
                                "apps": apps.most_common(), "paises": paises.most_common(),
                                "top": eps.most_common(10), "dias": sorted(dias.items())})
        filas.append([k, tit, n, horas, len(oyentes)])
    tot = sum(s.get("descargas", 0) for s in salida["shows"])
    th = round(sum(s.get("horas", 0) for s in salida["shows"]), 1)
    print(f"\nTOTAL {INI} → {FIN} (sin incluir): {tot} descargas · {th} horas")
    (AQUI / f"estadisticas_{INI}.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(AQUI / f"estadisticas_{INI}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["show", "titulo", "descargas", "horas", "oyentes"])
        w.writerows(sorted(filas, key=lambda r: -r[2]))


if __name__ == "__main__":
    main()
