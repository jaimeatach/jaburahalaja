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
    python instalar_otzar.py --quitar=nacach:texto1|texto2   # sacar del feed lo que no era del show
    python instalar_otzar.py --vaciar-fuente=hilu             # borrar lo captado en audios_whatsapp del show
    python instalar_otzar.py --anunciar-tambien=efshar        # ese show avisa también en los grupos generales
    python instalar_otzar.py --nuevo=hilu --nuevo-nombre="Rab Joshua Hilu" --nuevo-rss=URL --nuevo-spotify=URL [--nuevo-grupo=LINK]
    python instalar_otzar.py --nacach-spotify=LINK          # el show de Nacach en Spotify
    python instalar_otzar.py --parasha=chazaq             # cada semana: el shiur de la parasha del canal de YouTube del show
    python instalar_otzar.py --correo=taamim:buzon@dominio:remitente@gmail.com --correo-clave=XXXX   # audios que llegan por mail
    python instalar_otzar.py --correo-carpeta=taamim:"G:\\Mi unidad\\OTZAR\\taamim"   # lo mismo vía Drive (script de Google) cuando el filtro no deja entrar a Gmail
    python instalar_otzar.py --nuevo=taamim ... --nuevo-sin-grupos   # show solo para Spotify, sin anunciar en grupos
    python instalar_otzar.py --reordenar=taamim                  # feed en orden de Tanaj (parashá, Tehilim, Rut, Ester)
    python instalar_otzar.py --compactar=musar                   # feed hinchado de espacios (GitHub 422): compactarlo ya
    python instalar_otzar.py --nombres=musar --excluir="musar:שער הבי?טחון"   # nombre del Rab en el título; series que no se bajan
    python instalar_otzar.py --rescatar=hilu,jabura:5          # el robot pide a WhatsApp los audios que se perdieron
    python instalar_otzar.py --tawil [--tawil-rss=RSS] [--tawil-numero=TEL]   # Rab Yosef Tawil: chat directo, temas, anuncio en su día
    python instalar_otzar.py --amazon=show:LINK --soundcloud=show:LINK --spotify-espera=torahanytime:6
    python instalar_otzar.py --revisar                       # en qué plataformas está cada show y qué le falta

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
import base64, importlib.util
import html
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

