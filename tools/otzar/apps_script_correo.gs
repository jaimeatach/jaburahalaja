// ============================================================
//  OTZAR · correo → Drive   (Google Apps Script)
//  Pegar TODO esto en https://script.google.com con la cuenta donde LLEGAN los
//  correos (albertoamiga1@gmail.com), guardar, elegir la función "instalar" y
//  apretar Ejecutar UNA vez (pide permisos: aceptar). Desde ahí, cada 10 minutos
//  guarda en Drive (Mi unidad\OTZAR\taamim) los audios que manden los
//  REMITENTES (adjuntos y links de Drive) y comparte esa carpeta con
//  COMPARTIR_CON (la cuenta cuyo Drive está montado en la PC de Otzar).
//  En esa cuenta: Compartido conmigo → taamim → Organizar → Agregar acceso
//  directo a Mi unidad. Drive la baja a la PC como
//  G:\.shortcut-targets-by-id\<ID>\taamim (el registro dice el ID) y
//  correo_shiurim.py la toma de ahí en cada ANUNCIAR.
// ============================================================
var REMITENTES = ['credi71@gmail.com'];
var CARPETA = 'OTZAR/taamim';                  // dentro de Mi unidad de esta cuenta
var COMPARTIR_CON = 'bamiga@autentafoods.com'; // el Drive que está en la PC (G:)
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
      var adj = m.getAttachments().filter(function (a) {
        return AUDIO.test(a.getName()) || /^audio\//.test(a.getContentType());
      });
      adj.forEach(function (a, i) {
        var nombre = a.getName();
        var ext = (nombre.match(/\.[^.]+$/) || ['.mp3'])[0];
        var base = nombre.replace(/\.[^.]+$/, '');
        if (generico(base)) base = asunto + (adj.length > 1 ? ' ' + (i + 1) : '');
        base = limpiar(base) || ('Shiur ' + Utilities.formatDate(m.getDate(), 'GMT', 'yyyy-MM-dd'));
        if (!f.getFilesByName(base + ext).hasNext()) {
          f.createFile(a.copyBlob().setName(base + ext));
          guardados++;
        }
      });
      // links de Google Drive en el cuerpo: se copia el archivo a la carpeta
      var cuerpo = m.getPlainBody() || '';
      var re = /drive\.google\.com\/(?:file\/d\/|open\?id=|uc\?[^\s]*id=)([-\w]{20,})/g, x;
      while ((x = re.exec(cuerpo)) !== null) {
        try {
          var src = DriveApp.getFileById(x[1]);
          var n = src.getName();
          if (AUDIO.test(n) && !f.getFilesByName(n).hasNext()) { src.makeCopy(n, f); guardados++; }
        } catch (e) { Logger.log('link de Drive sin acceso: ' + x[1]); }
      }
    });
    h.addLabel(etq);
  });
  Logger.log(hilos.length + ' correo(s) revisados, ' + guardados + ' audio(s) guardados en ' + CARPETA);
}

function generico(s) {
  return /^(audio|voice|ptt|rec|recording|whatsapp ?audio|aud|new recording|voz|grabaci[oó]n|msg|vn|voice ?note|nota de voz|audio track)\b/i.test(s)
    || s.replace(/[^A-Za-z\u05D0-\u05EA]/g, '').length <= 3;
}

function limpiar(s) {
  return (s || '').replace(/^\s*((fwd?|re|rv|fw)\s*:\s*)+/i, '').replace(/_/g, ' ')
    .replace(/[<>:"\/\\|?*\x00-\x1f]/g, '').replace(/\s+/g, ' ').trim().slice(0, 120);
}
