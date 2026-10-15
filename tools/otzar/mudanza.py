#!/usr/bin/env python3
"""MUDANZA de Otzar a otra PC (la HP que se queda prendida siempre).

  En la PC de ahora (con el robot y el piloto CERRADOS):
      python mudanza.py empacar E:\\MUDANZA_OTZAR
      (E: = una memoria USB o disco externo con espacio; también sirve una carpeta de red)
  En la HP:
      python mudanza.py desempacar E:\\MUDANZA_OTZAR
  En cualquiera, para ver si está todo:
      python mudanza.py revisar

Empacar COPIA (no mueve ni borra nada): C:\\robotwhats (robot + sesión de WhatsApp) y
C:\\OTZAR (shows, configuraciones, llaves) + una lista de lo que hay instalado.
Desempacar instala lo que falte (Node, ffmpeg, paquetes de Python), pone las carpetas en
el mismo lugar (si ya había algo, lo renombra .antes_<fecha>, no lo borra), hace que el
robot y el piloto se abran solos al prender la PC, y deja la energía para que nunca se
suspenda ni se caliente de más. Las llaves viajan en la USB: bórrala al terminar.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROBOT = Path(r"C:\robotwhats")
BASE = Path(r"C:\OTZAR")
NO_COPIAR = ("audio_temp", "__pycache__", "*.bak_*", "robot.lock", "piloto.lock", "comando.txt")

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def ok(m):
    print("   ✔ " + m, flush=True)


def mal(m):
    print("   ✖ " + m, flush=True)


def paso(m):
    print("\n== " + m, flush=True)


def salida(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=isinstance(cmd, str))
        return (r.stdout or r.stderr or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def tamano(p):
    total = 0
    for raiz, _d, archivos in os.walk(p):
        for f in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, f))
            except OSError:
                pass
    return total


def leer_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def rutas_fuera():
    """Carpetas que el robot/los shows usan FUERA de C:\\OTZAR (el Drive de la jabura, el correo...)."""
    out = set()
    cfg = leer_json(ROBOT / "config_whatsapp.json")
    for d in (cfg.get("escuchar") or {}).values():
        if isinstance(d, dict) and d.get("carpetaDestino"):
            out.add(d["carpetaDestino"])
    for e in cfg.get("escuchar_directo") or []:
        if isinstance(e, dict) and e.get("carpetaDestino"):
            out.add(e["carpetaDestino"])
    if BASE.is_dir():
        for show in BASE.iterdir():
            c = leer_json(show / "config.json") if show.is_dir() else {}
            for k in ("correo_carpeta", "carpeta_whatsapp"):
                if c.get(k):
                    out.add(c[k])
    return sorted(x for x in out if not str(x).lower().startswith((str(BASE).lower(), str(ROBOT).lower())))


def robot_abierto():
    for f in (ROBOT / "robot.lock", BASE / "piloto.lock"):
        try:
            if time.time() - f.stat().st_mtime < 120:
                return f.name
        except Exception:
            pass
    return ""


def inventario():
    pip = salida([sys.executable, "-m", "pip", "freeze"])
    return {
        "fecha": dt.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "node": salida("node -v"),
        "ffmpeg": bool(salida("ffmpeg -version")),
        "yt_dlp": salida([sys.executable, "-m", "yt_dlp", "--version"]) or salida("yt-dlp --version"),
        "pip": [x for x in pip.splitlines() if x and not x.startswith(("-e ", "#"))],
        "rutas_fuera": rutas_fuera(),
        "bats_robot": sorted(p.name for p in ROBOT.glob("*.bat")) if ROBOT.is_dir() else [],
    }


# ── empacar ──────────────────────────────────────────────────────────────────
def empacar(destino):
    destino = Path(destino)
    paso("1. Revisar que el robot y el piloto estén CERRADOS")
    abierto = robot_abierto()
    if abierto:
        mal(f"el robot o el piloto siguen abiertos ({abierto} reciente). Cierra sus ventanas, espera 2 minutos y vuelve a correr.")
        return 1
    ok("cerrados")
    paso("2. Cuánto pesa")
    pesos = {p: tamano(p) for p in (ROBOT, BASE) if p.is_dir()}
    for p, b in pesos.items():
        ok(f"{p}: {b / 1e9:.1f} GB")
    destino.mkdir(parents=True, exist_ok=True)
    libre = shutil.disk_usage(str(destino)).free
    if libre < sum(pesos.values()) * 1.05:
        mal(f"en {destino} solo hay {libre / 1e9:.1f} GB libres; hace falta {sum(pesos.values()) / 1e9:.1f} GB")
        return 1
    ok(f"en {destino} hay {libre / 1e9:.1f} GB libres")
    paso("3. Copiar (no se mueve ni se borra nada de esta PC)")
    for p in pesos:
        print(f"   copiando {p} … (puede tardar)", flush=True)
        shutil.copytree(p, destino / p.name, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*NO_COPIAR))
        ok(f"{p} copiado")
    paso("4. Lista de lo instalado en esta PC")
    inv = inventario()
    (destino / "inventario.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    ok(f"Python {inv['python']} · Node {inv['node'] or '?'} · ffmpeg {'sí' if inv['ffmpeg'] else 'no'} · yt-dlp {inv['yt_dlp'] or '?'} · {len(inv['pip'])} paquetes")
    for r in inv["rutas_fuera"]:
        print(f"   · usa también: {r}")
    print("\nLISTO. Lleva la USB a la HP y ahí corre:  python mudanza.py desempacar " + str(destino))
    print("NO vuelvas a abrir el robot en esta PC: si quedan los dos abiertos se pelean la sesión de WhatsApp.")
    return 0


# ── desempacar ───────────────────────────────────────────────────────────────
def winget(ident, nombre):
    if not salida("winget --version"):
        mal(f"falta {nombre} y no hay winget: instálalo a mano")
        return False
    print(f"   instalando {nombre} con winget …", flush=True)
    r = subprocess.run(["winget", "install", "-e", "--id", ident, "--accept-source-agreements",
                        "--accept-package-agreements", "--silent"])
    if r.returncode == 0:
        ok(f"{nombre} instalado (cierra y abre CMD para que se vea)")
        return True
    mal(f"no pude instalar {nombre} (código {r.returncode})")
    return False


def poner_en_inicio():
    inicio = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    if not inicio.is_dir():
        mal(f"no encuentro la carpeta de Inicio ({inicio})")
        return
    bat = next((ROBOT / n for n in ("ROBOT_WHATSAPP.bat", "ROBOT.bat", "INICIAR_ROBOT.bat") if (ROBOT / n).exists()), None)
    bat = bat or next(iter(sorted(ROBOT.glob("ROBOT*.bat"))), None)
    lineas = ["@echo off", "rem Otzar: al prender la PC abre el robot y el piloto (lo puso mudanza.py)",
              "timeout /t 60 /nobreak >nul"]
    if bat:
        lineas.append(f'start "ROBOT" /d "{ROBOT}" "{bat}"')
    else:
        lineas.append(f'start "ROBOT" /d "{ROBOT}" cmd /k node robot_whatsapp.js')
    lineas += ["timeout /t 90 /nobreak >nul", f'start "PILOTO" /d "{ROBOT}" "{ROBOT / "PILOTO.bat"}"']
    (inicio / "OTZAR_inicio.cmd").write_text("\r\n".join(lineas) + "\r\n", encoding="utf-8")
    ok("al prender la PC se abren solos el robot (al minuto) y el piloto (a los 2 min y medio)")


def energia():
    """Nunca suspender ni hibernar con corriente, tapa cerrada = nada, pantalla se apaga a los 10 min,
    procesador al 85% como máximo (calienta mucho menos y para esto sobra)."""
    cmds = [
        "powercfg /change standby-timeout-ac 0",
        "powercfg /change hibernate-timeout-ac 0",
        "powercfg /change monitor-timeout-ac 10",
        "powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0",
        "powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 85",
        "powercfg /setactive SCHEME_CURRENT",
    ]
    fallos = [c for c in cmds if subprocess.run(c, shell=True, capture_output=True).returncode != 0]
    if fallos:
        mal("no se pudo: " + " | ".join(fallos) + "  (prueba abrir CMD como administrador)")
    else:
        ok("energía: nunca se suspende con corriente, la tapa cerrada no la apaga, procesador al 85% (menos calor)")


def desempacar(origen):
    origen = Path(origen)
    inv = leer_json(origen / "inventario.json")
    if not inv:
        mal(f"no encuentro {origen / 'inventario.json'}: ¿es la carpeta que dejó 'empacar'?")
        return 1
    paso(f"1. Lo que tenía la otra PC ({inv.get('fecha')})")
    print(f"   Python {inv.get('python')} · Node {inv.get('node')} · ffmpeg {'sí' if inv.get('ffmpeg') else 'no'} · yt-dlp {inv.get('yt_dlp')}")
    if robot_abierto():
        mal("aquí hay un robot o piloto abierto; ciérralo primero")
        return 1
    paso("2. Programas")
    if sys.version_info[:2] != tuple(int(x) for x in inv.get("python", "3.0").split(".")[:2]):
        print(f"   · aquí hay Python {sys.version.split()[0]} (allá {inv.get('python')}); sigo, pero si algo falla instala la misma versión")
    if salida("node -v"):
        ok(f"Node {salida('node -v')}")
    else:
        winget("OpenJS.NodeJS.LTS", "Node.js")
    if salida("ffmpeg -version"):
        ok("ffmpeg")
    elif inv.get("ffmpeg"):
        winget("Gyan.FFmpeg", "ffmpeg")
    paquetes = inv.get("pip") or []
    if paquetes:
        req = Path(os.environ.get("TEMP", ".")) / "otzar_requisitos.txt"
        req.write_text("\n".join(paquetes), encoding="utf-8")
        print(f"   instalando {len(paquetes)} paquetes de Python …", flush=True)
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
        if r.returncode != 0:      # alguno con versión que ya no existe: sin versión, uno por uno
            for p in paquetes:
                nombre = p.split("==")[0].split(" @ ")[0]
                subprocess.run([sys.executable, "-m", "pip", "install", "-q", nombre])
        ok("paquetes de Python")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"])
    ok("yt-dlp al día")
    paso("3. Carpetas (C:\\robotwhats y C:\\OTZAR)")
    sello = time.strftime("%Y%m%d%H%M%S")
    for destino in (ROBOT, BASE):
        src = origen / destino.name
        if not src.is_dir():
            mal(f"no está {src}")
            continue
        if destino.exists() and any(destino.iterdir()):
            destino.rename(destino.with_name(destino.name + ".antes_" + sello))
            ok(f"lo que ya había en {destino} quedó en {destino.name}.antes_{sello}")
        print(f"   copiando {destino} … (puede tardar)", flush=True)
        shutil.copytree(src, destino, dirs_exist_ok=True)
        ok(f"{destino} listo")
    paso("4. Al prender la PC, y energía")
    poner_en_inicio()
    energia()
    paso("5. Revisión")
    revisar()
    print("""
