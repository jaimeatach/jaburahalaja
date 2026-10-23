#!/usr/bin/env python3
"""¿Cuánto ocupan los shiurim en la PC y cuáles ya están a salvo en archive.org?

    python espacio.py

NO BORRA NADA y no toca el robot (puede estar abierto). Es el primer paso para dejar de
guardar los audios en la PC (oct/2026):
1. Por cada show de C:\\OTZAR: cuántos audios tiene en la PC, cuánto pesan y cuántos ya
   están en su ítem de archive.org con el MISMO tamaño (esos son los que se podrán borrar).
2. Espacio libre del disco y lo que ocupan otras carpetas grandes.
3. Manda al repo (con github_token.txt de la jabura) una copia de cada podcast_bot.py
   distinto y este reporte, para revisar cómo sabe cada bot qué ya bajó/subió antes de
   borrar nada: si un bot lo decide mirando su carpeta, al vaciarla volvería a bajar y a
   publicar todo repetido. Antes de mandar un bot se revisa que no lleve llaves adentro.
El reporte queda también en C:\\OTZAR\\espacio_reporte.txt.

    python espacio.py limpiar          → dice qué se borraría (no borra) y deja la lista en
                                         C:\\OTZAR\\limpieza_lista.txt
    python espacio.py limpiar --si     → lo aparta a C:\\OTZAR\\_papelera (14 días y se borra solo)

Un audio sale de la PC SOLO si (oct/2026, el usuario: "no quiero perder shiurim"):
  · está en el ítem de archive.org de su show con el MISMO tamaño y la MISMA huella (md5);
  · y ya está en el feed publicado (salvo shows frenados, cuyo feed ya no se usa);
  · un audio original de WhatsApp: el bot ya lo marcó como publicado (procesados_whatsapp.txt)
    y su mp3 está en archive.org;
  · no es de los últimos 7 días ni de los 3 más nuevos de su carpeta (el robot se guía por ellos).
Antes se pone "solo_agregar": true en el config.json del show: sin eso, podcast_bot rearma el
feed con lo que haya en la carpeta y perdería los episodios borrados. Nunca toca la jabura
(Drive compartido de Saúl) ni nada fuera de C:\\OTZAR. Si archive.org o el feed no contestan,
ese show no se toca. Con --si queda C:\\OTZAR\\limpieza_auto.json y mantenimiento.py la corre
una vez al día (lo que se va publicando sale solo de la PC).
"""
import base64
import hashlib
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
REPO = "jaimeatach/jaburahalaja"
RAMA = "claude/shiurim-halachot-shabbat-vriig5"
AUDIO = {".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aac", ".mp4", ".webm", ".oga", ".amr"}
LLAVES = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_\w{20,}|gho_\w{20,}|AKIA[0-9A-Z]{16}|"
                    r"(?i:(secret|password|passwd|api_key|apikey|token|clave)\s*[:=]\s*['\"][^'\"\s]{12,}['\"])")

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

lineas = []


def decir(t=""):
    print(t)
    lineas.append(t)


