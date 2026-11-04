#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drive para Sammy (nov/2026): todos los shiurim de todos los podcasts (menos Daf Yomi y Shawat)
acomodados por tema, al estilo del Drive de Rab Shweke:

    1. Parashá/<libro>/<NN parashá>       4. Musar y Emuná/<Rab>
    2. Jaguim/<fiesta>                     5. Tanaj/<libro o serie>
    3. Halajá/<Óraj Jaim|Yoré Deá|…>/<tema>  6. Shmirat HaLashon y Ahavat Jésed/<Rab>

    python drive_sammy.py                       (destino: "Mi unidad\\Shiurim Otzar HaTorah" de Google Drive)
    python drive_sammy.py --destino=D:\\Carpeta  (otra carpeta)
    python drive_sammy.py --revisar             (solo dice cuánto falta, no baja nada)

El plan (qué archivo va a qué carpeta) es drive_sammy_plan.json.gz, armado en el repo con los
títulos de los feeds. Si el mp3 ya está en C:\\OTZAR\\<show> con el mismo tamaño se copia de ahí;
si no, se baja de archive.org. Lo que ya está en el destino no se vuelve a bajar: se puede
cerrar y volver a abrir cuando sea (y sigue solo al prender la PC hasta terminar, por el
OTZAR_drive_sammy.cmd de la carpeta Inicio). Nada en Shabat ni Yom Tov. Log en
C:\\OTZAR\\drive_sammy.log; al terminar deja DRIVE_SAMMY_TERMINADO.txt y se quita de Inicio.
Nunca borra ni mueve nada de C:\\OTZAR: solo lee y copia.
"""
import datetime as dt
import gzip
import importlib.util
import json
import os
import shutil
import string
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(r"C:\OTZAR")
for a in sys.argv[1:]:
    if a.startswith("--base="):
        BASE = Path(a.split("=", 1)[1])
AQUI = Path(__file__).resolve().parent
PLAN = AQUI / "drive_sammy_plan.json.gz"
LOG = BASE / "drive_sammy.log"
FIN = BASE / "DRIVE_SAMMY_TERMINADO.txt"
LOCK = BASE / "drive_sammy.lock"
TMP = BASE / "_drive_sammy_tmp"
INICIO = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
CARPETA = "Shiurim Otzar HaTorah"
REVISAR = "--revisar" in sys.argv
MIN_LIBRE_C = 25e9          # Drive para PC guarda en C: lo que aún no sube: si C: baja de esto, espera
MIN_LIBRE_DRIVE = 2e9


def log(m):
    linea = f"[{dt.datetime.now():%d/%m %H:%M}] {m}"
    print(linea, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def gb(n):
    return f"{n / 1e9:.1f} GB"


def hallar_destino():
    for a in sys.argv[1:]:
        if a.startswith("--destino="):
            return Path(a.split("=", 1)[1].strip('"'))
    candidatos = []
    for letra in string.ascii_uppercase:
        for mi in ("Mi unidad", "My Drive"):
            p = Path(f"{letra}:\\") / mi
            try:
                if p.is_dir():
                    candidatos.append(p)
            except OSError:
                pass
    home = Path.home()
    for mi in ("Mi unidad", "My Drive", "Google Drive"):
        if (home / mi).is_dir():
            candidatos.append(home / mi)
    if not candidatos:
        return None
    if len(candidatos) > 1:
        log("hay más de un Google Drive: " + " · ".join(str(c) for c in candidatos) + f" — uso {candidatos[0]}"
            " (para otro: --destino=RUTA)")
    return candidatos[0] / CARPETA


def largo(p):
    """Rutas largas en Windows (más de 260 letras)."""
    s = str(p)
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + os.path.abspath(s)
    return s


def bloqueo_piloto():
    p = BASE / "jabura" / "piloto.py"
    if p.exists():
        argv = sys.argv
        try:
            sys.argv = [str(p)]
            spec = importlib.util.spec_from_file_location("piloto_otzar", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m.bloqueo
        except Exception as e:                       # noqa: BLE001
            log(f"no pude usar el candado del piloto ({e}); uso uno sencillo")
        finally:
            sys.argv = argv

    def sencillo(ahora):
        if ahora.weekday() == 4 and ahora.hour >= 16:
            return "Erev Shabat"
        if ahora.weekday() == 5 and ahora.hour < 21:
            return "Shabat"
        return None
    return sencillo


def indice_local(shows):
    """(nombre en minúsculas, tamaño) → ruta, de los mp3 que ya están en C:\\OTZAR\\<show>."""
    idx = {}
    for show in shows:
        d = BASE / show
        if not d.is_dir():
            continue
        for raiz, carpetas, archivos in os.walk(d):
            carpetas[:] = [c for c in carpetas if not c.startswith("_")]
            for a in archivos:
                if a.lower().endswith((".mp3", ".m4a")):
                    p = Path(raiz) / a
                    try:
                        idx[(a.lower(), p.stat().st_size)] = p
                    except OSError:
                        pass
    return idx


def ya_esta(dest, b):
    try:
        t = os.path.getsize(largo(dest))
    except OSError:
        return False
    return t > 0 and (not b or t == b)


def bajar(url, tmp):
    req = urllib.request.Request(url, headers={"User-Agent": "otzar-drive/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(largo(tmp), "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)


def poner_fecha(dest, f):
    try:
        t = dt.datetime.strptime(f[:10], "%Y-%m-%d").timestamp() + 12 * 3600
        os.utime(largo(dest), (t, t))
    except Exception:                                # noqa: BLE001
        pass


def terminar(destino, n):
    try:
        (INICIO / "OTZAR_drive_sammy.cmd").unlink()
    except OSError:
        pass
    FIN.write_text(f"Drive para Sammy terminado {dt.datetime.now():%d/%m/%Y %H:%M}: {n} shiurim en {destino}\n",
                   encoding="utf-8")
    log(f"=== TERMINADO: {n} shiurim en {destino}. Ya no se abre al prender la PC. "
        "Comparte esa carpeta con Sammy desde drive.google.com (clic derecho → Compartir). ===")


def _pid_vivo(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:                                             # en Windows os.kill MATA: se pregunta a tasklist
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=20)
        return str(pid) in (r.stdout or "")
    except Exception:                                # noqa: BLE001
        return True


def otra_ventana():
    try:
        if not (LOCK.exists() and time.time() - LOCK.stat().st_mtime < 5 * 60):
            return False
        pid = int(LOCK.read_text(encoding="utf-8").strip() or 0)
        return pid != os.getpid() and _pid_vivo(pid)
    except (OSError, ValueError):
        return False


def refrescar_lock():
    while True:
        try:
            LOCK.write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            pass
        time.sleep(60)


def pendientes(plan, destino):
    return [x for x in plan if not ya_esta(destino.joinpath(*x["r"], x["n"]), x["b"])]


def una_vuelta(falta, destino, bloqueo, idx):
    """Baja/copia lo que falta. Devuelve (errores, se_lleno)."""
    falta_b = sum(x["b"] or 0 for x in falta)
    hechos = copiados = errores = 0
    inicio = time.time()
    bytes_hechos = 0
    for i, x in enumerate(falta, 1):
        while True:
            b = bloqueo(dt.datetime.now())
            if not b:
                break
            log(f"{b}: no se baja nada; sigo después")
            time.sleep(15 * 60)
        while shutil.disk_usage("C:\\" if os.name == "nt" else "/").free < MIN_LIBRE_C:
            log(f"C: con menos de {gb(MIN_LIBRE_C)} libres (Drive aún está subiendo): espero 20 min")
            time.sleep(20 * 60)
        if shutil.disk_usage(destino).free < MIN_LIBRE_DRIVE + (x["b"] or 0):
            log("el Drive se llenó: hace falta más espacio en la cuenta de Google. Paro aquí; "
                "con más espacio se vuelve a abrir (o al prender la PC) y sigue donde se quedó.")
            return errores, True
        dest = destino.joinpath(*x["r"], x["n"])
        tmp = TMP / "bajando.part"                  # se baja en C: y ya completo pasa al Drive (no sube pedazos)
        try:
            os.makedirs(largo(dest.parent), exist_ok=True)
            nombre = urllib.parse.unquote(x["u"].split("?")[0].rsplit("/", 1)[-1]).lower()
            local = idx.get((nombre, x["b"])) if x["b"] else None
            if local:
                tmp = local
                copiados += 1
            else:
                TMP.mkdir(parents=True, exist_ok=True)
                bajar(x["u"], tmp)
            real = os.path.getsize(largo(tmp))
            if real == 0 or (x["b"] and real < 0.9 * x["b"]):   # el tamaño del feed de anchor no siempre es exacto
                raise OSError(f"llegó incompleto ({real} de {x['b']} bytes)")
            shutil.copyfile(largo(tmp), largo(dest))
            if tmp != local:
                os.remove(largo(tmp))
            poner_fecha(dest, x.get("f") or "")
            hechos += 1
            bytes_hechos += x["b"] or real
        except Exception as e:                       # noqa: BLE001
            errores += 1
            log(f"ERROR {'/'.join(x['r'])}/{x['n'][:60]}: {e}")
            for p in (TMP / "bajando.part", dest):     # nada a medias (dest solo si quedó chico)
                try:
                    if p == TMP / "bajando.part" or not ya_esta(p, x["b"]):
                        os.remove(largo(p))
                except OSError:
                    pass
            time.sleep(10)
        if i % 25 == 0 or i == len(falta):
            seg = max(time.time() - inicio, 1)
            vel = bytes_hechos / seg
            resto = (falta_b - bytes_hechos) / vel / 3600 if vel else 0
            log(f"{i}/{len(falta)} · {hechos} listos ({copiados} copiados de C:\\OTZAR) · {errores} con error · "
                f"{gb(bytes_hechos)} · faltan unas {resto:.0f} h")
    return errores, False


def main():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                            # noqa: BLE001
            pass
    if not PLAN.exists():
        print(f"no encuentro {PLAN}")
        return
    plan = json.loads(gzip.decompress(PLAN.read_bytes()).decode("utf-8"))
    destino = hallar_destino()
    if destino is None:
        log("no encontré Google Drive en esta PC (\"Mi unidad\"). Instala Google Drive para PC con la cuenta "
            "donde va a quedar, o di dónde: --destino=RUTA")
        return
    destino.mkdir(parents=True, exist_ok=True)
    arbol = {}
    for x in plan:
        for i in range(1, min(len(x["r"]), 3) + 1):
            arbol[tuple(x["r"][:i])] = arbol.get(tuple(x["r"][:i]), 0) + 1
    try:
        (destino / "ÍNDICE.txt").write_text(
            "Shiurim de Otzar HaTorah, por tema (el número es cuántos shiurim hay en la carpeta)\n\n"
            + "\n".join("    " * (len(k) - 1) + f"{k[-1]}  ({n})" for k, n in sorted(arbol.items())) + "\n",
            encoding="utf-8")
    except OSError:
        pass
    total_b = sum(x["b"] or 0 for x in plan)
    falta = pendientes(plan, destino)
    falta_b = sum(x["b"] or 0 for x in falta)
    libre = shutil.disk_usage(destino).free
    log(f"=== DRIVE PARA SAMMY → {destino}: {len(plan)} shiurim ({gb(total_b)}); faltan {len(falta)} "
        f"({gb(falta_b)}); libre en ese Drive: {gb(libre)} ===")
    if falta_b > libre:
        log(f"OJO: el Drive tiene {gb(libre)} libres y faltan {gb(falta_b)}. Hace falta un plan de Google "
            "con más espacio (200 GB o más); mientras, bajo lo que quepa.")
    if REVISAR:
        por = {}
        for x in falta:
            por[x["r"][0]] = por.get(x["r"][0], 0) + 1
        for k in sorted(por):
            print(f"   {k}: faltan {por[k]}")
        return
    if otra_ventana():
        print("ya hay otra ventana pasando los shiurim al Drive; esta se cierra")
        return
    threading.Thread(target=refrescar_lock, daemon=True).start()
    bloqueo = bloqueo_piloto()
    log("buscando los que ya están en C:\\OTZAR para copiarlos en vez de bajarlos…")
    idx = indice_local({x["show"] for x in plan})
    for vuelta in range(1, 4):
        if not falta:
            break
        errores, lleno = una_vuelta(falta, destino, bloqueo, idx)
        if lleno:
            return
        if not errores:
            break
        falta = pendientes(plan, destino)
        if vuelta < 3:
            log(f"vuelta {vuelta} con {errores} error(es); en 30 min reintento esos {len(falta)}")
            time.sleep(30 * 60)
    falta = pendientes(plan, destino)
    if falta:
        (BASE / "drive_sammy_faltan.txt").write_text(
            "\n".join(f"{'/'.join(x['r'])}/{x['n']}  ←  {x['u']}" for x in falta) + "\n", encoding="utf-8")
        log(f"{len(falta)} no se pudieron bajar en 3 vueltas (lista en {BASE / 'drive_sammy_faltan.txt'})")
    terminar(destino, len(plan) - len(falta))


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            if LOCK.exists() and LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK.unlink()
        except OSError:
            pass
