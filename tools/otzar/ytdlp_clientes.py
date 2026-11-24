#!/usr/bin/env python3
"""Lo corre el piloto por orden a distancia (24/11/2026). Los podcast_bot.py de YouTube forzaban
`youtube:player_client=web_embedded`, y muchos videos ya no dan formatos con ese cliente ("Requested
format is not available"). Lo cambia a `default,web_embedded` (prueba los clientes normales y además el
embebido) en todos los .py de C:\\OTZAR (con respaldo .antes_clientes) y prueba un video."""
import subprocess
from pathlib import Path

VIEJO, NUEVO = "youtube:player_client=web_embedded\"", "youtube:player_client=default,web_embedded\""
n = 0
for f in list(Path(r"C:\OTZAR").glob("*/podcast_bot.py")) + list(Path(r"C:\OTZAR").glob("*.py")) + list(Path(r"C:\OTZAR\jabura").glob("*.py")):
    try:
        t = f.read_text(encoding="utf-8")
    except Exception:
        continue
    if VIEJO in t:
        f.with_name(f.name + ".antes_clientes").write_text(t, encoding="utf-8")
        f.write_text(t.replace(VIEJO, NUEVO), encoding="utf-8")
        n += 1
        print("cambiado:", f)
print("archivos cambiados:", n)
r = subprocess.run(["yt-dlp", "--simulate", "--no-warnings", "-f", "bestaudio/best", "--extractor-args",
                    "youtube:player_client=default,web_embedded", "--print", "%(title)s · %(format_id)s",
                    "https://www.youtube.com/watch?v=OaX_-9PRQ6M"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=300)
print("prueba:", (r.stdout + r.stderr)[-1500:])