# rama donde vive esta versión del instalador; "main" de respaldo
REFS = ("claude/shiurim-halachot-shabbat-vriig5", "main")
RAW = f"https://raw.githubusercontent.com/jaimeatach/jaburahalaja/{REFS[0]}/tools/"
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
    # un grupo de anuncios no es fuente de audios (lo que manden ahi no se sube)
    ("""  for (const [show, datos] of Object.entries(CFG.escuchar || {})) {
    const r = reg['escucha:' + show] || reg[show];  // acepta registro con o sin prefijo
    if (r && r.id === jid) return { show, carpeta: datos.carpetaDestino };
  }
  // shows de escucha directa (!otzar <show> en un grupo = ese grupo es su buzon)
  for (const e of (CFG.escuchar_directo || [])) {
    const r = reg['escucha:' + e.show] || reg[e.show];
    if (r && r.id === jid) return { show: e.show, carpeta: e.carpetaDestino };
  }
  return null;
""", """  // Un grupo donde se ANUNCIA no es fuente de audios. reg[show] (sin prefijo)
  // solo vale como fuente cuando lo registro "!otzar <show>" en ese grupo, o sea
  // cuando el show NO tiene link de anuncio en el config; si lo tiene, reg[show]
  // es el grupo de anuncios y lo que manden ahi no se sube.
  const fuenteDe = show => {
    if (reg['escucha:' + show]) return reg['escucha:' + show];
    const an = (CFG.anunciar || {})[show] || {};
    const conInvite = Array.isArray(an.invite) ? an.invite.length > 0 : !!(an.invite && String(an.invite).startsWith('http'));
    return conInvite ? null : reg[show];
  };
  for (const [show, datos] of Object.entries(CFG.escuchar || {})) {
    const r = fuenteDe(show);
    if (r && r.id === jid) return { show, carpeta: datos.carpetaDestino };
  }
  // shows de escucha directa (!otzar <show> en un grupo = ese grupo es su buzon)
  for (const e of (CFG.escuchar_directo || [])) {
    const r = fuenteDe(e.show);
    if (r && r.id === jid) return { show: e.show, carpeta: e.carpetaDestino };
  }
  return null;
"""),
    # clases sin texto: título por defecto del show, y se publican
    ("""  let base = limpiarTitulo(titulo) ||
    (_etq + ' ' + new Date(item.ts).toLocaleDateString('es-MX').replace(/\\//g, '-') +
     ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.'));
""", """  // "titulo_defecto" en escuchar -> <show>: un audio que llega sin texto se
  // guarda como "<titulo_defecto> <fecha>" y SI se publica (el subidor solo
  // aparta los que empiezan con "Shiur ...").
  const _porDefecto = ((CFG.escuchar || {})[item.show] || {}).titulo_defecto;
  let base = limpiarTitulo(titulo) ||
    (_porDefecto
      ? (_porDefecto + ' ' + new Date(item.ts).toLocaleDateString('es-MX').replace(/\\//g, '-'))
      : (_etq + ' ' + new Date(item.ts).toLocaleDateString('es-MX').replace(/\\//g, '-') +
         ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.')));
"""),
    # fuente de audios: '!otzar <show>' en un grupo la registra como fuente cuando el
    # show anuncia en otros grupos; reconoce el grupo por 'nombre' si el link falla;
    # dice el nombre del grupo que ignora y el show de cada GUARDADO
    ("""    const validas = Object.keys(CFG.anunciar || {});
    if (!clave || !validas.includes(clave)) {
      log('Clave no valida en "!otzar": ' + (clave || '(vacia)'));
      return;
    }
    const reg = leerRegistro();
    reg[clave] = { id: jid, nombre: 'grupo ' + jid.slice(0, 14) + '...' };
    guardarRegistro(reg);
    log(`REGISTRADO: ${clave} -> ${jid}  (ya puedes borrar tu mensaje)`);
    return;
""", """    const validas = Object.keys(CFG.anunciar || {}).concat(Object.keys(CFG.escuchar || {}));
    if (!clave || !validas.includes(clave)) {
      log('Clave no valida en "!otzar": ' + (clave || '(vacia)'));
      return;
    }
    const reg = leerRegistro();
    let nombreGrupo = 'grupo ' + jid.slice(0, 14) + '...';
    try { const md = await sock.groupMetadata(jid); if (md && md.subject) nombreGrupo = md.subject; } catch (e) {}
    // === FUENTE (sep/2026): si el show anuncia en OTROS grupos (invite en
    // anunciar) y este grupo se registra a mano, es su FUENTE de audios
    // (escucha:<clave>); reg[clave] queda para los grupos de anuncio.
    const _an = (CFG.anunciar || {})[clave] || {};
    const _anuncia = Array.isArray(_an.invite) ? _an.invite.length > 0 : !!(_an.invite && String(_an.invite).startsWith('http'));
    if ((CFG.escuchar || {})[clave] && _anuncia) {
      reg['escucha:' + clave] = { id: jid, nombre: nombreGrupo, manual: true };
      guardarRegistro(reg);
      log(`REGISTRADO fuente de audios: ${clave} -> "${nombreGrupo}" ${jid}  (ya puedes borrar tu mensaje)`);
      return;
    }
    reg[clave] = { id: jid, nombre: nombreGrupo };
    guardarRegistro(reg);
    log(`REGISTRADO: ${clave} -> "${nombreGrupo}" ${jid}  (ya puedes borrar tu mensaje)`);
    return;
"""),
    ("""  const escuchaGrupo = esGrupo ? grupoEscuchaDe(jid) : null;

  if (esGrupo && !escuchaGrupo) {
    if (audioDe(m)) log(`AUDIO IGNORADO (grupo no registrado para escucha): jid=${jid}` +
      ' -> agrega el grupo en "escuchar" del config o manda "!otzar <clave>" en ese grupo');
    return;
  }
""", """  let escuchaGrupo = esGrupo ? grupoEscuchaDe(jid) : null;

  // === FUENTE POR NOMBRE (sep/2026): si el grupo no esta registrado pero su
  // nombre coincide con "nombre" en escuchar.<show> del config, se registra
  // solo como fuente de ese show (por si el link de invitacion no se pudo leer).
  if (esGrupo && !escuchaGrupo && audioDe(m)) {
    const nombreGrupo = await nombreDeGrupo(jid);
    const show = showPorNombre(nombreGrupo);
    if (show) {
      const reg = leerRegistro();
      reg['escucha:' + show] = { id: jid, nombre: nombreGrupo, porNombre: true };
      guardarRegistro(reg);
      log(`FUENTE reconocida por nombre: ${show} -> "${nombreGrupo}" ${jid}`);
      escuchaGrupo = grupoEscuchaDe(jid);
    } else {
      log(`AUDIO IGNORADO (grupo no registrado para escucha): "${nombreGrupo}" jid=${jid}` +
        ' -> agrega el grupo en "escuchar" del config o manda "!otzar <clave>" en ese grupo');
      return;
    }
  }
  if (esGrupo && !escuchaGrupo) return;  // (ya se avisó arriba)
"""),
    ("""async function resolverGruposEscucha() {
""", """// nombre (subject) de un grupo, con cache; '' si no se pudo leer
const _nombresGrupo = {};
async function nombreDeGrupo(jid) {
  if (_nombresGrupo[jid] !== undefined) return _nombresGrupo[jid];
  let n = '';
  try { const md = await sock.groupMetadata(jid); n = (md && md.subject) || ''; } catch (e) {}
  _nombresGrupo[jid] = n;
  return n;
}
// show de escuchar.<show>.nombre cuyo nombre esta contenido en el subject del grupo
function showPorNombre(subject) {
  const s = String(subject || '').toLowerCase().trim();
  if (!s) return null;
  for (const [show, datos] of Object.entries(CFG.escuchar || {})) {
    const n = String((datos && datos.nombre) || '').toLowerCase().trim();
    if (n && (s === n || s.includes(n) || n.includes(s))) return show;
  }
  return null;
}

async function resolverGruposEscucha() {
"""),
    ("""      const info = await sock.groupGetInviteInfo(cod);

      if (!info || !info.id) { log(`  escucha ${show}: sin ID (esta el robot en el grupo?)`); continue; }

      reg['escucha:' + show] = { id: info.id, nombre: info.subject || show, invite: datos.invite };
""", """      let info = null;
      try { info = await sock.groupGetInviteInfo(cod); }
      catch (e) { log(`  escucha ${show}: no pude leer la invitacion (${e.message || e}); busco el grupo por nombre`); }
      if ((!info || !info.id) && datos.nombre) {
        // === FUENTE POR NOMBRE (sep/2026): entre los grupos del robot
        try {
          const todos = await sock.groupFetchAllParticipating();
          const n = String(datos.nombre).toLowerCase().trim();
          const hit = Object.values(todos || {}).find(g => String(g.subject || '').toLowerCase().includes(n));
          if (hit) info = { id: hit.id, subject: hit.subject };
        } catch (e) { log(`  escucha ${show}: no pude listar los grupos (${e.message || e})`); }
      }
      if (!info || !info.id) { log(`  escucha ${show}: sin ID (esta el robot en el grupo? manda "!otzar ${show}" dentro del grupo)`); continue; }

      reg['escucha:' + show] = { id: info.id, nombre: info.subject || show, invite: datos.invite };
"""),
    ("""  log('GUARDADO: ' + nombre);
""", """  log(`GUARDADO [${item.show || '?'}]: ${nombre}  -> ${carpeta}`);
"""),
    # grupos de anuncio por nombre cuando el link da bad-request (config grupos_nombre)
    ("""      try {
        const info = await sock.groupGetInviteInfo(cod);
        if (!info || !info.id) { log(`  ${show}: una invitacion no trajo ID`); continue; }
        grupos.push({ id: info.id, nombre: info.subject || show, invite: inv });
        log(`  OK ${show} -> "${info.subject || show}"`);
      } catch (e) {
        log(`  ${show}: no pude leer una invitacion (${e.message || e})`);
      }
""", """      let info = null;
      try { info = await sock.groupGetInviteInfo(cod); }
      catch (e) { log(`  ${show}: no pude leer una invitacion (${e.message || e})`); }
      // === GRUPO POR NOMBRE (sep/2026): si el link no se puede leer, el grupo se
      // busca por su nombre entre los grupos del robot: config "grupos_nombre"
      // = { "<link>": "<nombre o parte del nombre>" }.
      if (!info || !info.id) {
        const nombreCfg = (CFG.grupos_nombre || {})[inv] || (CFG.grupos_nombre || {})[inv.split('?')[0]];
        const hit = nombreCfg ? await grupoPorNombre(nombreCfg) : null;
        if (hit) { info = { id: hit.id, subject: hit.subject }; log(`  OK ${show} -> "${hit.subject}" (por nombre, el link no sirve)`); }
        else if (nombreCfg) log(`  ${show}: tampoco encontre un grupo llamado "${nombreCfg}" (esta el robot dentro?)`);
      }
      if (!info || !info.id) { log(`  ${show}: una invitacion no trajo ID`); continue; }
      if (!grupos.some(g => g.id === info.id)) grupos.push({ id: info.id, nombre: info.subject || show, invite: inv });
      if (!String(info.subject || '').includes('(por nombre')) log(`  OK ${show} -> "${info.subject || show}"`);
"""),
    ("""// nombre (subject) de un grupo, con cache; '' si no se pudo leer
""", """// grupo del robot cuyo nombre contiene el texto dado (lista con cache por arranque)
let _todosLosGrupos = null;
async function grupoPorNombre(nombre) {
  const n = String(nombre || '').toLowerCase().trim();
  if (!n) return null;
  if (!_todosLosGrupos) {
    try { _todosLosGrupos = Object.values(await sock.groupFetchAllParticipating() || {}); }
    catch (e) { log('no pude listar los grupos: ' + (e.message || e)); return null; }
  }
  return _todosLosGrupos.find(g => String(g.subject || '').toLowerCase().includes(n)) || null;
}
// nombre (subject) de un grupo, con cache; '' si no se pudo leer
"""),
    # si una corrida anterior duplicó el aviso de grupo no registrado, se quita
    ("""  if (esGrupo && !escuchaGrupo) return;
  if (esGrupo && !escuchaGrupo) {
    if (audioDe(m)) log(`AUDIO IGNORADO (grupo no registrado para escucha): jid=${jid}` +
      ' -> agrega el grupo en "escuchar" del config o manda "!otzar <clave>" en ese grupo');
    return;
  }
""", """  if (esGrupo && !escuchaGrupo) return;  // (ya se avisó arriba)
""", "todos"),
    # fuente por nombre aunque el show no tenga link de invitacion (grupo de Nacach)
    ("""    if (!datos.invite) continue;

    const reg = leerRegistro();
""", """    if (!datos.invite && !datos.nombre) continue;  // sin link ni nombre no hay como ubicarlo

    const reg = leerRegistro();
""", "todos"),
    ("""      const cod = codigoDeInvite(datos.invite);

      if (!cod) { log(`  escucha ${show}: invitacion rara`); continue; }

      let info = null;
      try { info = await sock.groupGetInviteInfo(cod); }
      catch (e) { log(`  escucha ${show}: no pude leer la invitacion (${e.message || e}); busco el grupo por nombre`); }
""", """      const cod = codigoDeInvite(datos.invite);

      if (!cod && !datos.nombre) { log(`  escucha ${show}: invitacion rara`); continue; }

      let info = null;
      if (cod) {
        try { info = await sock.groupGetInviteInfo(cod); }
        catch (e) { log(`  escucha ${show}: no pude leer la invitacion (${e.message || e}); busco el grupo por nombre`); }
      }
""", "todos"),
    # nombre del Rab al frente del titulo (prefijo_titulo) y grupos de anuncio quitados del config
    ("""         ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.')));
""", """         ' ' + new Date(item.ts).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }).replace(':', '.')));
  // "prefijo_titulo" en escuchar -> <show>: el nombre del Rab al frente del titulo
  // (va a grupos generales), salvo que el titulo ya lo traiga.
  const _pref = String(((CFG.escuchar || {})[item.show] || {}).prefijo_titulo || '').trim();
  if (_pref && !base.toLowerCase().includes(_pref.replace(/[·:\\-–]+$/, '').trim().toLowerCase())) base = _pref + ' ' + base;
"""),
    ("""    const yaTiene = gruposDeShow(reg, show);
""", """    // los grupos registrados con un link que YA NO esta en el config se sueltan
    const yaTeniaTodos = gruposDeShow(reg, show);
    const yaTiene = yaTeniaTodos.filter(g => !g.invite || invites.includes(g.invite));
    if (yaTiene.length !== yaTeniaTodos.length) {
      log(`  ${show}: ya no anuncia en ${yaTeniaTodos.filter(g => !yaTiene.includes(g)).map(g => g.nombre).join(' + ')}`);
      if (yaTiene.length) reg[show] = { id: yaTiene[0].id, nombre: yaTiene[0].nombre, grupos: yaTiene };
      else delete reg[show];
    }
"""),
    # prefijo y titulo por defecto tambien para shows de chat directo
    ("""  const _pref = String(((CFG.escuchar || {})[item.show] || {}).prefijo_titulo || '').trim();
""", """  const _deDirecto = k => (((CFG.escuchar_directo || []).find(e => e && e.show === item.show) || {})[k]);
  const _pref = String(((CFG.escuchar || {})[item.show] || {}).prefijo_titulo || _deDirecto('prefijo_titulo') || '').trim();
""", "todos"),
    ("""  const _porDefecto = ((CFG.escuchar || {})[item.show] || {}).titulo_defecto;
""", """  const _porDefecto = ((CFG.escuchar || {})[item.show] || {}).titulo_defecto ||
    (((CFG.escuchar_directo || []).find(e => e && e.show === item.show) || {}).titulo_defecto);
""", "todos"),
    # el titulo puede venir con un link pegado (soundcloud): se quita el link
    ("""function esTituloValido(t) {
  if (!t) return false;
""", """// El rab a veces pega un link (soundcloud, drive) junto al titulo: fuera el link,
// el resto es el titulo. Si no queda nada, no era titulo.
function sinLinks(t) {
  return String(t || '').replace(/https?:\\/\\/\\S+/gi, ' ').replace(/\\bwww\\.\\S+/gi, ' ')
    .replace(/[ \\t]+/g, ' ').replace(/\\s*\\n\\s*/g, '\\n').trim();
}
function esTituloValido(t) {
  if (!t) return false;
"""),
    ("""    const captura = textoDe(m);
    if (captura && esTituloValido(captura)) { guardarAudio(item, captura); return; }
""", """    const captura = sinLinks(textoDe(m));
    if (captura && esTituloValido(captura)) { guardarAudio(item, captura); return; }
"""),
    ("""  // ---- TEXTO (posible titulo) ----
  if (cuerpo && esTituloValido(cuerpo)) {
    const i = audiosPendientes.findIndex(a => a.autor === autor);
    if (i >= 0) {
      const a = audiosPendientes.splice(i, 1)[0];
      clearTimeout(a.timer);
      guardarAudio(a, cuerpo);
      return;
    }
    const t = { texto: cuerpo, ts: Date.now(), autor };
""", """  // ---- TEXTO (posible titulo) ----
  const cuerpoTitulo = sinLinks(cuerpo);
  if (cuerpoTitulo && esTituloValido(cuerpoTitulo)) {
    const i = audiosPendientes.findIndex(a => a.autor === autor);
    if (i >= 0) {
      const a = audiosPendientes.splice(i, 1)[0];
      clearTimeout(a.timer);
      guardarAudio(a, cuerpoTitulo);
      return;
    }
    const t = { texto: cuerpoTitulo, ts: Date.now(), autor };
"""),
    # nombre del Rab en el mensaje del anuncio (prefijo_anuncio / sufijo_anuncio)
    ("""function armarMensaje(titulo, spotify, whatsapp, show, app) {
""", """// "prefijo_anuncio" / "sufijo_anuncio" en anunciar -> <show>: el nombre del Rab
// en el mensaje (p. ej. "Titulo · Rab Igal Snertz") cuando el feed no lo trae.
// Solo cambia el texto del anuncio; el link exacto se busca con el titulo original.
function tituloAnuncio(show, tit) {
  const d = (CFG.anunciar || {})[show] || {};
  let t = String(tit || '');
  const limpio = x => String(x || '').replace(/[·:\\-–]+$|^[·:\\-–]+/g, '').trim().toLowerCase();
  if (d.prefijo_anuncio && !t.toLowerCase().includes(limpio(d.prefijo_anuncio))) t = String(d.prefijo_anuncio).trim() + ' ' + t;
  if (d.sufijo_anuncio && !t.toLowerCase().includes(limpio(d.sufijo_anuncio))) t = t + ' ' + String(d.sufijo_anuncio).trim();
  return t;
}
function armarMensaje(titulo, spotify, whatsapp, show, app) {
"""),
    ("""      let texto = listos.map(x => `*${x.ep.tit}*\\n${x.epLink}`).join('\\n\\n');
""", """      let texto = listos.map(x => `*${tituloAnuncio(show, x.ep.tit)}*\\n${x.epLink}`).join('\\n\\n');
"""),
    ("""        let texto = appLink ? `🎧 *${ep.tit}*` : `*${ep.tit}*`;
""", """        let texto = appLink ? `🎧 *${tituloAnuncio(show, ep.tit)}*` : `*${tituloAnuncio(show, ep.tit)}*`;
"""),
    ("""      const texto = armarMensaje(ep.tit, epLink, wa, show, datos.app ? (ep.link || datos.app) : '');
""", """      const texto = armarMensaje(tituloAnuncio(show, ep.tit), epLink, wa, show, datos.app ? (ep.link || datos.app) : '');
"""),
    # reglas de titulo por show: quitar lineas, unir lineas, sufijo (Isaac Credi)
    ("""  const _porDefecto = ((CFG.escuchar || {})[item.show] || {}).titulo_defecto ||
    (((CFG.escuchar_directo || []).find(e => e && e.show === item.show) || {}).titulo_defecto);
  let base = limpiarTitulo(titulo) ||
""", """  const _porDefecto = ((CFG.escuchar || {})[item.show] || {}).titulo_defecto ||
    (((CFG.escuchar_directo || []).find(e => e && e.show === item.show) || {}).titulo_defecto);
  // === REGLAS DE TITULO por show (sep/2026), en escuchar -> <show>:
  //   "quitar_lineas": regex; las lineas del mensaje que casan se tiran
  //                    (p. ej. "1151 Siman 639" al frente de cada halaja)
  //   "unir_lineas":   con que se unen las lineas que quedan (", ")
  //   "sufijo_titulo": lo que va al final ("- Sr. Isaac Credi"), si no lo trae ya
  const _regla = ((CFG.escuchar || {})[item.show] || {});
  const _reglaDm = ((CFG.escuchar_directo || []).find(e => e && e.show === item.show) || {});
  const _r = k => _regla[k] || _reglaDm[k];
  if (titulo && (_r('quitar_lineas') || _r('unir_lineas'))) {
    let lineas = String(titulo).split(/\\r?\\n/).map(l => l.trim()).filter(Boolean);
    if (_r('quitar_lineas')) {
      try { const re = new RegExp(_r('quitar_lineas'), 'i'); const q = lineas.filter(l => !re.test(l)); if (q.length) lineas = q; } catch (e) {}
    }
    titulo = lineas.join(_r('unir_lineas') || ' ');
  }
  let base = limpiarTitulo(titulo) ||
"""),
    ("""  if (_pref && !base.toLowerCase().includes(_pref.replace(/[·:\\-–]+$/, '').trim().toLowerCase())) base = _pref + ' ' + base;
""", """  if (_pref && !base.toLowerCase().includes(_pref.replace(/[·:\\-–]+$/, '').trim().toLowerCase())) base = _pref + ' ' + base;
  const _suf = String(_r('sufijo_titulo') || '').trim();
  if (_suf && !base.toLowerCase().includes(_suf.replace(/^[·:\\-–]+/, '').trim().toLowerCase())) base = base + ' ' + _suf;
"""),
    ("""const ESTADO_FILE   = path.join(__dirname, 'estado_anuncios.json');
""", """const ESTADO_FILE   = path.join(__dirname, 'estado_anuncios.json');
// === NO REPETIR (otzar): memoria de titulos ya anunciados, por show ===
// Un shiur que ya salio no se vuelve a mandar aunque reaparezca en el feed con
// otro guid (re-subida, cambio de url, el mismo video en dos canales).
const TITULOS_FILE  = path.join(__dirname, 'estado_titulos.json');
function normTitulo(t) {
  return String(t || '').toLowerCase().replace(/[\\u0591-\\u05C7]/g, '')
    .replace(/[^\\p{L}\\p{N}]+/gu, ' ').trim().replace(/\\s+/g, ' ');
}
function titulosVistos(show, titulosDelFeed) {
  let e = {};
  try { e = JSON.parse(fs.readFileSync(TITULOS_FILE, 'utf8')); } catch (err) { e = {}; }
  const s = new Set(e[show] || []);
  for (const t of titulosDelFeed) { const k = normTitulo(t); if (k) s.add(k); }
  e[show] = Array.from(s).slice(-3000);
  try { fs.writeFileSync(TITULOS_FILE, JSON.stringify(e, null, 1)); } catch (err) {}
  return s;
}
"""),
    ("""    if (!nuevos.length) { log(`${show}: nada nuevo.`); continue; }
""", """    // NO REPETIR: los titulos de lo ya visto se aprenden del propio feed en cada corrida
    if (!(CFG.anunciar[show] || {}).permitir_repetidos) {
      const _titVistos = titulosVistos(show, items.filter(it => vistos.has(sacaGuid(it))).map(sacaTitulo));
      const _repetidos = [];
      const _enEstaCorrida = new Set();
      nuevos = nuevos.filter(ep => {
        const k = normTitulo(ep.tit);
        if (!k) return true;
        if (_titVistos.has(k) || _enEstaCorrida.has(k)) { _repetidos.push(ep); return false; }
        _enEstaCorrida.add(k);
        return true;
      });
      if (_repetidos.length) {
        log(`${show}: ${_repetidos.length} repetido(s) (mismo titulo ya anunciado), no se mandan: ` + _repetidos.map(e => e.tit.slice(0, 50)).join(' | '));
        for (const ep of _repetidos) { marcarAnunciado(show, ep.guid); estado[show].push(ep.guid); }
      }
    }
    if (!nuevos.length) { log(`${show}: nada nuevo.`); continue; }
"""),
    ("""  // ---- TEXTO (posible titulo) ----
""", """  // ---- AVISO (oct/2026): en un grupo FUENTE llego algo que NO es audio ----
  // (video, documento, link de SoundCloud/Drive/YouTube): no se sube, pero queda
  // escrito en el log para saber por que un shiur "no se mando".
  if (esGrupo && destinoAudio && destinoAudio.show) {
    const _c = contenido(m);
    const _tipo = _c.videoMessage ? 'un VIDEO'
      : _c.documentMessage ? ('un DOCUMENTO ' + (_c.documentMessage.fileName || ''))
      : /https?:\\/\\/\\S*(soundcloud|drive\\.google|youtu|spotify|dropbox|mega\\.nz)/i.test(cuerpo) ? 'un LINK' : '';
    if (_tipo) log(`SIN AUDIO en la fuente de ${destinoAudio.show}: llego ${_tipo} (${String(cuerpo || '').replace(/\\s+/g, ' ').slice(0, 90)}) -> no se sube; si es un shiur, que lo manden como audio`);
  }

  // ---- TEXTO (posible titulo) ----
"""),
    ("""}

conectar();
""", """}

// === UNA SOLA VENTANA (oct/2026) ===
// Dos ventanas del robot abiertas se roban la sesion de WhatsApp una a otra
// cada pocos segundos (codigo 440) y los audios que llegan en ese rato se
// pierden. robot.lock guarda el proceso que manda; se refresca cada 30 s.
// Si otra ventana viva lo refresco hace menos de 90 s, esta NO se conecta.
const LOCK_FILE = path.join(__dirname, 'robot.lock');
function otroRobotVivo() {
  try {
    const st = fs.statSync(LOCK_FILE);
    const pid = parseInt(fs.readFileSync(LOCK_FILE, 'utf8'), 10);
    if (!pid || pid === process.pid || Date.now() - st.mtimeMs > 90000) return 0;
    try { process.kill(pid, 0); return pid; } catch (e) { return e.code === 'EPERM' ? pid : 0; }
  } catch (e) { return 0; }
}
const _otro = otroRobotVivo();
if (_otro) {
  log(`*** YA HAY OTRO ROBOT ABIERTO (proceso ${_otro}). Esta ventana NO se conecta, para no pelearse la sesion.`);
  log('*** Deja abierta solo una ventana del robot. Esta se cierra en 15 segundos.');
  setTimeout(() => process.exit(0), 15000);
} else {
  const _lock = () => { try { fs.writeFileSync(LOCK_FILE, String(process.pid)); } catch (e) {} };
  _lock();
  setInterval(_lock, 30000);
  process.on('exit', () => {
    try { if (parseInt(fs.readFileSync(LOCK_FILE, 'utf8'), 10) === process.pid) fs.unlinkSync(LOCK_FILE); } catch (e) {}
  });
  conectar();
}
"""),
    ("""        for (const e of (CFG.escuchar_directo || [])) {
          if (e.show === showPrefijo) carpeta = e.carpetaDestino;
        }
        guardarAudio({ archivoTemp: p, ext: path.extname(f) || '.ogg', ts: st.mtimeMs, carpeta }, null);
""", """        for (const e of (CFG.escuchar_directo || [])) {
          if (e.show === showPrefijo) carpeta = e.carpetaDestino;
        }
        // (oct/2026) un audio de hilu/jabura/credi... que quedo esperando titulo va a SU
        // carpeta: antes caia en la de Peretz y alli se apartaba como "Shiur Familia Perets".
        if (!carpeta && CFG.escuchar && CFG.escuchar[showPrefijo] && CFG.escuchar[showPrefijo].carpetaDestino)
          carpeta = CFG.escuchar[showPrefijo].carpetaDestino;
        guardarAudio({ archivoTemp: p, ext: path.extname(f) || '.ogg', ts: st.mtimeMs, carpeta, show: showPrefijo }, null);
"""),
    ("""  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' && type !== 'append') return;
    for (const m of messages) {
""", """  // === RESCATE (oct/2026): lo que pide revisarRescate() llega aqui como historial ===
  sock.ev.on('messaging-history.set', async ({ messages }) => {
    try { await rescatarDeHistorial(messages || []); }
    catch (e) { log('RESCATE error: ' + (e.stack || e.message || e)); }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' && type !== 'append') return;
    for (const m of messages) anclar(m);
    for (const m of messages) {
"""),
    ("""async function procesarMensaje(m) {
""", """// === RESCATE (oct/2026) ===
// Si un audio se perdio (dos ventanas del robot peleandose la sesion, PC apagada
// mucho tiempo...), rescatar.json dice que shows rescatar y desde que fecha:
//   { "hilu": { "desde": "2026-10-06" }, "jabura": { "desde": "2026-10-06" } }
// El robot le pide a WhatsApp los ultimos mensajes del grupo fuente
// (fetchMessageHistory, anclado al ultimo mensaje visto en ese grupo) y procesa
// los audios que llegaron DESPUES del ultimo audio guardado en su carpeta (asi
// nunca duplica lo que ya estaba). Lo escribe instalar_otzar.py --rescatar=...
const ANCLAS_FILE  = path.join(__dirname, 'anclas.json');
const RESCATE_FILE = path.join(__dirname, 'rescatar.json');
let _anclas = null, _anclasSucio = false;
const _rescateVistos = new Set();
function _leerAnclas() {
  if (!_anclas) { try { _anclas = JSON.parse(fs.readFileSync(ANCLAS_FILE, 'utf8')); } catch (e) { _anclas = {}; } }
  return _anclas;
}
function anclar(m) {
  try {
    const k = m && m.key; const jid = k && k.remoteJid;
    if (!jid || !jid.endsWith('@g.us') || !k.id) return;
    const ts = Number(m.messageTimestamp) || 0;
    const a = _leerAnclas(); const prev = a[jid];
    if (prev && prev.ts >= ts) return;
    a[jid] = { key: { remoteJid: jid, id: k.id, fromMe: !!k.fromMe, participant: k.participant || undefined }, ts };
    _anclasSucio = true;
  } catch (e) {}
}
setInterval(() => {
  if (!_anclasSucio) return;
  _anclasSucio = false;
  try { fs.writeFileSync(ANCLAS_FILE, JSON.stringify(_anclas)); } catch (e) {}
}, 15000);
function _leerRescate() { try { return JSON.parse(fs.readFileSync(RESCATE_FILE, 'utf8')); } catch (e) { return null; } }
function _guardarRescate(r) { try { fs.writeFileSync(RESCATE_FILE, JSON.stringify(r, null, 2)); } catch (e) {} }
function _fuenteDe(show, reg) {
  return reg['escucha:' + show] || (show === 'peretz' ? reg.peretz : null);
}
function _carpetaDe(show) {
  const e = (CFG.escuchar || {})[show];
  if (e && e.carpetaDestino) return e.carpetaDestino;
  const d = (CFG.escuchar_directo || []).find(x => x && x.show === show);
  return d ? d.carpetaDestino : null;
}
// el ultimo audio guardado en la carpeta del show: lo anterior ya esta, no se repite
function _ultimoAudioMs(carpeta) {
  let max = 0;
  try {
    for (const f of fs.readdirSync(carpeta)) {
      if (!/\\.(m4a|mp3|ogg|opus|aac|wav|amr)$/i.test(f)) continue;
      try { const t = fs.statSync(path.join(carpeta, f)).mtimeMs; if (t > max) max = t; } catch (e) {}
    }
  } catch (e) {}
  return max;
}
async function revisarRescate() {
  if (!listo || !sock) return;
  const pend = _leerRescate();
  if (!pend) return;
  const reg = leerRegistro();
  let cambio = false;
  for (const [show, r] of Object.entries(pend)) {
    if (!r || r.hecho || r.rendido) continue;
    const fuente = _fuenteDe(show, reg);
    if (!fuente || !fuente.id) {
      if (!r.avisado) { log(`RESCATE ${show}: no se cual es su grupo fuente; no puedo rescatar.`); r.avisado = true; cambio = true; }
      continue;
    }
    const ahora = Date.now();
    if (r.pedido && ahora - r.pedido < 10 * 60000) continue;   // esperar la respuesta
    if ((r.intentos || 0) >= 24) {
      log(`RESCATE ${show}: WhatsApp no mando el historial de "${fuente.nombre}" tras 24 intentos (4 horas). Guarda el audio a mano en su carpeta.`);
      r.rendido = true; cambio = true; continue;
    }
    const a = _leerAnclas()[fuente.id];
    const key = a ? a.key : { remoteJid: fuente.id, fromMe: false,
      id: '3EB0' + Array.from({ length: 16 }, () => '0123456789ABCDEF'[Math.floor(Math.random() * 16)]).join('') };
    const tsMs = a ? a.ts * 1000 : ahora;
    try {
      await sock.fetchMessageHistory(r.cuantos || 50, key, tsMs);
      r.pedido = ahora; r.intentos = (r.intentos || 0) + 1; cambio = true;
      log(`RESCATE ${show}: pedi a WhatsApp los ultimos mensajes de "${fuente.nombre}" ` +
          `(${a ? 'desde el ultimo mensaje visto' : 'sin mensaje de referencia todavia'}), intento ${r.intentos}.`);
    } catch (e) { log(`RESCATE ${show}: no pude pedir el historial (${e.message || e})`); }
  }
  if (cambio) _guardarRescate(pend);
}
setInterval(() => { revisarRescate().catch(e => log('RESCATE error: ' + (e.message || e))); }, 20000);
async function rescatarDeHistorial(messages) {
  for (const m of messages) anclar(m);
  const pend = _leerRescate();
  if (!pend) return;
  const reg = leerRegistro();
  let cambio = false;
  for (const [show, r] of Object.entries(pend)) {
    if (!r || r.hecho) continue;
    const fuente = _fuenteDe(show, reg);
    if (!fuente || !fuente.id) continue;
    const delGrupo = messages.filter(m => m && m.key && m.key.remoteJid === fuente.id)
      .sort((x, y) => Number(x.messageTimestamp) - Number(y.messageTimestamp));
    if (!delGrupo.length) continue;
    const carpeta = _carpetaDe(show);
    const desde = Math.max(Date.parse(r.desde || 0) || 0, (carpeta ? _ultimoAudioMs(carpeta) : 0) + 60000);
    const nuevos = delGrupo.filter(m => Number(m.messageTimestamp) * 1000 > desde && !_rescateVistos.has(m.key.id));
    const audios = nuevos.filter(m => audioDe(m));
    log(`RESCATE ${show}: llegaron ${delGrupo.length} mensajes de "${fuente.nombre}"; ` +
        `${audios.length} audio(s) sin guardar desde ${new Date(desde).toLocaleString('es-MX')}.`);
    for (const m of nuevos) {
      _rescateVistos.add(m.key.id);
      try { await procesarMensaje(m); } catch (e) { log('RESCATE mensaje: ' + (e.message || e)); }
    }
    r.hecho = true; r.audios = (r.audios || 0) + audios.length; r.cuando = new Date().toISOString();
    cambio = true;
  }
  if (cambio) _guardarRescate(pend);
}

async function procesarMensaje(m) {
"""),
    ("""// === RESCATE (oct/2026) ===
// Si un audio se perdio""", """// === PLATAFORMAS, PLANTILLA Y TEMAS (oct/2026) ===
// Cada anuncio lleva, ademas de Spotify, el link del episodio en Apple Podcasts
// (API publica de iTunes, sin llaves) y el del show en Amazon Music / SoundCloud.
// plataformas.json lo escribe jabura\\plataformas.py (una vez al dia, desde ANUNCIAR);
// "apple" / "amazon" / "soundcloud" en anunciar.<show> lo pisan.
const PLATAFORMAS_FILE = path.join(__dirname, 'plataformas.json');
function _plataformasDe(show) {
  let p = {};
  try { p = (JSON.parse(fs.readFileSync(PLATAFORMAS_FILE, 'utf8')) || {})[show] || {}; } catch (e) {}
  const d = (CFG.anunciar || {})[show] || {};
  const apple = String(d.apple || p.apple || '');
  const id = String(p.apple_id || (apple.match(/id(\\d{5,})/) || [])[1] || '');
  return { apple, apple_id: id, amazon: String(d.amazon || p.amazon || ''), soundcloud: String(d.soundcloud || p.soundcloud || '') };
}
const _appleCache = {};
async function linkApple(show, titulo) {
  const pl = _plataformasDe(show);
  if (!pl.apple_id) return pl.apple;
  try {
    let c = _appleCache[pl.apple_id];
    if (!c || Date.now() - c.t > 10 * 60000) {
      const j = JSON.parse(await fetchTexto(`https://itunes.apple.com/lookup?id=${pl.apple_id}&entity=podcastEpisode&limit=200`));
      c = _appleCache[pl.apple_id] = { t: Date.now(), lista: (j.results || []).filter(r => r.wrapperType === 'podcastEpisode') };
      if (!pl.apple) { const sh = (j.results || []).find(r => r.wrapperType === 'track'); if (sh && sh.collectionViewUrl) pl.apple = sh.collectionViewUrl.split('?')[0]; }
    }
    const k = normTitulo(titulo);
    const ep = c.lista.find(r => normTitulo(r.trackName) === k) ||
      c.lista.find(r => { const n = normTitulo(r.trackName); return n && k && Math.min(n.length, k.length) > 12 && (n.includes(k) || k.includes(n)); });
    if (ep && ep.trackViewUrl) return ep.trackViewUrl.replace(/&uo=\\d+$/, '');
  } catch (e) {}
  return pl.apple;   // el episodio aun no aparece en Apple: el link del show
}
async function bloquePlataformas(show, titulo) {
  const pl = _plataformasDe(show);
  const out = [];
  const apple = await linkApple(show, titulo);
  if (apple) out.push(['Apple Podcasts', apple]);
  if (pl.amazon) out.push(['Amazon Music', pl.amazon]);
  if (pl.soundcloud) out.push(['SoundCloud', pl.soundcloud]);
  return out;
}
function conPlataformas(texto, lista) {
  if (!lista || !lista.length) return texto;
  const extra = lista.map(([n, l]) => `${n}\\n${l}`).join('\\n');
  const i = texto.lastIndexOf('\\n\\n📢');
  return i >= 0 ? texto.slice(0, i) + '\\n' + extra + texto.slice(i) : texto + '\\n' + extra;
}
// "plantilla" en anunciar.<show>: lista de bloques con {fecha_hebrea} {fecha} {titulo}
// {spotify} {apple} {amazon} {soundcloud} {whatsapp} {dedicatoria}; un bloque cuyo
// dato falta no sale. Los bloques van separados por una linea en blanco.
const _MESES_HE = { Tishri: 'Tishre', Heshvan: 'Jeshvan', Cheshvan: 'Jeshvan' };
function fechaHebrea(ms) {
  try {
    const p = new Intl.DateTimeFormat('en-u-ca-hebrew', { day: 'numeric', month: 'long' }).formatToParts(new Date(ms));
    const dia = (p.find(x => x.type === 'day') || {}).value, mes = (p.find(x => x.type === 'month') || {}).value;
    return dia && mes ? `${dia} de ${_MESES_HE[mes] || mes}` : '';
  } catch (e) { return ''; }
}
function fechaCivil(ms) {
  return new Date(ms).toLocaleDateString('es-MX', { day: 'numeric', month: 'long' })
    .replace(/de (\\p{L})/u, (a, b) => 'de ' + b.toUpperCase());
}
function armarPlantilla(datos, v) {
  const pl = Object.fromEntries((v.plataformas || []).map(([n, l]) => [n, l]));
  const val = { fecha_hebrea: fechaHebrea(v.fecha), fecha: fechaCivil(v.fecha), titulo: v.titulo || '',
    spotify: v.spotify || '', apple: pl['Apple Podcasts'] || '', amazon: pl['Amazon Music'] || '',
    soundcloud: pl['SoundCloud'] || '', whatsapp: v.whatsapp || '', dedicatoria: datos.dedicatoria || '' };
  const bloques = Array.isArray(datos.plantilla) ? datos.plantilla : String(datos.plantilla || '').split(/\\n\\s*\\n/);
  return bloques.map(b => {
    let falta = false;
    const t = String(b).replace(/\\{(\\w+)\\}/g, (a, k) => { if (!val[k]) falta = true; return val[k] || ''; });
    return falta ? '' : t.trim();
  }).filter(Boolean).join('\\n\\n');
}
// "temas": true en escuchar / escuchar_directo -> <show>. El que manda pone solo
// "Dia 21. Domingo"; el titulo sale del tema de la semana: "#21 Encendido de Velas (1)".
// Los temas vienen de tools/otzar/temas/<show>.json en GitHub (se actualizan sin
// tocar la PC) y de <show>\\temas.json en la PC ("!tema <show> <dia> <tema>" por
// WhatsApp lo escribe); el de la PC manda. El dia de la semana fija la fecha del
// episodio y, con "esperar_fecha" en anunciar, el anuncio sale ese dia.
const _temasRemotos = {};
async function cargarTemasRemotos() {
  const shows = new Set([
    ...Object.entries(CFG.escuchar || {}).filter(([, v]) => v && v.temas).map(([k]) => k),
    ...(CFG.escuchar_directo || []).filter(e => e && e.temas).map(e => e.show)]);
  for (const sh of shows) {
    try {
      const j = JSON.parse(await fetchTexto(`https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/otzar/temas/${sh}.json`));
      if (Array.isArray(j)) _temasRemotos[sh] = j;
    } catch (e) {}
  }
}
setTimeout(() => { cargarTemasRemotos().catch(() => {}); }, 5000);
setInterval(() => { cargarTemasRemotos().catch(() => {}); }, 30 * 60000);
function _archivoTemas(show) { const c = _carpetaDe(show); return c ? path.join(path.dirname(c), 'temas.json') : null; }
function temasDe(show) {
  let local = [];
  try { local = JSON.parse(fs.readFileSync(_archivoTemas(show), 'utf8')); } catch (e) {}
  const por = {};
  for (const t of [].concat(_temasRemotos[show] || [], Array.isArray(local) ? local : []))
    if (t && Number(t.desde) && t.tema) por[Number(t.desde)] = String(t.tema).trim();
  return Object.keys(por).map(Number).sort((a, b) => a - b).map(d => ({ desde: d, tema: por[d] }));
}
const _DIAS_SEMANA = { domingo: 0, lunes: 1, martes: 2, miercoles: 3, jueves: 4, viernes: 5, sabado: 6 };
function tituloPorTema(show, texto, carpeta) {
  const plano = String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  let n = Number((plano.match(/dia\\s*#?\\s*(\\d{1,4})/) || plano.match(/#\\s*(\\d{1,4})/) || plano.match(/\\b(\\d{1,4})\\b/) || [])[1] || 0);
  if (!n) {   // sin numero: el que sigue al ultimo guardado
    let max = 0;
    try { for (const f of fs.readdirSync(carpeta)) { const mm = f.match(/^#\\s*(\\d+)/); if (mm) max = Math.max(max, +mm[1]); } } catch (e) {}
    if (!max) return null;
    n = max + 1;
  }
  const lista = temasDe(show).filter(t => t.desde <= n);
  const t = lista[lista.length - 1];
  if (!t) log(`TEMAS ${show}: no hay tema para el dia ${n}; se guarda como "#${n}". Avisa el tema de la semana.`);
  const titulo = t ? `#${n} ${t.tema} (${n - t.desde + 1})` : `#${n}`;
  let fecha = 0;
  const dm = plano.match(/\\b(domingo|lunes|martes|miercoles|jueves|viernes|sabado)\\b/);
  if (dm) {
    const hoy = new Date(); hoy.setHours(6, 0, 0, 0);
    fecha = hoy.getTime() + ((_DIAS_SEMANA[dm[1]] - hoy.getDay() + 7) % 7) * 86400000;
    // en orden: un dia mayor nunca cae antes que uno menor ya guardado
    const ef = path.join(__dirname, 'temas_estado.json');
    let st = {}; try { st = JSON.parse(fs.readFileSync(ef, 'utf8')); } catch (e) {}
    const u = st[show];
    if (u && n > u.n) while (fecha <= u.fecha) fecha += 7 * 86400000;
    if (!u || n >= u.n) { st[show] = { n, fecha }; try { fs.writeFileSync(ef, JSON.stringify(st)); } catch (e) {} }
  }
  return { titulo, fecha };
}

// === RESCATE (oct/2026) ===
// Si un audio se perdio"""),
    ("""  const directo = chatDirecto();
""", """  const directo = chatDirecto();

  // === "!tema <show> <dia> <tema>" (oct/2026), en chat privado con el robot ===
  if (!esGrupo) {
    const _mt = /^!tema\\s+(\\w+)\\s+(\\d{1,4})\\s+([\\s\\S]+)$/i.exec(String(textoDe(m) || '').trim());
    if (_mt) {
      const show = _mt[1].toLowerCase(), desde = Number(_mt[2]), tema = _mt[3].replace(/\\s+/g, ' ').trim();
      const f = _archivoTemas(show);
      if (!f) { log(`TEMAS: "${show}" no tiene carpeta; ignoro "!tema"`); return; }
      let l = []; try { l = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) {}
      l = (Array.isArray(l) ? l : []).filter(t => Number(t.desde) !== desde).concat([{ desde, tema }]).sort((a, b) => a.desde - b.desde);
      try { fs.writeFileSync(f, JSON.stringify(l, null, 2)); } catch (e) {}
      log(`TEMAS ${show}: desde el dia ${desde} el tema es "${tema}"`);
      try { await sock.sendMessage(jid, { text: `✅ ${show}: desde el día ${desde} el tema es "${tema}"\\n#${desde} ${tema} (1), #${desde + 1} ${tema} (2)...` }); } catch (e) {}
      return;
    }
  }
"""),
    ("""  if (titulo && (_r('quitar_lineas') || _r('unir_lineas'))) {
""", """  // === TEMAS (oct/2026): "Dia 21. Domingo" -> "#21 Encendido de Velas (1)", con fecha de ese dia ===
  if (_r('temas')) {
    const _t = tituloPorTema(item.show, String(titulo || ''), carpeta);
    if (_t) { titulo = _t.titulo; if (_t.fecha) item._fecha = _t.fecha; }
  }
  if (titulo && (_r('quitar_lineas') || _r('unir_lineas'))) {
"""),
    ("""  log(`GUARDADO [${item.show || '?'}]: ${nombre}  -> ${carpeta}`);
""", """  if (item._fecha) { try { fs.utimesSync(destino, item._fecha / 1000, item._fecha / 1000); } catch (e) {} }   // fecha del episodio = su dia
  log(`GUARDADO [${item.show || '?'}]: ${nombre}  -> ${carpeta}`);
"""),
    ("""      .filter(ep => !vistos.has(ep.guid))
""", """      .filter(ep => !vistos.has(ep.guid))
      .filter(ep => !((CFG.anunciar[show] || {}).esperar_fecha && ep.fecha > Date.now()))   // (oct/2026) sale en su dia
"""),
    ("""      const epLink = (spotShow && !sinSpot)
""", """      let epLink = (spotShow && !sinSpot)
"""),
    ("""      // BLINDAJE: sin link exacto NO se anuncia (ni con link del show, ni solo whatsapp)
      if (!epLink) {
""", """      // (oct/2026) "spotify_espera_horas": N en anunciar.<show>: si Spotify no toma el
      // episodio en N horas, sale con el link del SHOW en vez de esperar para siempre
      // (asi se quedaba trabado TorahAnytime).
      const _espera = Number(datos.spotify_espera_horas || 0);
      if (!epLink && spotShow && !sinSpot && _espera > 0 && ep.fecha && Date.now() - ep.fecha > _espera * 3600000) {
        log(`${show}: "${ep.tit.slice(0, 45)}" Spotify no lo tomo en ${_espera} h; sale con el link del show.`);
        epLink = spotShow;
      }
      // BLINDAJE: sin link exacto NO se anuncia (ni con link del show, ni solo whatsapp)
      if (!epLink) {
"""),
    ("""      const texto = armarMensaje(tituloAnuncio(show, ep.tit), epLink, wa, show, datos.app ? (ep.link || datos.app) : '');
""", """      const _plat = await bloquePlataformas(show, ep.tit);
      const texto = datos.plantilla
        ? armarPlantilla(datos, { titulo: tituloAnuncio(show, ep.tit), spotify: epLink, whatsapp: datos.whatsapp_link || wa, fecha: ep.fecha || Date.now(), plataformas: _plat })
        : conPlataformas(armarMensaje(tituloAnuncio(show, ep.tit), epLink, wa, show, datos.app ? (ep.link || datos.app) : ''), _plat);
"""),
    ("""        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
""", """        if (wa && !datos.sin_whatsapp) texto += `\\nWhatsapp\\n${wa}`;
        texto += `\\n\\n${DIFUNDE[idiomaDeShow(show)]}`;
        {
          const _plat = await bloquePlataformas(show, ep.tit);
          texto = datos.plantilla
            ? armarPlantilla(datos, { titulo: tituloAnuncio(show, ep.tit), spotify: spotShow, whatsapp: datos.whatsapp_link || wa, fecha: ep.fecha || Date.now(), plataformas: _plat })
            : conPlataformas(texto, _plat);
        }
"""),
    ("""    r.hecho = true; r.audios = (r.audios || 0) + audios.length; r.cuando = new Date().toISOString();
    cambio = true;
""", """    r.hecho = true; r.audios = (r.audios || 0) + audios.length; r.cuando = new Date().toISOString();
    // (oct/2026) se guarda SOLO este show, leyendo el archivo fresco: dos respuestas
    // del historial al mismo tiempo se pisaban y un rescate hecho se volvia a pedir
    { const _f = _leerRescate() || {}; _f[show] = Object.assign(_f[show] || {}, r); _guardarRescate(_f); }
"""),
    ("""  if (cambio) _guardarRescate(pend);
}
setInterval(() => { revisarRescate()""", """  if (cambio) {   // (oct/2026) sin pisar un rescate que termino mientras se pedia
    const _f = _leerRescate() || {};
    for (const [k, v] of Object.entries(pend)) {
      const cur = _f[k] || {};
      if (cur.hecho) continue;
      _f[k] = Object.assign(cur, { pedido: v.pedido, intentos: v.intentos, avisado: v.avisado, rendido: v.rendido });
    }
    _guardarRescate(_f);
  }
}
setInterval(() => { revisarRescate()"""),
    ("""  // ---- AVISO (oct/2026): en un grupo FUENTE llego algo que NO es audio ----
""", """  // ---- MEKOROT (oct/2026): "guardar_documentos": true en escuchar.<show> ----
  // Los PDF / Word que mandan al grupo fuente (los mekorot del shiur) se guardan en
  // la carpeta del show como "מקורות · nombre.pdf": el publicador los sube a
  // archive.org y la app los muestra en מראי מקומות. No se anuncian.
  if (esGrupo && destinoAudio && destinoAudio.show && ((CFG.escuchar || {})[destinoAudio.show] || {}).guardar_documentos) {
    const _doc = contenido(m).documentMessage;
    const _nom = _doc ? String(_doc.fileName || '') : '';
    if (_doc && /\\.(pdf|docx?)$/i.test(_nom)) {
      try {
        const _buf = await downloadMediaMessage({ ...m, message: contenido(m) }, 'buffer', {},
          { logger: pino({ level: 'silent' }), reuploadRequest: sock.updateMediaMessage });
        const _carp = destinoAudio.carpeta;
        fs.mkdirSync(_carp, { recursive: true });
        const _base = 'מקורות · ' + limpiarTitulo(_nom.replace(/\\.[^.]+$/, ''));
        const _ext = path.extname(_nom).toLowerCase();
        if (fs.existsSync(path.join(_carp, _base + _ext))) { log(`MEKOROT [${destinoAudio.show}]: "${_base}${_ext}" ya estaba`); return; }
        fs.writeFileSync(path.join(_carp, _base + _ext), _buf);
        log(`GUARDADO MEKOROT [${destinoAudio.show}]: ${_base}${_ext}  -> ${_carp}`);
      } catch (e) { log('No pude guardar el documento: ' + (e.message || e)); }
      return;
    }
  }

  // ---- AVISO (oct/2026): en un grupo FUENTE llego algo que NO es audio ----
"""),
    ("""    const nuevos = delGrupo.filter(m => Number(m.messageTimestamp) * 1000 > desde && !_rescateVistos.has(m.key.id));
""", """    const nuevos = delGrupo.filter(m => !_rescateVistos.has(m.key.id) && (Number(m.messageTimestamp) * 1000 > desde ||
      // (oct/2026) "documentos": los PDF/Word (mekorot) desde la fecha pedida, aunque haya un audio despues
      (r.documentos && contenido(m).documentMessage && Number(m.messageTimestamp) * 1000 > (Date.parse(r.desde || 0) || 0))));
"""),
    ("""  return punt >= 0.90 ? mejor : null;   // menos de 90% de parecido: NO se manda
""", """  if (punt >= 0.90) return mejor;
  // (oct/2026) segunda mirada, por PALABRAS: Spotify a veces le pone otro titulo al
  // mismo shiur ("Rab Joshua Hilu - No intentes cambiarla" vs "Parashat bereshit -
  // No intentes cambiarla Rab Joshua Hilu"). Se comparan solo las palabras que dicen
  // de que trata, sin el nombre del Rab ni las que se repiten en todo el show.
  const _pp = elegirPorPalabras(candidatos, tituloOriginal || objetivo, marcaObjetivo);
  if (_pp) { if (diag) diag.porPalabras = _pp.name; return _pp; }
  return null;   // no se parece lo suficiente: NO se manda
"""),
    ("""// ---- LLAVES OFICIALES (spotify_keys.txt: linea1=ID, linea2=secret) ----
""", """// Palabras que no dicen de que trata el shiur
const _PALABRAS_RELLENO = new Set(('de del la las el los en y o a al con por para que un una su sus es se lo le ' +
  'the of and to in on for with a an is by from ' +
  'rab rav rabbi harav hagaon jajam hacham sr shlita shlit שליטא הרב הגאון רבי מרן ' +
  'parashat parasha parsha perasha parashá perashat פרשת שיעור shiur clase class soundcloud spotify podcast').split(/\\s+/));
function _palabrasClave(t) {
  return String(t || '').normalize('NFD').replace(/[̀-֑ͯ-ׇ]/g, '').toLowerCase()
    .replace(/[^\\p{L}\\p{N}]+/gu, ' ').trim().split(/\\s+/)
    .filter(w => w.length >= 3 && !/^\\d+$/.test(w) && !_PALABRAS_RELLENO.has(w));
}
function elegirPorPalabras(candidatos, titulo, marcaObjetivo) {
  if (!candidatos.length) return null;
  // las palabras que salen en muchos episodios del show (el nombre del Rab, la serie) no cuentan
  const freq = new Map();
  for (const e of candidatos) for (const w of new Set(_palabrasClave(e.name))) freq.set(w, (freq.get(w) || 0) + 1);
  const comun = w => candidatos.length >= 5 && (freq.get(w) || 0) / candidatos.length > 0.3;
  const nucleo = arr => [...new Set(arr.filter(w => !comun(w)))];
  const objetivo = nucleo(_palabrasClave(titulo));
  if (objetivo.length < 2) return null;
  const puntos = [];
  for (const e of candidatos) {
    if (marcadores(e.name) !== marcaObjetivo) continue;          // "(5)" nunca es "(6)"
    const suyo = nucleo(_palabrasClave(e.name));
    if (suyo.length < 2) continue;
    const comunes = suyo.filter(w => objetivo.includes(w)).length;
    const menor = Math.min(suyo.length, objetivo.length);
    const ok = menor <= 2 ? comunes === menor : (comunes >= 3 && comunes / menor >= 0.8);
    if (ok) puntos.push({ e, comunes, cubre: comunes / Math.max(suyo.length, objetivo.length) });
  }
  if (!puntos.length) return null;
  puntos.sort((a, b) => b.comunes - a.comunes || b.cubre - a.cubre);
  // si dos episodios distintos empatan, no se adivina
  if (puntos.length > 1 && puntos[1].comunes === puntos[0].comunes && puntos[1].cubre === puntos[0].cubre &&
      puntos[1].e.id !== puntos[0].e.id) return null;
  return puntos[0].e;
}

// ---- LLAVES OFICIALES (spotify_keys.txt: linea1=ID, linea2=secret) ----
"""),
    ("""  if (pl.soundcloud) out.push(['SoundCloud', pl.soundcloud]);
""", """  // (oct/2026) el link del EPISODIO en SoundCloud (lo deja jabura\\\\soundcloud_subir.py); si no, el del perfil
  let _sc = pl.soundcloud;
  try {
    const _m = JSON.parse(fs.readFileSync(path.join(__dirname, 'soundcloud_episodios.json'), 'utf8'))[show] || {};
    const _k = normTitulo(titulo);
    for (const [t, u] of Object.entries(_m)) if (u && normTitulo(t) === _k) { _sc = u; break; }
  } catch (e) {}
  if (_sc) out.push(['SoundCloud', _sc]);
"""),
    # (oct/2026) Tawil: calendario por numero (sin Shabat ni Yom Tov), dedicatoria de la semana, "#22- Tema (2)"
    ("""  return { titulo, fecha };
}

// === RESCATE (oct/2026) ===
""", """  return { titulo, fecha };
}

// === CALENDARIO (oct/2026): "calendario": {"n": 21, "fecha": "2026-10-11"} en anunciar.<show> ===
// Un shiur por dia: el #21 sale el 11/10, el #22 el dia siguiente que se puede, etc.
// Sabado y Yom Tov (diaspora) no cuentan y ese dia no se manda nada ("no_shabat": true).
// El de un dia que ya paso se marca en silencio (no sale tarde); el de manana espera.
let _hebcal = null;
try { _hebcal = require('@hebcal/core'); } catch (e) {}
const _YOM_TOV = new Set(['2026-10-03', '2026-10-04', '2027-04-22', '2027-04-23', '2027-04-28', '2027-04-29',
  '2027-06-11', '2027-06-12', '2027-10-02', '2027-10-03', '2027-10-11', '2027-10-16', '2027-10-17', '2027-10-23',
  '2027-10-24', '2028-04-11', '2028-04-12', '2028-04-17', '2028-04-18', '2028-05-31', '2028-06-01', '2028-09-21',
  '2028-09-22', '2028-09-30']);
function _diaLocal(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function esYomTov(d) {
  if (_hebcal) {
    try {
      const ev = _hebcal.HebrewCalendar.getHolidaysOnDate(new _hebcal.HDate(new Date(d.getFullYear(), d.getMonth(), d.getDate())), false) || [];
      return ev.some(e => e.getFlags() & _hebcal.flags.CHAG);
    } catch (e) {}
  }
  return _YOM_TOV.has(_diaLocal(d));
}
function diaSinEnvio(d) { return d.getDay() === 6 || esYomTov(d); }
function numeroDe(tit) { const m = String(tit || '').match(/^\\s*#\\s*(\\d{1,4})/); return m ? Number(m[1]) : 0; }
function fechaDeNumero(cal, n) {
  const [y, mo, da] = String(cal.fecha).split('-').map(Number);
  const d = new Date(y, mo - 1, da, 6, 0, 0, 0);
  let k = n - Number(cal.n);
  const paso = k >= 0 ? 1 : -1;
  for (let i = 0; k !== 0 && i < 3000; i++) {
    d.setDate(d.getDate() + paso);
    if (!diaSinEnvio(d)) k -= paso;
  }
  return d.getTime();
}
// dedicatoria de la semana: en tools/otzar/temas/<show>.json, {"desde": 22, "dedicatoria": "..."}
function dedicatoriaDe(show, tit) {
  const n = numeroDe(tit);
  if (!n) return '';
  let local = [];
  try { local = JSON.parse(fs.readFileSync(_archivoTemas(show), 'utf8')); } catch (e) {}
  const por = {};
  for (const t of [].concat(_temasRemotos[show] || [], Array.isArray(local) ? local : []))
    if (t && Number(t.desde) && t.dedicatoria) por[Number(t.desde)] = String(t.dedicatoria).trim();
  const d = Object.keys(por).map(Number).filter(x => x <= n).sort((a, b) => a - b).pop();
  return d ? por[d] : '';
}
// el titulo del anuncio sale del tema: "#22- Encendido de Velas (2)" (asi lo quieren en el grupo)
function tituloDeTema(show, tit) {
  const n = numeroDe(tit);
  const esc = (CFG.escuchar || {})[show] || {};
  if (!n || !esc.temas) return tit;
  const t = temasDe(show).filter(x => x.desde <= n).pop();
  return t ? `#${n}- ${t.tema} (${n - t.desde + 1})` : String(tit).replace(/^\\s*#\\s*(\\d+)\\s*-?\\s*/, '#$1- ');
}

// === RESCATE (oct/2026) ===
"""),
    ("""function tituloAnuncio(show, tit) {
  const d = (CFG.anunciar || {})[show] || {};
  let t = String(tit || '');
""", """function tituloAnuncio(show, tit) {
  const d = (CFG.anunciar || {})[show] || {};
  let t = String(tituloDeTema(show, tit) || '');
"""),
    ("""    if ((CFG.anunciar[show] || {}).pausado) { log(`${show}: EN PAUSA, no se anuncia (pausado en el config).`); continue; }
""", """    if ((CFG.anunciar[show] || {}).pausado) { log(`${show}: EN PAUSA, no se anuncia (pausado en el config).`); continue; }
    if ((CFG.anunciar[show] || {}).no_shabat && diaSinEnvio(new Date())) { log(`${show}: hoy es Shabat o Yom Tov, no se manda.`); continue; }
"""),
    ("""      .filter(ep => !vistos.has(ep.guid))
      .filter(ep => !((CFG.anunciar[show] || {}).esperar_fecha && ep.fecha > Date.now()))   // (oct/2026) sale en su dia
      .sort((a, b) => enOrden ? (a.fecha - b.fecha) : (b.fecha - a.fecha));
""", """      .filter(ep => !vistos.has(ep.guid))
      .map(ep => {   // (oct/2026) "calendario": la fecha sale del numero del shiur, no de cuando se subio
        const _cal = (CFG.anunciar[show] || {}).calendario;
        if (_cal && _cal.n && _cal.fecha && numeroDe(ep.tit)) { ep.fecha = fechaDeNumero(_cal, numeroDe(ep.tit)); ep.cal = true; }
        return ep;
      })
      .filter(ep => !((CFG.anunciar[show] || {}).esperar_fecha && ep.fecha > Date.now()))   // (oct/2026) sale en su dia
      .sort((a, b) => enOrden ? (a.fecha - b.fecha) : (b.fecha - a.fecha));
    {
      const _hoy0 = new Date(); _hoy0.setHours(0, 0, 0, 0);
      const _pasados = nuevos.filter(ep => ep.cal && ep.fecha < _hoy0.getTime());
      if (_pasados.length) {
        log(`${show}: ${_pasados.length} shiur(es) de dias que ya pasaron, no salen tarde: ` + _pasados.map(e => e.tit.slice(0, 40)).join(' | '));
        for (const ep of _pasados) { marcarAnunciado(show, ep.guid); estado[show].push(ep.guid); }
        nuevos = nuevos.filter(ep => !_pasados.includes(ep));
      }
    }
"""),
    ("""armarPlantilla(datos, { titulo: tituloAnuncio(show, ep.tit), """, """armarPlantilla(datos, { dedicatoria: dedicatoriaDe(show, ep.tit), titulo: tituloAnuncio(show, ep.tit), """, True),
    ("""dedicatoria: datos.dedicatoria || '' };""", """dedicatoria: v.dedicatoria || datos.dedicatoria || '' };"""),
    ("""  const titulo = t ? `#${n} ${t.tema} (${n - t.desde + 1})` : `#${n}`;""", """  const titulo = t ? `#${n}- ${t.tema} (${n - t.desde + 1})` : `#${n}`;"""),
    # (oct/2026) anunciar se relee en cada corrida (una pausa vale sin reiniciar); temas desde la rama de trabajo
    ("""  log(esVigilante ? `=== VIGILANTE: reintento automatico ${vigilanteIntentos}/12 ===` : '=== ANUNCIANDO (boton) ===');
  const estado = leerEstado();
""", """  log(esVigilante ? `=== VIGILANTE: reintento automatico ${vigilanteIntentos}/12 ===` : '=== ANUNCIANDO (boton) ===');
  // (oct/2026) "anunciar" se relee del disco en cada corrida: una pausa (--pausar=show)
  // o cualquier cambio del instalador vale YA, sin reiniciar el robot
  try {
    const _f = JSON.parse(fs.readFileSync(path.join(__dirname, 'config_whatsapp.json'), 'utf8'));
    if (_f && _f.anunciar && typeof _f.anunciar === 'object') CFG.anunciar = _f.anunciar;
  } catch (e) { log('no pude releer config_whatsapp.json (sigo con el de memoria): ' + e.message); }
  const estado = leerEstado();
"""),
    ("""    try {
      const j = JSON.parse(await fetchTexto(`https://raw.githubusercontent.com/jaimeatach/jaburahalaja/main/tools/otzar/temas/${sh}.json`));
      if (Array.isArray(j)) _temasRemotos[sh] = j;
    } catch (e) {}
""", """    for (const rama of ['claude/shiurim-halachot-shabbat-vriig5', 'main']) {   // (oct/2026) la rama de trabajo primero
      try {
        const j = JSON.parse(await fetchTexto(`https://raw.githubusercontent.com/jaimeatach/jaburahalaja/${rama}/tools/otzar/temas/${sh}.json`));
        if (Array.isArray(j)) { _temasRemotos[sh] = j; break; }
      } catch (e) {}
    }
"""),
    # (oct/2026) calendario: el shiur sale desde las 00:00 de su dia; "nada para hoy; el proximo es..."
    ("""  const d = new Date(y, mo - 1, da, 6, 0, 0, 0);
""", """  const d = new Date(y, mo - 1, da, 0, 0, 0, 0);   // (oct/2026) desde las 00:00 de su dia (el ANUNCIAR de las 5:30 ya lo manda)
"""),
    ("""    if (!nuevos.length) { log(`${show}: nada nuevo.`); continue; }
""", """    if (!nuevos.length) {
      // (oct/2026) con calendario: decir cuando sale el proximo, en vez de solo "nada nuevo"
      const _cal = (CFG.anunciar[show] || {}).calendario;
      const _prox = (_cal && _cal.n && _cal.fecha) ? items.filter(it => !vistos.has(sacaGuid(it)) && numeroDe(sacaTitulo(it)))
        .map(it => ({ t: sacaTitulo(it), f: fechaDeNumero(_cal, numeroDe(sacaTitulo(it))) })).sort((a, b) => a.f - b.f)[0] : null;
      log(_prox ? `${show}: nada para hoy; el proximo es "${_prox.t.slice(0, 40)}" el ${new Date(_prox.f).toLocaleDateString('es-MX')}.`
                : `${show}: nada nuevo.`);
      continue;
    }
"""),
    # (oct/2026) "!tawil" por WhatsApp: tema y donador de la semana en un solo mensaje
    ("""      return;
    }
  }

  // ===== NUBE DE TORA: solo privados que NO son chat directo =====
""", """      return;
    }
  }

  // === "!tawil" (oct/2026), en chat privado con el robot: tema y donador de la semana ===
  //   !tawil 27                  <- numero del shiur desde el que vale (sin numero: el del domingo que viene)
  //   tema: Kidush               <- el titulo sale "#27- Kidush (1)", "#28- Kidush (2)"...
  //   donador: L"N               <- todo lo que sigue va tal cual en el mensaje
  //   Fulano Ben Fulana
  // Se guarda en C:\\OTZAR\\<show>\\temas.json (manda sobre el del repo) y el robot contesta como va a salir.
  if (!esGrupo) {
    const _txt = String(textoDe(m) || '').replace(/\\r/g, '').trim();
    const _mc = /^!(tawil|tema-dedica|semana)\\b[ \\t]*(\\w+)?[ \\t]*(\\d{1,4})?/i.exec(_txt);
    if (_mc && /tema\\s*:|donador\\s*:|dedicatoria\\s*:/i.test(_txt)) {
      const show = (_mc[1].toLowerCase() === 'tawil' ? 'tawil' : String(_mc[2] || '').toLowerCase());
      const datosAn = (CFG.anunciar || {})[show] || {};
      const f = _archivoTemas(show);
      const responder = async t => { try { await sock.sendMessage(jid, { text: t }); } catch (e) {} };
      if (!f) { await responder(`❌ No encuentro el show "${show}".`); return; }
      let desde = Number(_mc[3] || (_mc[1].toLowerCase() === 'tawil' ? _mc[2] : 0) || 0);
      const _cal = datosAn.calendario;
      if (!desde && _cal && _cal.n && _cal.fecha) {   // sin numero: el shiur del domingo (hoy si es domingo)
        const obj = new Date(); obj.setHours(0, 0, 0, 0); obj.setDate(obj.getDate() + ((7 - obj.getDay()) % 7));
        for (let k = Number(_cal.n) - 30; k < Number(_cal.n) + 2000; k++) if (fechaDeNumero(_cal, k) >= obj.getTime()) { desde = k; break; }
      }
      if (!desde) { await responder('❌ Falta el número del shiur. Ejemplo:\\n!tawil 27\\ntema: Kidush\\ndonador: L"N Fulano Ben Fulana'); return; }
      const lineas = _txt.split('\\n');
      let tema = '', dedic = [], enDedic = false;
      for (const l of lineas.slice(1)) {
        const mt = /^\\s*tema\\s*:\\s*(.*)$/i.exec(l), md = /^\\s*(donador|dedicatoria)\\s*:\\s*(.*)$/i.exec(l);
        if (mt) { tema = mt[1].trim(); enDedic = false; }
        else if (md) { enDedic = true; if (md[2].trim()) dedic.push(md[2].trim()); }
        else if (enDedic && l.trim()) dedic.push(l.trim());
      }
      let l = []; try { l = JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) {}
      l = Array.isArray(l) ? l : [];
      let e = l.find(t => Number(t.desde) === desde);
      if (!e) { e = { desde }; l.push(e); }
      if (tema) e.tema = tema.replace(/\\s+/g, ' ');
      if (dedic.length) e.dedicatoria = dedic.join('\\n');
      l.sort((a, b) => a.desde - b.desde);
      try { fs.writeFileSync(f, JSON.stringify(l, null, 2)); } catch (err) { await responder('❌ No pude guardar: ' + err.message); return; }
      log(`SEMANA ${show}: desde el #${desde}` + (tema ? ` tema "${tema}"` : '') + (dedic.length ? ` donador "${dedic.join(' / ')}"` : ''));
      const tit = tituloAnuncio(show, `#${desde} x`);
      const ded = dedicatoriaDe(show, `#${desde} x`) || datosAn.dedicatoria || '';
      const dia = _cal && _cal.n ? new Date(fechaDeNumero(_cal, desde)).toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' }) : '';
      await responder(`✅ ${show}: guardado desde el #${desde}${dia ? ' (' + dia + ')' : ''}.\\n\\nAsí sale:\\n*${tit}*\\n\\n${ded}`);
      return;
    }
  }

  // ===== NUBE DE TORA: solo privados que NO son chat directo =====
"""),
    # (oct/2026) "!tawil" tambien dentro del grupo fuente del show
    ("""  if (!esGrupo) {
    const _txt = String(textoDe(m) || '').replace(/\\r/g, '').trim();
""", """  // (oct/2026) tambien dentro del GRUPO FUENTE del show (p. ej. "Shiurim rab yosi" de Tawil);
  // la respuesta del propio robot ahi ("✅ ..."/"❌ ...") no se toma como titulo de ningun audio
  const _t0 = String(textoDe(m) || '').trim();
  const _fuenteCmd = (esGrupo && /^(!|✅ |❌ )/.test(_t0)) ? (() => {
    const r = leerRegistro();
    return Object.keys(r).find(k => k.startsWith('escucha:') && r[k] && r[k].id === jid) || null;
  })() : null;
  if (_fuenteCmd && /^(✅|❌) /.test(_t0)) return;
  if (!esGrupo || _fuenteCmd) {
    const _txt = String(textoDe(m) || '').replace(/\\r/g, '').trim();
"""),
    # (oct/2026) Tawil: el mismo tema otra semana sigue la cuenta (#27 = (7))
    ("""  return Object.keys(por).map(Number).sort((a, b) => a - b).map(d => ({ desde: d, tema: por[d] }));
""", """  // (oct/2026) si una semana se avisa el MISMO tema que venia, la cuenta sigue (#27 = (7)), no vuelve a (1)
  const _nt = x => String(x || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase()
    .replace(/\\(\\s*\\d+\\s*\\)\\s*$/, '').replace(/[^\\p{L}\\p{N}]+/gu, ' ').trim();
  const _lista = Object.keys(por).map(Number).sort((a, b) => a - b).map(d => ({ desde: d, tema: por[d] }));
  return _lista.filter((t, i) => i === 0 || _nt(t.tema) !== _nt(_lista[i - 1].tema));
"""),
    # (oct/2026) Spotify: buscar tambien con el titulo corregido del tema
    ("""      // (oct/2026) "spotify_espera_horas": N en anunciar.<show>: si Spotify no toma el
""", """      // (oct/2026) con temas: si el titulo guardado quedo con otra cuenta ("(1)" en vez de "(7)"),
      // se busca tambien con el titulo corregido del tema
      if (!epLink && spotShow && !sinSpot && tituloDeTema(show, ep.tit) !== ep.tit) {
        epLink = await linkEpisodio(spotShow, tituloDeTema(show, ep.tit), {}, 1, (CFG.anunciar[show] || {}).market);
        if (epLink) log(`${show}: "${ep.tit.slice(0, 40)}" encontrado en Spotify como "${tituloDeTema(show, ep.tit)}"`);
      }
      // (oct/2026) "spotify_espera_horas": N en anunciar.<show>: si Spotify no toma el
"""),
    # (oct/2026) temas del repo guardados en la PC (temas_cache.json) y el mismo tema no reinicia la cuenta
    ("""const _temasRemotos = {};
""", """// (oct/2026) la ultima lista del repo queda guardada en temas_cache.json: al arrancar el robot ya
// la tiene (antes, un "!tawil" que llegaba en el primer segundo veia solo la de la PC y contaba mal)
const _temasRemotos = (() => { try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'temas_cache.json'), 'utf8')) || {}; } catch (e) { return {}; } })();
"""),
    ("""        if (Array.isArray(j)) { _temasRemotos[sh] = j; break; }
""", """        if (Array.isArray(j)) {
          _temasRemotos[sh] = j;
          try { fs.writeFileSync(path.join(__dirname, 'temas_cache.json'), JSON.stringify(_temasRemotos)); } catch (e) {}
          break;
        }
"""),
    ("""      if (!f) { await responder(`❌ No encuentro el show "${show}".`); return; }
""", """      if (!f) { await responder(`❌ No encuentro el show "${show}".`); return; }
      try { await cargarTemasRemotos(); } catch (e) {}   // (oct/2026) la lista del repo al dia antes de contestar
"""),
    ("""      if (tema) e.tema = tema.replace(/\\s+/g, ' ');
""", """      if (tema) {   // (oct/2026) el MISMO tema que venia no se guarda como tema nuevo: la cuenta sigue
        const _nt2 = x => String(x || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/[^\\p{L}\\p{N}]+/gu, ' ').trim();
        const _prev = temasDe(show).filter(t => t.desde < desde).pop();
        if (_prev && _nt2(_prev.tema) === _nt2(tema)) delete e.tema;
        else e.tema = tema.replace(/\\s+/g, ' ');
      }
"""),
    # (oct/2026) el robot nunca anuncia en Shabat ni Yom Tov (boton, vigilante y piloto)
    ("""  } catch (e) { log('no pude releer config_whatsapp.json (sigo con el de memoria): ' + e.message); }
  const estado = leerEstado();
""", """  } catch (e) { log('no pude releer config_whatsapp.json (sigo con el de memoria): ' + e.message); }
  // (oct/2026) NUNCA en Shabat ni Yom Tov: desde las 16:00 de la vispera hasta la medianoche del dia
  // (vale para el boton, el vigilante y el piloto automatico)
  {
    const _ah = new Date(), _man = new Date(_ah.getFullYear(), _ah.getMonth(), _ah.getDate() + 1);
    const _bq = _ah.getDay() === 6 ? 'Shabat' : esYomTov(_ah) ? 'Yom Tov'
      : (_ah.getHours() >= 16 && (_ah.getDay() === 5 || esYomTov(_man))) ? (_ah.getDay() === 5 ? 'Erev Shabat' : 'Erev Yom Tov') : '';
    if (_bq) { log(`${_bq}: no se anuncia nada hasta que termine.`); return; }
  }
  const estado = leerEstado();
"""),
    # (oct/2026) Tawil: el archivo nunca con fecha futura (se ve ya en Spotify/Apple)
    ("""    if (_t) { titulo = _t.titulo; if (_t.fecha) item._fecha = _t.fecha; }
""", """    // (oct/2026) nunca fecha futura en el archivo: el episodio se ve YA en Spotify/Apple; el anuncio sale en su dia (calendario)
    if (_t) { titulo = _t.titulo; if (_t.fecha && _t.fecha <= Date.now()) item._fecha = _t.fecha; }
"""),
    # (oct/2026) Motzaei Shabat / Yom Tov: se puede anunciar desde la puesta del sol + 50 min
    ("""function diaSinEnvio(d) { return d.getDay() === 6 || esYomTov(d); }
""", """function diaSinEnvio(d) { return d.getDay() === 6 || esYomTov(d); }
// (oct/2026) puesta del sol en CDMX (formula de la NOAA; coincide con hebcal +-1 min)
function puestaSol(dia, lat = 19.4326, lon = -99.1332) {
  const y = dia.getFullYear(), m = dia.getMonth(), d = dia.getDate();
  const N = Math.round((Date.UTC(y, m, d) - Date.UTC(y, 0, 1)) / 864e5) + 1;
  const g = 2 * Math.PI / 365 * (N - 1 + (18 - 12) / 24), r = Math.PI / 180;
  const eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const de = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const ha = Math.acos(Math.cos(90.833 * r) / (Math.cos(lat * r) * Math.cos(de)) - Math.tan(lat * r) * Math.tan(de)) / r;
  return Date.UTC(y, m, d) + (720 - 4 * (lon - ha) - eq) * 60000;
}
// Shabat / Yom Tov: desde las 16:00 de la vispera hasta 50 min despues de la puesta del sol del
// ultimo dia (Motzaei Shabat ya se anuncia). '' = se puede.
function bloqueoSagrado(ah) {
  const hoy = new Date(ah.getFullYear(), ah.getMonth(), ah.getDate());
  const man = new Date(ah.getFullYear(), ah.getMonth(), ah.getDate() + 1);
  const hoyS = diaSinEnvio(hoy), manS = diaSinEnvio(man);
  if (hoyS && (manS || ah.getTime() < puestaSol(hoy) + 50 * 60000)) return hoy.getDay() === 6 ? 'Shabat' : 'Yom Tov';
  if (!hoyS && manS && ah.getHours() >= 16) return man.getDay() === 6 ? 'Erev Shabat' : 'Erev Yom Tov';
  return '';
}
"""),
    ("""  // (oct/2026) NUNCA en Shabat ni Yom Tov: desde las 16:00 de la vispera hasta la medianoche del dia
  // (vale para el boton, el vigilante y el piloto automatico)
  {
    const _ah = new Date(), _man = new Date(_ah.getFullYear(), _ah.getMonth(), _ah.getDate() + 1);
    const _bq = _ah.getDay() === 6 ? 'Shabat' : esYomTov(_ah) ? 'Yom Tov'
      : (_ah.getHours() >= 16 && (_ah.getDay() === 5 || esYomTov(_man))) ? (_ah.getDay() === 5 ? 'Erev Shabat' : 'Erev Yom Tov') : '';
""", """  // (oct/2026) NUNCA en Shabat ni Yom Tov: desde las 16:00 de la vispera hasta que sale (puesta del
  // sol + 50 min); vale para el boton, el vigilante y el piloto automatico
  {
    const _bq = bloqueoSagrado(new Date());
"""),
    # (oct/2026) avisos del piloto al admin y comandos !reporte !estado !pausa !sigue
    ("""// ---------------- anuncios ----------------
// Busca el link EXACTO del episodio en Spotify por su titulo.
""", """// === AVISOS AL ADMIN (oct/2026) ===
// El piloto deja avisos en <robot>\\avisos\\*.txt (reporte de la mañana, algo que fallo) y el
// robot los manda al chat que se registro con "!reporte". Sin chat registrado, esperan ahi.
const AVISOS_DIR = path.join(__dirname, 'avisos');
setInterval(async () => {
  if (!listo || bloqueoSagrado(new Date())) return;   // en Shabat / Yom Tov esperan
  let archivos = [];
  try { archivos = fs.readdirSync(AVISOS_DIR).filter(f => f.endsWith('.txt')).sort(); } catch (e) { return; }
  if (!archivos.length) return;
  while (archivos.length > 20) { try { fs.unlinkSync(path.join(AVISOS_DIR, archivos.shift())); } catch (e) { break; } }
  const destino = (leerRegistro()['admin:reporte'] || {}).id;
  if (!destino) return;
  for (const f of archivos.slice(0, 3)) {
    const p = path.join(AVISOS_DIR, f);
    let t = ''; try { t = fs.readFileSync(p, 'utf8').trim(); } catch (e) {}
    try { if (t) await sock.sendMessage(destino, { text: t }); fs.unlinkSync(p); }
    catch (e) { log('AVISO no enviado: ' + (e.message || e)); break; }
    await new Promise(r => setTimeout(r, 2000));
  }
}, 30000);

// ---------------- anuncios ----------------
// Busca el link EXACTO del episodio en Spotify por su titulo.
"""),
    ("""  // ===== NUBE DE TORA: solo privados que NO son chat directo =====
""", """  // === "!reporte" / "!estado" / "!pausa" / "!sigue" (oct/2026), en chat privado con el robot ===
  // "!reporte" registra ESTE chat para el reporte de cada mañana y los avisos del piloto (el primero
  // que lo manda; despues solo ese chat puede cambiarlo). Los demas comandos, solo desde ese chat.
  if (!esGrupo) {
    const _ma = /^!(reporte|estado|pausa|sigue)\\b/i.exec(String(textoDe(m) || '').trim());
    if (_ma) {
      const orden = _ma[1].toLowerCase();
      const reg = leerRegistro();
      const adm = reg['admin:reporte'];
      const resp = async t => { try { await sock.sendMessage(jid, { text: t }); } catch (e) {} };
      const PAUSA_PILOTO = path.join('C:\\\\OTZAR', 'PILOTO_PAUSA.txt');
      if (orden === 'reporte') {
        if (adm && adm.id && adm.id !== jid) { await resp('❌ Los reportes ya van a otro chat.'); return; }
        reg['admin:reporte'] = { id: jid, nombre: 'reportes del piloto' };
        guardarRegistro(reg);
        log(`ADMIN: los reportes del piloto van a ${jid}`);
        await resp('✅ Listo: aquí te llega cada mañana el reporte del robot y del piloto, y un aviso si algo falla.\\n\\nComandos:\\n!estado → cómo está todo ahora\\n!pausa → el piloto deja de subir y anunciar\\n!sigue → vuelve a andar');
        return;
      }
      if (!adm || adm.id !== jid) { await resp('❌ Primero manda !reporte desde el chat que va a recibir los avisos.'); return; }
      if (orden === 'pausa') {
        try { fs.writeFileSync(PAUSA_PILOTO, 'pausado por WhatsApp ' + new Date().toLocaleString('es-MX')); } catch (e) {}
        await resp('⏸️ Piloto en pausa: no sube ni anuncia nada hasta que mandes !sigue.');
        return;
      }
      if (orden === 'sigue') {
        try { fs.unlinkSync(PAUSA_PILOTO); } catch (e) {}
        await resp('▶️ Piloto andando otra vez.');
        return;
      }
      let est = '';
      try { est = fs.readFileSync(path.join('C:\\\\OTZAR', 'piloto_reporte.txt'), 'utf8').trim(); } catch (e) {}
      await resp(est || '🤖 El robot está conectado, pero el piloto todavía no dejó reporte (¿está abierta su ventana?).');
      return;
    }
  }

  // ===== NUBE DE TORA: solo privados que NO son chat directo =====
"""),
]
MARCAS_ROBOT = ("PARCHE LID", "JABURA (sep/2026)", "const sinAudio", "if (sinAudio(show))", "const appLink", "show, app)",
                "function feedDeShow", "datos.link_audio", "const fuenteDe", "_porDefecto",
                "REGISTRADO fuente de audios", "function showPorNombre", "FUENTE reconocida por nombre",
                "groupFetchAllParticipating", "GUARDADO [${item.show", "function grupoPorNombre", "CFG.grupos_nombre", "!datos.invite && !datos.nombre", "prefijo_titulo", "yaTeniaTodos", "_deDirecto", "function sinLinks", "function tituloAnuncio", "quitar_lineas", "function normTitulo", "permitir_repetidos", "SIN AUDIO en la fuente", "function otroRobotVivo", "function rescatarDeHistorial", "carpeta, show: showPrefijo", "function armarPlantilla", "function tituloPorTema", "spotify_espera_horas", "esperar_fecha && ep.fecha", "sin pisar un rescate", "GUARDADO MEKOROT", "r.documentos && contenido(m)", "function elegirPorPalabras", "soundcloud_episodios.json", "function fechaDeNumero", "dedicatoria: dedicatoriaDe", "se relee del disco en cada corrida", "la rama de trabajo primero", "desde las 00:00 de su dia", "nada para hoy; el proximo es", "=== \"!tawil\" (oct/2026)", "tambien dentro del GRUPO FUENTE", "la cuenta sigue (#27 = (7))", "se busca tambien con el titulo corregido del tema", "temas_cache.json", "la lista del repo al dia antes de contestar", "NUNCA en Shabat ni Yom Tov", "nunca fecha futura en el archivo", "function bloqueoSagrado", "AVISOS AL ADMIN", "!reporte\" / \"!estado")
