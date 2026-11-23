#!/usr/bin/env python3
"""Lo corre el piloto por orden a distancia (accion "script"). Shalom Bait en la HP:
las clases ya convertidas (C:\\OTZAR\\efshar\\shalom_bait_listo) no pasaron en la mudanza, así que
shalom_bait.py creía que el curso estaba completo. 1) preparar: las vuelve a convertir desde G:;
2) semana auto --sin-portada: sube la clase de esta semana (el robot la anuncia el lunes)."""
import os
import subprocess
import sys
from pathlib import Path

EF = Path(r"C:\OTZAR\efshar")
env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
pasos = [["preparar"], ["semana", "auto", "--sin-portada"]] if "--solo-semana" not in sys.argv else [["semana", "auto", "--sin-portada"]]
listo = EF / "shalom_bait_listo"
print("antes:", sorted(p.name for p in listo.glob("*.mp3")) if listo.exists() else "no existe shalom_bait_listo")
for p in pasos:
    print("\n===== shalom_bait.py", " ".join(p), flush=True)
    r = subprocess.run([sys.executable, "shalom_bait.py"] + p, cwd=str(EF), env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3000)
    print(r.stdout[-30000:], r.stderr[-8000:], f"(código {r.returncode})", flush=True)
    if r.returncode not in (0, None) and p[0] == "preparar":
        break
print("\ndespués:", sorted(p.name for p in listo.glob("*.mp3")) if listo.exists() else "-")