FALTA (a mano, una sola vez):
  1. Google Drive para escritorio con la MISMA cuenta (para la carpeta de la jabura). Revisión: arriba
     tienen que salir con ✔ las carpetas de "usa también".
  2. Cierra el robot de la PC vieja (y que no se vuelva a abrir allá) y abre aquí ROBOT_WHATSAPP.bat.
     Si pide QR: WhatsApp del celular del robot → Dispositivos vinculados → Vincular.
  3. Desde TU celular, en chat privado con el robot, manda:  !reporte
  4. Borra la carpeta de la USB (lleva las llaves).
""")
    return 0


# ── revisar ──────────────────────────────────────────────────────────────────
def revisar():
    paso("Revisión")
    for nombre, cmd in (("Node", "node -v"), ("ffmpeg", "ffmpeg -version"), ("yt-dlp", [sys.executable, "-m", "yt_dlp", "--version"])):
        v = salida(cmd)
        (ok if v else mal)(f"{nombre}: {v.splitlines()[0] if v else 'NO está'}")
    for p in (ROBOT / "robot_whatsapp.js", ROBOT / "config_whatsapp.json", ROBOT / "sesion_baileys",
              ROBOT / "PILOTO.bat", BASE / "jabura" / "piloto.py", BASE / "jabura" / "mantenimiento.py"):
        (ok if p.exists() else mal)(f"{p}")
    for r in rutas_fuera():
        (ok if Path(r).exists() else mal)(f"usa también: {r}" + ("" if Path(r).exists() else "  ← falta (¿Google Drive?)"))
    inicio = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "OTZAR_inicio.cmd"
    (ok if inicio.exists() else mal)("se abre solo al prender la PC" if inicio.exists() else "NO se abre solo al prender (corre desempacar)")
    try:
        libre = shutil.disk_usage(str(BASE if BASE.exists() else Path.home())).free / 1e9
        (ok if libre >= 10 else mal)(f"disco: {libre:.0f} GB libres")
    except Exception:
        pass
    abierto = robot_abierto()
    print(f"   · robot/piloto abiertos ahora: {'sí (' + abierto + ')' if abierto else 'no'}")
    return 0


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("empacar", "desempacar", "revisar"):
        print(__doc__)
        return 1
    if a[0] == "revisar":
        return revisar()
    if len(a) < 2:
        print(f"falta la carpeta: python mudanza.py {a[0]} E:\\MUDANZA_OTZAR")
        return 1
    return empacar(a[1]) if a[0] == "empacar" else desempacar(a[1])


if __name__ == "__main__":
    sys.exit(main())
