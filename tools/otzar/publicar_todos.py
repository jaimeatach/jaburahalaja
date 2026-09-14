#!/usr/bin/env python3
"""
Corre podcast_bot.py en cada show de C:\\OTZAR que publique desde WhatsApp
(config.json con "modo_whatsapp": true), salvo los manuales o pausados.
Lo llama ANUNCIAR.bat antes de mandar la orden de anunciar: así Peretz,
Nacach, Ofir Malka y Tefila publican lo que el robot guardó, y el anuncio
ya los encuentra en el feed. La jabura tiene su propio publicador.
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\OTZAR")
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

corridos = 0
for show in sorted(BASE.iterdir()):
    cfgp, bot = show / "config.json", show / "podcast_bot.py"
    if not (show.is_dir() and cfgp.exists() and bot.exists()):
        continue
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not cfg.get("modo_whatsapp") or cfg.get("manual") or cfg.get("pausado"):
        continue
    if (show / "PAUSADO.txt").exists() or (show / "PAUSADOS.txt").exists():
        continue
    print(f"--- {show.name}: publicando lo que dejó el robot ---", flush=True)
    subprocess.run([sys.executable, "podcast_bot.py"], cwd=str(show))
    corridos += 1
print(f"publicar_todos: {corridos} show(s) revisados.")
