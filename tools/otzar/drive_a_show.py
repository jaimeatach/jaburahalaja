#!/usr/bin/env python3
"""Sube a un show los shiurim VIEJOS que el Rab mandó en un Google Drive, abajo de todo.

    python drive_a_show.py turquie --ver          dice qué encontró, en qué orden y con qué título
    python drive_a_show.py turquie                los pone en el show y los publica
    python drive_a_show.py turquie "C:\\ruta"      de esa carpeta o zip (si no, el último
                                                  drive-download-*.zip de Descargas, con sus partes)

En Drive: abrir la carpeta → los tres puntos / "Descargar" → baja uno o varios zip a Descargas.
Orden: por el número del nombre si casi todos lo tienen; si no, por la fecha del archivo.
Fecha en el feed: la del archivo si es real; si no, uno por día terminando hace 30 días.
Así quedan ABAJO de lo que llega por WhatsApp (que toma la fecha de hoy) y no se anuncian
como nuevos. El título es el nombre del archivo limpio, con "<Rab> ·" al frente como los del
robot. Videos y otros formatos se pasan a audio con ffmpeg. Nunca borra nada del Drive ni de
Descargas; lo que ya está en la carpeta del show no se repite.
"""
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(r"C:\OTZAR")
ROBOT = Path(r"C:\robotwhats")
AUDIO = {".ogg", ".m4a", ".mp3", ".opus", ".wav"}
CONVERTIR = {".mp4", ".mov", ".3gp", ".aac", ".wma", ".flac", ".mpeg", ".mpg", ".webm", ".amr", ".mkv", ".avi", ".m4v"}
RABS = {"turquie": "Rab Beto Turquie"}
VER = "--ver" in sys.argv

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


