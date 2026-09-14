#!/usr/bin/env python3
"""
Instalador de un solo paso para la PC de Otzar (correr desde C:\\OTZAR):

    python instalar_otzar.py            # hace todo
    python instalar_otzar.py --ver      # solo muestra qué haría, no toca nada
    python instalar_otzar.py --robot=C:\\ruta\\robotwhats   # si no encuentra el robot solo
    python instalar_otzar.py --tefila-grupo=LINK            # link de invitación de Clases Tefila Habitat
    python instalar_otzar.py --tefila-spotify=LINK          # cuando exista el show en Spotify
    python instalar_otzar.py --reanunciar-jabura            # que el próximo ANUNCIAR mande el último shiur
    python instalar_otzar.py --grupos-generales=L1,L2       # grupos generales donde anuncian Nacach y Tefila
    python instalar_otzar.py --al-dia=nacach:2,peretz:2     # publica lo pendiente y memoriza todo menos los últimos N
    python instalar_otzar.py --ofir-grupo=LINK              # Ofir Malka también en tu grupo
    python instalar_otzar.py --tefila-rss=URL               # rescatar lo subido a mano en Spotify (RSS del show) al feed
    python instalar_otzar.py --portada=tefila:C:\\ruta\\img.jpg  # portada del show (va al repo, Spotify la toma del feed)
    python instalar_otzar.py --nuevo=hilu --nuevo-nombre="Rab Joshua Hilu" --nuevo-rss=URL --nuevo-spotify=URL [--nuevo-grupo=LINK]
    python instalar_otzar.py --nacach-spotify=LINK          # el show de Nacach en Spotify

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
     anunciar.jabura activo: titulo + link a la app, al mismo grupo. Nada corre
     programado: todo pasa cuando se pica ANUNCIAR.bat.
  4. Nacach: busca los audios que quedaron sin publicar (teshuba 5, Kaparot 1 y
     2, Rosh Hashana q se junta) en todas las carpetas del robot, los deja en la
     carpeta de WhatsApp de nacach y corre podcast_bot.py ahí.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
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
SPOTIFY_JABURA = "https://open.spotify.com/show/1tH0BEW6Aj5Y6jjgaLyLp5"
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
    # link directo al shiur (el <link> del feed) en el anuncio, con formato
    ("""      .map(it => ({ tit: sacaTitulo(it), guid: sacaGuid(it), audio: sacaAudio(it), peso: sacaPeso(it), fecha: sacaFecha(it) }))
""", """      .map(it => ({ tit: sacaTitulo(it), guid: sacaGuid(it), audio: sacaAudio(it), peso: sacaPeso(it), fecha: sacaFecha(it),
                    link: ((it.match(/<link>([\\s\\S]*?)<\\/link>/) || [])[1] || '').trim() }))