def leer_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def mb(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def peso_carpeta(d):
    total = 0
    for f in d.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def en_archive(ident):
    """{nombre de archivo: tamaño} del ítem de archive.org."""
    if not ident:
        return {}
    try:
        req = urllib.request.Request(f"https://archive.org/metadata/{ident}", headers={"User-Agent": "otzar-espacio"})
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    out = {}
    for f in j.get("files") or []:
        try:
            out[Path(f.get("name", "")).name.lower()] = int(f.get("size") or 0)
        except ValueError:
            pass
    return out


def en_archive_md5(ident):
    """{nombre en minúsculas: [(tamaño, md5), ...]} del ítem; None si archive.org no contesta."""
    if not ident:
        return None
    try:
        req = urllib.request.Request(f"https://archive.org/metadata/{ident}", headers={"User-Agent": "otzar-espacio"})
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    if not j.get("files"):
        return None
    out = {}
    for f in j["files"]:
        try:
            out.setdefault(Path(f.get("name", "")).name.lower(), []).append((int(f.get("size") or 0), str(f.get("md5") or "").lower()))
        except ValueError:
            pass
    return out


def carpetas_de(d, c):
    cs = [d / "episodios", d / "audios_whatsapp", d / "convertidos", d / "descargas", d / "audios"]
    if c.get("carpeta_whatsapp"):
        cs.append(Path(c["carpeta_whatsapp"]))
    vistas, out = set(), []
    for x in cs:
        k = str(x).lower()
        if k not in vistas and x.is_dir():
            vistas.add(k)
            out.append(x)
    return out


def subir_al_repo(tok, ruta, contenido, mensaje):
    cab = {"Authorization": "token " + tok, "User-Agent": "otzar-espacio", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPO}/contents/{ruta}"
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url + f"?ref={RAMA}", headers=cab), timeout=60) as r:
            sha = json.loads(r.read().decode())["sha"]
    except Exception:
        pass
    datos = {"message": mensaje, "branch": RAMA, "content": base64.b64encode(contenido).decode()}
    if sha:
        datos["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(datos).encode(), headers=cab, method="PUT")
    with urllib.request.urlopen(req, timeout=120) as r:
        r.read()


# ── limpiar ──────────────────────────────────────────────────────────────────
PAPELERA = BASE / "_papelera"
DIAS_PAPELERA = 14
DIAS_RECIENTES = 7
NUEVOS_QUE_QUEDAN = 3


def md5_de(f):
    h = hashlib.md5()
    with open(f, "rb") as x:
        for bloque in iter(lambda: x.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_feed(c, show):
    user, repo = c.get("github_user", "rabmeireliyahu"), c.get("github_repo", show)
    for url in (f"https://raw.githubusercontent.com/{user}/{repo}/main/feed.xml",
                f"https://raw.githubusercontent.com/{user}/{repo}/master/feed.xml",
                f"https://{user}.github.io/{repo}/feed.xml"):
        try:
            req = urllib.request.Request(url + "?x=" + str(int(time.time())), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                t = r.read().decode("utf-8", "replace")
            if "<item>" in t:
                return t
        except Exception:
            continue
    return None


def frenado(d, c):
    bot = d / "podcast_bot.py"
    try:
        stub = bot.exists() and "PAUSADO por instalar_otzar.py" in bot.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stub = False
    return stub or (d / "podcast_bot.py.pausado").exists()


def bajo_base(p):
    try:
        Path(p).resolve().relative_to(BASE.resolve())
        return True
    except Exception:
        return False


def candidatos(carpeta):
    """audios de la carpeta (sin subcarpetas), menos los recientes y los 3 más nuevos."""
    try:
        fs = [f for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() in AUDIO]
    except OSError:
        return []
    fs.sort(key=lambda f: f.stat().st_mtime)
    fs = fs[:-NUEVOS_QUE_QUEDAN] if len(fs) > NUEVOS_QUE_QUEDAN else []
    limite = time.time() - DIAS_RECIENTES * 86400
    return [f for f in fs if f.stat().st_mtime < limite]


def vaciar_papelera():
    if not PAPELERA.is_dir():
        return
    limite = time.time() - DIAS_PAPELERA * 86400
    for d in PAPELERA.iterdir():
        try:
            if d.is_dir() and time.mktime(time.strptime(d.name[:10], "%Y-%m-%d")) < limite:
                shutil.rmtree(d, ignore_errors=True)
                decir(f"papelera: {d.name} tenía más de {DIAS_PAPELERA} días, borrada")
        except (ValueError, OSError):
            continue


def limpiar(si, auto):
    decir("=== Limpieza de audios ya a salvo en archive.org " + ("(APARTANDO)" if si else "(solo la lista, no se borra nada)") + " ===")
    lista, total_n, total_b = [], 0, 0
    destino_dia = PAPELERA / time.strftime("%Y-%m-%d_%H%M")
    for d in sorted(BASE.iterdir()) if BASE.is_dir() else []:
        if not d.is_dir() or d.name in ("jabura", "_papelera") or not (d / "config.json").exists():
            continue
        c = leer_json(d / "config.json")
        if not c.get("archive_id"):
            continue
        carpetas_mp3 = [x for x in (d / "episodios", d / "convertidos") if x.is_dir()]
        wa = Path(c["carpeta_whatsapp"]) if c.get("carpeta_whatsapp") else d / "audios_whatsapp"
        wa = wa if (wa.is_dir() and bajo_base(wa)) else None
        cand_mp3 = [f for x in carpetas_mp3 for f in candidatos(x)]
        cand_wa = candidatos(wa) if wa else []
        if not (cand_mp3 or cand_wa):
            continue
        arc = en_archive_md5(c["archive_id"])
        if arc is None:
            decir(f"{d.name}: archive.org no contestó; no toco nada")
            continue
        parado = frenado(d, c)
        feed = None if parado else leer_feed(c, d.name)
        if not parado and feed is None:
            decir(f"{d.name}: no pude leer su feed; no toco nada")
            continue
        procesados = set()
        pw = d / "procesados_whatsapp.txt"
        if pw.exists():
            procesados = set(pw.read_text(encoding="utf-8", errors="replace").splitlines())
        salen = []
        for f in cand_mp3:
            regs = arc.get(f.name.lower()) or []
            tam = f.stat().st_size
            if not any(t == tam for t, _ in regs):
                continue
            if not parado and html.escape(f.name, quote=False) not in feed and urllib.parse.quote(f.name) not in feed:
                continue
            if not any(m and m == md5_de(f) for t, m in regs if t == tam):
                continue
            salen.append(f)
        for f in cand_wa:
            if f.name not in procesados:
                continue
            mp3 = re.sub(r'[<>:"/\\|?*]', "", f.stem).strip()[:120] + ".mp3"
            if not arc.get(mp3.lower()):
                continue
            if f.suffix.lower() == ".mp3" and not any(t == f.stat().st_size for t, _ in arc[mp3.lower()]):
                continue
            salen.append(f)
        if not salen:
            continue
        b = sum(f.stat().st_size for f in salen)
        total_n += len(salen)
        total_b += b
        decir(f"{d.name:<20}{len(salen):>6} audios  {mb(b):>9}" + ("   (show frenado)" if parado else ""))
        lista += [f"{d.name}\t{f}" for f in salen]
        if si:
            if not parado and not c.get("solo_agregar"):
                shutil.copy2(d / "config.json", d / ("config.json.bak_" + time.strftime("%Y%m%d%H%M%S")))
                c["solo_agregar"] = True
                (d / "config.json").write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                decir(f"   {d.name}: puesto solo_agregar (el feed ya no se rearma con la carpeta)")
            for f in salen:
                dest = destino_dia / d.name / f.parent.name / f.name
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(dest))
                except OSError as ex:
                    decir(f"   no pude apartar {f.name}: {ex}")
    decir("")
    decir(f"TOTAL: {total_n} audios, {mb(total_b)} " + ("apartados a " + str(destino_dia) if si else "se pueden quitar"))
    try:
        (BASE / "limpieza_lista.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    except OSError:
        pass
    if si:
        vaciar_papelera()
        try:
            (BASE / "limpieza_auto.json").write_text(json.dumps({"desde": time.strftime("%Y-%m-%d"), "ultima": time.time()}), encoding="utf-8")
        except OSError:
            pass
        if not auto:
            decir(f"Quedan {DIAS_PAPELERA} días en {PAPELERA} por si acaso; después se borran solos.")
            decir("Desde ahora mantenimiento.py lo hace solo una vez al día.")
    elif total_n:
        decir("Para apartarlos: python espacio.py limpiar --si")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "limpiar":
        return limpiar("--si" in sys.argv, "--auto" in sys.argv)
    decir("=== Espacio de los shiurim en la PC (no se borra nada) ===")
    try:
        du = shutil.disk_usage("C:\\")
        decir(f"Disco C: libres {mb(du.free)} de {mb(du.total)}")
    except Exception:
        pass
    decir("")
    decir(f"{'show':<20}{'audios':>7}{'pesan':>10}{'en archive':>12}{'se podrían borrar':>20}")
    total, total_libre, bots = 0, 0, {}
    for d in sorted(BASE.iterdir()) if BASE.is_dir() else []:
        if not d.is_dir():
            continue
        c = leer_json(d / "config.json")
        if d.name == "jabura":
            continue                      # la jabura vive en el Drive compartido de Saúl: no se toca
        bot = d / "podcast_bot.py"
        if bot.exists():
            h = hashlib.sha256(bot.read_bytes()).hexdigest()[:10]
            bots.setdefault(h, {"ruta": bot, "shows": []})["shows"].append(d.name)
        archivos = []
        for carpeta in carpetas_de(d, c):
            for f in carpeta.rglob("*"):
                if f.is_file() and f.suffix.lower() in AUDIO:
                    archivos.append(f)
        if not archivos:
            continue
        peso = sum(f.stat().st_size for f in archivos)
        arc = en_archive(c.get("archive_id"))
        if arc is None:
            seguros, txt = [], "no abrió"
        else:
            seguros = [f for f in archivos if arc.get(f.name.lower()) == f.stat().st_size]
            txt = str(len(seguros))
        libre = sum(f.stat().st_size for f in seguros)
        total += peso
        total_libre += libre
        decir(f"{d.name:<20}{len(archivos):>7}{mb(peso):>10}{txt:>12}{mb(libre):>20}")
    decir("")
    decir(f"TOTAL en la PC: {mb(total)} · ya a salvo en archive.org (mismo tamaño): {mb(total_libre)}")
    for extra in (ROBOT, BASE / "jabura"):
        if extra.is_dir():
            decir(f"{extra}: {mb(peso_carpeta(extra))}")
    decir("El Drive de la jabura (G:) es del grupo de Saúl: NO se borra (se borraría para todos).")

    tok_p = BASE / "jabura" / "github_token.txt"
    if not tok_p.exists():
        decir("\n(no está jabura\\github_token.txt: no pude mandar los bots para revisarlos)")
    else:
        tok = tok_p.read_text(encoding="utf-8").strip()
        decir("")
        lista = {}
        for h, b in bots.items():
            texto = b["ruta"].read_bytes()
            if LLAVES.search(texto.decode("utf-8", "replace")):
                decir(f"podcast_bot {h} ({', '.join(b['shows'])}): lleva algo que parece una llave; NO lo mando")
                continue
            try:
                subir_al_repo(tok, f"tools/otzar/bots/podcast_bot_{h}.py", texto, f"podcast_bot {h} para revisar ({', '.join(b['shows'])})")
                lista[h] = b["shows"]
                decir(f"podcast_bot {h} mandado ({', '.join(b['shows'])})")
            except Exception as ex:
                decir(f"podcast_bot {h}: no pude mandarlo ({ex})")
        try:
            rep = "\n".join(lineas) + "\n\nbots: " + json.dumps(lista, ensure_ascii=False) + "\n"
            subir_al_repo(tok, "tools/otzar/bots/espacio_reporte.txt", rep.encode("utf-8"), "reporte de espacio")
            decir("Reporte mandado. Avísale a Claude: «ya corrí espacio.py».")
        except Exception as ex:
            decir(f"no pude mandar el reporte ({ex})")
    try:
        (BASE / "espacio_reporte.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