def fuente(args):
    if args:
        return Path(args[0])
    desc = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads"
    zips = sorted(desc.glob("drive-download-*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        return None
    # Drive parte en varios zip con el mismo sello: drive-download-20261109T180000Z-1-001.zip
    sello = re.match(r"(drive-download-[^-]+)", zips[-1].name).group(1)
    return [z for z in zips if z.name.startswith(sello)]


def archivos(src, tmp):
    """[(ruta_local, nombre, mtime)] de todos los audios/videos."""
    out = []
    lista = src if isinstance(src, list) else [src]
    for s in lista:
        s = Path(s)
        if s.is_dir():
            for p in s.rglob("*"):
                if p.is_file() and p.suffix.lower() in AUDIO | CONVERTIR:
                    out.append((p, p.name, p.stat().st_mtime))
        elif s.suffix.lower() == ".zip":
            with zipfile.ZipFile(s) as z:
                for i in z.infolist():
                    nombre = Path(i.filename).name
                    if i.is_dir() or Path(nombre).suffix.lower() not in AUDIO | CONVERTIR:
                        continue
                    try:
                        mt = time.mktime(datetime(*i.date_time).timetuple())
                    except Exception:
                        mt = 0
                    destino = tmp / nombre
                    if not VER and not destino.exists():
                        tmp.mkdir(parents=True, exist_ok=True)
                        with z.open(i) as a, open(destino, "wb") as b:
                            b.write(a.read())
                    out.append((destino, nombre, mt))
    return out


def numero(nombre):
    t = Path(nombre).stem
    m = re.match(r"\s*(\d{1,4})(?!\d)", t) or re.search(r"(?<![\dA-Za-z])(\d{1,4})\s*$", t)
    if m and not re.search(r"\d{1,2}[-_.]\d{1,2}[-_.]\d{2,4}", t[:12]):
        return int(m.group(1))
    return None


def natural(nombre):
    """"avot 5, 20 (2)-21" → (5, 20, 2, 21): ordena perek, luego mishná, luego parte."""
    t = Path(nombre).stem.lower()
    return [int(x) for x in re.findall(r"\d+", t)] + [t]


def _mishna(txt):
    """'20 (2)-21' → 'Mishná 20 (2ª parte) y 21' · '7- 8' → 'Mishnayot 7-8' · '13' → 'Mishná 13'"""
    txt = re.sub(r"\s+", " ", txt).strip(" ,.-")
    txt = re.sub(r"\((\d)\)", lambda m: f"({m.group(1)}ª parte)", txt)
    partes = [x.strip() for x in re.split(r"\s*-\s*", txt) if x.strip()]
    if len(partes) == 2 and all(re.fullmatch(r"\d+", x) for x in partes):
        return f"Mishnayot {partes[0]}-{partes[1]}"
    if len(partes) == 2:
        return f"Mishná {partes[0]} y {partes[1]}"
    return f"Mishná {txt}"


def titulo(nombre, rab):
    m = re.match(r"(?i)\s*(pirk[eé]i?\s+)?avot\s*(\d+)\s*[,:.]\s*(.+)$", Path(nombre).stem)
    if m:
        t = f"Pirké Avot · Perek {m.group(2)} · {_mishna(m.group(3))}"
        return f"{rab} · {t}" if rab else t
    t = Path(nombre).stem
    t = re.sub(r"(?i)^(whatsapp (audio|ptt|video)|aud|ptt|audio|vid)[-_ ]?", "", t)
    t = re.sub(r"^\s*(\d{4}[-_.]\d{1,2}[-_.]\d{1,2}|\d{1,2}[-_.]\d{1,2}[-_.]\d{2,4})\s*[-_.]?\s*", "", t)  # fecha al frente
    t = re.sub(r"^\s*\d{1,4}\s*[-_.)]+\s*", "", t)          # "03 - tema" / "03_tema" / "3) tema"
    t = re.sub(r"[_]+", " ", t)
    t = re.sub(r"\s*[-–]\s*$", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -–·.")
    if not re.search(r"[A-Za-zÀ-ÿא-ת]{3,}", re.sub(r"(?i)\b(wa\d*|ptt|at|pm|am|a las)\b", "", t)):
        t = ""                                              # solo fecha/hora o "WA0001": sin título
    if rab and rab.split()[-1].lower() not in t.lower():
        t = f"{rab} · {t}" if t else f"Shiur · {rab}"
    return re.sub(r'[<>:"/\\|?*]', "", t)[:110].strip()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("Uso: python drive_a_show.py <show> [--ver] [carpeta o zip]")
        return 1
    show = args[0].lower()
    d = BASE / show
    c = leer_json(d / "config.json")
    if not c:
        print(f"✖ no existe {d / 'config.json'}: primero crea el show (--nuevo={show}).")
        return 1
    carpeta = Path(c.get("carpeta_whatsapp") or (d / "audios_whatsapp"))
    rab = RABS.get(show) or c.get("titulo", "")
    src = fuente(args[1:])
    if not src:
        print("✖ no encuentro el zip del Drive en Descargas (drive-download-….zip). Bájalo del Drive o dame la ruta.")
        return 1
    print("Fuente:", ", ".join(str(s) for s in (src if isinstance(src, list) else [src])))
    tmp = d / "_drive_tmp"
    lista = archivos(src, tmp)
    if not lista:
        print("✖ no hay audios ni videos ahí.")
        return 1
    # orden
    if sum(bool(re.search(r"\d", Path(n).stem)) for _, n, _ in lista) >= 0.8 * len(lista):
        lista.sort(key=lambda x: (natural(x[1]), x[2]))
        como = "por los números del nombre (perek, mishná, parte…)"
    else:
        lista.sort(key=lambda x: (x[2], x[1]))
        como = "por la fecha del archivo"
    # fechas: reales si son distintas y viejas; si no, una por día terminando hace 30 días
    ahora = time.time()
    mts = [m for _, _, m in lista]
    reales = all(0 < m < ahora - 86400 for m in mts) and len({int(m // 60) for m in mts}) == len(mts) \
        and mts == sorted(mts)
    if reales:
        fechas = mts
    else:
        fin = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=30)
        fechas = [(fin - timedelta(days=len(lista) - 1 - i)).timestamp() for i in range(len(lista))]
    # títulos únicos
    vistos, plan = {}, []
    for (ruta, nombre, _), f in zip(lista, fechas):
        t = titulo(nombre, rab)
        vistos[t] = vistos.get(t, 0) + 1
        if vistos[t] > 1:
            t = f"{t} ({vistos[t]})"
        plan.append((ruta, nombre, t, f))
    print(f"{len(plan)} shiurim, {como}; fechas {'del archivo' if reales else 'seguidas, hasta hace 30 días'}:\n")
    for i, (_, nombre, t, f) in enumerate(plan, 1):
        print(f"{i:3}. {datetime.fromtimestamp(f):%d/%m/%Y}  {t}    ← {nombre}")
    (d / "drive_plan.txt").write_text("\n".join(f"{datetime.fromtimestamp(f):%Y-%m-%d}\t{t}\t{n}" for _, n, t, f in plan),
                                      encoding="utf-8")
    if VER:
        print(f"\n(prueba: no se cambió nada; la lista quedó en {d / 'drive_plan.txt'})")
        return 0
    carpeta.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for ruta, nombre, t, f in plan:
        ext = ruta.suffix.lower()
        destino = carpeta / (t + (ext if ext in AUDIO else ".m4a"))
        if any((carpeta / (t + e)).exists() for e in AUDIO):
            print(f"   (ya estaba) {t}")
            continue
        if ext in AUDIO:
            destino.write_bytes(ruta.read_bytes())
        else:
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ruta), "-vn",
                                "-c:a", "aac", "-b:a", "96k", "-ac", "1", str(destino)])
            if r.returncode != 0 or not destino.exists():
                print(f"   ✖ no pude pasar a audio: {nombre}")
                continue
        os.utime(destino, (f, f))
        hechos += 1
    print(f"\n✔ {hechos} en {carpeta}. Publicando (puede tardar: sube cada uno a archive.org)…")
    r = subprocess.run([sys.executable, "podcast_bot.py"], cwd=str(d))
    if r.returncode == 0:
        print(f"✔ listo: https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}/feed.xml")
    else:
        print("✖ podcast_bot.py terminó con error; vuelve a correr este mismo comando (no repite).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
