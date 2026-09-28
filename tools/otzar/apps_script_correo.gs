// ============================================================
//  OTZAR · correo → Drive   (Google Apps Script)
//  Pegar TODO esto en https://script.google.com con la cuenta del buzón
//  (bamiga@autentafoods.com), guardar, elegir la función "instalar" y apretar
//  Ejecutar UNA vez (pide permisos: aceptar). Desde ahí, cada 10 minutos guarda
//  en Drive (Mi unidad\OTZAR\taamim) los audios que manden los REMITENTES:
//  adjuntos, correos reenviados "como archivo adjunto" (.eml) y links de Drive.
//  Drive los baja a la PC y correo_shiurim.py los toma de esa carpeta en cada
//  ANUNCIAR. Si el script vive en otra cuenta, COMPARTIR_CON comparte la carpeta
//  con la del Drive de la PC (ahí: Compartido conmigo → Agregar acceso directo).
// ============================================================
var REMITENTES = ['credi71@gmail.com', 'albertoamiga1@gmail.com'];  // el Rab, y lo reenviado desde el otro correo
var CARPETA = 'OTZAR/taamim';          // dentro de Mi unidad de esta cuenta
var COMPARTIR_CON = '';                // vacío: el Drive de esta cuenta ya está en la PC (G:).
                                       // Si el script vive en OTRA cuenta, poner aquí la del Drive de la PC.
var ETIQUETA = 'otzar-guardado';               // se pone al hilo cuando ya se guardó
var AUDIO = /\.(mp3|m4a|wav|ogg|opus|aac|wma|amr|flac)$/i;

function instalar() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('guardar').timeBased().everyMinutes(10).create();
  var f = carpeta();
  if (COMPARTIR_CON) {
    try { f.addEditor(COMPARTIR_CON); } catch (e) { Logger.log('no pude compartir con ' + COMPARTIR_CON + ': ' + e); }
  }
  guardar();
  Logger.log('CARPETA ID: ' + f.getId());
  Logger.log('En la PC de Otzar (tras el acceso directo en Mi unidad de ' + COMPARTIR_CON + '):');
  Logger.log('  G:\\.shortcut-targets-by-id\\' + f.getId() + '\\' + f.getName());
  Logger.log('  python instalar_otzar.py --correo-carpeta=taamim:"G:\\.shortcut-targets-by-id\\' + f.getId() + '\\' + f.getName() + '"');
}

function carpeta() {
  var f = DriveApp.getRootFolder();
  CARPETA.split('/').forEach(function (n) {
    var it = f.getFoldersByName(n);
    f = it.hasNext() ? it.next() : f.createFolder(n);
  });
  return f;
}

function guardar() {
  var etq = GmailApp.getUserLabelByName(ETIQUETA) || GmailApp.createLabel(ETIQUETA);
  var f = carpeta();
  var q = REMITENTES.map(function (r) { return 'from:' + r; }).join(' OR ');
  var hilos = GmailApp.search('(' + q + ') -label:' + ETIQUETA + ' newer_than:1y', 0, 50);
  var guardados = 0;
  hilos.forEach(function (h) {
    h.getMessages().forEach(function (m) {
      var asunto = limpiar(m.getSubject());
      var todos = m.getAttachments();
      // correos reenviados "como archivo adjunto" (.eml): se abren y se sacan sus audios
      todos.filter(function (a) { return /\.eml$/i.test(a.getName()) || /message\/rfc822/i.test(a.getContentType()); })
        .forEach(function (a) { guardados += guardarEml(a.getDataAsString(), f, m.getDate()); });
      var adj = todos.filter(function (a) {
        return AUDIO.test(a.getName()) || /^audio\//.test(a.getContentType());
      });
      guardados += guardarAudios(adj.map(function (a) { return { nombre: a.getName(), blob: a.copyBlob() }; }), asunto, f, m.getDate());
      // links de Google Drive en el cuerpo: se copia el archivo a la carpeta
      var cuerpo = m.getPlainBody() || '';
      var re = /drive\.google\.com\/(?:file\/d\/|open\?id=|uc\?[^\s]*id=)([-\w]{20,})/g, x;
      while ((x = re.exec(cuerpo)) !== null) {
        try {
          var src = DriveApp.getFileById(x[1]);
          var n = src.getName();
          if (/\.eml$/i.test(n)) guardados += guardarEml(src.getBlob().getDataAsString(), f, m.getDate());
          else if (AUDIO.test(n) && !f.getFilesByName(n).hasNext()) { src.makeCopy(n, f); guardados++; }
        } catch (e) { Logger.log('link de Drive sin acceso: ' + x[1]); }
      }
    });
    h.addLabel(etq);
  });
  Logger.log(hilos.length + ' correo(s) revisados, ' + guardados + ' audio(s) guardados en ' + CARPETA);
}

