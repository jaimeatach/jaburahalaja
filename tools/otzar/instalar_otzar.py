#!/usr/bin/env python3
"""
Instalador de un solo paso para la PC de Otzar (correr desde C:\\OTZAR):

    python instalar_otzar.py            # hace todo
    python instalar_otzar.py --ver      # solo muestra qué haría, no toca nada
    python instalar_otzar.py --robot=C:\\ruta\\robotwhats   # si no encuentra el robot solo

Los shows (nacach, peretz…) viven en C:\\OTZAR; el robot en C:\\robotwhats. Los busca solo.

Qué hace, con copia de respaldo de cada archivo que toca:
  1. Parcha robot_whatsapp.js: chats privados "@lid" (por eso se perdían audios
     de Nacach) y numeración de la jabura. Si ya está parchado, no hace nada.
  2. Agrega la jabura a config_whatsapp.json (escuchar + anunciar). Sin tocar
     los demás shows.
  3. Arma la carpeta jabura\\ con jabura_publicar.py, subir_a_archive.py,
     jabura_publicar.bat, config.json y portada.jpg, y le copia el github_token.txt.
     El publicador crea solo el repo rabmeireliyahu/jabura con Pages si no existe.
  5. Pone en ANUNCIAR.bat el paso que sube la jabura antes de anunciar, y deja
     anunciar.jabura activo: titulo + link a la app, al mismo grupo.
  4. Nacach: busca los audios que quedaron sin publicar (teshuba 5, Kaparot 1 y
     2, Rosh Hashana q se junta) en todas las carpetas del robot, los deja en la
     carpeta de WhatsApp de nacach y corre podcast_bot.py ahí.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

for flujo in (sys.stdout, sys.stderr):
    try:
        if (flujo.encoding or "").lower().replace("-", "") != "utf8":
            flujo.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RAW = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/"
VER = "--ver" in sys.argv
BASE = Path(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--base=")), r"C:\OTZAR"))


def hallar_robot():
    """El robot (robot_whatsapp.js + config_whatsapp.json) no vive en C:\\OTZAR:
    está en la carpeta robotwhats del escritorio. Se busca en los lugares
    conocidos y, si no, por todo el perfil del usuario."""
    dado = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--robot=")), "")
    candidatos = [Path(dado)] if dado else []
    perfil = Path(os.environ.get("USERPROFILE") or Path.home())
    candidatos += [Path(r"C:\robotwhats"), BASE, BASE / "robotwhats",
                   perfil / "OneDrive" / "Escritorio" / "TORAHSPOTIFY" / "robotwhats",
                   perfil / "Desktop" / "TORAHSPOTIFY" / "robotwhats",
                   perfil / "Escritorio" / "TORAHSPOTIFY" / "robotwhats"]
    for c in candidatos:
        if (c / "robot_whatsapp.js").exists():
            return c
    for raiz in (perfil / "OneDrive", perfil / "Desktop", perfil / "Escritorio", perfil, Path("C:\\")):
        try:
            for r in raiz.glob("**/robotwhats/robot_whatsapp.js"):
                return r.parent
        except Exception:
            pass
    return None


ROBOT = hallar_robot()
SHA_ROBOT_ORIGINAL = "20799775c6a828c5a6eb5938bfa15eb2344f8d1d2ebdf52f3d8c0f27863905a1"
AUDIO = (".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".amr")
NACACH_PERDIDOS = ["10 días de teshuba 5", "kaparot 1", "kaparot 2", "rosh hashana q se junta"]
GRUPO_JABURA = "https://chat.whatsapp.com/DOallmE8DiABCZcaebstOY"
DRIVE_JABURA = r"G:\.shortcut-targets-by-id\1-1NbLQmWMK5QfqArZT1X0twlTL5M_dBk\חבורה הלכות שבת"

# Los cinco cambios del robot, tal cual el diff (tools/otzar/robot_whatsapp_parche_lid.diff)
HUNKS = [
    ("""  const base = limpiarTitulo(titulo) ||
    (_etq + ' ' + new Date(item.ts).toLocaleDateString('es-MX').replace(/\\//g, '-') +
     ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.'));
""", """  let base = limpiarTitulo(titulo) ||
    (_etq + ' ' + new Date(item.ts).toLocaleDateString('es-MX').replace(/\\//g, '-') +
     ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.'));
  // === JABURA (sep/2026): los shiurim van numerados para conservar el orden ===
  // La carpeta de la jabura es la misma que lee la app: cada archivo lleva el
  // numero que sigue ("5 titulo.m4a"), contando los audios que ya hay.
  if (item.show === 'jabura' || /jabura/i.test(String(carpeta))) {
    let n = 0;
    try { n = fs.readdirSync(carpeta).filter(f => /\\.(m4a|mp3|ogg|opus|aac|wav|amr)$/i.test(f)).length; } catch (e) {}
    base = String(n + 1).padStart(2, '0') + ' ' + base;
  }
"""),
    ("""    const soloDigitos = (jid.split('@')[0] || '').replace(/\\D/g, '');
""", """    // === PARCHE LID (sep/2026) ===
    // WhatsApp ya manda muchos chats privados como "NNNN@lid": ese numero NO es el
    // telefono, asi que buscar el telefono dentro del jid fallaba en silencio y el
    // audio del rab se iba a la "nube" en vez de guardarse. Baileys trae el
    // telefono real en senderPn / participantPn / remoteJidAlt: se revisan todos.
    const k = m.key || {};
    const candidatos = [jid, k.senderPn, k.participantPn, k.remoteJidAlt, k.participantAlt]
      .filter(Boolean).map(x => String(x).split('@')[0].replace(/\\D/g, ''));
    const soloDigitos = candidatos.join('|');
"""),
    ("""  if (!esGrupo && !directo && !/^!otzar\\s/i.test(textoDe(m))) {
    try {
      const N = nube();
""", """  if (!esGrupo && !directo && !/^!otzar\\s/i.test(textoDe(m))) {
    // Si lo que llego es un AUDIO y no reconocimos el chat, que quede escrito:
    // asi se ve en el log de quien vino y con que jid, en vez de perderse.
    if (audioDe(m)) log(`AUDIO IGNORADO (chat privado no registrado): jid=${jid}` +
      (m.key && m.key.senderPn ? ` tel=${m.key.senderPn}` : '') +
      ' -> si es un rab, agregalo en escuchar_directo o manda "!otzar <clave>" desde ese chat');
    try {
      const N = nube();
"""),
    ("""  if (esGrupo && !escuchaGrupo) return;
""", """  if (esGrupo && !escuchaGrupo) {
    if (audioDe(m)) log(`AUDIO IGNORADO (grupo no registrado para escucha): jid=${jid}` +
      ' -> agrega el grupo en "escuchar" del config o manda "!otzar <clave>" en ese grupo');
    return;
  }
"""),
    ("""    const item = { buffer, ext, ts, autor, timer: null, archivoTemp: null,
                   carpeta: destinoAudio.carpeta };
""", """    const item = { buffer, ext, ts, autor, timer: null, archivoTemp: null,
                   carpeta: destinoAudio.carpeta, show: destinoAudio.show };
"""),
    # anuncio de la jabura sin Spotify: link a la app, sin audio, sin repetir el grupo
    ("""const SHOWS_SIN_AUDIO = ['peretz'];
""", """const SHOWS_SIN_AUDIO = ['peretz'];
// "sin_audio": true en anunciar -> <show> hace lo mismo desde el config (la
// jabura: el audio ya esta en el grupo, solo va el aviso).
const sinAudio = show => SHOWS_SIN_AUDIO.includes(show) || !!((CFG.anunciar || {})[show] || {}).sin_audio;
"""),
    ("""        let texto = `*${ep.tit}*`;
        if (spotShow) texto += `\\n${spotShow}`;
        if (wa) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
""", """        let texto = `*${ep.tit}*`;
        if (spotShow) texto += `\\n${spotShow}`;
        // "app": link a la app del show (la jabura) en vez de Spotify;
        // "sin_whatsapp": no repetir el link del grupo cuando se anuncia en el mismo grupo
        if (datos.app) texto += `\\nApp\\n${datos.app}`;
        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
"""),
    ("""if (SHOWS_SIN_AUDIO.includes(show))""", """if (sinAudio(show))""", "todos"),
]
MARCAS_ROBOT = ("PARCHE LID", "JABURA (sep/2026)", "const sinAudio", "datos.app", "if (sinAudio(show))")


def paso(n, msg):
    print(f"\n[{n}] {msg}")


def ok(msg):
    print("   ✔ " + msg)


def aviso(msg):
    print("   ⚠ " + msg)


def respaldar(ruta):
    if VER or not ruta.exists():
        return
    dest = ruta.with_name(ruta.name + ".bak_" + time.strftime("%Y%m%d%H%M%S"))
    shutil.copy2(ruta, dest)
    ok(f"respaldo: {dest.name}")


API_CONTENTS = "https://api.github.com/repos/jaimeatach/jaburahalaja/contents/tools/"


def bajar(nombre, destino):
    """Baja tools/<nombre> del repo. Primero por la API (siempre trae la última
    versión); si falla, por raw.githubusercontent (que tarda unos minutos en refrescar)."""
    if VER:
        print(f"   (bajaría) {RAW + nombre}")
        return True
    intentos = [(API_CONTENTS + nombre, {"User-Agent": "instalar-otzar", "Accept": "application/vnd.github.raw"}),
                (RAW + nombre, {"User-Agent": "instalar-otzar"})]
    for url, cab in intentos:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=60) as r:
                datos = r.read()
            destino.write_bytes(datos)
            ok(f"bajado {destino.name} ({len(datos)//1024} KB)")
            return True
        except Exception as e:                              # noqa: BLE001
            ultimo = e
    aviso(f"no pude bajar {nombre}: {ultimo}")
    return False


def escribir(ruta, texto):
    if VER:
        print(f"   (escribiría) {ruta}")
        return
    ruta.write_text(texto, encoding="utf-8", newline="")


# ── 1. robot ──────────────────────────────────────────────────────────────────
def parchar_robot():
    paso(1, "Robot de WhatsApp (robot_whatsapp.js)")
    if not ROBOT:
        aviso("no encontré robot_whatsapp.js; pásame la carpeta con --robot=C:\\ruta\\robotwhats")
        return
    ruta = ROBOT / "robot_whatsapp.js"
    ok(f"robot en {ROBOT}")
    crudo = ruta.read_bytes()
    texto = crudo.decode("utf-8")
    if all(m in texto for m in MARCAS_ROBOT):
        ok("ya estaba parchado, no toco nada")
        return
    salto = "\r\n" if "\r\n" in texto else "\n"
    plano = texto.replace("\r\n", "\n")
    aplicados = 0
    for h in HUNKS:
        viejo, nuevo, todos = h[0], h[1], len(h) > 2
        if nuevo in plano and (todos and viejo not in plano or not todos):
            aplicados += 1
            continue
        if todos and viejo in plano:
            plano = plano.replace(viejo, nuevo)
            aplicados += 1
        elif plano.count(viejo) == 1:
            plano = plano.replace(viejo, nuevo, 1)
            aplicados += 1
    if aplicados == len(HUNKS):
        respaldar(ruta)
        escribir(ruta, plano.replace("\n", salto))
        ok(f"{len(HUNKS)} cambios aplicados a tu robot")
    elif hashlib.sha256(crudo).hexdigest() == SHA_ROBOT_ORIGINAL:
        respaldar(ruta)
        if bajar("otzar/robot_whatsapp.js", ruta):
            ok("robot reemplazado por la copia parchada")
    else:
        aviso(f"tu robot cambió y solo pude aplicar {aplicados} de {len(HUNKS)} cambios; lo dejo como está.")
        aviso("Bájate tools/otzar/robot_whatsapp.js del repo y compáralo a mano.")
        return
    if not VER:
        r = subprocess.run(["node", "--check", str(ruta)], capture_output=True, text=True)
        if r.returncode == 0:
            ok("node --check: sintaxis OK")
        else:
            aviso("node --check falló: " + (r.stderr or r.stdout).strip()[:300])
    print("   → reinicia el robot (cierra su ventana y abre ROBOT_WHATSAPP.bat)")


# ── 2. config_whatsapp.json ───────────────────────────────────────────────────
def carpeta_siman_actual():
    """La subcarpeta del siman que se estudia ahora. Si el Drive está a mano,
    toma la carpeta con el audio más reciente; si no, כותב ומוחק (שמ)."""
    fijo = DRIVE_JABURA + "\\שיעורים בהלכה\\כותב ומוחק"
    if "--sin-drive" in sys.argv:
        return fijo
    base = Path(DRIVE_JABURA) / "שיעורים בהלכה"
    print("   mirando el Drive para ver qué siman va (si tarda, Ctrl+C y corre con --sin-drive)...")
    limite = time.time() + 20                      # el Drive por streaming puede ser lento
    try:
        mejor, cuando = None, 0
        for d in base.iterdir():
            if not d.is_dir():
                continue
            for f in d.iterdir():                  # solo el primer nivel, sin rglob
                if time.time() > limite:
                    raise TimeoutError
                if f.suffix.lower() in AUDIO:
                    m = f.stat().st_mtime
                    if m > cuando:
                        mejor, cuando = d, m
        if mejor:
            return str(mejor)
    except TimeoutError:
        aviso("el Drive tarda demasiado; dejo כותב ומוחק")
    except Exception:
        pass
    return fijo


def configurar_whatsapp():
    paso(2, "config_whatsapp.json: agregar la jabura")
    ruta = (ROBOT or BASE) / "config_whatsapp.json"
    if not ruta.exists():
        aviso(f"no está {ruta}")
        return
    cfg = json.loads(ruta.read_text(encoding="utf-8"))
    cambios = 0
    esc = cfg.setdefault("escuchar", {})
    if "jabura" not in esc:
        carpeta = carpeta_siman_actual()
        esc["jabura"] = {"invite": GRUPO_JABURA, "carpetaDestino": carpeta}
        ok(f"escuchar.jabura → {carpeta}")
        cambios += 1
    else:
        ok(f"escuchar.jabura ya estaba (carpeta: {esc['jabura'].get('carpetaDestino')})")
    an = cfg.setdefault("anunciar", {})
    quiero = {
        "invite": GRUPO_JABURA, "idioma": "he", "max_anuncios": 2, "en_orden": True,
        "sin_spotify": True, "sin_audio": True, "sin_whatsapp": True,
        "app": "https://jaburahalajasaul.netlify.app",
        "_nota": "Anuncia al mismo grupo donde caen los audios: titulo + link a la app, sin audio (ya esta en "
                 "el grupo). Cuando exista el show en Spotify: pon el link en spotify y sin_spotify en false.",
    }
    ja = an.setdefault("jabura", {"spotify": "PENDIENTE_SHOW_NUEVO_DESDE_EL_RSS"})
    antes = json.dumps(ja, sort_keys=True)
    for k, v in quiero.items():
        ja.setdefault(k, v)
    ja["_nota"] = quiero["_nota"]
    ja["pausado"] = False
    if json.dumps(ja, sort_keys=True) != antes:
        ok("anunciar.jabura: activo, con link a la app y sin Spotify por ahora")
        cambios += 1
    else:
        ok("anunciar.jabura ya estaba")
    nac = an.get("nacach", {})
    if str(nac.get("spotify", "")).upper().startswith("PENDIENTE") or not nac.get("spotify"):
        aviso("anunciar.nacach.spotify sigue en PENDIENTE: sin el link del show, 'anunciar' no manda los de Nacach.")
    if cambios:
        respaldar(ruta)
        escribir(ruta, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok("config_whatsapp.json guardado")


# ── 3. carpeta jabura ─────────────────────────────────────────────────────────
def armar_jabura():
    paso(3, "Carpeta jabura\\ con el publicador")
    d = BASE / "jabura"
    if not VER:
        d.mkdir(exist_ok=True)
    for nombre, remoto in [("jabura_publicar.py", "jabura_publicar.py"), ("subir_a_archive.py", "subir_a_archive.py"),
                           ("jabura_publicar.bat", "jabura_publicar.bat"), ("config.json", "otzar/config.json"),
                           ("portada.jpg", "otzar/portada.jpg")]:
        if nombre == "portada.jpg" and (d / nombre).exists():
            continue
        dest = d / nombre
        if nombre == "config.json" and dest.exists():
            ok("config.json ya existe, lo respeto")
            continue
        bajar(remoto, dest)
    tok = d / "github_token.txt"
    if not tok.exists():
        for origen in sorted(BASE.glob("*/github_token.txt")):
            if VER:
                print(f"   (copiaría) {origen} → {tok}")
            else:
                shutil.copy2(origen, tok)
                ok(f"github_token.txt copiado de {origen.parent.name}\\")
            break
        else:
            aviso("no encontré github_token.txt en ninguna carpeta de show: cópialo a mano a jabura\\")
    print("   → para publicar: doble clic en jabura\\jabura_publicar.bat (o ANUNCIAR.bat, que ya lo corre)")


def instalar_anunciar():
    paso(5, "ANUNCIAR.bat: que suba la jabura antes de anunciar")
    if not ROBOT:
        aviso("sin carpeta del robot no puedo poner ANUNCIAR.bat")
        return
    ruta = ROBOT / "ANUNCIAR.bat"
    if ruta.exists() and "jabura_publicar" in ruta.read_text(encoding="utf-8", errors="replace"):
        ok("ya tenía el paso de la jabura")
        return
    respaldar(ruta)
    if bajar("otzar/ANUNCIAR.bat", ruta):
        ok("ANUNCIAR.bat actualizado: primero sube la jabura, luego anuncia todo")


# ── 4. nacach ─────────────────────────────────────────────────────────────────
def carpetas_del_robot(cfg):
    vistas = []
    for datos in (cfg.get("escuchar") or {}).values():
        if isinstance(datos, dict) and datos.get("carpetaDestino"):
            vistas.append(Path(datos["carpetaDestino"]))
    for e in cfg.get("escuchar_directo") or []:
        if e.get("carpetaDestino"):
            vistas.append(Path(e["carpetaDestino"]))
    vistas.append((ROBOT or BASE) / "audios_esperando_titulo")
    for show in BASE.iterdir():
        if show.is_dir():
            vistas += [show / "audios_whatsapp", show / "episodios"]
    unicas, ya = [], set()
    for v in vistas:
        k = str(v).lower()
        if k not in ya:
            ya.add(k)
            unicas.append(v)
    return unicas


def rescatar_nacach():
    paso(4, "Nacach: audios que quedaron sin publicar")
    nac = BASE / "nacach"
    cfg_nac = nac / "config.json"
    if not cfg_nac.exists():
        aviso(f"no está {cfg_nac}")
        return
    cfgn = json.loads(cfg_nac.read_text(encoding="utf-8"))
    destino = Path(cfgn.get("carpeta_whatsapp") or (nac / "audios_whatsapp"))
    ok(f"el subidor de nacach lee: {destino}")
    try:
        cfgw = json.loads(((ROBOT or BASE) / "config_whatsapp.json").read_text(encoding="utf-8"))
    except Exception:
        cfgw = {}
    # Primero el feed publicado: lo que ya está ahí no se vuelve a subir
    feed = ""
    try:
        url = f"https://{cfgn.get('github_user', 'rabmeireliyahu')}.github.io/{cfgn.get('github_repo', 'nacach')}/feed.xml"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar"}), timeout=30) as r:
            feed = r.read().decode("utf-8", "replace")
        ok(f"feed leído: {feed.count('<item>')} episodios publicados")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed publicado ({e}); sigo sin esa referencia")
    hallados = []
    for carpeta in carpetas_del_robot(cfgw):
        if not carpeta.is_dir():
            continue
        for f in carpeta.iterdir():
            if f.is_file() and f.suffix.lower() in AUDIO and any(p in f.stem.lower() for p in NACACH_PERDIDOS):
                hallados.append(f)
    if not hallados:
        aviso("no encontré ninguno de los 4 audios en las carpetas del robot.")
        aviso("Pídele a Nacach que los reenvíe al chat del robot: con el robot parchado ya se guardan.")
        return
    procesados = nac / "procesados_whatsapp.txt"
    lista = procesados.read_text(encoding="utf-8").splitlines() if procesados.exists() else []
    movidos = 0
    publicados = [f for f in hallados if f"<title>{f.stem}</title>" in feed]
    for f in publicados:
        # Ya está en el feed: se marca como procesado para que el subidor no lo
        # vuelva a subir, y si es un mp3 duplicado del m4a en la carpeta de
        # WhatsApp (lo movió una corrida anterior de este instalador), se borra.
        print(f"   · {f.name}  ({f.parent})  [YA PUBLICADO en el feed]")
        if f.parent.resolve() == destino.resolve():
            if f.name not in lista:
                lista.append(f.name)
                ok("marcado como procesado")
            if f.suffix.lower() == ".mp3" and any((destino / (f.stem + e)).exists() for e in (".m4a", ".ogg", ".opus")):
                if VER:
                    print("     (borraría el mp3 duplicado)")
                else:
                    f.unlink()
                    ok("mp3 duplicado borrado")
    hallados = [f for f in hallados if f not in publicados]
    if not hallados:
        if not VER and procesados.exists() or lista:
            procesados.write_text("\n".join(lista) + ("\n" if lista else ""), encoding="utf-8")
        ok("Nacach al día: los 4 ya están en el feed.")
        return
    for f in hallados:
        en_destino = f.parent.resolve() == destino.resolve()
        print(f"   · {f.name}  ({f.parent})" + ("  [ya en la carpeta de nacach]" if en_destino else ""))
        if f.name in lista:
            aviso(f"estaba marcado como procesado sin estar en el feed: lo desmarco")
            lista = [x for x in lista if x != f.name]
        if not en_destino:
            if VER:
                print(f"     (movería a {destino})")
            else:
                destino.mkdir(parents=True, exist_ok=True)
                objetivo = destino / f.name
                if objetivo.exists():
                    objetivo = destino / (f.stem + "_" + str(int(time.time())) + f.suffix)
                shutil.move(str(f), str(objetivo))
                ok(f"movido a nacach\\audios_whatsapp")
                movidos += 1
    if not VER and procesados.exists():
        procesados.write_text("\n".join(lista) + ("\n" if lista else ""), encoding="utf-8")
    if VER:
        print("   (correría) python podcast_bot.py en", nac)
        return
    print("\n   Corriendo el subidor de nacach (sube a archive.org y al feed)...\n")
    subprocess.run([sys.executable, "podcast_bot.py"], cwd=str(nac))


def main():
    print("=== Instalador Otzar · jabura + nacach ===")
    print("Base:", BASE, "(prueba en seco)" if VER else "")
    print("Robot:", ROBOT or "NO ENCONTRADO (pásame --robot=C:\\ruta\\robotwhats)")
    if not BASE.is_dir():
        sys.exit(f"No existe {BASE}. Pásame --base=C:\\ruta\\de\\los\\shows")
    parchar_robot()
    configurar_whatsapp()
    armar_jabura()
    instalar_anunciar()
    rescatar_nacach()
    print("\nListo." if not VER else "\nPrueba en seco terminada: no se cambió nada.")


if __name__ == "__main__":
    main()