# הלכות מוקצה: la carpeta "שיעורים מוקצה" que comparte Saúl aparte (31 shiurim
# numerados al FINAL del nombre). Mismos títulos y simanim que el catálogo de la app.
MUKZE_CARPETA = r"G:\.shortcut-targets-by-id\1OcakbiF7zD5biDpWYElkB-DoIlidbTlT\שיעורים מוקצה"
MUKZE_COMO = "הלכות מוקצה"
MUKZE = [
    ("חריות של דקל- סעיף כ-עד סעיף כד 01.m4a", "חריות של דקל · סעיף כ עד כד", 308),
    ("לילד אבן או דבר מוקצה לטילטול 02.m4a", "ליקח ילד אבן או דבר מוקצה", 308),
    ("גרעינים וקליפות סעיף כז-עט 03.m4a", "גרעינים וקליפות · סעיף כז עד כט", 308),
    ("פירורים-עצמות-וקליפים 04.m4a", "פירורים · עצמות · וקליפים", 308),
    ("כללים-בקליפות וגרעינים 05.m4a", "כללים בקליפות וגרעינים", 308),
    ("קליפות בענין מוקצה 06.m4a", "קליפות בענין מוקצה", 308),
    ("גרף של רעי - מכניס אדם מלא קופתו עפר 07.m4a", "גרף של רעי · מכניס אדם מלא קופתו עפר", 308),
    ("טלטול כדור בשבת, וטלטול בהימות 08.m4a", "טלטול כדור בשבת · וטלטול בהמות", 308),
    ("סימן ש״ח סעיף מו עד סוף הסימן 09.m4a", "סימן ש״ח · סעיף מו עד נב", 308),
    ("סעיף א סימן שט 10.m4a", "סימן ש״ט · סעיף א", 309),
    ("יסוד של בסיס לדבר האסור 11.m4a", "יסוד של בסיס לדבר האסור", 310),
    ("בסיס לדבר אסור. - וטלטול מן הצד לצורך דבר המותר. 12.m4a", "בסיס לדבר האסור · וטלטול מן הצד לצורך דבר המותר", 310),
    ("ביאור במחלוקת ר׳ שמעון ור׳ יהודה 13.m4a", "ביאור במחלוקת ר׳ שמעון ור׳ יהודה", 310),
    ("מגן דאיתקצאי לבין השמשות 14.m4a", "מיגו דאיתקצאי לבין השמשות", 310),
    ("בטל כלי מהכינו 15.m4a", "ביטול כלי מהיכנו", 310),
    ("מעות שעל הכיס 16.m4a", "מעות שעל הכיס", 310),
    ("שולחן שיש בה מגירה עם מעות 17.m4a", "שולחן שיש בו מגירה עם מעות", 310),
    ("טלטול מן הצד 18.m4a", "טלטול מן הצד", 311),
    ("טלטול מן הצד - וטלטול המת בשבת 19.m4a", "טלטול מן הצד · וטלטול המת בשבת", 311),
    ("טלטול בגופו 20.m4a", "טלטול בגופו", 311),
    ("גדול כבוד הבריות שדוחה ל״ת 21.m4a", "גדול כבוד הבריות שדוחה לא תעשה", 312),
    ("מוקצה על ידי גוי 22.m4a", "מוקצה על ידי גוי", 308),
    ("כלי שמלאכתו לאיסור-ומוקצה מחמת חיסרון כיס 23.m4a", "כלי שמלאכתו לאיסור · ומוקצה מחמת חסרון כיס", 308),
    ("סימן ש״י סעיף ז 24.m4a", "סימן ש״י · סעיף ז", 310),
    ("מוקצה מחמת חיסרון כיס וכלי גדול וכבד 25.m4a", "מוקצה מחמת חסרון כיס · וכלי גדול וכבד", 308),
    ("ציורים של כלי שמלאכתו לאיסור 26.m4a", "ציורים של כלי שמלאכתו לאיסור", 308),
    ("כלי חדש שמלאכתו לאיסור- וכלי שמלאכתו לאיסור שאין בו צד היתר 27.m4a", "כלי חדש שמלאכתו לאיסור · וכלי שמלאכתו לאיסור שאין בו צד היתר", 308),
    ("כלי שמשמש לאיסור 28.m4a", "כלי שמשמש לאיסור", 308),
    ("כללים בהליכות מוקצה 29.m4a", "כללים בהליכות מוקצה", 308),
    ("טלטול הנר - סימן רע״ט 30.m4a", "טלטול הנר · סימן רע״ט", 279),
    ("הקדמה ביאור באופנים המחולקים של מוקצה 31.m4a", "הקדמה · ביאור באופנים המחולקים של מוקצה", 308),
]
# el mismo הקדמה sin número (grabación de 2024): no se sube dos veces
MUKZE_IGNORAR = ["הקדמה ביאור באופנים המחולקים של מוקצה.m4a"]
GRUPOS_NOMBRE = {"https://chat.whatsapp.com/5xGJ6YLeGT97rL94uJnPyZo": "3 Solo Shiurim",
                 "https://chat.whatsapp.com/BjgiQwlndcK6hyzFPuP7Vn": "Clases Tefila Habitat",
                 "https://chat.whatsapp.com/KpJ10DwoMVv7Te7ZWknDF7": "Halajot Generales"}