"""),
    ("""function armarMensaje(titulo, spotify, whatsapp, show) {
  let t = `*${titulo}*`;
  if (spotify)  t += `\\nSpotify\\n${spotify}`;
  if (whatsapp) t += `\\nWhatsapp\\n${whatsapp}`;
""", """function armarMensaje(titulo, spotify, whatsapp, show, app) {
  // "app": link directo al shiur en la app del show (viene del <link> del feed)
  let t = app ? `🎧 *${titulo}*` : `*${titulo}*`;
  if (app)      t += `\\n📲 App\\n${app}`;
  if (spotify)  t += app ? `\\n🎵 Spotify\\n${spotify}` : `\\nSpotify\\n${spotify}`;
  if (whatsapp) t += `\\nWhatsapp\\n${whatsapp}`;
"""),
    ("""        let texto = `*${ep.tit}*`;
        if (spotShow) texto += `\\n${spotShow}`;
        // "app": link a la app del show (la jabura) en vez de Spotify;
        // "sin_whatsapp": no repetir el link del grupo cuando se anuncia en el mismo grupo
        if (datos.app) texto += `\\nApp\\n${datos.app}`;
        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
""", """        // "app": link directo al shiur en la app (el <link> del feed, o el de la app);
        // "sin_whatsapp": no repetir el link del grupo cuando se anuncia en el mismo grupo
        const appLink = datos.app ? (ep.link || datos.app) : '';
        let texto = appLink ? `🎧 *${ep.tit}*` : `*${ep.tit}*`;
        if (appLink) texto += `\\n📲 App\\n${appLink}`;
        if (spotShow) texto += appLink ? `\\n🎵 Spotify\\n${spotShow}` : `\\n${spotShow}`;
        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
"""),
    ("""      const texto = armarMensaje(ep.tit, epLink, wa, show);
""", """      const texto = armarMensaje(ep.tit, epLink, wa, show, datos.app ? (ep.link || datos.app) : '');
"""),
    # feed por show (la jabura no vive en github.io) y link directo al audio
    ("""  try { xml = await fetchTexto(`https://rabmeireliyahu.github.io/${show}/feed.xml`); }
""", """  try { xml = await fetchTexto(feedDeShow(show)); }
""", "todos"),
    ("""function armarMensaje(titulo, spotify, whatsapp, show, app) {
""", """// "feed": URL del RSS del show cuando no vive en rabmeireliyahu.github.io
// (la jabura lo publica junto con su app). Por defecto, el de siempre.
function feedDeShow(show) {
  const d = (CFG.anunciar || {})[show] || {};
  return (d.feed && String(d.feed).startsWith('http')) ? d.feed : `https://rabmeireliyahu.github.io/${show}/feed.xml`;
}
function armarMensaje(titulo, spotify, whatsapp, show, app) {
"""),
    ("""        if (spotShow) texto += appLink ? `\\n🎵 Spotify\\n${spotShow}` : `\\n${spotShow}`;
        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
""", """        if (spotShow) texto += appLink ? `\\n🎵 Spotify\\n${spotShow}` : `\\n${spotShow}`;
        // "link_audio": el link directo al mp3 (archive.org) mientras no haya Spotify
        if (datos.link_audio && ep.audio) texto += `\\n🎧 Audio\\n${ep.audio}`;
        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
"""),
]
MARCAS_ROBOT = ("PARCHE LID", "JABURA (sep/2026)", "const sinAudio", "if (sinAudio(show))", "const appLink", "show, app)",
                "function feedDeShow", "datos.link_audio")
FEED_JABURA = "https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/feed.xml"


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
    for i, h in enumerate(HUNKS):
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
        elif viejo not in plano and any(h2[1] in plano for h2 in HUNKS[i + 1:]):
            aplicados += 1                    # un parche posterior ya reemplazó este bloque
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
                 "el grupo). Cuando el show de Spotify ya lea el feed nuevo, pon sin_spotify en false.",
    }
    ja = an.setdefault("jabura", {"spotify": "PENDIENTE_SHOW_NUEVO_DESDE_EL_RSS"})
    antes = json.dumps(ja, sort_keys=True)
    for k, v in quiero.items():
        ja.setdefault(k, v)
    ja["_nota"] = quiero["_nota"]
    ja["feed"] = FEED_JABURA           # el robot lee el feed de aquí (netlify.app no siempre abre en esa PC)
    ja["sin_spotify"] = False          # el show ya lee el feed: va el link exacto del episodio
    if not str(ja.get("spotify", "")).startswith("http"):
        ja["spotify"] = SPOTIFY_JABURA
    ja["pausado"] = False
    if json.dumps(ja, sort_keys=True) != antes:
        ok("anunciar.jabura: activo, con link a la app y link exacto de Spotify")
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
            try:
                viejo = json.loads(dest.read_text(encoding="utf-8"))
            except Exception:
                viejo = {}
            if viejo.get("feed_url"):
                faltan = {"spotify_show": SPOTIFY_JABURA, "robot": str(ROBOT or r"C:\robotwhats"),
                          "link": "https://jaburahalajasaul.netlify.app"}
                nuevas = {k: v for k, v in faltan.items() if not viejo.get(k)}
                if nuevas and not VER:
                    viejo.update(nuevas)
                    dest.write_text(json.dumps(viejo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                ok("config.json ya existe" + (f", le agregué {', '.join(nuevas)}" if nuevas else ", lo respeto"))
                continue
            # config viejo (feed en rabmeireliyahu/jabura): ahora el feed vive con la app en Netlify
            respaldar(dest)
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
    llaves = d / "spotify_keys.txt"
    if not llaves.exists() and ROBOT and (ROBOT / "spotify_keys.txt").exists():
        if not VER:
            shutil.copy2(ROBOT / "spotify_keys.txt", llaves)
        ok("llaves de Spotify copiadas del robot: la app va a enlazar cada shiur con su episodio")
    print("   → para publicar: doble clic en jabura\\jabura_publicar.bat (o ANUNCIAR.bat, que ya lo corre)")


# ── 8. sin tarea programada: todo pasa cuando Beto pica ANUNCIAR.bat ──────────
def tarea_programada():
    paso(8, "Tarea programada: quitarla (todo corre con ANUNCIAR.bat)")
    if VER or os.name != "nt":
        print("   (borraría) la tarea 'Otzar publicar' si existiera")
        return
    r = subprocess.run(["schtasks", "/Delete", "/TN", "Otzar publicar", "/F"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    ok("tarea 'Otzar publicar' borrada" if r.returncode == 0 else "no había tarea programada")
    viejo = BASE / "jabura" / "auto_publicar.bat"
    if viejo.exists():
        viejo.unlink()
    print("   → ANUNCIAR.bat hace todo: sube jabura y tefila, espeja nacach y manda anunciar al robot")


# ── 10. --reanunciar-jabura: que el próximo ANUNCIAR mande el último shiur ─────
def reanunciar_jabura():
    if "--reanunciar-jabura" not in sys.argv:
        return
    paso(10, "Jabura: volver a poner en cola el último shiur para el próximo ANUNCIAR")
    estado = (ROBOT or BASE) / "estado_anuncios.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(FEED_JABURA, headers={"User-Agent": "instalar-otzar"}), timeout=30) as r:
            feed = r.read().decode("utf-8", "replace")
        guids = re.findall(r"<guid[^>]*>(.*?)</guid>", feed)
        ultimo = guids[-1].replace("&amp;", "&") if guids else ""
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed: {e}")
        return
    if not ultimo:
        aviso("el feed no tiene episodios")
        return
    try:
        e = json.loads(estado.read_text(encoding="utf-8")) if estado.exists() else {}
    except Exception:
        e = {}
    lista = e.get("jabura")
    if lista is None:
        # Primera vez del show: el robot memorizaría TODO el catálogo sin anunciar.
        # Se le deja memorizado todo menos el último, para que ese sí salga.
        respaldar(estado)
        e["jabura"] = [g.replace("&amp;", "&") for g in guids[:-1]]
        escribir(estado, json.dumps(e, ensure_ascii=False, indent=2))
        ok(f"catálogo memorizado ({len(guids) - 1}); '{ultimo.split('/')[-1]}' sale en el próximo ANUNCIAR")
    elif ultimo in lista:
        respaldar(estado)
        e["jabura"] = [g for g in lista if g != ultimo]
        escribir(estado, json.dumps(e, ensure_ascii=False, indent=2))
        ok(f"desmarcado: {ultimo.split('/')[-1]} → sale en el próximo ANUNCIAR")
    else:
        ok(f"'{ultimo.split('/')[-1]}' no estaba marcado: sale en el próximo ANUNCIAR")


# ── 11. nacach: título + link a tres grupos ───────────────────────────────────
def nacach_anuncio():
    grupos = next((a.split("=", 1)[1] for a in sys.argv if a.startswith(("--nacach-grupos=", "--grupos-generales="))), "")
    spot = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--nacach-spotify=")), "").split("?")[0]
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    paso(11, "Nacach: anuncio = título + link, a sus grupos")
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    an = cfg.setdefault("anunciar", {}).setdefault("nacach", {"spotify": "PENDIENTE", "invite": "", "idioma": "es"})
    antes = json.dumps(an, sort_keys=True)
    if grupos:
        lista = [g.strip().split("?")[0] for g in grupos.split(",") if g.strip().startswith("http")]
        for g in lista:
            cod = g.rstrip("/").split("/")[-1]
            if len(cod) < 20:
                aviso(f"este link se ve mal cortado: {g}")
        if lista:
            an["invite"] = lista if len(lista) > 1 else lista[0]
            ok(f"{len(lista)} grupo(s) de anuncio")
    if spot.startswith("http"):
        an["spotify"] = spot
    tiene = str(an.get("spotify", "")).startswith("http")
    an.update({"sin_audio": True, "sin_whatsapp": True, "max_anuncios": 2, "en_orden": True,
               "sin_spotify": not tiene, "link_audio": not tiene, "pausado": False})
    an["_nota"] = ("Solo título + link, sin audio adjunto. Con link del show en spotify va el episodio exacto; "
                   "mientras, va el link directo al mp3 (link_audio).")
    if json.dumps(an, sort_keys=True) != antes:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok("anunciar.nacach guardado")
    inv = an.get("invite")
    n_inv = len(inv) if isinstance(inv, list) else (1 if str(inv).startswith("http") else 0)
    if not n_inv:
        aviso("sin grupos: python instalar_otzar.py --nacach-grupos=LINK1,LINK2,LINK3")
    ok("link exacto de Spotify" if tiene else "sin show en Spotify: manda el link directo al mp3 (--nacach-spotify=LINK para cambiarlo)")


# ── 16. sin atrasos: solo_ultimos por show (lo aplica mantenimiento.py en cada ANUNCIAR)
def sin_atrasos_config():
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    paso(16, "Sin atrasos: cada show anuncia solo sus últimos N")
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    an = cfg.setdefault("anunciar", {})
    defectos = {"nacach": 2, "peretz": 2, "ofirmalka": 2, "tefila": 2, "jabura": 3}
    cambios = 0
    for show, n in defectos.items():
        if show in an and an[show].get("solo_ultimos") != n and "solo_ultimos" not in an[show]:
            an[show]["solo_ultimos"] = n
            cambios += 1
    if cambios:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok(", ".join(f"{s}: {an[s]['solo_ultimos']}" for s in defectos if s in an and an[s].get("solo_ultimos")))


# ── 15. Ofir Malka: también en el grupo de Beto ───────────────────────────────
def ofir_grupo():
    link = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--ofir-grupo=")), "").split("?")[0]
    if not link.startswith("http"):
        return
    paso(15, "Ofir Malka: anunciar también en tu grupo")
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    an = cfg.setdefault("anunciar", {}).setdefault("ofirmalka", {})
    inv = an.get("invite") or []
    inv = inv if isinstance(inv, list) else ([inv] if inv else [])
    if link not in inv:
        inv.append(link)
        an["invite"] = inv
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok(f"ofirmalka anuncia en {len(inv)} grupos")
    else:
        ok("ya estaba")


# ── 17. --tefila-rss=URL: rescatar lo que ya se subió a mano en Spotify ────────
def tefila_rescate():
    rss = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tefila-rss=")), "").strip()
    if not rss.startswith("http"):
        return
    paso(17, "Tefila: rescatar los episodios subidos a mano en Spotify y meterlos al feed")
    d = BASE / "tefila"
    cfgp = d / "config.json"
    if not (d / "podcast_bot.py").exists() or not cfgp.exists():
        aviso("falta tefila\\podcast_bot.py o config.json")
        return
    c = json.loads(cfgp.read_text(encoding="utf-8"))
    if c.get("rss_original") != rss:
        c["rss_original"] = rss
        respaldar(cfgp)
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        ok("rss_original guardado")
    if VER:
        print("   (correría) podcast_bot.py rescatar / subir / feed en", d)
        return
    for cmd in ("rescatar", "subir", "feed"):
        print(f"   --- podcast_bot.py {cmd} ---")
        r = subprocess.run([sys.executable, "podcast_bot.py", cmd], cwd=str(d))
        if r.returncode != 0:
            aviso(f"podcast_bot.py {cmd} terminó con error; revisa arriba")
            return
    ok("episodios rescatados, subidos a archive.org y publicados en el feed de tefila")
    print("   → ahora en Spotify for Creators haz el redirect a https://rabmeireliyahu.github.io/tefila/feed.xml")


# ── 18. show nuevo estilo Peretz, de un tirón ─────────────────────────────────
#   --nuevo=hilu --nuevo-nombre="Rab Joshua Hilu" --nuevo-rss=URL --nuevo-spotify=URL [--nuevo-grupo=LINK]
def show_nuevo():
    arg = lambda k: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), "").strip()
    clave = re.sub(r"[^a-z0-9]", "", arg("nuevo").lower())
    if not clave:
        return
    nombre = arg("nuevo-nombre") or clave
    rss = arg("nuevo-rss")
    spot = arg("nuevo-spotify").split("?")[0]
    grupo = arg("nuevo-grupo").split("?")[0]
    paso(18, f"Show nuevo: {nombre} ({clave})")
    d = BASE / clave
    modelo = next((BASE / m for m in ("tefila", "peretz", "nacach") if (BASE / m / "podcast_bot.py").exists()), None)
    if not modelo:
        aviso("no encuentro un podcast_bot.py de otro show para copiar")
        return
    if not VER:
        (d / "audios_whatsapp").mkdir(parents=True, exist_ok=True)
        for f in ("podcast_bot.py", "github_token.txt"):
            if not (d / f).exists() and (modelo / f).exists():
                shutil.copy2(modelo / f, d / f)
    cfgp = d / "config.json"
    c = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
    base_cfg = json.loads((modelo / "config.json").read_text(encoding="utf-8"))
    antes = json.dumps(c, sort_keys=True)
    c.setdefault("titulo", nombre)
    c.setdefault("descripcion", f"Shiurim de {nombre}. Otzar HaTorah - אוצר התורה")
    c.setdefault("autor", nombre)
    c.setdefault("email", base_cfg.get("email", "rabmeireliyahu@gmail.com"))
    c.setdefault("idioma", "es")
    c["modo_whatsapp"] = True
    c["carpeta_whatsapp"] = str(d / "audios_whatsapp")
    c.setdefault("archive_id", "rab-" + clave)
    c.setdefault("github_user", "rabmeireliyahu")
    c.setdefault("github_repo", clave)
    c["solo_agregar"] = True
    if rss:
        c["rss_original"] = rss
    if json.dumps(c, sort_keys=True) != antes:
        if cfgp.exists():
            respaldar(cfgp)
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        ok("config.json del show")
    # repo + Pages + portada (la del show en Spotify) + feed inicial
    tok = d / "github_token.txt"
    if tok.exists() and not VER:
        cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
               "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
        base = f"https://api.github.com/repos/{c['github_user']}/{c['github_repo']}"
        def gh(metodo, url, cuerpo=None):
            datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
            req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    t = r.read().decode()
                    return r.status, (json.loads(t) if t.strip() else {})
            except urllib.error.HTTPError as e:
                return e.code, {}
            except Exception as e:                          # noqa: BLE001
                return 0, {"message": str(e)}
        def poner(ruta, contenido, msg):
            st, j = gh("GET", f"{base}/contents/{ruta}")
            cuerpo = {"message": msg, "content": base64.b64encode(contenido).decode()}
            if st == 200 and j.get("sha"):
                cuerpo["sha"] = j["sha"]
            st, _ = gh("PUT", f"{base}/contents/{ruta}", cuerpo)
            return st in (200, 201)
        st, _ = gh("GET", base)
        if st == 404:
            st, j = gh("POST", "https://api.github.com/user/repos",
                       {"name": c["github_repo"], "description": nombre, "private": False, "auto_init": False})
            ok("repo creado" if st in (200, 201) else f"no pude crear el repo ({st})")
            poner("README.md", f"# {clave}\n{nombre}\n".encode(), "readme")
        pages = f"https://{c['github_user']}.github.io/{c['github_repo']}"
        st, _ = gh("GET", f"{base}/contents/portada.jpg")
        if st == 404 and rss:
            try:
                with urllib.request.urlopen(urllib.request.Request(rss, headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as r:
                    xml = r.read().decode("utf-8", "replace")
                m = re.search(r'<itunes:image[^>]*href="([^"]+)"', xml) or re.search(r"<url>([^<]+)</url>", xml)
                if m:
                    with urllib.request.urlopen(urllib.request.Request(m.group(1), headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                        img = r.read()
                    if poner("portada.jpg", img, "portada"):
                        ok("portada tomada del show en Spotify")
            except Exception as e:                          # noqa: BLE001
                aviso(f"portada: {e}")
        st, _ = gh("GET", f"{base}/contents/feed.xml")
        if st == 404:
            from xml.sax.saxutils import escape
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(c['titulo'])}</title>
    <description>{escape(c['descripcion'])}</description>
    <link>{pages}</link>
    <language>{c['idioma']}</language>
    <itunes:author>{escape(c['autor'])}</itunes:author>
    <itunes:owner><itunes:name>{escape(c['autor'])}</itunes:name><itunes:email>{c['email']}</itunes:email></itunes:owner>
    <itunes:image href="{pages}/portada.jpg"/>
    <itunes:category text="Religion &amp; Spirituality"/>
    <itunes:explicit>false</itunes:explicit>
  </channel>
</rss>
"""
            ok("feed inicial creado" if poner("feed.xml", xml.encode("utf-8"), "feed inicial") else "no pude crear el feed")
        st, _ = gh("POST", f"{base}/pages", {"source": {"branch": "main", "path": "/"}})
        if st in (200, 201):
            ok("GitHub Pages prendido")
    # robot: escuchar (grupo fuente) + anunciar (grupos generales, como nacach)
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    antes = json.dumps(cfg, sort_keys=True)
    esc = cfg.setdefault("escuchar", {}).setdefault(clave, {"invite": ""})
    esc["carpetaDestino"] = str(d / "audios_whatsapp")
    if grupo.startswith("http"):
        esc["invite"] = grupo
    an = cfg.setdefault("anunciar", {}).setdefault(clave, {"spotify": "PENDIENTE", "invite": ""})
    generales = (cfg.get("anunciar", {}).get("nacach") or {}).get("invite")
    if generales and not an.get("invite"):
        an["invite"] = generales
    if spot.startswith("http"):
        an["spotify"] = spot
    tiene = str(an.get("spotify", "")).startswith("http")
    for k, v in {"idioma": "es", "max_anuncios": 2, "en_orden": True, "sin_audio": True, "sin_whatsapp": True, "solo_ultimos": 2}.items():
        an.setdefault(k, v)
    an["sin_spotify"] = not tiene
    an["link_audio"] = not tiene
    an["pausado"] = not bool(an.get("invite"))
    if json.dumps(cfg, sort_keys=True) != antes:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok(f"robot: escucha {clave}" + (" (grupo por link)" if grupo else " (falta el grupo: --nuevo-grupo=LINK)") +
           f" · anuncia en {len(an['invite']) if isinstance(an.get('invite'), list) else (1 if an.get('invite') else 0)} grupo(s)")
    # rescatar lo que ya está en Spotify
    if rss and not VER:
        for cmd in ("rescatar", "subir", "feed"):
            print(f"   --- podcast_bot.py {cmd} ---")
            r = subprocess.run([sys.executable, "podcast_bot.py", cmd], cwd=str(d))
            if r.returncode != 0:
                aviso(f"podcast_bot.py {cmd} terminó con error")
                return
        ok("episodios rescatados y publicados en el feed nuevo")
        print(f"   → en Spotify for Creators, redirect del show a https://{c['github_user']}.github.io/{c['github_repo']}/feed.xml")
    if not grupo.startswith("http") and not esc.get("invite"):
        print(f"   → cuando tengas el grupo del Rab: python instalar_otzar.py --sin-drive --nuevo={clave} --nuevo-grupo=LINK")


# ── 19. --portada=show:C:\\ruta\\imagen.jpg → portada del show en su repo ────────
def portada():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--portada=")), "")
    if not arg or ":" not in arg:
        return
    show, ruta = arg.split(":", 1)
    ruta = Path(ruta.strip('"'))
    paso(19, f"Portada de {show}")
    d = BASE / show
    if not ruta.exists():
        # sin extensión o con otra: se busca "nombre.*" en esa carpeta
        candidatos = sorted(ruta.parent.glob(ruta.stem + ".*")) if ruta.parent.exists() else []
        candidatos = [c for c in candidatos if c.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if candidatos:
            ruta = candidatos[0]
        else:
            aviso(f"no encuentro la imagen: {ruta}")
            return
    c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
    tok = d / "github_token.txt"
    if not tok.exists():
        aviso("falta github_token.txt en la carpeta del show")
        return
    img = ruta.read_bytes()
    # Spotify quiere JPG/PNG cuadrado de 1400 a 3000 px: con Pillow se deja en JPG
    # de 1400 mínimo; sin Pillow se sube tal cual y se avisa
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(img)).convert("RGB")
        w, h = im.size
        lado = min(w, h)
        if w != h:
            im = im.crop(((w - lado) // 2, (h - lado) // 2, (w - lado) // 2 + lado, (h - lado) // 2 + lado))
        if lado < 1400:
            im = im.resize((1400, 1400), Image.LANCZOS)
        elif lado > 3000:
            im = im.resize((3000, 3000), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        img = buf.getvalue()
        ok(f"imagen preparada: {im.size[0]}x{im.size[1]} JPG ({len(img) // 1024} KB)")
    except ImportError:
        if not img[:3] == b"\xff\xd8\xff":
            aviso("la imagen no es JPG y no tengo Pillow para convertirla (pip install pillow); la subo igual")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude preparar la imagen ({e}); la subo tal cual")
    if len(img) > 2_500_000:
        aviso("la imagen pesa más de 2.5 MB; Spotify la puede rechazar")
    if not VER:
        (d / "portada.jpg").write_bytes(img)
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    if VER:
        print("   (subiría) portada.jpg a", base)
        return
    sha = None
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base}/contents/portada.jpg", headers=cab), timeout=60) as r:
            sha = json.loads(r.read().decode()).get("sha")
    except Exception:
        pass
    cuerpo = {"message": "portada", "content": base64.b64encode(img).decode()}
    if sha:
        cuerpo["sha"] = sha
    req = urllib.request.Request(f"{base}/contents/portada.jpg", data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            ok(f"portada subida ({len(img) // 1024} KB). Spotify la toma al leer el feed (mínimo 1400x1400 px).")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude subir la portada: {e}")


# ── 20. --restaurar=mishnaberura,yalkutyosef: dejar el feed y las portadas como
#        estaban antes del 14/9 (lo cambiaron otras sesiones por PR) ────────────
def restaurar():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--restaurar=")), "")
    if not arg:
        return
    paso(20, "Restaurar feed y portadas al estado anterior al 14/9")
    tok = next((BASE / m / "github_token.txt" for m in ("nacach", "peretz", "jabura") if (BASE / m / "github_token.txt").exists()), None)
    if not tok:
        aviso("no encuentro github_token.txt")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    for repo in [x.strip() for x in arg.split(",") if x.strip()]:
        base = f"https://api.github.com/repos/rabmeireliyahu/{repo}"
        # el feed NO se reemplaza entero (podría tener episodios nuevos): solo se
        # devuelve la portada a portada_20260831.jpg y se quita el bloque <image> agregado
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{base}/contents/feed.xml", headers=cab), timeout=60) as r:
                j = json.loads(r.read().decode())
            feed = base64.b64decode(j["content"]).decode("utf-8")
            nuevo = re.sub(r'<itunes:image href="[^"]*"/>',
                           f'<itunes:image href="https://rabmeireliyahu.github.io/{repo}/portada_20260831.jpg"/>', feed, count=1)
            nuevo = re.sub(r"\n\s*<image>[\s\S]*?</image>", "", nuevo, count=1)
            if nuevo != feed and not VER:
                cuerpo = {"message": "portada de vuelta a la del 31/8", "sha": j["sha"],
                          "content": base64.b64encode(nuevo.encode("utf-8")).decode()}
                req = urllib.request.Request(f"{base}/contents/feed.xml", data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
                with urllib.request.urlopen(req, timeout=120):
                    ok(f"{repo}/feed.xml: portada apuntando a la del 31/8, episodios intactos")
            elif nuevo == feed:
                ok(f"{repo}/feed.xml ya apuntaba a la portada del 31/8")
        except Exception as e:                              # noqa: BLE001
            aviso(f"{repo}/feed.xml: {e}")
        for archivo in ("portada.jpg", "portada_20260831.jpg"):
            url = API_CONTENTS.replace("/contents/tools/", f"/contents/tools/otzar/restaurar/{repo}/") + archivo
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar", "Accept": "application/vnd.github.raw"}), timeout=60) as r:
                    datos = r.read()
            except Exception as e:                          # noqa: BLE001
                aviso(f"{repo}/{archivo}: no pude bajar la copia buena ({e})")
                continue
            if VER:
                print(f"   (subiría) {repo}/{archivo} ({len(datos)//1024} KB)")
                continue
            sha = None
            try:
                with urllib.request.urlopen(urllib.request.Request(f"{base}/contents/{archivo}", headers=cab), timeout=60) as r:
                    sha = json.loads(r.read().decode()).get("sha")
            except Exception:
                pass
            cuerpo = {"message": f"restaurar {archivo} (estado del 31/8)", "content": base64.b64encode(datos).decode()}
            if sha:
                cuerpo["sha"] = sha
            req = urllib.request.Request(f"{base}/contents/{archivo}", data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
            try:
                with urllib.request.urlopen(req, timeout=120):
                    ok(f"{repo}/{archivo} restaurado")
            except Exception as e:                          # noqa: BLE001
                aviso(f"{repo}/{archivo}: {e}")


# ── 12. tefila: feed inicial en el repo (podcast_bot solo AGREGA; sin feed truena) ─
def tefila_feed_inicial():
    d = BASE / "tefila"
    tok = d / "github_token.txt"
    cfgp = d / "config.json"
    if not (d.is_dir() and tok.exists() and cfgp.exists()):
        return
    paso(12, "Tefila: feed inicial en rabmeireliyahu/tefila")
    c = json.loads(cfgp.read_text(encoding="utf-8"))
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', 'tefila')}"
    def gh(metodo, url, cuerpo=None):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                t = r.read().decode()
                return r.status, (json.loads(t) if t.strip() else {})
        except urllib.error.HTTPError as e:
            return e.code, {}
        except Exception as e:                              # noqa: BLE001
            return 0, {"message": str(e)}
    st, _ = gh("GET", f"{base}/contents/feed.xml")
    if st == 200:
        ok("feed.xml ya existe en el repo")
    elif st == 404:
        from xml.sax.saxutils import escape
        pages = f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', 'tefila')}"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(c.get('titulo', 'Rab Tofi Cherem'))}</title>
    <description>{escape(c.get('descripcion', ''))}</description>
    <link>{pages}</link>
    <language>{c.get('idioma', 'es')}</language>
    <itunes:author>{escape(c.get('autor', ''))}</itunes:author>
    <itunes:owner><itunes:name>{escape(c.get('autor', ''))}</itunes:name><itunes:email>{c.get('email', '')}</itunes:email></itunes:owner>
    <itunes:image href="{pages}/portada.jpg"/>
    <itunes:category text="Religion &amp; Spirituality"/>
    <itunes:explicit>false</itunes:explicit>
  </channel>
</rss>
"""
        if VER:
            print("   (subiría) feed.xml vacío al repo")
        else:
            st, j = gh("PUT", f"{base}/contents/feed.xml",
                       {"message": "feed inicial", "content": base64.b64encode(xml.encode("utf-8")).decode()})
            ok("feed.xml inicial creado (0 episodios): el bot ya puede agregarle") if st in (200, 201) else aviso(f"no pude crear el feed: {st} {j.get('message', '')}")
        st, j = gh("POST", f"{base}/pages", {"source": {"branch": "main", "path": "/"}})
        if st in (200, 201):
            ok("GitHub Pages prendido")
    else:
        aviso(f"no pude ver el repo tefila ({st}): revisa github_token.txt")


# ── 13. shows de WhatsApp al día: carpeta del bot = carpeta del robot, y lo que
#        ya está en el feed no se vuelve a subir ─────────────────────────────────
def shows_whatsapp_al_dia():
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    paso(13, "Shows de WhatsApp: carpeta del bot = carpeta del robot; lo publicado, marcado")
    cfgw = json.loads(rw.read_text(encoding="utf-8"))
    carpetas = {}
    for show, datos in (cfgw.get("escuchar") or {}).items():
        if isinstance(datos, dict) and datos.get("carpetaDestino"):
            carpetas[show] = datos["carpetaDestino"]
    for e in cfgw.get("escuchar_directo") or []:
        if e.get("show") and e.get("carpetaDestino"):
            carpetas.setdefault(e["show"], e["carpetaDestino"])
    for show, carpeta in sorted(carpetas.items()):
        d = BASE / show
        cfgp = d / "config.json"
        if not (d.is_dir() and cfgp.exists()):
            continue
        try:
            c = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not c.get("modo_whatsapp"):
            continue
        # (a) el bot tiene que leer donde el robot escribe
        if str(c.get("carpeta_whatsapp", "")).rstrip("\\").lower() != str(carpeta).rstrip("\\").lower():
            aviso(f"{show}: el robot guarda en {carpeta} pero el bot leía {c.get('carpeta_whatsapp')}")
            c["carpeta_whatsapp"] = carpeta
            respaldar(cfgp)
            escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            ok(f"{show}: bot apuntado a la carpeta del robot")
        # (b) lo que ya está en el feed, marcado como procesado (si no, se resube cada vez)
        try:
            url = f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}/feed.xml"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar"}), timeout=30) as r:
                feed = r.read().decode("utf-8", "replace")
        except Exception:
            feed = ""
        if not feed:
            continue
        procesados = d / "procesados_whatsapp.txt"
        lista = procesados.read_text(encoding="utf-8").splitlines() if procesados.exists() else []
        marcados = 0
        try:
            audios = [f for f in Path(carpeta).iterdir() if f.is_file() and f.suffix.lower() in AUDIO]
        except Exception:
            audios = []
        for f in audios:
            if f.name in lista:
                continue
            titulo = re.sub(r"\s+", " ", f.stem).strip()
            if f"<title>{titulo}</title>" in feed or f"<guid isPermaLink=\"false\">{titulo}.mp3</guid>" in feed:
                lista.append(f.name)
                marcados += 1
                mp3 = d / "episodios" / (re.sub(r'[<>:"/\\|?*]', "", f.stem).strip()[:120] + ".mp3")
                if mp3.exists() and not VER:
                    mp3.unlink()
        if marcados and not VER:
            procesados.write_text("\n".join(lista) + "\n", encoding="utf-8")
        pend = len([f for f in audios if f.name not in lista])
        ok(f"{show}: {marcados} marcados como ya publicados · {pend} por publicar en el próximo ANUNCIAR")


# ── 14. --al-dia=show1,show2: memorizar todo lo del feed sin anunciar ───────────
def al_dia():
    shows = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--al-dia=")), "")
    if not shows:
        return
    paso(14, "Anuncios al día: memorizar lo que ya está en el feed, sin mandarlo")
    estado = (ROBOT or BASE) / "estado_anuncios.json"
    try:
        e = json.loads(estado.read_text(encoding="utf-8")) if estado.exists() else {}
    except Exception:
        e = {}
    cambio = False
    for item in [x.strip() for x in shows.split(",") if x.strip()]:
        show, _, n = item.partition(":")
        dejar = int(n) if n.isdigit() else 0
        d = BASE / show
        if show != "jabura" and (d / "podcast_bot.py").exists() and not VER:
            # primero se publica lo que el robot dejó pendiente, para que el feed esté completo
            print(f"   {show}: publicando lo pendiente antes de ponerlo al día...")
            subprocess.run([sys.executable, "podcast_bot.py"], cwd=str(d))
        url = FEED_JABURA if show == "jabura" else f"https://rabmeireliyahu.github.io/{show}/feed.xml"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar"}), timeout=30) as r:
                feed = r.read().decode("utf-8", "replace")
        except Exception as ex:                             # noqa: BLE001
            aviso(f"{show}: no pude leer el feed ({ex})")
            continue
        from email.utils import parsedate_to_datetime
        pares = []
        for it in re.findall(r"<item>([\s\S]*?)</item>", feed):
            g = re.search(r"<guid[^>]*>(.*?)</guid>", it)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not g:
                continue
            try:
                cuando = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
            except Exception:
                cuando = 0
            pares.append((cuando, g.group(1).replace("&amp;", "&")))
        guids = [g for _, g in pares]
        # los N más nuevos por fecha quedan sin memorizar para que salgan; lo ya anunciado no se toca
        ultimos = [g for _, g in sorted(pares)[-dejar:]] if dejar else []
        memorizar = [g for g in guids if g not in ultimos]
        previos = e.get(show) or []
        nuevos = [g for g in memorizar if g not in previos]
        e[show] = (previos + nuevos)[-2000:]
        cambio = True
        ok(f"{show}: {len(memorizar)} memorizados; salen los últimos {dejar}: " +
           " | ".join(g.split("/")[-1][:40] for g in ultimos) if dejar else f"{show}: {len(memorizar)} memorizados; solo se anuncia lo nuevo")
    if cambio and not VER:
        respaldar(estado)
        escribir(estado, json.dumps(e, ensure_ascii=False, indent=2))


# ── 9. diagnóstico de la jabura: ¿qué hizo el robot con el último audio? ───────
def diagnostico_jabura():
    paso(9, "Jabura: últimos audios en el Drive y qué dijo el robot")
    try:
        cfg = json.loads(((ROBOT or BASE) / "config_whatsapp.json").read_text(encoding="utf-8"))
        carpeta = Path(cfg["escuchar"]["jabura"]["carpetaDestino"])
    except Exception:
        carpeta = None
    if carpeta:
        try:
            archivos = sorted([f for f in carpeta.iterdir() if f.is_file()], key=lambda f: f.stat().st_mtime)[-5:]
            print(f"   carpeta: {carpeta}")
            for f in archivos:
                print(f"   · {time.strftime('%d/%m %H:%M', time.localtime(f.stat().st_mtime))}  {f.name}  ({f.stat().st_size // 1024} KB)")
            if not archivos:
                aviso("la carpeta está vacía")
        except Exception as e:                              # noqa: BLE001
            aviso(f"no pude leer la carpeta del Drive: {e}")
    log_robot = (ROBOT or BASE) / "robot_whatsapp.log"
    if log_robot.exists():
        hoy = time.strftime("%-d/%-m/%Y") if os.name != "nt" else time.strftime("%#d/%#m/%Y")
        lineas = log_robot.read_text(encoding="utf-8", errors="replace").splitlines()
        claves = ("GUARDADO", "IGNORADO", "Esperando titulo", "escucha jabura", "Mekorot", "AUDIO", "REGISTRADO", "RECUPERADOS", "ANUNCIADO")
        util = [l for l in lineas if any(k in l for k in claves) and hoy in l[:14]]
        print(f"   robot hoy ({hoy}): {len(util)} líneas de audio")
        for l in util[-15:]:
            print("   " + l[:150])
        if not util:
            ult = [l for l in lineas if "GUARDADO" in l][-3:]
            print("   últimos GUARDADO de cualquier día:")
            for l in ult:
                print("   " + l[:150])
    else:
        aviso("no encontré robot_whatsapp.log")


# ── 7. tefila (Rab Tofi Cherem) ───────────────────────────────────────────────
def tefila():
    paso(7, "Tefila (Rab Tofi Cherem): grupo Clases Tefila Habitat → archive.org → feed → Spotify")
    d = BASE / "tefila"
    if not d.is_dir():
        aviso("no está C:\\OTZAR\\tefila (NUEVO_TEFILA.bat no corrió); no toco nada")
        return
    carpeta_wa = str(d / "audios_whatsapp")
    spot = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tefila-spotify=")), "").split("?")[0]
    grupo = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tefila-grupo=")), "").split("?")[0]
    # config.json del show: herencia de peretz fuera
    cfgp = d / "config.json"
    if cfgp.exists():
        c = json.loads(cfgp.read_text(encoding="utf-8"))
        antes = json.dumps(c, sort_keys=True)
        if "peret" in str(c.get("archive_id", "")).lower() or not c.get("archive_id"):
            c["archive_id"] = "rab-tofi-cherem"
            ok("archive_id propio: rab-tofi-cherem (antes era el ítem de Peretz)")
        c.pop("rss_original", None)
        c["modo_whatsapp"] = True
        c["carpeta_whatsapp"] = carpeta_wa
        c["solo_agregar"] = True
        for k in list(c):
            if "youtube" in k or k == "filtro_titulo":
                c.pop(k)
        if json.dumps(c, sort_keys=True) != antes:
            respaldar(cfgp)
            escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            ok("tefila\\config.json limpio")
        else:
            ok("tefila\\config.json ya estaba bien")
    else:
        aviso("falta tefila\\config.json")
    if not VER:
        (d / "audios_whatsapp").mkdir(exist_ok=True)
    if not (d / "podcast_bot.py").exists():
        aviso("falta tefila\\podcast_bot.py: cópialo de C:\\OTZAR\\peretz")
    if not (d / "github_token.txt").exists():
        for origen in sorted(BASE.glob("*/github_token.txt")):
            if not VER:
                shutil.copy2(origen, d / "github_token.txt")
            ok(f"github_token.txt copiado de {origen.parent.name}\\")
            break
    # robot: escuchar y anunciar en el MISMO grupo, registrado con "!otzar tefila"
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if rw.exists():
        cfg = json.loads(rw.read_text(encoding="utf-8"))
        antes = json.dumps(cfg, sort_keys=True)
        esc = cfg.setdefault("escuchar", {}).setdefault("tefila", {"invite": ""})
        esc["carpetaDestino"] = carpeta_wa
        for k in ("carpeta", "grupos"):
            esc.pop(k, None)
        an = cfg.setdefault("anunciar", {}).setdefault("tefila", {"spotify": "PENDIENTE", "invite": ""})
        generales = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--grupos-generales=")), "")
        generales = [g.strip().split("?")[0] for g in generales.split(",") if g.strip().startswith("http")]
        if grupo.startswith("http"):
            # con el link de invitación el robot registra el grupo solo al arrancar;
            # no hace falta mandar "!otzar tefila". Ese grupo es la FUENTE de audios.
            esc["invite"] = grupo
            ok("grupo Clases Tefila Habitat puesto por link: el robot lo registra al arrancar")
        if generales:
            # los avisos van a los grupos generales (los mismos de Nacach), no al grupo de clases
            an["invite"] = generales if len(generales) > 1 else generales[0]
            ok(f"anuncios de tefila a {len(generales)} grupo(s) generales")
        elif grupo.startswith("http") and not an.get("invite"):
            an["invite"] = grupo
        for k, v in {"idioma": "es", "max_anuncios": 2, "en_orden": True, "sin_audio": True, "sin_whatsapp": True}.items():
            an.setdefault(k, v)
        if spot.startswith("http"):
            an["spotify"] = spot
        tiene_spotify = str(an.get("spotify", "")).startswith("http")
        an["sin_spotify"] = not tiene_spotify
        an["link_audio"] = not tiene_spotify
        tiene_grupos = bool(an.get("invite"))
        an["pausado"] = not tiene_grupos
        an["_nota"] = ("Titulo + link (sin audio) a los grupos generales. Sin show en Spotify va el link directo al mp3; "
                       "con show: python instalar_otzar.py --tefila-spotify=LINK")
        for k in list(an):
            if isinstance(an[k], str) and ("peret" in an[k].lower() and k != "_nota"):
                an[k] = "" if k != "spotify" else "PENDIENTE"
                aviso(f"anunciar.tefila.{k} traía algo de Peretz: lo vacié")
        if json.dumps(cfg, sort_keys=True) != antes:
            respaldar(rw)
            escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
            ok("config_whatsapp.json: tefila en escuchar y anunciar")
        else:
            ok("config_whatsapp.json: tefila ya estaba bien")
        ok("anunciar.tefila " + ("ACTIVO con link exacto de Spotify" if tiene_spotify else ("ACTIVO con link al mp3 (sin show en Spotify aún)" if tiene_grupos else "en pausa: faltan los grupos generales (--grupos-generales=L1,L2)")))
    # ¿el grupo ya está registrado?
    reg = (ROBOT or BASE) / "grupos_registrados.json"
    try:
        r = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:
        r = {}
    g = r.get("tefila") or r.get("escucha:tefila")
    if grupo.startswith("http") and not (g and g.get("id")):
        print("   → reinicia el robot: al arrancar debe decir 'OK escucha tefila -> Clases Tefila Habitat'")
    elif g and g.get("id"):
        ok(f"grupo registrado: {g.get('nombre', g['id'])}")
        if "peret" in str(g.get("nombre", "")).lower():
            aviso("¡ese grupo es de Peretz! Manda \"!otzar tefila\" en el grupo del Rab para corregirlo")
    else:
        aviso("grupo SIN registrar: con el robot prendido, manda \"!otzar tefila\" dentro de Clases Tefila Habitat")
    # ¿qué hay capturado y qué hay publicado?
    try:
        n_audios = len([f for f in (d / "audios_whatsapp").iterdir() if f.suffix.lower() in AUDIO])
    except Exception:
        n_audios = 0
    try:
        with urllib.request.urlopen("https://rabmeireliyahu.github.io/tefila/feed.xml", timeout=30) as f:
            n_feed = f.read().decode("utf-8", "replace").count("<item>")
    except Exception:
        n_feed = -1
    print(f"   · audios capturados en tefila\\audios_whatsapp: {n_audios} · episodios en el feed: "
          f"{n_feed if n_feed >= 0 else 'no pude leerlo'}")
    print("   → Spotify: con el primer episodio en el feed, da de alta el show con "
          "https://rabmeireliyahu.github.io/tefila/feed.xml y luego: python instalar_otzar.py --tefila-spotify=LINK")


def instalar_anunciar():
    paso(5, "ANUNCIAR.bat: que suba la jabura antes de anunciar")
    if not ROBOT:
        aviso("sin carpeta del robot no puedo poner ANUNCIAR.bat")
        return
    ruta = ROBOT / "ANUNCIAR.bat"
    if not VER:
        bajar("otzar/mantenimiento.py", BASE / "jabura" / "mantenimiento.py")
    if ruta.exists() and "mantenimiento.py" in ruta.read_text(encoding="utf-8", errors="replace"):
        ok("ya llama al mantenimiento (jabura, shows de WhatsApp, espejo, sin atrasos)")
        return
    respaldar(ruta)
    if bajar("otzar/ANUNCIAR.bat", ruta):
        ok("ANUNCIAR.bat actualizado: mantenimiento completo y luego anuncia")


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


def espejo_nacach():
    paso(6, "Nacach: espejo del feed al repo viejo (nacash), el que lee Spotify")
    nac = BASE / "nacach"
    if not nac.is_dir():
        aviso("no está la carpeta nacach")
        return
    dest = nac / "espejo_nacash.py"
    if not bajar("otzar/espejo_nacash.py", dest):
        return
    if VER:
        print("   (correría) python espejo_nacash.py en", nac)
        return
    subprocess.run([sys.executable, "espejo_nacash.py"], cwd=str(nac))


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
    espejo_nacach()
    tefila()
    tarea_programada()
    diagnostico_jabura()
    reanunciar_jabura()
    nacach_anuncio()
    tefila_feed_inicial()
    tefila_rescate()
    show_nuevo()
    portada()
    restaurar()
    shows_whatsapp_al_dia()
    ofir_grupo()
    sin_atrasos_config()
    al_dia()
    print("\nListo." if not VER else "\nPrueba en seco terminada: no se cambió nada.")


if __name__ == "__main__":
    main()
