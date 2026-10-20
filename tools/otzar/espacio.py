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
"""
import base64
import hashlib
import json
import re
import shutil
import sys
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


def main():
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