NOMBRES_FUENTE = {"tefila": "Clases Tefila Habitat", "jabura": "Mekorot", "nacach": "Shiurim jajam ezra nacach", "credi": "Halajot Generales"}
# shows que toman audios de un grupo (por nombre) aunque el config solo tuviera chat directo
FUENTES_NUEVAS = {"nacach": "Shiurim jajam ezra nacach"}
# nombre del Rab en el MENSAJE del anuncio, para shows cuyo feed no lo trae (van a grupos generales)
SUFIJOS_ANUNCIO = {"efshar": "· Rab Igal Snertz", "mishlei": "· Rab Igal Snertz"}
# reglas de título al guardar (escuchar.<show>): Isaac Credi manda "1151 Siman 639" en la
# primera línea y luego el tema en 1-2 líneas; sale "tema1, tema2 - Sr. Isaac Credi"
REGLAS_TITULO = {"isaaccredi": {"quitar_lineas": r"^\s*\d+\s*(siman|סימן|halaja|halajot)?\s*\d*\s*$",
                               "unir_lineas": ", ", "sufijo_titulo": "- Sr. Isaac Credi"}}
# nombre del Rab al frente del titulo (va a grupos generales)
PREFIJOS = {"tefila": "Rab Tofi Cherem ·", "nacach": "Rab Ezra Nacach ·", "efshar": "Rab Igal Snertz ·", "credi": "David Credi ·",
            "hilu": "Rab Joshua Hilu ·", "ofirmalka": "הרב אופיר מלכא ·"}
# shows que NO van a cierto grupo general (vacío: todos van al 6 y al 3)
SIN_GRUPO = {}
TITULOS_DEFECTO = {"tefila": "Clase de Tefilá · Rab Tofi Cherem", "hilu": "Shiur · Rab Joshua Hilu", "nacach": "Shiur · Rab Ezra Nacach",
                   "efshar": "Shiur · Rab Igal Snertz", "ofirmalka": "הרב אופיר מלכא · שיעור", "credi": "Shiur · David Credi",
                   "isaaccredi": "Halajot Yalkut Yosef - Sr. Isaac Credi"}
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
    intentos = []
    for ref in REFS:
        intentos.append((f"{API_CONTENTS}{nombre}?ref={ref}", {"User-Agent": "instalar-otzar", "Accept": "application/vnd.github.raw"}))
        intentos.append((f"https://raw.githubusercontent.com/jaimeatach/jaburahalaja/{ref}/tools/{nombre}", {"User-Agent": "instalar-otzar"}))
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
def _ya_puesto(viejo, nuevo, plano):
    lineas_plano = {x.strip() for x in plano.split("\n")}
    viejas = {x.strip() for x in viejo.split("\n")}
    propias = [x.strip() for x in nuevo.split("\n") if len(x.strip()) > 15 and x.strip() not in viejas]
    return bool(propias) and all(x in lineas_plano for x in propias)


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
        # ya aplicado y luego retocado por un parche posterior (su "viejo" vive dentro
        # de este "nuevo" y su "nuevo" ya está): no se vuelve a meter
        if any(h2[0] in nuevo and h2[1] in plano for h2 in HUNKS[i + 1:]):
            aplicados += 1
            continue
        # (oct/2026) retocado por una CADENA de parches posteriores: si todas las líneas
        # propias que agrega este parche ya están en el robot, ya está puesto (antes se
        # volvía a meter y duplicaba feedDeShow y el filtro de esperar_fecha)
        if _ya_puesto(viejo, nuevo, plano):
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
    if aplicados == len(HUNKS) and all(m in plano for m in MARCAS_ROBOT):
        respaldar(ruta)
        escribir(ruta, plano.replace("\n", salto))
        ok(f"{len(HUNKS)} cambios aplicados a tu robot")
    elif hashlib.sha256(crudo).hexdigest() == SHA_ROBOT_ORIGINAL:
        respaldar(ruta)
        if bajar("otzar/robot_whatsapp.js", ruta):
            ok("robot reemplazado por la copia parchada")
    else:
        aviso(f"tu robot cambió y solo pude aplicar {aplicados} de {len(HUNKS)} cambios")
        for i, h in enumerate(HUNKS):
            v_, n_, todos_ = h[0], h[1], len(h) > 2
            if n_ in plano or (todos_ and v_ not in plano) or plano.count(v_) == 1:
                continue
            print(f"     · parche {i + 1} no encontró: {v_.strip().splitlines()[0][:70]}")
        # la copia del repo ES tu robot con todos los parches: se pone entera (con respaldo)
        respaldar(ruta)
        if bajar("otzar/robot_whatsapp.js", ruta):
            ok("robot reemplazado por la copia parchada del repo (tu versión quedó en el respaldo)")
        else:
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
                # el correo del dueño va en el feed: Apple, Amazon y Spotify mandan ahí el código
                if "CAMBIAR" in str(viejo.get("email", "CAMBIAR")):
                    nuevas["email"] = "rabmeireliyahu@gmail.com"
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
    an.update({"sin_audio": True, "sin_whatsapp": True, "max_anuncios": 4, "en_orden": True,
               "sin_spotify": not tiene, "link_audio": False, "pausado": False})
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
    defectos = {"nacach": 2, "peretz": 2, "ofirmalka": 2, "tefila": 2, "hilu": 2, "credi": 2, "isaaccredi": 2, "jabura": 3}
    cambios = 0
    for show, n in defectos.items():
        if show in an and (an[show].get("sin_filtro_fecha") or an[show].get("curso")):
            continue                               # curso en orden: ni tope ni memorizar
        if show in an and an[show].get("solo_ultimos") != n and "solo_ultimos" not in an[show]:
            an[show]["solo_ultimos"] = n
            cambios += 1
        tope = 20 if show == "peretz" else 4       # Peretz manda muchos: salen todos los que se subieron
        if show in an and show != "jabura" and int(an[show].get("max_anuncios") or 0) < tope:
            an[show]["max_anuncios"] = tope        # varios shiurim del mismo día salen en un solo clic
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
    canal = {}
    if rss:
        # el show ya existe en Spotify: se conservan su nombre, descripción y autor
        try:
            with urllib.request.urlopen(urllib.request.Request(rss, headers={"User-Agent": "Mozilla/5.0"}), timeout=40) as r:
                cab_xml = r.read().decode("utf-8", "replace").split("<item>", 1)[0]
            for k, pat in (("titulo", r"<title>(.*?)</title>"), ("descripcion", r"<description>(.*?)</description>"),
                           ("autor", r"<itunes:author>(.*?)</itunes:author>")):
                m = re.search(pat, cab_xml, re.S)
                if m:
                    canal[k] = re.sub(r"^<!\[CDATA\[|\]\]>$", "", m.group(1).strip()).strip()
            if canal.get("titulo"):
                ok(f"show en Spotify: '{canal['titulo']}' (se conserva el nombre y la portada)")
        except Exception as e:                              # noqa: BLE001
            aviso(f"no pude leer el RSS del show ({e}); uso el nombre dado")
    c.setdefault("titulo", canal.get("titulo") or nombre)
    c.setdefault("descripcion", canal.get("descripcion") or f"Shiurim de {nombre}. Otzar HaTorah - אוצר התורה")
    c.setdefault("autor", canal.get("autor") or nombre)
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
    generales = (cfg.get("anunciar", {}).get("nacach") or {}).get("invite") or []
    generales = generales if isinstance(generales, list) else [generales]
    # el aviso va al grupo del Rab (primero, para que "Whatsapp" sea el link de SU grupo)
    # y a los grupos generales; sin audio, porque en su grupo ya está
    destinos = ([grupo] if grupo.startswith("http") else []) + [g for g in generales if g != grupo]
    if "--nuevo-sin-grupos" in sys.argv:
        destinos = []                 # solo Spotify: no se anuncia en ningún grupo
        an["invite"] = ""
    if destinos:
        an["invite"] = destinos if len(destinos) > 1 else destinos[0]
        an["sin_whatsapp"] = not grupo.startswith("http")
    if spot.startswith("http"):
        an["spotify"] = spot
    tiene = str(an.get("spotify", "")).startswith("http")
    for k, v in {"idioma": "es", "max_anuncios": 2, "en_orden": True, "sin_audio": True, "sin_whatsapp": True, "solo_ultimos": 2}.items():
        an.setdefault(k, v)
    an["sin_spotify"] = not tiene
    an["link_audio"] = False          # nunca link al audio: título + Spotify + WhatsApp
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
        # lo rescatado YA estaba en Spotify: se marca como anunciado para que el robot
        # no lo mande a los grupos como si fuera nuevo (solo sale lo que llegue de aquí en adelante)
        try:
            j = _gh_get(f"https://api.github.com/repos/{c['github_user']}/{c['github_repo']}", cab, "feed.xml")
            feed = base64.b64decode(j["content"]).decode("utf-8")
            guids = [g.replace("&amp;", "&") for g in re.findall(r"<guid[^>]*>(.*?)</guid>", feed)]
            estado_p = (ROBOT or BASE) / "estado_anuncios.json"
            try:
                e = json.loads(estado_p.read_text(encoding="utf-8"))
            except Exception:
                e = {}
            previos = e.get(clave) or []
            e[clave] = (previos + [g for g in guids if g not in previos])[-2000:]
            respaldar(estado_p)
            escribir(estado_p, json.dumps(e, ensure_ascii=False, indent=2))
            ok(f"{len(guids)} episodio(s) rescatados marcados como ya anunciados (no se mandan a los grupos)")
        except Exception as e_:                             # noqa: BLE001
            aviso(f"no pude marcar lo rescatado como anunciado: {e_}")
        print(f"   → en Spotify for Creators, redirect del show a https://{c['github_user']}.github.io/{c['github_repo']}/feed.xml")
    if not grupo.startswith("http") and not esc.get("invite") and "--tawil" not in sys.argv:
        print(f"   → cuando tengas el grupo del Rab: python instalar_otzar.py --sin-drive --nuevo={clave} --nuevo-grupo=LINK")