// guarda audios [{nombre, blob}] con título = nombre del archivo, o el asunto si es genérico
function guardarAudios(lista, asunto, f, fecha) {
  var n = 0;
  lista.forEach(function (a, i) {
    var ext = (a.nombre.match(/\.[^.]+$/) || ['.mp3'])[0].toLowerCase();
    var base = a.nombre.replace(/\.[^.]+$/, '');
    if (generico(base)) base = asunto + (lista.length > 1 ? ' ' + (i + 1) : '');
    base = limpiar(base) || ('Shiur ' + Utilities.formatDate(fecha, 'GMT', 'yyyy-MM-dd'));
    if (!f.getFilesByName(base + ext).hasNext()) {
      f.createFile(a.blob.setName(base + ext));
      n++;
    }
  });
  return n;
}

// un correo completo (.eml) → sus audios adjuntos
function guardarEml(texto, f, fecha) {
  var partes = partesEml(texto);
  if (!partes.length) return 0;
  var asunto = limpiar(decodificarPalabra(partes[0].raiz['subject'] || ''));
  var lista = [];
  partes.forEach(function (p) {
    var cd = p.h['content-disposition'] || '', ct = p.h['content-type'] || '';
    var nombre = '';
    var m = cd.match(/filename\*=(?:utf-8|UTF-8)''([^;]+)/) || ct.match(/name\*=(?:utf-8|UTF-8)''([^;]+)/);
    if (m) { try { nombre = decodeURIComponent(m[1].trim()); } catch (e) { nombre = m[1]; } }
    if (!nombre) { m = cd.match(/filename="?([^";]+)"?/i) || ct.match(/name="?([^";]+)"?/i); if (m) nombre = decodificarPalabra(m[1].trim()); }
    var esAudio = AUDIO.test(nombre) || /^audio\//i.test(ct);
    if (!esAudio) return;
    if (!/base64/i.test(p.h['content-transfer-encoding'] || '')) return;
    var tipo = (ct.split(';')[0] || 'audio/mpeg').trim();
    lista.push({ nombre: nombre || ('audio' + (lista.length + 1) + '.mp3'),
                 blob: Utilities.newBlob(Utilities.base64Decode(p.body.replace(/\s/g, '')), tipo, nombre) });
  });
  return guardarAudios(lista, asunto, f, fecha);
}

// MIME: devuelve las hojas [{h: cabeceras, body, raiz: cabeceras del correo}]
function partesEml(texto, raiz) {
  var sep = texto.indexOf('\r\n\r\n'), largo = 4;
  if (sep < 0) { sep = texto.indexOf('\n\n'); largo = 2; }
  if (sep < 0) return [];
  var cab = texto.slice(0, sep).replace(/\r?\n[ \t]+/g, ' ');
  var cuerpo = texto.slice(sep + largo);
  var h = {};
  cab.split(/\r?\n/).forEach(function (l) { var m = l.match(/^([\w-]+):\s*(.*)$/); if (m) h[m[1].toLowerCase()] = m[2]; });
  raiz = raiz || h;
  var ct = h['content-type'] || '';
  var b = ct.match(/boundary="?([^";]+)"?/i);
  if (/^multipart\//i.test(ct) && b) {
    var out = [];
    cuerpo.split('--' + b[1]).slice(1).forEach(function (p) {
      if (p.indexOf('--') === 0) return;
      out = out.concat(partesEml(p.replace(/^\r?\n/, ''), raiz));
    });
    return out;
  }
  return [{ h: h, body: cuerpo, raiz: raiz }];
}

// "=?UTF-8?B?...?=" y "=?UTF-8?Q?...?=" → texto
function decodificarPalabra(s) {
  return (s || '').replace(/\?=\s+=\?/g, '?==?').replace(/=\?([^?]+)\?([BbQq])\?([^?]*)\?=/g, function (_, cs, enc, txt) {
    try {
      if (enc.toUpperCase() === 'B') return Utilities.newBlob(Utilities.base64Decode(txt)).getDataAsString(cs);
      var bytes = []; txt = txt.replace(/_/g, ' ');
      for (var i = 0; i < txt.length; i++) {
        if (txt[i] === '=' && i + 2 < txt.length) { bytes.push(parseInt(txt.substr(i + 1, 2), 16)); i += 2; }
        else bytes.push(txt.charCodeAt(i));
      }
      return Utilities.newBlob(bytes).getDataAsString(cs);
    } catch (e) { return txt; }
  });
}

function generico(s) {
  return /^(audio|voice|ptt|rec|recording|whatsapp ?audio|aud|new recording|voz|grabaci[oó]n|msg|vn|voice ?note|nota de voz|audio track)\b/i.test(s)
    || s.replace(/[^A-Za-z\u05D0-\u05EA]/g, '').length <= 3;
}

function limpiar(s) {
  return (s || '').replace(/^\s*((fwd?|re|rv|fw)\s*:\s*)+/i, '').replace(/_/g, ' ')
    .replace(/[<>:"\/\\|?*\x00-\x1f]/g, '').replace(/\s+/g, ' ').trim().slice(0, 120);
}
