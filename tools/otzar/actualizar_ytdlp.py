#!/usr/bin/env python3
"""Lo corre el piloto por orden a distancia (accion "script"), 23/11/2026: YouTube ya no le daba
formatos a la yt-dlp vieja de la HP ("Requested format is not available"). Actualiza yt-dlp (con
yt-dlp-ejs), le dice que use Node para el JavaScript de YouTube (config de yt-dlp del usuario) y
prueba bajar el audio de un video."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sal(cmd, t=600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=t, shell=isinstance(cmd, str))
    return (r.stdout + r.stderr).strip()


print("antes:", sal("yt-dlp --version"), "·", shutil.which("yt-dlp"))
print(sal([sys.executable, "-m", "pip", "install", "-U", "--no-warn-script-location", "yt-dlp[default]"], 900)[-3000:])
print("después:", sal("yt-dlp --version"), "·", shutil.which("yt-dlp"))
print("node:", sal("node -v"), "· deno:", shutil.which("deno"))
cfg = Path(os.environ.get("APPDATA", str(Path.home()))) / "yt-dlp" / "config.txt"
try:
    txt = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if "--js-runtimes" not in txt and shutil.which("node"):
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(txt + ("\n" if txt and not txt.endswith("\n") else "") + "--js-runtimes node\n", encoding="utf-8")
        print("config de yt-dlp:", cfg, "→ --js-runtimes node")
    else:
        print("config de yt-dlp:", cfg, "(sin cambios)")
except Exception as e:
    print("no pude escribir la config:", e)
prueba = sal(["yt-dlp", "--simulate", "-f", "bestaudio/best", "--print", "%(title)s · %(format_id)s", "--no-warnings",
              "https://www.youtube.com/watch?v=rB5EwIcCJC0"], 300)
print("prueba:", prueba[-2000:])