def _gh_get(base, cab, ruta):
    with urllib.request.urlopen(urllib.request.Request(f"{base}/contents/{ruta}", headers=cab), timeout=60) as r:
        return json.loads(r.read().decode())


def _gh_texto(base, cab, ruta):
    """(texto, sha) de un archivo del repo; para los que pesan más de 1 MB la API no
    manda el contenido en el JSON y hay que pedirlo en crudo."""
    j = _gh_get(base, cab, ruta)
    if j.get("content"):
        return base64.b64decode(j["content"]).decode("utf-8"), j["sha"]
    cab2 = dict(cab)
    cab2["Accept"] = "application/vnd.github.raw"
    with urllib.request.urlopen(urllib.request.Request(f"{base}/contents/{ruta}", headers=cab2), timeout=180) as r:
        return r.read().decode("utf-8", "replace"), j["sha"]


def _compactar_feed(s):
    """Quita el espacio acumulado (líneas en blanco, colas de espacios, sangrías enormes).
    El feed de musar llegó a 40 MB de puro espacio y GitHub lo rechazaba (422)."""
    out = []
    for ln in s.splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            continue
        out.append(re.sub(r"^[ \t]{7,}", "      ", ln))
    return "\n".join(out) + "\n"


def _gh_put(base, cab, ruta, datos, msg, sha=None):
    cuerpo = {"message": msg, "content": base64.b64encode(datos).decode()}
    if sha:
        cuerpo["sha"] = sha
    req = urllib.request.Request(f"{base}/contents/{ruta}", data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
    with urllib.request.urlopen(req, timeout=120):
        pass


def portada_fechada(show, c, cab, img=None):
    """Sube la portada como portada_<fecha>.jpg y deja el feed apuntando ahí.
    Spotify NO vuelve a bajar una imagen si la URL es la misma: con nombre nuevo
    la toma en la siguiente lectura del feed. Sin img, usa la portada.jpg del repo."""
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    pages = f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}"
    try:
        j = _gh_get(base, cab, "feed.xml")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"{show}: no pude leer el feed ({e})")
        return False
    feed = base64.b64decode(j["content"]).decode("utf-8")
    m = re.search(r'<itunes:image href="([^"]+)"', feed)
    actual = m.group(1) if m else ""
    if img is None:
        if not actual.endswith("/portada.jpg"):
            return True                                     # ya tiene nombre fechado
        try:
            img = base64.b64decode(_gh_get(base, cab, "portada.jpg")["content"])
        except Exception as e:                              # noqa: BLE001
            aviso(f"{show}: no pude leer portada.jpg del repo ({e})")
            return False
    nombre = "portada_" + time.strftime("%Y%m%d%H%M") + ".jpg"
    if VER:
        print(f"   (subiría) {nombre} y apuntaría el feed de {show} ahí")
        return True
    try:
        _gh_put(base, cab, nombre, img, "portada")
        nuevo = re.sub(r'<itunes:image href="[^"]*"', f'<itunes:image href="{pages}/{nombre}"', feed, count=1)
        nuevo = re.sub(r"<image>\s*<url>[^<]*</url>", f"<image><url>{pages}/{nombre}</url>", nuevo, count=1)
        if nuevo != feed:
            _gh_put(base, cab, "feed.xml", nuevo.encode("utf-8"), f"portada {nombre}", j["sha"])
        ok(f"{show}: portada publicada como {nombre} y el feed apunta ahí (Spotify la refresca al leer el feed)")
        return True
    except Exception as e:                                  # noqa: BLE001
        aviso(f"{show}: no pude publicar la portada fechada ({e})")
        return False


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
            ok(f"portada subida ({len(img) // 1024} KB, mínimo 1400x1400 px)")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude subir la portada: {e}")
        return
    portada_fechada(show, c, cab, img)


# ── 29. הלכות מוקצה: la carpeta aparte de Saúl entra al feed, a Spotify (hasta
#        abajo, es el tema anterior) y a la app, con títulos curados ────────────
def mukze():
    d = BASE / "jabura"
    cfgp = d / "config.json"
    if not cfgp.exists():
        return
    paso(29, "הלכות מוקצה: la carpeta aparte de Saúl, con títulos curados y hasta abajo en Spotify")
    try:
        c = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer jabura\\config.json: {e}")
        return
    antes = json.dumps(c, sort_keys=True)
    extras = [x for x in (c.get("carpetas_extra") or []) if isinstance(x, dict)]
    if not any(x.get("como") == MUKZE_COMO for x in extras):
        extras.append({"ruta": MUKZE_CARPETA, "como": MUKZE_COMO})
    c["carpetas_extra"] = extras
    c["ignorar_carpetas"] = sorted(set(c.get("ignorar_carpetas") or []) | {"מוקצה"})
    c["ignorar"] = sorted(set(c.get("ignorar") or []) | set(MUKZE_IGNORAR))
    c["al_fondo"] = sorted(set(c.get("al_fondo") or []) | {MUKZE_COMO})
    if json.dumps(c, sort_keys=True) != antes:
        respaldar(cfgp)
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        ok("config.json: carpeta extra, la מוקצה vieja de 3 shiurim fuera, fechas al fondo")
    titulos = {}
    tj = d / "titulos.json"
    try:
        titulos = json.loads(tj.read_text(encoding="utf-8"))
    except Exception:
        titulos = {}
    cambio = False
    for archivo, t, s in MUKZE:
        if titulos.get(archivo) != {"t": t, "s": s}:
            titulos[archivo] = {"t": t, "s": s}
            cambio = True
    if cambio:
        escribir(tj, json.dumps(titulos, ensure_ascii=False, indent=1) + "\n")
        ok(f"titulos.json: {len(MUKZE)} títulos de מוקצה (feed, Spotify y app se llaman igual)")
    if Path(MUKZE_CARPETA).is_dir():
        n_ = len([f for f in Path(MUKZE_CARPETA).iterdir() if f.suffix.lower() in AUDIO])
        ok(f"carpeta encontrada: {n_} audios · se suben y entran al feed con ANUNCIAR")
    else:
        aviso("no veo la carpeta de מוקצה en el Drive (¿está montado G:?); ANUNCIAR la busca de nuevo")


