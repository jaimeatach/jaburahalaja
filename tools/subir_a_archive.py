#!/usr/bin/env python3
"""
Sube la carpeta de shiurim a archive.org conservando la estructura de carpetas,
que es de donde la app deduce el módulo y el shiur de cada archivo.

Uso típico (en tu computadora, no en el servidor):

    pip install internetarchive
    python subir_a_archive.py --ver            # prueba en seco, no sube nada
    python subir_a_archive.py                  # sube de verdad

Credenciales: sacá tus claves en https://archive.org/account/s3.php y ponelas
en las variables de entorno IA_ACCESS_KEY / IA_SECRET_KEY, o corré `ia configure`
una vez y el script las toma solo.

Se puede cortar y volver a correr: lo que ya está subido se saltea.
"""
import argparse
import os
import sys
import time

# La consola de Windows no usa UTF-8 por defecto: sin esto, imprimir un nombre
# en hebreo corta el script con UnicodeEncodeError.
for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CARPETA = r"G:\.shortcut-targets-by-id\1-1NbLQmWMK5QfqArZT1X0twlTL5M_dBk\חבורה הלכות שבת"
ITEM = "jabura-halajot-shabat"
EXTS = {".m4a", ".mp3", ".mp4", ".m4v", ".mov", ".wav", ".ogg", ".opus",
        ".aac", ".wma", ".aif", ".aiff", ".3gp", ".pdf", ".docx", ".doc"}

METADATA = {
    "title": "חבורה הלכות שבת · שיעורים",
    "mediatype": "audio",
    "collection": "opensource_audio",
    "language": "heb",
    "subject": ["halacha", "shabbat", "shiurim", "torah"],
}


def listar(carpeta):
    """Devuelve [(ruta_local, nombre_remoto)] conservando las subcarpetas."""
    salida = []
    for raiz, _, archivos in os.walk(carpeta):
        for nombre in sorted(archivos):
            if os.path.splitext(nombre)[1].lower() not in EXTS:
                continue
            local = os.path.join(raiz, nombre)
            rel = os.path.relpath(local, carpeta).replace(os.sep, "/")
            salida.append((local, rel))
    return sorted(salida, key=lambda x: x[1])


def humano(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}"
        n /= 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", default=CARPETA)
    ap.add_argument("--item", default=ITEM, help="identificador en archive.org")
    ap.add_argument("--ver", action="store_true", help="prueba en seco: lista y no sube")
    args = ap.parse_args()

    if not os.path.isdir(args.carpeta):
        sys.exit(f"No encuentro la carpeta:\n  {args.carpeta}\n"
                 f"Pasala con --carpeta \"ruta\\a\\la\\carpeta\"")

    archivos = listar(args.carpeta)
    if not archivos:
        sys.exit("No hay archivos de audio ni PDFs en esa carpeta.")

    total = sum(os.path.getsize(l) for l, _ in archivos)
    print(f"{len(archivos)} archivos · {humano(total)}")
    print(f"Ítem de destino: https://archive.org/details/{args.item}\n")

    if args.ver:
        for _, remoto in archivos[:15]:
            print("   ", remoto)
        if len(archivos) > 15:
            print(f"    … y {len(archivos) - 15} más")
        print("\nPrueba en seco: no se subió nada. Sacá --ver para subir.")
        return

    try:
        from internetarchive import get_item
    except ImportError:
        sys.exit("Falta la librería. Instalala con:  pip install internetarchive")

    claves = {}
    if os.environ.get("IA_ACCESS_KEY") and os.environ.get("IA_SECRET_KEY"):
        claves = {"access_key": os.environ["IA_ACCESS_KEY"],
                  "secret_key": os.environ["IA_SECRET_KEY"]}

    item = get_item(args.item)
    ya = {f["name"] for f in (item.files or [])}
    if ya:
        print(f"El ítem ya tiene {len(ya)} archivos; esos se saltean.\n")

    subidos = fallidos = salteados = 0
    for i, (local, remoto) in enumerate(archivos, 1):
        if remoto in ya:
            salteados += 1
            continue
        etiqueta = f"[{i}/{len(archivos)}] {remoto}"
        for intento in range(1, 4):
            try:
                item.upload(
                    {remoto: local},
                    metadata=METADATA if subidos == 0 else None,
                    retries=3,
                    retries_sleep=5,
                    verbose=False,
                    **claves,
                )
                print(f"  ok   {etiqueta}")
                subidos += 1
                break
            except Exception as e:                      # noqa: BLE001
                if intento == 3:
                    print(f"  FALLA {etiqueta}\n        {e}")
                    fallidos += 1
                else:
                    time.sleep(5 * intento)

    print(f"\nSubidos {subidos} · salteados {salteados} · fallidos {fallidos}")
    if fallidos:
        print("Volvé a correr el script: retoma solo lo que falta.")
    else:
        print("\nListo. Ahora en la app, como admin:")
        print("  Importar de archive.org  →  pegá este identificador:")
        print(f"      {args.item}")


if __name__ == "__main__":
    main()