# ── 30. --curso=show:N[:porclic]: el show sale EN ORDEN desde el episodio 1 ─────
#   N = cuántos ya salieron (0 = empezar desde el primero); porclic = cuántos
#   manda cada ANUNCIAR (1 por defecto). Quita solo_ultimos y deja el estado
#   exactamente con los N primeros (por fecha), ni uno más.
def curso():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--curso=")), "")
    if not arg or ":" not in arg:
        return
    partes = arg.split(":")
    show, cuantos = partes[0].strip(), int(partes[1] or 0)
    porclic = int(partes[2]) if len(partes) > 2 and partes[2] else 1
    paso(30, f"{show}: curso en orden, ya salieron {cuantos}, {porclic} por clic")
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    an = (cfg.get("anunciar") or {}).get(show)
    if not isinstance(an, dict):
        aviso(f"{show} no está en anunciar del robot")
        return
    an.update({"en_orden": True, "sin_filtro_fecha": True, "curso": True, "max_anuncios": porclic})
    an.pop("solo_ultimos", None)
    an.pop("uno_por_dia", None)
    respaldar(rw)
    escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok(f"config: en orden, sin filtro de fecha, {porclic} por clic, sin 'solo últimos'")
    c = {}
    try:
        c = json.loads((BASE / show / "config.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    url = an.get("feed") if str(an.get("feed", "")).startswith("http") else \
        f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}/feed.xml"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar"}), timeout=60) as r:
            feed = r.read().decode("utf-8", "replace")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed {url}: {e}")
        return
    from email.utils import parsedate_to_datetime
    eps = []
    for it in re.findall(r"<item>([\s\S]*?)</item>", feed):
        g = re.search(r"<guid[^>]*>(.*?)</guid>", it)
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it)
        if not g:
            continue
        try:
            cuando = parsedate_to_datetime(d.group(1).strip()).timestamp() if d else 0
        except Exception:
            cuando = 0
        eps.append((cuando, g.group(1).replace("&amp;", "&"), (t.group(1) if t else "").strip()))
    eps.sort()
    estado_p = (ROBOT or BASE) / "estado_anuncios.json"
    try:
        e = json.loads(estado_p.read_text(encoding="utf-8"))
    except Exception:
        e = {}
    e[show] = [g for _, g, _ in eps[:cuantos]]
    respaldar(estado_p)
    escribir(estado_p, json.dumps(e, ensure_ascii=False, indent=2))
    ok(f"estado: {len(e[show])} marcados como ya salidos de {len(eps)}")
    if len(eps) > cuantos:
        print(f"   → el próximo ANUNCIAR manda: {eps[cuantos][2][:70]}")
    print("   → reinicia el robot para que tome el config nuevo")


# ── 31. --retitular=show:texto_viejo|titulo_nuevo: renombrar un episodio del feed ─
#   Cambia <title> y <description> del primer episodio cuyo título contenga el
#   texto viejo. Sirve cuando un audio se publicó con el título por defecto.
def retitular():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--retitular=")), "").strip().strip('"')
    if not arg or ":" not in arg or "|" not in arg:
        return
    show, resto = arg.split(":", 1)
    viejo, nuevo = [x.strip() for x in resto.split("|", 1)]
    paso(31, f"{show}: retitular '{viejo[:40]}' → '{nuevo[:60]}'")
    d = BASE / show
    c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
    tok = next((p for p in (d / "github_token.txt", BASE / "nacach" / "github_token.txt", BASE / "jabura" / "github_token.txt") if p.exists()), None)
    if not tok:
        aviso("falta github_token.txt")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    try:
        j = _gh_get(base, cab, "feed.xml")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed: {e}")
        return
    feed = base64.b64decode(j["content"]).decode("utf-8")
    from xml.sax.saxutils import escape, unescape
    hecho = [False]
    def cambiar(m):
        it = m.group(0)
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        if hecho[0] or not t or viejo.lower() not in unescape(t.group(1)).lower():
            return it
        hecho[0] = True
        it = it.replace(t.group(0), f"<title>{escape(nuevo)}</title>", 1)
        it = re.sub(r"<description>.*?</description>", f"<description>{escape(nuevo)}</description>", it, count=1, flags=re.S)
        return it
    nuevo_feed = re.sub(r"<item>[\s\S]*?</item>", cambiar, feed)
    if not hecho[0]:
        aviso("no encontré un episodio con ese texto en el título")
        return
    if not VER:
        _gh_put(base, cab, "feed.xml", nuevo_feed.encode("utf-8"), f"retitular: {nuevo[:50]}", j["sha"])
    ok("feed actualizado; Spotify toma el título nuevo al leer el feed y el robot lo anuncia con ese nombre")


# ── 32. --shows: qué shows hay en C:\OTZAR, a qué Spotify van y cómo reciben audios ─
def shows():
    if "--shows" not in sys.argv:
        return
    paso(32, f"Shows en {BASE}")
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    try:
        cfgw = json.loads(rw.read_text(encoding="utf-8"))
    except Exception:
        cfgw = {}
    for d in sorted(BASE.iterdir()):
        cfgp = d / "config.json"
        if not (d.is_dir() and cfgp.exists()):
            continue
        try:
            c = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception:
            continue
        an = (cfgw.get("anunciar") or {}).get(d.name) or {}
        spot = an.get("spotify") if str(an.get("spotify", "")).startswith("http") else (c.get("spotify") or "(sin link en el robot)")
        modo = "WhatsApp → " + str(c.get("carpeta_whatsapp") or (d / "audios_whatsapp")) if c.get("modo_whatsapp") else \
            ("RSS de otro lado" if c.get("rss_original") and not c.get("modo_whatsapp") else "carpeta local / manual")
        try:
            n_eps = len(list((d / "episodios").glob("*.mp3")))
        except Exception:
            n_eps = 0
        print(f"   · {d.name}: '{c.get('titulo', '?')}'")
        print(f"       Spotify: {spot}")
        print(f"       entrada: {modo} · episodios locales: {n_eps}" + (" · PAUSADO" if c.get("pausado") or (d / "PAUSADO.txt").exists() else ""))
    print("   → para publicar audios sueltos en un show: cópialos a su carpeta de WhatsApp con el título como nombre")
    print("     (p. ej. 'Sucot · Rab Fulano.mp3') y aprieta ANUNCIAR")


# ── 35. Archive con calma: cada podcast_bot.py sube por tandas de 25, espera cuando
#   Archive dice "reduce your request rate" y NO vuelve a subir lo que ya está en el
#   ítem (checksum). Antes, 185 audios de golpe tronaban a la mitad y el siguiente
#   ANUNCIAR volvía a empezar desde cero.
MARCA_CALMA = "# === archive con calma v2 (otzar) ==="
MARCA_CALMA_VIEJA = "# === archive con calma (otzar) ==="
CUERPO_CALMA = '''    log(f"Subiendo {len(archivos)} archivo(s) a Archive.org...")
    # === archive con calma v2 (otzar) ===
    # por tandas, sin repetir lo ya subido (checksum) y esperando si Archive pide calma
    rutas = [str(a) for a in archivos]
    lote = 25
    for i in range(0, len(rutas), lote):
        parte = rutas[i:i + lote]
        for intento in range(8):
            try:
                upload(CFG["archive_id"], files=parte,
                       metadata={"title": CFG["titulo"], "mediatype": "audio",
                                 "collection": "opensource_audio"},
                       retries=10, retries_sleep=30, checksum=True)
                break
            except Exception as e:
                txt = str(e)
                if "reduce your request rate" in txt or "rationed" in txt or "exceeds" in txt:
                    log(f"Archive pide calma ({i + len(parte)}/{len(rutas)}); espero 5 min y sigo...")
                    time.sleep(300)
                    continue
                if ("Connection aborted" in txt or "ConnectionReset" in txt or "10054" in txt or "timed out" in txt
                        or "Max retries" in txt or "RemoteDisconnected" in txt or "503" in txt or "SlowDown" in txt):
                    log(f"Archive corto la conexion ({i + len(parte)}/{len(rutas)}); espero {2 + intento} min y reintento...")
                    time.sleep(60 * (2 + intento))
                    continue
                log(f"ERROR subiendo a Archive: {e}")
                return False
        else:
            log("Archive sigue pidiendo calma; lo reintento en el proximo ANUNCIAR.")
            return False
        if i + lote < len(rutas):
            log(f"  {i + len(parte)}/{len(rutas)} subidos...")
            time.sleep(20)
    log("Subida a Archive: OK")
    return True
'''


def archive_calma():
    paso(35, "Archive.org con calma: subir por tandas y no repetir lo ya subido")
    n = 0
    for d in sorted(BASE.iterdir()):
        bot = d / "podcast_bot.py"
        if not (d.is_dir() and bot.exists()):
            continue
        s = bot.read_text(encoding="utf-8", errors="replace")
        if MARCA_CALMA in s:
            continue
        if MARCA_CALMA_VIEJA in s:
            # versión anterior del parche: se reemplaza el cuerpo completo
            a = s.index('    log(f"Subiendo {len(archivos)} archivo(s) a Archive.org...")\n')
            b = s.index('    log("Subida a Archive: OK")\n    return True\n', a) + len('    log("Subida a Archive: OK")\n    return True\n')
            nuevo = s[:a] + CUERPO_CALMA + s[b:]
            try:
                compile(nuevo, str(bot), "exec")
            except SyntaxError as ex:
                aviso(f"{d.name}: el parche v2 no compila ({ex}); no lo toco")
                continue
            respaldar(bot)
            escribir(bot, nuevo)
            n += 1
            continue
        m = re.search(r'\n    log\(f"Subiendo \{len\(archivos\)\} archivo\(s\) a Archive\.org\.\.\."\)\n', s)
        if not m:
            aviso(f"{d.name}: podcast_bot.py distinto, no lo toco")
            continue
        fin = re.search(r"\n(?=def |\S)", s[m.end():])     # hasta la siguiente cosa de primer nivel
        if not fin:
            aviso(f"{d.name}: no encontré el final de subir_nuevos_a_archive")
            continue
        nuevo = s[:m.start() + 1] + CUERPO_CALMA + "\n" + s[m.end() + fin.start() + 1:]
        if "import time" not in nuevo and "time.time()" not in nuevo:
            nuevo = nuevo.replace("import ", "import time, ", 1)
        try:
            compile(nuevo, str(bot), "exec")
        except SyntaxError as ex:
            aviso(f"{d.name}: el parche no compila ({ex}); no lo toco")
            continue
        respaldar(bot)
        escribir(bot, nuevo)
        n += 1
    ok(f"{n} podcast_bot.py parchados" if n else "todos ya suben con calma")


# ── 36. --reordenar=show: el feed en orden de Tanaj (parashá 1..54 → Tehilim → Rut →
#   Ester → resto), con fechas seguidas. Primero mete al feed los mp3 locales que
#   falten (podcast_bot.py feed). Sirve cuando un episodio se quedó fuera o con fecha
#   de otro día (taamim: los 16 rescatados de Spotify).
def reordenar():
    show = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--reordenar=")), "").strip().lower()
    if not show:
        return
    paso(36, f"{show}: feed en orden de Tanaj con fechas seguidas")
    d = BASE / show
    c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
    tok = next((p for p in (d / "github_token.txt", BASE / "jabura" / "github_token.txt") if p.exists()), None)
    if not tok:
        aviso("falta github_token.txt")
        return
    if (d / "podcast_bot.py").exists() and not VER:
        print("   --- podcast_bot.py feed (mete los mp3 locales que falten) ---")
        subprocess.run([sys.executable, "podcast_bot.py", "feed"], cwd=str(d))
    spec = importlib.util.spec_from_file_location("correo_shiurim", BASE / "jabura" / "correo_shiurim.py")
    try:
        co = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(co)
    except Exception as ex:
        aviso(f"no pude cargar jabura\\correo_shiurim.py ({ex}); corre el instalador sin argumentos primero")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    try:
        feed, sha_feed = _gh_texto(base, cab, "feed.xml")
        j = {"sha": sha_feed}
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed: {e}")
        return
    feed = _compactar_feed(feed)
    from email.utils import parsedate_to_datetime, format_datetime
    from datetime import datetime
    items = re.findall(r"[ \t]*<item>[\s\S]*?</item>\n?", feed)
    if not items:
        aviso("el feed no tiene episodios")
        return
    filas = []
    vistos = set()
    for k, it in enumerate(items):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
        titulo = (t.group(1) if t else "").replace("&amp;", "&").strip()
        g = re.search(r"<guid[^>]*>(.*?)</guid>", it)
        clave = (g.group(1) if g else titulo).strip()
        if clave in vistos:
            print(f"   (repetido, se quita) {titulo[:60]}")
            continue                                          # GitHub Pages a veces sirve un feed viejo y el bot duplica
        vistos.add(clave)
        m = re.search(r"<pubDate>(.*?)</pubDate>", it)
        try:
            viejo = parsedate_to_datetime(m.group(1).strip()).timestamp() if m else 0
        except Exception:
            viejo = 0
        cat, idx = co.clasificar(co.limpiar_titulo(titulo))
        filas.append((cat, idx, viejo, k, titulo, it))
    filas.sort(key=lambda f: f[:4])
    n = len(filas)
    inicio = time.time() - (n + 2) * 60 - 3600           # todas en el pasado, una por minuto
    primero = min(f[2] for f in filas if f[2]) if any(f[2] for f in filas) else 0
    if primero and primero + n * 60 < time.time() - 60:
        inicio = primero                                  # se respeta la fecha más vieja que ya tenía el feed
    nuevos = []
    for k, (cat, idx, viejo, _k, titulo, it) in enumerate(filas):
        fecha = format_datetime(datetime.fromtimestamp(inicio + k * 60).astimezone())
        it2 = re.sub(r"<pubDate>.*?</pubDate>", "<pubDate>%s</pubDate>" % fecha, it, count=1)
        if "<pubDate>" not in it2:
            it2 = it2.replace("</title>", "</title>\n      <pubDate>%s</pubDate>" % fecha, 1)
        nuevos.append(it2)
        print(f"   {k + 1:3d}. [{['parashá', 'Tehilim', 'Rut', 'Ester', 'otro'][cat]} {idx}] {titulo[:60]}")
    ini = feed.find(items[0])
    fin = feed.rfind("</item>") + len("</item>")
    nuevo = feed[:ini] + "".join(x if x.endswith("\n") else x + "\n" for x in nuevos) + feed[fin:].lstrip("\n")
    if VER:
        print(f"   (reordenaría {n} episodios)")
        return
    _gh_put(base, cab, "feed.xml", nuevo.encode("utf-8"), f"feed en orden de Tanaj ({n} episodios)", j["sha"])
    ok(f"{n} episodios en orden; Spotify toma el orden nuevo cuando relea el feed")


# ── 37. podcast_bot: nombre del Rab en el título (canales con "prefijo") y
#   "excluir_titulo" (regex) para saltar series enteras. Se aplica a todos los shows.
MARCA_NOMBRES = "# === nombre del rab y exclusiones (otzar) ==="


def bots_nombres():
    paso(37, "podcast_bot: nombre del Rab en el título y series excluidas")
    n = 0
    for d in sorted(BASE.iterdir()):
        bot = d / "podcast_bot.py"
        if not (d.is_dir() and bot.exists()):
            continue
        s = bot.read_text(encoding="utf-8", errors="replace")
        if MARCA_NOMBRES in s:
            continue
        a1 = "def _lista_plana(url, n, filtro):"
        a2 = '        if filtro and not re.search(filtro, tit, re.I): continue\n        out.append((vid, tit))'
        a3 = '"-o", str(CARPETA / "%(title)s.%(ext)s"), url]'
        a4 = "def bajar_nuevos():\n"
        if not all(x in s for x in (a1, a2, a3, a4)):
            aviso(f"{d.name}: podcast_bot.py distinto, no lo toco")
            continue
        s = s.replace(a1, MARCA_NOMBRES + '''
_EXCLUIR = CFG.get("excluir_titulo") or ""     # regex: titulos que NO se bajan (p. ej. una serie)
_PREFIJO = ""                                    # nombre del Rab del canal en turno

def _nombra(titulo, prefijo):
    # True si el titulo ya trae el nombre (todas las palabras del prefijo salvo 'הרב'/'Rab')
    palabras = [p for p in re.split(r"\\s+", prefijo) if p and p not in ("הרב", 'הרה"ג', "הגאון", "רבי", "Rab", "Rav", "Rabbi", "Sr.")]
    return bool(palabras) and all(p in titulo for p in palabras)

''' + a1, 1)
        s = s.replace(a2, '        if filtro and not re.search(filtro, tit, re.I): continue\n'
                          '        if _EXCLUIR and re.search(_EXCLUIR, tit, re.I): continue   # excluir_titulo\n'
                          '        out.append((vid, tit))', 1)
        s = s.replace(a3, '"-o", str(CARPETA / (((_PREFIJO + " · ") if _PREFIJO and not _nombra(titulo, _PREFIJO) else "") + "%(title)s.%(ext)s")), url]', 1)
        s = s.replace(a4, a4 + "    global _EXCLUIR, _PREFIJO   # === otzar ===\n", 1)
        # por canal: prefijo y exclusión propios
        a5 = '            u = ch; n = cuantos_global; filtro = CFG.get("filtro_titulo"); nombre = u\n'
        if a5 in s:
            s = s.replace(a5, a5 + '        _EXCLUIR = (ch.get("excluir_titulo") if isinstance(ch, dict) else None) or CFG.get("excluir_titulo") or ""\n'
                                   '        _PREFIJO = (ch.get("prefijo") if isinstance(ch, dict) else None) or ""\n', 1)
        else:
            aviso(f"{d.name}: sin el bloque por canal; solo prefijo/exclusión globales")
        try:
            compile(s, str(bot), "exec")
        except SyntaxError as ex:
            aviso(f"{d.name}: el parche no compila ({ex}); no lo toco")
            continue
        respaldar(bot)
        escribir(bot, s)
        n += 1
    ok(f"{n} podcast_bot.py parchados" if n else "todos ya lo tenían")


# ── 39. Feed compacto: cada podcast_bot.py compacta el feed antes de subirlo a GitHub
#   (el de musar creció a 40 MB de espacios y GitHub lo rechazaba con 422: nada se
#   publicaba desde el 29/09). --compactar=show lo arregla ya, sin esperar a ACTUALIZAR.
MARCA_COMPACTO = "# === feed compacto (otzar) ==="


def bots_compacto():
    paso(39, "podcast_bot: feed compacto antes de subirlo a GitHub")
    n = 0
    for d in sorted(BASE.iterdir()):
        bot = d / "podcast_bot.py"
        if not (d.is_dir() and bot.exists()):
            continue
        s = bot.read_text(encoding="utf-8", errors="replace")
        if MARCA_COMPACTO in s:
            continue
        a1 = "def subir_feed_a_github():"
        a2 = '"content": base64.b64encode(Path(FEED).read_bytes()).decode()}'
        if a1 not in s or a2 not in s:
            aviso(f"{d.name}: podcast_bot.py distinto, no lo toco")
            continue
        s = s.replace(a1, MARCA_COMPACTO + '''
def _compacto(s):
    # quita espacio acumulado (lineas en blanco, colas, sangrias enormes): el feed crecia sin fin
    out = []
    for ln in s.splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            continue
        out.append(re.sub(r"^[ \\t]{7,}", "      ", ln))
    return "\\n".join(out) + "\\n"


''' + a1, 1)
        s = s.replace(a2, '"content": base64.b64encode(_feed_compacto_bytes()).decode()}', 1)
        s = s.replace(a1, '''def _feed_compacto_bytes():
    texto = _compacto(Path(FEED).read_text(encoding="utf-8", errors="replace"))
    Path(FEED).write_text(texto, encoding="utf-8")
    return texto.encode("utf-8")


''' + a1, 1)
        try:
            compile(s, str(bot), "exec")
        except SyntaxError as ex:
            aviso(f"{d.name}: el parche no compila ({ex}); no lo toco")
            continue
        respaldar(bot)
        escribir(bot, s)
        n += 1
    ok(f"{n} podcast_bot.py parchados" if n else "todos ya lo tenían")


def compactar():
    show = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--compactar=")), "").strip().lower()
    if not show:
        return
    paso(40, f"{show}: compactar el feed en GitHub")
    d = BASE / show
    c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
    tok = next((p for p in (d / "github_token.txt", BASE / "jabura" / "github_token.txt") if p.exists()), None)
    if not tok:
        aviso("falta github_token.txt")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    try:
        feed, sha = _gh_texto(base, cab, "feed.xml")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed: {e}")
        return
    nuevo = _compactar_feed(feed)
    print(f"   antes: {len(feed.encode('utf-8')) // 1024} KB · después: {len(nuevo.encode('utf-8')) // 1024} KB · episodios: {nuevo.count('<item>')}")
    if VER or len(nuevo) >= len(feed):
        ok("nada que compactar" if len(nuevo) >= len(feed) else "(prueba en seco)")
        return
    _gh_put(base, cab, "feed.xml", nuevo.encode("utf-8"), "feed compacto", sha)
    ok("feed compacto subido; el próximo ACTUALIZAR ya publica")


# ── 38. --nombres=show: prefijo (nombre del Rab en hebreo) para cada canal del show;
#   --excluir=show:regex: series que no se bajan más (p. ej. שער הביטחון en musar).
PREFIJOS_CANAL = {
    "biderman": "הרב אלימלך בידרמן", "ben porat": "הרב יוסף בן פורת", "rosenblum": "הרב ברוך רוזנבלום",
    "amrami": "הרב אייל עמרמי", "gueta": "הרב שניר גואטה", "zamir cohen": "הרב זמיר כהן",
    "yigal cohen": "הרב יגאל כהן", "shalom arush": "הרב שלום ארוש", "panger": "הרב יצחק פנגר",
    "lasri": "הרב מיכאל לסרי", "levinstein": "הרב שלמה לוינשטיין", "shaulov": "הרב רונן שאולוב",
    "alonimail": "",                                     # agregador: sus títulos ya traen el nombre
}


def nombres():
    show = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--nombres=")), "").strip().lower()
    exc = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--excluir=")), "").strip().strip('"')
    if not show and not exc:
        return
    if exc and ":" in exc:
        s_, _, rx = exc.partition(":")
        cfgp = BASE / s_.strip().lower() / "config.json"
        if cfgp.exists():
            paso(38, f"{s_}: no bajar más lo que diga /{rx}/")
            c = json.loads(cfgp.read_text(encoding="utf-8"))
            try:
                re.compile(rx)
            except re.error as ex:
                aviso(f"regex inválida: {ex}")
                return
            c["excluir_titulo"] = rx
            escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            ok(f"excluir_titulo = {rx} (aplica a todos los canales del show)")
            print(f"   → para sacar del feed lo ya subido: python instalar_otzar.py --quitar=\"{s_}:TEXTO\"")
        else:
            aviso(f"no existe {cfgp}")
    if show:
        cfgp = BASE / show / "config.json"
        if not cfgp.exists():
            aviso(f"no existe {cfgp}")
            return
        paso(38, f"{show}: nombre del Rab al frente del título, por canal")
        c = json.loads(cfgp.read_text(encoding="utf-8"))
        canales = c.get("canales_youtube") or []
        puestos = []
        for k, ch in enumerate(canales):
            if not isinstance(ch, dict):
                canales[k] = ch = {"url": ch}
            nombre = (ch.get("nombre") or "").lower()
            if ch.get("prefijo") is not None:
                continue
            pref = next((v for clave, v in PREFIJOS_CANAL.items() if clave in nombre), None)
            if pref is None:
                aviso(f"canal '{ch.get('nombre') or ch.get('url')}': no sé el nombre en hebreo; ponle \"prefijo\" a mano en config.json")
                continue
            ch["prefijo"] = pref
            if pref:
                puestos.append(f"{ch.get('nombre')} → {pref}")
        c["canales_youtube"] = canales
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        for p in puestos:
            print("   · " + p)
        ok(f"{len(puestos)} canal(es) con nombre; el título queda 'הרב X · título' cuando el video no lo trae")


# ── 34. --correo=show:buzon:remitente[,remitente]: los audios llegan por mail ──
#   Deja "correo" en el config.json del show y la contraseña de aplicación en
#   <show>\correo_clave.txt (--correo-clave=XXXX o el archivo a mano). En cada
#   ANUNCIAR, mantenimiento.py corre jabura\correo_shiurim.py: baja adjuntos y
#   links de Drive de esos remitentes, los ordena (parashá → Tehilim → Rut →
#   Ester) y los deja en audios_whatsapp; podcast_bot los publica en ese orden.
def correo():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--correo=")), "").strip().strip('"')
    carp = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--correo-carpeta=")), "").strip().strip('"')
    if carp:
        # modo carpeta: el script de Google (apps_script_correo.gs) deja los audios en Drive
        show, _, ruta = carp.partition(":")
        show, ruta = show.strip().lower(), ruta.strip().strip('"')
        paso(34, f"{show}: audios por correo vía Drive → {ruta}")
        cfgp = BASE / show / "config.json"
        if not cfgp.exists():
            aviso(f"no existe {cfgp}; primero crea el show con --nuevo={show} ...")
            return
        if not VER:
            bajar("otzar/correo_shiurim.py", BASE / "jabura" / "correo_shiurim.py")
            bajar("otzar/apps_script_correo.gs", BASE / "jabura" / "apps_script_correo.gs")
        c = json.loads(cfgp.read_text(encoding="utf-8"))
        c["correo"] = {"carpeta": ruta,
                       "_nota": "el script de Google (jabura\\apps_script_correo.gs) guarda en esa carpeta de Drive los audios que llegan por correo; cada ANUNCIAR los toma de ahí en orden parashá, Tehilim, Rut, Ester"}
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        ok(f"config.json: los audios se toman de {ruta}")
        if not Path(ruta).is_dir():
            aviso("esa carpeta todavía no existe en esta PC: el script de Google la crea en Drive y Drive la baja (Mi unidad\\OTZAR\\taamim)")
        print(f"   → el script para pegar en script.google.com: {BASE / 'jabura' / 'apps_script_correo.gs'}")
        print(f"   → probar: python {BASE / 'jabura' / 'correo_shiurim.py'} {show} --ver")
        return
    if not arg:
        return
    partes = arg.split(":")
    if len(partes) < 3:
        aviso("uso: --correo=show:buzon@dominio:remitente@dominio[,otro@dominio]")
        return
    show, buzon, remitentes = partes[0].strip().lower(), partes[1].strip(), [x.strip() for x in partes[2].split(",") if x.strip()]
    paso(34, f"{show}: audios por correo de {', '.join(remitentes)} al buzón {buzon}")
    d = BASE / show
    cfgp = d / "config.json"
    if not cfgp.exists():
        aviso(f"no existe {cfgp}; primero crea el show con --nuevo={show} ...")
        return
    if not VER:
        bajar("otzar/correo_shiurim.py", BASE / "jabura" / "correo_shiurim.py")
    c = json.loads(cfgp.read_text(encoding="utf-8"))
    co = c.setdefault("correo", {})
    co["usuario"] = buzon
    co["de"] = remitentes
    co.setdefault("servidor", "imap.gmail.com")        # Gmail / Google Workspace
    co.setdefault("desde", time.strftime("%Y-%m-01"))
    co["_nota"] = "cada ANUNCIAR baja los audios (adjuntos o links de Drive) de esos remitentes y los publica en orden: parashá, Tehilim, Rut, Ester"
    escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    ok(f"config.json: correo {buzon} · remitentes {', '.join(remitentes)} · desde {co['desde']}")
    clave = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--correo-clave=")), "").strip().strip('"')
    cp = d / "correo_clave.txt"
    if clave:
        escribir(cp, clave.replace(" ", "") + "\n")
        ok("contraseña guardada en " + str(cp))
    elif cp.exists() or (BASE / "correo_clave.txt").exists():
        ok("ya había contraseña (correo_clave.txt)")
    else:
        aviso(f"falta la contraseña: python instalar_otzar.py --correo={arg} --correo-clave=XXXX")
        print("     (Gmail / Google Workspace: contraseña de APLICACIÓN, no la normal:")
        print("      Cuenta Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones)")
    print(f"   → probar sin guardar nada: python {BASE / 'jabura' / 'correo_shiurim.py'} {show} --ver")
    print("   → luego cada ANUNCIAR los baja, los publica en orden y Spotify los lee")


# ── 33. --parasha=show1,show2: la parasha de la semana desde YouTube, cada semana ──
#   Marca "parasha_semanal": true en el config.json del show (chazaq): en cada
#   ANUNCIAR, mantenimiento.py corre jabura\parasha_youtube.py, que busca en el
#   canal del show el shiur de la parasha que viene, lo publica y el robot lo
#   anuncia. También deja "parasha": {"auto": true, "dia": 0} en el robot: las dos
#   (Rav Asher Weiss con parasha_semanal.js y chazaq) salen con el ANUNCIAR del lunes.
#   --sin-parasha=show lo quita.
def parasha():
    poner = [x.strip().lower() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--parasha=")), "").split(",") if x.strip()]
    quitar_ = [x.strip().lower() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--sin-parasha=")), "").split(",") if x.strip()]
    if not poner and not quitar_:
        return
    paso(33, "Parasha semanal desde YouTube: " + ", ".join(poner + ["sin " + q for q in quitar_]))
    if not VER:
        bajar("otzar/parasha_youtube.py", BASE / "jabura" / "parasha_youtube.py")
    for show in poner + quitar_:
        cfgp = BASE / show / "config.json"
        if not cfgp.exists():
            aviso(f"no existe {cfgp}")
            continue
        try:
            c = json.loads(cfgp.read_text(encoding="utf-8"))
        except Exception as ex:
            aviso(f"{show}: config.json ilegible ({ex})")
            continue
        if show in quitar_:
            c.pop("parasha_semanal", None)
            escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2))
            ok(f"{show}: ya no busca la parasha")
            continue
        if not (c.get("canales_youtube") or c.get("canal_youtube")):
            aviso(f"{show}: no tiene canales_youtube en config.json; no sé de dónde bajar")
        c["parasha_semanal"] = True
        c.setdefault("parasha_max", 2)
        c["parasha_min_minutos"] = min(int(c.get("parasha_min_minutos") or 2), 2)
        c["_parasha_nota"] = ("cada ANUNCIAR busca en el canal el shiur de la parasha de la semana (hasta parasha_max, "
                              "mínimo parasha_min_minutos), lo publica y el robot lo anuncia; candado parasha_ultimo.json")
        escribir(cfgp, json.dumps(c, ensure_ascii=False, indent=2))
        ok(f"{show}: parasha_semanal activada (hasta {c['parasha_max']} shiurim por semana)")
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if poner and rw.exists():
        try:
            cfgw = json.loads(rw.read_text(encoding="utf-8"))
        except Exception:
            cfgw = None
        if cfgw is not None and not ((cfgw.get("parasha") or {}).get("auto") and "dia" in (cfgw.get("parasha") or {})):
            cfgw.setdefault("parasha", {})
            cfgw["parasha"]["auto"] = True
            cfgw["parasha"].setdefault("dia", 0)
            cfgw["parasha"]["_nota"] = ("dia 0 = lunes: con el ANUNCIAR de ese día (o el primero de la semana hasta el viernes) "
                                        "salen la parasha de Rav Asher Weiss (parasha_semanal.js) y la de los shows con parasha_semanal")
            respaldar(rw)
            escribir(rw, json.dumps(cfgw, ensure_ascii=False, indent=2))
            ok("robot: las parashot salen con el ANUNCIAR del lunes (parasha.auto, parasha.dia = 0)")
    print(f"   → probar sin bajar nada: python {BASE / 'jabura' / 'parasha_youtube.py'} {' '.join(poner)} --ver")
    print("   → esta semana y la que viene son jag (Sukot, Sheminí Atzeret): el primer shiur sale para Bereshit")


# ── 28. --listar=RUTA: ver qué hay en una carpeta (subcarpetas y archivos) ──────
def listar():
    ruta = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--listar=")), "").strip().strip('"')
    if not ruta:
        return
    paso(28, f"Contenido de {ruta}")
    base = Path(ruta)
    if not base.is_dir():
        aviso("no existe esa carpeta (¿está montado el Drive? ¿el nombre es exacto?)")
        padre = base.parent
        if padre.is_dir():
            print("   en la carpeta de arriba hay:")
            for x in sorted(padre.iterdir()):
                print(f"     · {'[carpeta] ' if x.is_dir() else ''}{x.name}")
        return
    total = 0
    for carpeta, subs, archivos in os.walk(base):
        rel = os.path.relpath(carpeta, base)
        print(f"   [{'.' if rel == '.' else rel}]  ({len(archivos)} archivos)")
        for f in sorted(archivos):
            p = Path(carpeta) / f
            try:
                kb = p.stat().st_size // 1024
                cuando = time.strftime("%d/%m/%Y %H:%M", time.localtime(p.stat().st_mtime))
            except Exception:
                kb, cuando = 0, "?"
            print(f"     · {f}  ({kb} KB, {cuando})")
            total += 1
    print(f"   total: {total} archivos")


# ── 27. --mismo-podcast=repo:URL_RSS_VIEJO  /  --mismo-podcast=repo:restaurar ──
#   Spotify solo acepta "Update RSS feed" si el feed nuevo parece EL MISMO podcast
#   que el viejo (mismo título, autor y correo del canal). Se copian esos datos del
#   RSS viejo al feed del repo, se hace el Update en Spotify, y con :restaurar
#   vuelven los datos de siempre (Spotify los actualiza en la siguiente lectura).
def mismo_podcast():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--mismo-podcast=")), "")
    if not arg or ":" not in arg:
        return
    repo, fuente = arg.split(":", 1)
    repo, fuente = repo.strip(), fuente.strip()
    paso(27, f"{repo}: que Spotify lo acepte como el mismo podcast")
    tok = next((BASE / m / "github_token.txt" for m in (repo, "nacach", "peretz", "jabura") if (BASE / m / "github_token.txt").exists()), None)
    if not tok:
        aviso("no encuentro github_token.txt")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/rabmeireliyahu/{repo}"
    try:
        j = _gh_get(base, cab, "feed.xml")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed de {repo}: {e}")
        return
    feed = base64.b64decode(j["content"]).decode("utf-8")
    canal = feed.split("<item>", 1)[0]
    campos = {"title": r"<title>(.*?)</title>", "author": r"<itunes:author>(.*?)</itunes:author>",
              "name": r"<itunes:name>(.*?)</itunes:name>", "email": r"<itunes:email>(.*?)</itunes:email>"}
    guardado = BASE / repo
    guardado.mkdir(exist_ok=True)
    guardado = guardado / "canal_original.json"
    if fuente.lower() == "restaurar":
        if not guardado.exists():
            aviso("no hay datos guardados que restaurar")
            return
        nuevos = json.loads(guardado.read_text(encoding="utf-8"))
        origen = "los datos de siempre"
    else:
        try:
            with urllib.request.urlopen(urllib.request.Request(fuente, headers={"User-Agent": "instalar-otzar"}), timeout=60) as r:
                viejo = r.read().decode("utf-8", "replace").split("<item>", 1)[0]
        except Exception as e:                              # noqa: BLE001
            aviso(f"no pude leer el RSS viejo: {e}")
            return
        nuevos = {k: (re.search(p, viejo, re.S).group(1).strip() if re.search(p, viejo, re.S) else None) for k, p in campos.items()}
        nuevos = {k: v for k, v in nuevos.items() if v}
        if not nuevos.get("title"):
            aviso("el RSS viejo no trae título; no hago nada")
            return
        if not guardado.exists():
            actuales = {k: (re.search(p, canal, re.S).group(1).strip() if re.search(p, canal, re.S) else None) for k, p in campos.items()}
            escribir(guardado, json.dumps({k: v for k, v in actuales.items() if v}, ensure_ascii=False, indent=2))
        origen = "los datos del RSS viejo de Spotify"
    canal2 = canal
    for k, p in campos.items():
        if nuevos.get(k) and re.search(p, canal2, re.S):
            canal2 = re.sub(p, lambda m, k=k: m.group(0).replace(m.group(1), nuevos[k]), canal2, count=1, flags=re.S)
    if canal2 == canal:
        ok("el feed ya tiene esos datos")
    elif not VER:
        _gh_put(base, cab, "feed.xml", (canal2 + "<item>" + feed.split("<item>", 1)[1]).encode("utf-8"),
                f"canal: {'restaurar' if fuente.lower() == 'restaurar' else 'como el RSS viejo para el Update en Spotify'}", j["sha"])
        ok(f"feed de {repo} con {origen}: título '{nuevos.get('title')}'" + (f", autor '{nuevos['author']}'" if nuevos.get("author") else "") + (f", correo {nuevos['email']}" if nuevos.get("email") else ""))
    if fuente.lower() != "restaurar":
        print("   → GitHub Pages tarda 1-3 minutos en servir el feed nuevo. Luego en Spotify for Creators: Settings → Details → RSS feed → Update →")
        print(f"     https://rabmeireliyahu.github.io/{repo}/feed.xml   y cuando lo acepte:")
        print(f"     python instalar_otzar.py --sin-drive --mismo-podcast={repo}:restaurar")


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


# ── 21. --quitar=show:texto1|texto2  y  --vaciar-fuente=show ─────────────────
#   Saca del feed (y de Spotify, que lo lee) los episodios cuyo título contenga
#   alguno de los textos, borra sus archivos locales y los marca para que no
#   vuelvan a entrar. --vaciar-fuente borra TODO lo que hay en audios_whatsapp
#   del show (audios captados de donde no debían).
def quitar():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--quitar=")), "")
    vaciar = [x.strip() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--vaciar-fuente=")), "").split(",") if x.strip()]
    if not arg and not vaciar:
        return
    paso(21, "Quitar lo que no era del show")
    for show in vaciar:
        d = BASE / show
        c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
        carpeta = Path(c.get("carpeta_whatsapp") or (d / "audios_whatsapp"))
        n = 0
        for f in list(carpeta.glob("*")) + list((d / "episodios").glob("*.mp3")):
            if f.is_file() and f.suffix.lower() in AUDIO:
                if not VER:
                    f.unlink()
                n += 1
        ok(f"{show}: {n} audio(s) captados borrados de la carpeta de WhatsApp y episodios")
    if not arg or ":" not in arg:
        return
    show, textos = arg.split(":", 1)
    textos = [t.strip().lower() for t in textos.split("|") if t.strip()]
    d = BASE / show
    c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
    tok = d / "github_token.txt"
    if not tok.exists():
        aviso("falta github_token.txt en la carpeta del show")
        return
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
    try:
        feed, sha_feed = _gh_texto(base, cab, "feed.xml")
        j = {"sha": sha_feed}
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el feed: {e}")
        return
    feed = _compactar_feed(feed)
    def fuera(m):
        it = m.group(0)
        t = re.search(r"<title>(.*?)</title>", it, re.S)
        titulo = (t.group(1) if t else "").lower()
        return "" if any(x in titulo for x in textos) else it
    nuevo = re.sub(r"[ \t]*<item>[\s\S]*?</item>\n?", fuera, feed)
    quitados = feed.count("<item>") - nuevo.count("<item>")
    if quitados and not VER:
        cuerpo = {"message": f"quitar {quitados} episodio(s) que no eran del show", "sha": j["sha"],
                  "content": base64.b64encode(nuevo.encode("utf-8")).decode()}
        req = urllib.request.Request(f"{base}/contents/feed.xml", data=json.dumps(cuerpo).encode(), headers=cab, method="PUT")
        with urllib.request.urlopen(req, timeout=120):
            pass
    ok(f"{show}: {quitados} episodio(s) quitados del feed (Spotify los quita al releerlo)")
    if show == "nacach" and quitados and not VER:
        subprocess.run([sys.executable, "espejo_nacash.py"], cwd=str(d))
    # archivos locales y marca de procesado, para que no vuelvan a entrar
    carpeta = Path(c.get("carpeta_whatsapp") or (d / "audios_whatsapp"))
    procesados = d / "procesados_whatsapp.txt"
    lista = procesados.read_text(encoding="utf-8").splitlines() if procesados.exists() else []
    n = 0
    for f in list(carpeta.glob("*")) + list((d / "episodios").glob("*.mp3")):
        if f.is_file() and any(x in f.name.lower() for x in textos):
            if f.name not in lista:
                lista.append(f.name)
            if not VER:
                f.unlink()
            n += 1
    if not VER:
        procesados.write_text("\n".join(lista) + ("\n" if lista else ""), encoding="utf-8")
    ok(f"{show}: {n} archivo(s) locales borrados y marcados")


# ── 22. --anunciar-tambien=efshar,otro: también en los grupos generales ───────
def anunciar_tambien():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--anunciar-tambien=")), "")
    if not arg:
        return
    paso(22, "Anunciar también en los grupos generales")
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    generales = (cfg.get("anunciar", {}).get("nacach") or {}).get("invite") or []
    generales = generales if isinstance(generales, list) else [generales]
    if not generales:
        aviso("nacach no tiene grupos generales configurados (--grupos-generales=L1,L2)")
        return
    cambio = False
    for show in [x.strip() for x in arg.split(",") if x.strip()]:
        an = cfg.get("anunciar", {}).get(show)
        if not an:
            aviso(f"{show} no está en anunciar")
            continue
        inv = an.get("invite") or []
        inv = inv if isinstance(inv, list) else ([inv] if inv else [])
        nuevos = [g for g in generales if g not in inv]
        if nuevos:
            an["invite"] = inv + nuevos
            cambio = True
        ok(f"{show}: anuncia en {len(inv) + len(nuevos)} grupos (sus {len(inv)} + {len(nuevos)} generales)")
    if cambio:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


# ── 23. --verificar=repo1,repo2 [--spotify-ver=LINK1,LINK2]: qué sirve cada feed
#        y qué muestra cada show en Spotify, para ver cuál lee cuál ──────────────
def verificar():
    repos = [x.strip() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--verificar=")), "").split(",") if x.strip()]
    shows = [x.strip() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--spotify-ver=")), "").split(",") if x.strip()]
    if not repos and not shows:
        return
    paso(23, "Verificar feeds y shows")
    for repo in repos:
        url = FEED_JABURA if repo == "jabura" else f"https://rabmeireliyahu.github.io/{repo}/feed.xml"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "instalar-otzar"}), timeout=30) as r:
                feed = r.read().decode("utf-8", "replace")
        except Exception as e:                              # noqa: BLE001
            aviso(f"{repo}: no pude leer {url} ({e})")
            continue
        titulos = re.findall(r"<title>(.*?)</title>", feed, re.S)
        img = re.search(r'<itunes:image href="([^"]+)"', feed)
        print(f"   {repo}: canal '{titulos[0].strip() if titulos else '?'}' · {feed.count('<item>')} episodios · "
              f"último: '{titulos[-1].strip()[:50] if len(titulos) > 1 else '-'}' · portada: {img.group(1).split('/')[-1] if img else '?'}")
        try:
            an = json.loads(((ROBOT or BASE) / "config_whatsapp.json").read_text(encoding="utf-8")).get("anunciar", {}).get(repo) or {}
            if str(an.get("spotify", "")).startswith("http"):
                print(f"      en el robot, {repo} anuncia con el show {an['spotify'].split('?')[0]}")
        except Exception:
            pass
    if shows and not any("show/" in x for x in shows):
        aviso("--spotify-ver= necesita los links de los shows (https://open.spotify.com/show/...), separados por coma")
        shows = []
    if shows:
        llaves = None
        for ruta in [(ROBOT or BASE) / "spotify_keys.txt", BASE / "jabura" / "spotify_keys.txt"]:
            try:
                l = [x.strip() for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
                if len(l) >= 2:
                    llaves = (l[0], l[1])
                    break
            except Exception:
                pass
        if not llaves:
            aviso("sin spotify_keys.txt; no puedo consultar Spotify")
            return
        try:
            cred = base64.b64encode(f"{llaves[0]}:{llaves[1]}".encode()).decode()
            req = urllib.request.Request("https://accounts.spotify.com/api/token", data=b"grant_type=client_credentials",
                                         headers={"Authorization": "Basic " + cred, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=30) as r:
                token = json.loads(r.read().decode())["access_token"]
        except Exception as e:                              # noqa: BLE001
            aviso(f"Spotify no aceptó las llaves: {e}")
            return
        for link in shows:
            m = re.search(r"show/([A-Za-z0-9]+)", link)
            if not m:
                continue
            try:
                with urllib.request.urlopen(urllib.request.Request(f"https://api.spotify.com/v1/shows/{m.group(1)}?market=MX",
                                                                   headers={"Authorization": "Bearer " + token}), timeout=30) as r:
                    sh = json.loads(r.read().decode())
                eps = [e for e in (sh.get("episodes") or {}).get("items") or [] if e]
                print(f"   Spotify {m.group(1)}: '{sh.get('name')}' · {sh.get('total_episodes')} episodios · "
                      f"más nuevo: '{eps[0]['name'][:50] if eps else '-'}' · portada: {(sh.get('images') or [{}])[0].get('url', '?')[-30:]}")
            except Exception as e:                          # noqa: BLE001
                aviso(f"{link}: {e}")


# ── 24. clases sin texto: título por defecto y rescate de lo apartado ───────────
def titulos_defecto():
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    paso(24, "Audios sin título: se publican con el nombre del show y la fecha")
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    cambio = False
    def entradas(show):
        # donde se configura el show: escuchar.<show> y/o sus entradas de escuchar_directo
        lista = []
        esc = (cfg.get("escuchar") or {}).get(show)
        if isinstance(esc, dict):
            lista.append(esc)
        lista += [e for e in (cfg.get("escuchar_directo") or []) if isinstance(e, dict) and e.get("show") == show]
        return lista
    for show, titulo in TITULOS_DEFECTO.items():
        for esc in entradas(show):
            if not esc.get("titulo_defecto"):
                esc["titulo_defecto"] = titulo
                cambio = True
    for show, pref in PREFIJOS.items():
        puesto = False
        for esc in entradas(show):
            if esc.get("prefijo_titulo") != pref:
                esc["prefijo_titulo"] = pref
                cambio = True
                puesto = True
        if puesto:
            ok(f"{show}: los títulos llevan \"{pref}\" al frente")
        elif not entradas(show) and show not in SUFIJOS_ANUNCIO:
            aviso(f"{show}: no está en escuchar ni en escuchar_directo del robot; no sé de dónde toma audios")
    for show, reglas in REGLAS_TITULO.items():
        for esc in entradas(show):
            for k, val in reglas.items():
                if esc.get(k) != val:
                    esc[k] = val
                    cambio = True
        if entradas(show):
            ok(f"{show}: título = líneas del mensaje sin el número de siman, unidas con ', ' y \"{reglas.get('sufijo_titulo', '')}\" al final")
    for show, suf in SUFIJOS_ANUNCIO.items():
        an = (cfg.get("anunciar") or {}).get(show)
        if isinstance(an, dict) and an.get("sufijo_anuncio") != suf:
            an["sufijo_anuncio"] = suf
            cambio = True
            ok(f"{show}: el anuncio dice el título y luego \"{suf}\"")
    if cambio:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok(", ".join(f"{k}: '{v}'" for k, v in TITULOS_DEFECTO.items() if k in (cfg.get("escuchar") or {})))
    # lo que el subidor ya apartó como "sin título" vuelve con el nombre por defecto
    for show, titulo in TITULOS_DEFECTO.items():
        d = BASE / show
        c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
        carpeta = Path(c.get("carpeta_whatsapp") or (d / "audios_whatsapp"))
        apart = carpeta / "_SIN_TITULO_renombrar"
        if not apart.is_dir():
            continue
        for f in sorted(apart.glob("*")):
            if not (f.is_file() and f.suffix.lower() in AUDIO):
                continue
            m = re.search(r"(\d{1,2}-\d{1,2}-\d{4})", f.stem)
            nuevo = f"{titulo} {m.group(1) if m else time.strftime('%d-%m-%Y', time.localtime(f.stat().st_mtime))}"
            destino = carpeta / (nuevo + f.suffix.lower())
            k = 2
            while destino.exists():
                destino = carpeta / f"{nuevo} ({k}){f.suffix.lower()}"
                k += 1
            if not VER:
                shutil.move(str(f), str(destino))
            ok(f"{show}: '{f.name}' → '{destino.name}' (se publica en el próximo ANUNCIAR)")


# ── 25. fuentes: de qué grupo toma audios cada show y si el robot ya lo ubicó ──
def fuentes():
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    paso(25, "Fuentes: de qué grupo toma audios cada show (y de cuáles NO)")
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    cambio = False
    for show, nombre in FUENTES_NUEVAS.items():
        # el grupo del Rab como fuente (además del chat directo, si lo hay)
        if show in (cfg.get("escuchar") or {}):
            continue
        carpeta = next((e.get("carpetaDestino") for e in (cfg.get("escuchar_directo") or []) if e.get("show") == show and e.get("carpetaDestino")), None)
        if not carpeta:
            c = BASE / show / "config.json"
            try:
                carpeta = json.loads(c.read_text(encoding="utf-8")).get("carpeta_whatsapp")
            except Exception:
                carpeta = None
        carpeta = carpeta or str(BASE / show / "audios_whatsapp")
        cfg.setdefault("escuchar", {})[show] = {"invite": "", "nombre": nombre, "carpetaDestino": carpeta}
        cambio = True
        ok(f"{show}: su grupo \"{nombre}\" queda como fuente de audios (carpeta {carpeta})")
    for show, nombre in NOMBRES_FUENTE.items():
        esc = (cfg.get("escuchar") or {}).get(show)
        if isinstance(esc, dict) and not esc.get("nombre"):
            esc["nombre"] = nombre
            cambio = True
    gn = cfg.setdefault("grupos_nombre", {})
    for link, nombre in GRUPOS_NOMBRE.items():
        if gn.get(link) != nombre:
            gn[link] = nombre
            cambio = True
            ok(f"si el link {link.split('/')[-1]} da bad-request, el robot busca el grupo \"{nombre}\" por nombre")
    if cambio:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    try:
        r = json.loads(((ROBOT or BASE) / "grupos_registrados.json").read_text(encoding="utf-8"))
    except Exception:
        r = {}
    faltan = []
    for show, esc in sorted((cfg.get("escuchar") or {}).items()):
        if not isinstance(esc, dict):
            continue
        an = (cfg.get("anunciar") or {}).get(show) or {}
        inv = an.get("invite")
        anuncia = bool(inv) if not isinstance(inv, list) else bool(inv)
        # peretz: su grupo de anuncios es también su fuente (regla fija del robot)
        g = r.get("escucha:" + show) or (r.get(show) if (show == "peretz" or not anuncia) else None)
        an_reg = r.get(show) or {}
        an_nombres = [x.get("nombre", "?") for x in (an_reg.get("grupos") or ([an_reg] if an_reg.get("id") else []))]
        donde = ("anuncia en: " + " + ".join(an_nombres)) if an_nombres else "no anuncia en grupos"
        if g and g.get("id"):
            ok(f"{show}: toma audios de \"{g.get('nombre', g['id'])}\" · {donde}")
        elif esc.get("invite") or esc.get("nombre"):
            aviso(f"{show}: FUENTE SIN UBICAR (el robot ignora sus audios) · {donde}")
            print(f"     link de la fuente en el config: {esc.get('invite') or '(ninguno)'}" + (f" · nombre: {esc['nombre']}" if esc.get("nombre") else ""))
            faltan.append(show)
        else:
            print(f"   · {show}: sin grupo fuente en el config · {donde}")
    for e in cfg.get("escuchar_directo") or []:
        dm = r.get("dm:" + str(e.get("show")))
        print(f"   · {e.get('show')}: chat directo " + (f"reconocido ({dm.get('id')})" if dm else f"del número {e.get('numero', '?')} (aún no escribe)"))
    if faltan:
        print("   → arranca el robot; al conectar busca cada fuente por link y por nombre. Si sigue sin ubicarla,")
        print("     manda el texto  !otzar <show>  DENTRO del grupo del Rab (p. ej. !otzar tefila) y vuelve a correr esto.")


# ── 26. Spotify: link exacto solo cuando el show ya lee nuestro feed ────────────
#   Mientras el show siga alojado en Spotify (sin redirect), los episodios nuevos
#   no existen ahí y el robot se quedaría esperando el link exacto para siempre.
#   Hasta entonces: link del show + audio directo. --redirigido=tefila,hilu lo cambia.
SHOWS_REDIRECT = ("tefila", "hilu", "credi", "isaaccredi")
def spotify_redirigido():
    rw = (ROBOT or BASE) / "config_whatsapp.json"
    if not rw.exists():
        return
    marcar = [x.strip() for x in next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--redirigido=")), "").split(",") if x.strip()]
    paso(26, "Spotify: link exacto del episodio solo cuando el show ya lee nuestro feed")
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    cambio = False
    for show in SHOWS_REDIRECT:
        an = (cfg.get("anunciar") or {}).get(show)
        if not isinstance(an, dict):
            continue
        if show in marcar and not an.get("redirigido"):
            an["redirigido"] = True
            cambio = True
        tiene = str(an.get("spotify", "")).startswith("http") and bool(an.get("redirigido"))
        if an.get("sin_spotify") != (not tiene) or an.get("link_audio"):
            an["sin_spotify"] = not tiene
            an["link_audio"] = False
            cambio = True
        if tiene:
            ok(f"{show}: link EXACTO del episodio en Spotify")
        else:
            print(f"   · {show}: link del SHOW en Spotify (aún no lee "
                  f"https://rabmeireliyahu.github.io/{show}/feed.xml)")
    quitados = []
    for show, an in (cfg.get("anunciar") or {}).items():
        if isinstance(an, dict) and an.get("link_audio"):
            an["link_audio"] = False
            cambio = True
            quitados.append(show)
    if quitados:
        ok("sin link al audio en: " + ", ".join(quitados) + " (solo título, Spotify y WhatsApp)")
    if cambio:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    pend = [s for s in SHOWS_REDIRECT if isinstance((cfg.get("anunciar") or {}).get(s), dict) and not (cfg["anunciar"][s].get("redirigido"))]
    if pend:
        print("   → cuando hagas el redirect en Spotify for Creators (Settings → Redirect to a new host → el feed.xml de arriba):")
        print(f"     python instalar_otzar.py --sin-drive --redirigido={','.join(pend)}")


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
        # lo de los últimos 2 días sale completo (si no son más de 10)
        recientes = [g for c, g in pares if c >= time.time() - 2 * 86400]
        if dejar and len(recientes) <= 30:
            ultimos = list(dict.fromkeys(ultimos + recientes))
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
        claves = ("GUARDADO", "IGNORADO", "Esperando titulo", "escucha ", "Mekorot", "AUDIO", "REGISTRADO", "RECUPERADOS", "ANUNCIADO", "FUENTE", "invitacion", "sin ID")
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
        if not grupo.startswith("http") and str(esc.get("invite", "")).startswith("http"):
            grupo = esc["invite"].split("?")[0]   # el link que ya estaba en el config
        esc["carpetaDestino"] = carpeta_wa
        esc.setdefault("nombre", NOMBRES_FUENTE["tefila"])
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
        if not generales:
            # sin --grupos-generales: los que ya tenga nacach (los generales de siempre)
            g_n = (cfg.get("anunciar", {}).get("nacach") or {}).get("invite") or []
            generales = [g for g in (g_n if isinstance(g_n, list) else [g_n]) if str(g).startswith("http")]
        # el aviso va al grupo del Rab (primero, para que "Whatsapp" sea el link de SU grupo)
        # y a los grupos generales; sin audio, porque en su grupo ya está
        generales = [g for g in generales if g.split("?")[0] not in SIN_GRUPO.get("tefila", [])]
        destinos = ([grupo] if grupo.startswith("http") else []) + [g for g in generales if g != grupo]
        if destinos:
            an["invite"] = destinos if len(destinos) > 1 else destinos[0]
            an["sin_whatsapp"] = not grupo.startswith("http")
            ok(f"anuncios de tefila a su grupo + {len(generales)} grupo(s) generales (6 y 3)")
        esc["prefijo_titulo"] = PREFIJOS["tefila"]
        for k, v in {"idioma": "es", "max_anuncios": 2, "en_orden": True, "sin_audio": True, "sin_whatsapp": True}.items():
            an.setdefault(k, v)
        if spot.startswith("http"):
            an["spotify"] = spot
        tiene_spotify = str(an.get("spotify", "")).startswith("http") and bool(an.get("redirigido"))
        an["sin_spotify"] = not tiene_spotify
        an["link_audio"] = False
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
        ok("anunciar.tefila " + ("ACTIVO con link exacto de Spotify" if tiene_spotify else ("ACTIVO con link del show + audio (hasta el redirect en Spotify)" if tiene_grupos else "en pausa: faltan los grupos generales (--grupos-generales=L1,L2)")))
    # ¿el grupo ya está registrado?
    reg = (ROBOT or BASE) / "grupos_registrados.json"
    try:
        r = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:
        r = {}
    an_reg = r.get("tefila") or {}
    an_nombres = [x.get("nombre", "?") for x in (an_reg.get("grupos") or ([an_reg] if an_reg.get("id") else []))]
    if an_nombres:
        ok("anuncia en: " + " + ".join(an_nombres))
    g = r.get("escucha:tefila")
    if g and g.get("id"):
        ok(f"FUENTE de audios (donde el Rab manda): {g.get('nombre', g['id'])}")
        if "peret" in str(g.get("nombre", "")).lower():
            aviso("¡esa fuente es de Peretz! Manda \"!otzar tefila\" en el grupo del Rab para corregirlo")
    else:
        aviso("FUENTE SIN registrar: el robot NO sabe cuál es Clases Tefila Habitat, por eso ignora los audios del Rab")
        print("   → con el robot prendido (ya reiniciado), manda el texto  !otzar tefila  dentro de Clases Tefila Habitat;")
        print("     el robot contesta en su ventana 'REGISTRADO fuente de audios: tefila'. Luego reenvía el audio del Rab ahí.")
    # portada: Spotify no la refresca si la URL no cambia -> nombre fechado en el feed
    if (d / "github_token.txt").exists() and cfgp.exists():
        try:
            c_ = json.loads(cfgp.read_text(encoding="utf-8"))
            cab_ = {"Authorization": "token " + (d / "github_token.txt").read_text(encoding="utf-8").strip(),
                    "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
            portada_fechada("tefila", c_, cab_)
        except Exception as e:                              # noqa: BLE001
            aviso(f"portada de tefila: {e}")
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
        bajar("otzar/parasha_youtube.py", BASE / "jabura" / "parasha_youtube.py")
        bajar("otzar/correo_shiurim.py", BASE / "jabura" / "correo_shiurim.py")
        bajar("otzar/robot_fiestas.py", BASE / "robot_fiestas.py")   # fiestas pasadas (mantenimiento lo lee)
        bajar("otzar/diagnostico.py", BASE / "jabura" / "diagnostico.py")
        bajar("otzar/plataformas.py", BASE / "jabura" / "plataformas.py")    # Apple/Amazon/Spotify por show (una vez al día)
        bajar("otzar/piloto.py", BASE / "jabura" / "piloto.py")   # (oct/2026) piloto automático
        bajar("otzar/PILOTO.bat", ROBOT / "PILOTO.bat")
        bajar("otzar/mudanza.py", BASE / "jabura" / "mudanza.py")   # (oct/2026) pasar todo a la HP
        bajar("otzar/revisar_spotify.py", BASE / "jabura" / "revisar_spotify.py")   # ¿por qué no se ve en Spotify?
        bajar("otzar/soundcloud_subir.py", BASE / "jabura" / "soundcloud_subir.py")   # SoundCloud automático (si hay llaves)   # "por qué no salió": python diagnostico.py <show>
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


# ── 41. rescatar audios perdidos ──────────────────────────────────────────────
#   --rescatar=hilu,jabura[:dias]  (5 días por defecto)
#   Deja C:\robotwhats\rescatar.json: al arrancar, el robot le pide a WhatsApp los
#   últimos mensajes del grupo fuente de cada show y guarda los audios que llegaron
#   después del último que ya está en su carpeta (nunca duplica). Además busca si
#   el audio quedó mal guardado (antes, uno que esperaba título y sobrevivía a un
#   reinicio caía en la carpeta de Peretz).
def rescatar():
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--rescatar=")), "")
    if not arg:
        return
    dias = 5
    if ":" in arg:
        arg, d = arg.rsplit(":", 1)
        dias = int(d) if d.strip().isdigit() else 5
    shows_ = [x.strip().lower() for x in arg.split(",") if x.strip()]
    paso(41, "Rescatar audios perdidos: " + ", ".join(shows_) + f" (últimos {dias} días)")
    if not ROBOT:
        aviso("sin carpeta del robot no puedo rescatar")
        return
    cfgw = json.loads((ROBOT / "config_whatsapp.json").read_text(encoding="utf-8"))
    try:
        reg = json.loads((ROBOT / "grupos_registrados.json").read_text(encoding="utf-8"))
    except Exception:
        reg = {}
    from datetime import datetime, timedelta
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00")
    rp = ROBOT / "rescatar.json"
    try:
        pend = json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        pend = {}
    for show in shows_:
        fuente = (reg.get("escucha:" + show) or (reg.get("peretz") if show == "peretz" else None) or {})
        if not fuente.get("id"):
            aviso(f"{show}: no tiene grupo fuente registrado; no se puede rescatar")
            continue
        pend[show] = {"desde": desde}
        if ((cfgw.get("escuchar") or {}).get(show) or {}).get("guardar_documentos"):
            pend[show]["documentos"] = True             # también los PDF/Word (mekorot)
        ok(f"{show}: el robot pedirá a WhatsApp los mensajes de \"{fuente.get('nombre', '?')}\" desde {desde[:10]}")
    if not VER:
        rp.write_text(json.dumps(pend, ensure_ascii=False, indent=2), encoding="utf-8")
    # ¿quedó guardado en otra carpeta?
    limite = time.time() - dias * 86400
    peretz = ((cfgw.get("escuchar") or {}).get("peretz") or {}).get("carpetaDestino")
    vistos = []
    for raiz in [peretz, str(ROBOT / "audios_esperando_titulo")]:
        if not raiz or not Path(raiz).exists():
            continue
        for f in Path(raiz).rglob("*"):
            try:
                if f.is_file() and f.suffix.lower() in (".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wav", ".amr") \
                        and f.stat().st_mtime >= limite and (raiz != peretz or f.name.lower().startswith("shiur ")):
                    vistos.append(f)
            except Exception:
                pass
    try:
        log_lineas = (ROBOT / "robot_whatsapp.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        log_lineas = []
    raros = [l for l in log_lineas[-20000:] if ("GUARDADO [?]" in l or "RECUPERADOS" in l)]
    if vistos or raros:
        print("   · audios que pudieron quedar en otra carpeta (revísalos):")
        for f in vistos[:15]:
            print("     ", time.strftime("%d/%m %H:%M", time.localtime(f.stat().st_mtime)), f)
        for l in raros[-10:]:
            print("     ", l[:200])
    else:
        ok("ningún audio quedó mal guardado")
    print("   → cierra TODAS las ventanas del robot y abre una sola: en 1-2 minutos el log dice")
    print("     \"RESCATE <show>: llegaron N mensajes...\" y \"GUARDADO [<show>]\". Luego aprieta ANUNCIAR.")


# ── 42. Rab Yosef Tawil ───────────────────────────────────────────────────────
#   --tawil [--tawil-rss=RSS_DEL_SHOW_EN_SPOTIFY] [--tawil-numero=TELEFONO]
#   Yehuda Avi Ezri manda cada semana los audios con "Dia 21. Domingo" al grupo
#   fuente (TAWIL["fuente"]); el robot los toma de ahí, les pone el tema de la semana ("#21 Encendido de Velas (1)", temas en
#   tools/otzar/temas/tawil.json o "!tema tawil 27 Tema" por WhatsApp), les da la
#   fecha de su día y los publica (archive.org + feed → Spotify, Apple, Amazon).
#   Cada uno se anuncia SU día en los dos grupos de Tawil y en los generales (3 y 6)
#   con el formato: fecha hebrea / civil, título, plataformas, L"N y link del grupo.
TAWIL = {
    "nombre": 'Harav Yosef Tawil Shlit"a',
    "spotify": "https://open.spotify.com/show/1gVVXZw6fNyrcqadB5pmLC",
    "grupos": ["https://chat.whatsapp.com/EeNJLWF5dbE3VqCX5WUCU2",
               "https://chat.whatsapp.com/JQRxF5FJDN05aI9otVcLE8"],
    "whatsapp_link": "https://chat.whatsapp.com/JQRxF5FJDN05aI9otVcLE8",
    "fuente": "https://chat.whatsapp.com/KE2AgbfPaGaElrVS8kwdJt",       # donde Yehuda manda los audios
    "calendario": {"n": 21, "fecha": "2026-10-11"},                      # el #21 salió el domingo 11/10; uno por día, sin Shabat ni Yom Tov
    "dedicatoria": 'L"N\nMoshe Ben Sara\nMiriam Bat Lea Luisa',
    "plantilla": ["{fecha_hebrea}\n{fecha}", "*{titulo}*", "*Spotify*\n{spotify}", "*Apple Podcasts*\n{apple}",
                  "*Amazon Music*\n{amazon}", "*SoundCloud*\n{soundcloud}", "{dedicatoria}",
                  "*Grupo de WhatsApp*\n{whatsapp}"],
}


def tawil():
    if not any(a == "--tawil" or a.startswith("--tawil-") for a in sys.argv):
        return
    arg = lambda k: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), "").strip()
    rss, numero = arg("tawil-rss"), re.sub(r"\D", "", arg("tawil-numero"))
    viejo = sys.argv[:]
    sys.argv = [a for a in sys.argv if not a.startswith("--nuevo")] + \
        ["--nuevo=tawil", "--nuevo-nombre=" + TAWIL["nombre"], "--nuevo-spotify=" + TAWIL["spotify"]] + \
        (["--nuevo-rss=" + rss] if rss else [])
    try:
        show_nuevo()
    finally:
        sys.argv = viejo
    if rss:
        guids_originales("tawil", rss)
    paso(42, "Rab Yosef Tawil: audios del grupo fuente, título por tema, anuncio en su día")
    if not ROBOT:
        aviso("sin carpeta del robot no puedo configurar el anuncio")
        return
    rw = ROBOT / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    antes = json.dumps(cfg, sort_keys=True)
    # fuente: el grupo donde Yehuda manda los audios ("Dia 21. Domingo" + audio)
    esc = cfg.setdefault("escuchar", {}).setdefault("tawil", {})
    esc["invite"] = TAWIL["fuente"]
    esc["carpetaDestino"] = str(BASE / "tawil" / "audios_whatsapp")
    esc["temas"] = True
    if numero:                                               # además, por chat directo
        dm = cfg.setdefault("escuchar_directo", [])
        e = next((x for x in dm if isinstance(x, dict) and x.get("show") == "tawil"), None)
        if e is None:
            e = {"show": "tawil"}
            dm.append(e)
        e.update({"carpetaDestino": esc["carpetaDestino"], "temas": True, "numero": numero})
    an = cfg.setdefault("anunciar", {}).setdefault("tawil", {})
    generales = (cfg.get("anunciar", {}).get("nacach") or {}).get("invite") or []
    generales = generales if isinstance(generales, list) else [generales]
    an["invite"] = TAWIL["grupos"] + [g for g in generales if g and g not in TAWIL["grupos"]]
    an.update({
        "spotify": TAWIL["spotify"], "sin_spotify": False, "spotify_espera_horas": 3,
        "whatsapp_link": TAWIL["whatsapp_link"], "dedicatoria": TAWIL["dedicatoria"],
        "plantilla": TAWIL["plantilla"], "sufijo_anuncio": "Rab Yosef Tawil",
        "esperar_fecha": True, "en_orden": True, "max_anuncios": 2, "solo_ultimos": 10,
        "sin_audio": False, "sin_whatsapp": True, "link_audio": False, "idioma": "es", "pausado": False,
        "calendario": TAWIL["calendario"], "no_shabat": True,
    })
    if json.dumps(cfg, sort_keys=True) != antes:
        respaldar(rw)
        if not VER:
            escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok("robot: toma los audios del grupo fuente de Tawil (link KE2Agbf…) y les pone el tema de la semana")
    ok(f"anuncia cada shiur SU día en {len(an['invite'])} grupos (los 2 de Tawil + generales) con fecha hebrea, L\"N y link del grupo")
    try:
        temas = json.loads(bajar_texto("otzar/temas/tawil.json"))
        ok("temas: " + ", ".join(f"desde el {t['desde']}: {t['tema']}" for t in temas))
    except Exception:
        pass
    print("   → 1) agrega al robot (2205947115) a los TRES grupos: el de los audios (KE2Agbf…) y los dos de Tawil")
    print("        (en los de anuncio, si solo los admins escriben, hazlo admin). Luego reinicia el robot:")
    print("        al arrancar dice 'escucha tawil: ...' y 'tawil: ...' con los nombres de los grupos")
    print("   → 2) si 'escucha tawil' no aparece, manda dentro del grupo de los audios:  !otzar tawil")
    print("   → 3) tema nuevo: dímelo y lo pongo, o manda al robot:  !tema tawil 27 Nombre del tema")
    try:
        ya_rss = json.loads((BASE / "tawil" / "config.json").read_text(encoding="utf-8")).get("rss_original")
    except Exception:
        ya_rss = ""
    if not (rss or ya_rss):
        print("   → 4) para que Spotify tome los episodios de aquí (sin perder #1-#26): en Spotify for Creators →")
        print("        Ajustes → Distribución → copia el link RSS y corre: python instalar_otzar.py --tawil --tawil-rss=LINK")
        print("        Mientras tanto, si subes a Spotify con el mismo título, el robot encuentra el link exacto;")
        print("        si no lo encuentra en 3 horas, manda el link del show.")


def bajar_texto(nombre):
    """Texto de tools/<nombre> en el repo (rama de trabajo primero, luego main)."""
    for ref in REFS:
        try:
            req = urllib.request.Request(f"https://raw.githubusercontent.com/jaimeatach/jaburahalaja/{ref}/tools/{nombre}",
                                         headers={"User-Agent": "instalar-otzar"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception:
            continue
    raise RuntimeError("no pude bajar " + nombre)


# ── 43. plataformas por show ──────────────────────────────────────────────────
#   --amazon=show:LINK[,show:LINK]  --soundcloud=show:LINK  --apple=show:LINK
#   --spotify-espera=show:HORAS     (si Spotify no toma el episodio en N horas, sale con el link del show)
def plataformas_links():
    claves = {"amazon": "amazon", "soundcloud": "soundcloud", "apple": "apple", "spotify-espera": "spotify_espera_horas"}
    pedidos = []
    for flag, campo in claves.items():
        v = next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{flag}=")), "")
        for par in [x for x in re.split(r",(?=\s*[a-z0-9]+:)", v) if x.strip()]:
            show, _, valor = par.strip().partition(":")
            if show and valor:
                pedidos.append((show.strip().lower(), campo, valor.strip()))
    if not pedidos:
        return
    paso(43, "Plataformas por show")
    if not ROBOT:
        aviso("sin carpeta del robot")
        return
    rw = ROBOT / "config_whatsapp.json"
    cfg = json.loads(rw.read_text(encoding="utf-8"))
    antes = json.dumps(cfg, sort_keys=True)
    for show, campo, valor in pedidos:
        an = (cfg.get("anunciar") or {}).get(show)
        if an is None:
            aviso(f"{show}: no está en anunciar")
            continue
        an[campo] = float(valor) if campo == "spotify_espera_horas" else valor.split("?")[0] if "spotify" in valor else valor
        ok(f"{show}: {campo} = {an[campo]}")
    if json.dumps(cfg, sort_keys=True) != antes and not VER:
        respaldar(rw)
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


# ── 44. revisión de todo ─────────────────────────────────────────────────────
#   --revisar: en qué plataformas está cada show, cuál no tiene grupo, cuál está trabado
def revisar_todo():
    if "--revisar" not in sys.argv:
        return
    paso(44, "Revisión: grupos, Spotify, Apple, Amazon y feeds de cada show")
    script = BASE / "jabura" / "plataformas.py"
    if VER or not script.exists():
        aviso("falta jabura\\plataformas.py")
        return
    subprocess.run([sys.executable, str(script)], cwd=str(script.parent))


# ── 45. mismos IDs que en Spotify ─────────────────────────────────────────────
#   Al rescatar un show de Spotify for Creators, podcast_bot le pone a cada episodio
#   un guid nuevo (el nombre del archivo). Si luego se hace el redirect, Spotify ve
#   episodios "nuevos" y los viejos se van con sus estadísticas. Aquí cada episodio
#   rescatado recupera el guid y la fecha que tiene en el RSS de Spotify: para
#   Spotify (y Apple) son los MISMOS episodios y conservan reproducciones y horas.
#   --guids-originales=show  (lo corre solo --tawil --tawil-rss=...)
def guids_originales(clave, rss=""):
    d = BASE / clave
    try:
        c = json.loads((d / "config.json").read_text(encoding="utf-8"))
    except Exception:
        aviso(f"{clave}: sin config.json")
        return
    rss = rss or c.get("rss_original", "")
    tok = d / "github_token.txt"
    if not rss or not tok.exists():
        aviso(f"{clave}: falta el RSS de Spotify o github_token.txt")
        return
    paso(45, f"{clave}: los episodios conservan su ID de Spotify (estadísticas)")
    norm = lambda x: re.sub(r"[^\w]+", " ", html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", x or "")).lower()).strip()
    try:
        with urllib.request.urlopen(urllib.request.Request(rss, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
            orig_xml = r.read().decode("utf-8", "replace")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer el RSS de Spotify ({e})")
        return
    orig = {}
    for it in re.findall(r"<item>([\s\S]*?)</item>", orig_xml):
        tt = re.search(r"<title>([\s\S]*?)</title>", it)
        g = re.search(r"<guid[^>]*>([\s\S]*?)</guid>", it)
        f = re.search(r"<pubDate>([\s\S]*?)</pubDate>", it)
        if tt and g:
            orig[norm(tt.group(1))] = (g.group(1).strip(), f.group(1).strip() if f else "")
    cab = {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
           "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', clave)}"
    try:
        feed, sha = _gh_texto(base, cab, "feed.xml")
    except Exception as e:                                  # noqa: BLE001
        aviso(f"no pude leer nuestro feed ({e})")
        return
    usados, cambios = set(), 0
    def arreglar(m):
        nonlocal cambios
        it = m.group(1)
        tt = re.search(r"<title>([\s\S]*?)</title>", it)
        k = norm(tt.group(1)) if tt else ""
        if k not in orig:
            return m.group(0)
        guid, fecha = orig[k]
        usados.add(k)
        nuevo = re.sub(r"<guid[^>]*>[\s\S]*?</guid>", f'<guid isPermaLink="false">{guid}</guid>', it, count=1) \
            if "<guid" in it else it + f'<guid isPermaLink="false">{guid}</guid>'
        if fecha:
            nuevo = re.sub(r"<pubDate>[\s\S]*?</pubDate>", f"<pubDate>{fecha}</pubDate>", nuevo, count=1)
        if nuevo != it:
            cambios += 1
        return f"<item>{nuevo}</item>"
    nuevo_feed = re.sub(r"<item>([\s\S]*?)</item>", arreglar, feed)
    faltan = [k for k in orig if k not in usados]
    if not VER:          # mantenimiento.py lo vuelve a aplicar si un feed nuevo pierde los IDs
        c["ids_spotify"] = {k: [g, f] for k, (g, f) in orig.items()}
        escribir(d / "config.json", json.dumps(c, ensure_ascii=False, indent=2) + "\n")
    if cambios and not VER:
        _gh_put(base, cab, "feed.xml", nuevo_feed.encode("utf-8"), "episodios con su ID de Spotify", sha)
    ok(f"{len(usados)} de {len(orig)} episodios con su MISMO ID de Spotify" + (f" ({cambios} corregidos)" if cambios else ""))
    if faltan:
        aviso(f"{len(faltan)} episodio(s) de Spotify no están en nuestro feed todavía: NO hagas el redirect aún")
        for k in faltan[:10]:
            print("     ·", k[:80])
    # los IDs originales cuentan como ya anunciados (ya estaban en Spotify)
    estado_p = (ROBOT or BASE) / "estado_anuncios.json"
    try:
        e = json.loads(estado_p.read_text(encoding="utf-8"))
    except Exception:
        e = {}
    previos = e.get(clave) or []
    nuevos = [g.replace("&amp;", "&") for g, _ in orig.values()]
    e[clave] = (previos + [g for g in nuevos if g not in previos])[-2000:]
    if not VER:
        respaldar(estado_p)
        escribir(estado_p, json.dumps(e, ensure_ascii=False, indent=2))
    if not faltan:
        pages = f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', clave)}/feed.xml"
        print(f"   → listo para el redirect: Spotify for Creators → Ajustes → 'Redirigir / mover el podcast' → {pages}")
        print("     NO borres el show ni episodios en Spotify for Creators: ahí siguen tus estadísticas.")


def guids_originales_flag():
    v = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--guids-originales=")), "")
    for show in [x.strip().lower() for x in v.split(",") if x.strip()]:
        guids_originales(show)


# ── 46. mekorot de la jabura ─────────────────────────────────────────────────
#   Los PDF / Word que mandan al grupo de la jabura se guardan en la carpeta del
#   siman como "מקורות · nombre.pdf"; el publicador los sube a archive.org y la app
#   los muestra en מראי מקומות. No se anuncian. (siempre)
def mekorot_jabura():
    if not ROBOT:
        return
    rw = ROBOT / "config_whatsapp.json"
    try:
        cfg = json.loads(rw.read_text(encoding="utf-8"))
    except Exception:
        return
    esc = (cfg.get("escuchar") or {}).get("jabura")
    if not isinstance(esc, dict) or esc.get("guardar_documentos"):
        return
    paso(46, "Jabura: los PDF de mekorot del grupo van a מראי מקומות de la app")
    esc["guardar_documentos"] = True
    respaldar(rw)
    escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok("el robot guarda los PDF/Word del grupo de la jabura (sin anunciarlos); reinicia el robot")


# ── 47. Tawil: cada shiur en su día (oct/2026) ────────────────────────────────
#   "calendario": el #N sale el día que le toca contando desde el #21 = 11/10, un
#   shiur por día, sin Shabat ni Yom Tov ("no_shabat"); el audio va al grupo para
#   darle play; la dedicatoria cambia cada semana (tools/otzar/temas/tawil.json).
#   La primera vez desmarca lo de hoy y lo que viene, para que salga en su día.
YOM_TOV = {"2026-10-03", "2026-10-04", "2027-04-22", "2027-04-23", "2027-04-28", "2027-04-29", "2027-06-11",
           "2027-06-12", "2027-10-02", "2027-10-03", "2027-10-11", "2027-10-16", "2027-10-17", "2027-10-23",
           "2027-10-24", "2028-04-11", "2028-04-12", "2028-04-17", "2028-04-18", "2028-05-31", "2028-06-01"}


def fecha_de_numero(cal, n):
    import datetime as dt
    d = dt.date.fromisoformat(cal["fecha"])
    k = n - int(cal["n"])
    paso_ = 1 if k >= 0 else -1
    for _ in range(3000):
        if k == 0:
            break
        d += dt.timedelta(days=paso_)
        if d.weekday() != 5 and d.isoformat() not in YOM_TOV:
            k -= paso_
    return d


def norm_titulo(t):
    t = re.sub(r"[֑-ׇ]", "", str(t or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[\W_]+", " ", t)).strip()


def tawil_calendario():
    if not ROBOT:
        return
    rw = ROBOT / "config_whatsapp.json"
    try:
        cfg = json.loads(rw.read_text(encoding="utf-8"))
    except Exception:
        return
    an = (cfg.get("anunciar") or {}).get("tawil")
    if not isinstance(an, dict) or (an.get("calendario") and an.get("no_shabat") and an.get("sin_audio") is False):
        return
    import datetime as dt
    paso(47, "Rab Yosef Tawil: cada shiur en su día, con audio, sin Shabat ni Yom Tov")
    an.update({"calendario": TAWIL["calendario"], "no_shabat": True, "sin_audio": False})
    respaldar(rw)
    if not VER:
        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    ok("tawil: el #22 sale el lunes 12/10, el #26 el viernes 16, el #27 el domingo 18 (sábado y Yom Tov no)")
    ok("tawil: con el audio para darle play, y la dedicatoria de la semana")
    try:
        import urllib.request
        req = urllib.request.Request("https://rabmeireliyahu.github.io/tawil/feed.xml", headers={"User-Agent": "otzar"})
        xml = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    except Exception as ex:
        aviso(f"no pude leer el feed de tawil ({ex}); lo de hoy puede no salir")
        return
    hoy = dt.date.today()
    pendientes = {}
    for it in re.findall(r"<item>([\s\S]*?)</item>", xml):
        t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
        g = re.search(r"<guid[^>]*>([\s\S]*?)</guid>", it)
        m = re.match(r"\s*#\s*(\d{1,4})", t.group(1) if t else "")
        if t and g and m and fecha_de_numero(TAWIL["calendario"], int(m.group(1))) >= hoy:
            pendientes[g.group(1).strip().replace("&amp;", "&")] = html.unescape(t.group(1).strip())
    if not pendientes:
        return
    for nombre, clave, quitar in (("estado_anuncios.json", "tawil", set(pendientes)),
                                  ("estado_titulos.json", "tawil", {norm_titulo(x) for x in pendientes.values()})):
        ruta = ROBOT / nombre
        try:
            e = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            continue
        antes = list(e.get(clave) or [])
        e[clave] = [x for x in antes if x not in quitar]
        if len(e[clave]) != len(antes) and not VER:
            respaldar(ruta)
            escribir(ruta, json.dumps(e, ensure_ascii=False, indent=1) + "\n")
    ok("listos para salir cada uno en su día: " + ", ".join(sorted(pendientes.values(), key=lambda x: int(re.sub(r"\D", "", x.split()[0]) or 0))))


# ── 48. --frenar=show: parar un show por completo y limpiar su feed (oct/2026) ──
#   - el robot deja de anunciarlo (anunciar.<show>.pausado)
#   - podcast_bot.py queda en podcast_bot.py.pausado y en su lugar uno que no hace
#     nada: ni ACTUALIZAR ni ANUNCIAR bajan, suben o publican ese show
#   - sus canales de YouTube se apartan (el robot de fiestas no busca ahí)
#   - si hay tools/otzar/limpieza_<show>.json, quita del feed esos episodios (los mp3
#     siguen en archive.org y en la PC; el feed de antes queda de respaldo en la carpeta)
#   --reanudar=show lo deshace. --nuevo-host=show:RSS (cuando el show ya vive en
#   Spotify for Creators) pone <itunes:new-feed-url> en el feed viejo.
STUB_PAUSADO = """# PAUSADO por instalar_otzar.py --frenar ({fecha}). El bot original es podcast_bot.py.pausado.
# Para volver a usarlo: python instalar_otzar.py --reanudar={show}
print("{show}: PAUSADO. No se baja ni se publica nada; los episodios se suben a mano en Spotify for Creators.")
"""


def _arg_lista(nombre):
    return [x.strip().lower() for a in sys.argv if a.startswith(f"--{nombre}=") for x in a.split("=", 1)[1].split(",") if x.strip()]


def _cab_github(d):
    tok = next((p for p in (d / "github_token.txt", BASE / "jabura" / "github_token.txt") if p.exists()), None)
    if not tok:
        return None
    return {"Authorization": "token " + tok.read_text(encoding="utf-8").strip(),
            "User-Agent": "instalar-otzar", "Accept": "application/vnd.github+json"}


def frenar():
    for show in _arg_lista("frenar"):
        paso(48, f"{show}: FRENAR todo (sin bajar, sin publicar, sin anunciar) y limpiar el feed")
        d = BASE / show
        if not d.is_dir():
            aviso(f"no existe {d}")
            continue
        # 1) robot: no anunciar
        if ROBOT:
            rw = ROBOT / "config_whatsapp.json"
            try:
                cfg = json.loads(rw.read_text(encoding="utf-8"))
                an = (cfg.get("anunciar") or {}).get(show)
                if isinstance(an, dict) and not an.get("pausado"):
                    an["pausado"] = True
                    respaldar(rw)
                    if not VER:
                        escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
                ok("robot: ya no anuncia este show")
            except Exception as ex:                       # noqa: BLE001
                aviso(f"config del robot: {ex}")
        # 2) el bot: apartado, con uno que no hace nada en su lugar
        bot, guardado = d / "podcast_bot.py", d / "podcast_bot.py.pausado"
        if bot.exists() and STUB_PAUSADO.splitlines()[0][:20] not in bot.read_text(encoding="utf-8", errors="replace"):
            if not VER:
                if guardado.exists():
                    respaldar(guardado)
                shutil.copy2(bot, guardado)
                escribir(bot, STUB_PAUSADO.format(show=show, fecha=time.strftime("%d/%m/%Y")))
            ok("podcast_bot.py apartado (quedó en podcast_bot.py.pausado): ACTUALIZAR ya no baja ni publica nada de este show")
        else:
            ok("el bot ya estaba pausado")
        # 3) config del show: canales apartados
        cp = d / "config.json"
        c = {}
        try:
            c = json.loads(cp.read_text(encoding="utf-8"))
            cambio = False
            for k in ("canales_youtube", "canal_youtube"):
                if c.get(k):
                    c[k + "_pausado"] = c.pop(k)
                    cambio = True
            if not c.get("pausado"):
                c["pausado"] = True
                cambio = True
            if cambio:
                respaldar(cp)
                if not VER:
                    escribir(cp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
            ok("canales de YouTube apartados: el robot de fiestas ya no busca en ellos")
        except Exception as ex:                           # noqa: BLE001
            aviso(f"config.json: {ex}")
        # 4) limpiar el feed
        try:
            lim = json.loads(bajar_texto(f"otzar/limpieza_{show}.json"))
        except Exception:
            lim = None
        if not lim:
            continue
        quitar = {q["guid"] for q in lim.get("quitar", [])}
        cab = _cab_github(d)
        if not cab:
            aviso("falta github_token.txt: no puedo limpiar el feed")
            continue
        base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
        try:
            feed, sha = _gh_texto(base, cab, "feed.xml")
        except Exception as ex:                           # noqa: BLE001
            aviso(f"no pude leer el feed: {ex}")
            continue
        quitados = []

        def _fuera(m):
            g = re.search(r"<guid[^>]*>([\s\S]*?)</guid>", m.group(0))
            if g and html.unescape(g.group(1).strip()) in quitar:
                t = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", m.group(0))
                quitados.append(html.unescape(t.group(1)) if t else g.group(1))
                return ""
            return m.group(0)
        nuevo = re.sub(r"[ \t]*<item>[\s\S]*?</item>[ \t]*\n?", _fuera, feed)
        quedan = nuevo.count("<item>")
        print(f"   episodios antes: {feed.count('<item>')} · se quitan: {len(quitados)} · quedan: {quedan}")
        for t in quitados[:8]:
            print("     - " + t[:90])
        if len(quitados) > 8:
            print(f"     ... y {len(quitados) - 8} más (lista completa en tools/otzar/limpieza_{show}.json)")
        if not quitados:
            ok("el feed ya estaba limpio")
            continue
        if quedan < 5:
            aviso("quedarían menos de 5 episodios; no toco el feed")
            continue
        if VER:
            ok("(prueba en seco)")
            continue
        (d / f"feed_antes_de_limpiar_{time.strftime('%Y%m%d%H%M%S')}.xml").write_text(feed, encoding="utf-8")
        _gh_put(base, cab, "feed.xml", nuevo.encode("utf-8"), f"quitar {len(quitados)} episodios que no son del show", sha)
        ok(f"feed limpio: {quedan} episodios. Spotify quita los otros en unas horas (los mp3 siguen en archive.org)")


def reanudar():
    for show in _arg_lista("reanudar"):
        paso(48, f"{show}: reanudar")
        d = BASE / show
        bot, guardado = d / "podcast_bot.py", d / "podcast_bot.py.pausado"
        if guardado.exists() and not VER:
            shutil.copy2(guardado, bot)
            ok("podcast_bot.py original de vuelta")
        cp = d / "config.json"
        try:
            c = json.loads(cp.read_text(encoding="utf-8"))
            for k in ("canales_youtube", "canal_youtube"):
                if c.get(k + "_pausado") and not c.get(k):
                    c[k] = c.pop(k + "_pausado")
            c.pop("pausado", None)
            if not VER:
                escribir(cp, json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        except Exception:
            pass
        if ROBOT:
            rw = ROBOT / "config_whatsapp.json"
            cfg = json.loads(rw.read_text(encoding="utf-8"))
            an = (cfg.get("anunciar") or {}).get(show)
            if isinstance(an, dict) and an.get("pausado"):
                an["pausado"] = False
                respaldar(rw)
                if not VER:
                    escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok("reanudado")


def nuevo_host():
    for par in [a.split("=", 1)[1] for a in sys.argv if a.startswith("--nuevo-host=")]:
        show, _, url = par.partition(":")
        show, url = show.strip().lower(), url.strip()
        if not url.startswith("http"):
            aviso("uso: --nuevo-host=show:https://anchor.fm/s/.../podcast/rss")
            continue
        paso(48, f"{show}: el show ya vive en Spotify for Creators")
        d = BASE / show
        c = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").exists() else {}
        cab = _cab_github(d)
        if not cab:
            aviso("falta github_token.txt")
            continue
        base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
        feed, sha = _gh_texto(base, cab, "feed.xml")
        feed = re.sub(r"\s*<itunes:new-feed-url>[\s\S]*?</itunes:new-feed-url>", "", feed)
        feed = re.sub(r"(<channel>)", r"\1\n    <itunes:new-feed-url>" + html.escape(url) + "</itunes:new-feed-url>", feed, count=1)
        if not VER:
            _gh_put(base, cab, "feed.xml", feed.encode("utf-8"), "el show se mudó a Spotify for Creators", sha)
            c["rss_nuevo_host"] = url
            escribir(d / "config.json", json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        if ROBOT:
            rw = ROBOT / "config_whatsapp.json"
            cfg = json.loads(rw.read_text(encoding="utf-8"))
            an = (cfg.get("anunciar") or {}).get(show)
            if isinstance(an, dict):
                an["feed"] = url                        # si se reanuda el anuncio, lee lo que se sube en Creators
                respaldar(rw)
                if not VER:
                    escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        ok("el feed viejo avisa a Apple/Amazon que el show se mudó; nosotros ya no publicamos nada ahí")


# ── 49. --pausar=show / --despausar=show: solo el ANUNCIO del robot (oct/2026) ──
#   No toca feeds, bots ni archivos: el robot deja de mandar ese show a los grupos
#   (o vuelve a mandarlo). Así se pausó mishlei (el curso saturó; vendrá otro).
def pausar_anuncio():
    for flag, valor in (("pausar", True), ("despausar", False)):
        shows = _arg_lista(flag)
        if not shows or not ROBOT:
            continue
        paso(49, ("PAUSAR" if valor else "REANUDAR") + " el anuncio de: " + ", ".join(shows))
        rw = ROBOT / "config_whatsapp.json"
        cfg = json.loads(rw.read_text(encoding="utf-8"))
        an_all = cfg.get("anunciar") or {}
        cambio = False
        for show in shows:
            an = an_all.get(show)
            if not isinstance(an, dict):
                aviso(f"{show}: no está en anunciar (hay: {', '.join(sorted(an_all))})")
                continue
            if bool(an.get("pausado")) != valor:
                an["pausado"] = valor
                cambio = True
            ok(f"{show}: " + ("EN PAUSA, el robot ya no lo manda a ningún grupo" if valor else "el robot lo vuelve a mandar"))
        if cambio:
            respaldar(rw)
            if not VER:
                escribir(rw, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
            print("   → reinicia el robot (cierra su ventana y abre ROBOT_WHATSAPP.bat)")


# ── 50. Encabezado del show igual al de Spotify (nombre, descripción, autor, foto) ──
#   tools/otzar/canales/<show>.json + la foto ORIGINAL en base64 (.b64): así el filtro de
#   la PC no la "tapa" (la portada de Tawil salió con la cara en negro). Se sube al repo del
#   show con nombre fechado (Spotify solo vuelve a bajar la foto si cambia la URL) y queda en
#   config.json → "canal"; mantenimiento.py (canal_feed) lo vuelve a poner en el feed siempre.
CANALES = ["tawil"]


def canales_shows():
    import hashlib
    for show in CANALES:
        d = BASE / show
        if not (d / "config.json").exists():
            continue
        try:
            datos = json.loads(bajar_texto(f"otzar/canales/{show}.json"))
        except Exception as ex:                             # noqa: BLE001
            aviso(f"{show}: no pude bajar canales/{show}.json ({ex})")
            continue
        c = json.loads((d / "config.json").read_text(encoding="utf-8"))
        previo = c.get("canal") or {}
        if previo.get("portada_sha256") == datos.get("portada_sha256") and all(
                previo.get(k) == datos.get(k) for k in ("title", "description", "author", "categoria")):
            continue
        paso(50, f"{show}: nombre, descripción y foto iguales a los de Spotify")
        canal = {k: datos.get(k) for k in ("title", "description", "author", "categoria")}
        canal["imagen"] = previo.get("imagen", "")
        canal["portada_sha256"] = previo.get("portada_sha256", "")
        if previo.get("portada_sha256") != datos.get("portada_sha256"):
            try:
                img = base64.b64decode(bajar_texto(f"otzar/canales/{datos['portada_b64']}"))
            except Exception as ex:                         # noqa: BLE001
                aviso(f"{show}: no pude bajar la foto ({ex})")
                continue
            if hashlib.sha256(img).hexdigest() != datos.get("portada_sha256"):
                aviso(f"{show}: la foto llegó alterada (¿filtro?); no la subo")
                continue
            cab = _cab_github(d)
            if not cab:
                aviso("falta github_token.txt")
                continue
            base = f"https://api.github.com/repos/{c.get('github_user', 'rabmeireliyahu')}/{c.get('github_repo', show)}"
            pages = f"https://{c.get('github_user', 'rabmeireliyahu')}.github.io/{c.get('github_repo', show)}"
            nombre = "portada_" + time.strftime("%Y%m%d%H%M") + ".jpg"
            if not VER:
                try:
                    _gh_put(base, cab, nombre, img, "portada original (sin tapar)")
                except Exception as ex:                     # noqa: BLE001
                    aviso(f"{show}: no pude subir la foto ({ex})")
                    continue
            canal["imagen"] = f"{pages}/{nombre}"
            canal["portada_sha256"] = datos.get("portada_sha256")
            ok(f"foto original (3000×3000, sin tapar) subida como {nombre}")
        c["canal"] = canal
        respaldar(d / "config.json")
        if not VER:
            escribir(d / "config.json", json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        ok(f"nombre: {canal['title']} · descripción: {canal['description']} · autor: {canal['author']}")
        ok("el próximo ANUNCIAR (o el piloto) lo pone en el feed; Spotify lo toma al leerlo")


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
    quitar()
    anunciar_tambien()
    verificar()
    titulos_defecto()
    fuentes()
    spotify_redirigido()
    mismo_podcast()
    mukze()
    curso()
    retitular()
    parasha()
    correo()
    archive_calma()
    bots_nombres()
    bots_compacto()
    compactar()
    reordenar()
    nombres()
    shows()
    listar()
    shows_whatsapp_al_dia()
    ofir_grupo()
    sin_atrasos_config()
    al_dia()
    mekorot_jabura()
    rescatar()
    tawil()
    tawil_calendario()
    canales_shows()
    frenar()
    reanudar()
    nuevo_host()
    pausar_anuncio()
    guids_originales_flag()
    plataformas_links()
    revisar_todo()
    print("\nListo." if not VER else "\nPrueba en seco terminada: no se cambió nada.")


if __name__ == "__main__":
    main()
