/**
 * Examen semanal de Rab Yosef Tawil · CARGADOR (26/11/2026).
 *
 * Pega SOLO esto en el proyecto de Apps Script. El código de verdad vive en el repo
 * (tools/otzar/apps_script_examen.gs) y este cargador lo baja cada vez que se usa: así
 * Claude lo puede corregir sin que tengas que volver a pegar nada ni volver a implementar.
 * Si GitHub no responde, usa la última copia que guardó.
 *
 * Instalar (una sola vez, en la cuenta rabmeireliyahu):
 *   1. script.google.com → Proyecto nuevo → borra lo que trae, pega TODO esto → Guardar.
 *   2. Arriba elige "instalar" → Ejecutar → acepta los permisos.
 *   3. Implementar → Nueva implementación → ⚙ Aplicación web →
 *      Ejecutar como: Yo · Quién tiene acceso: Cualquier usuario → Implementar.
 *      Copia la URL (termina en /exec) y pásasela a Claude.
 */
const CODIGO_URL = 'https://raw.githubusercontent.com/jaimeatach/jaburahalaja/claude/shiurim-halachot-shabbat-vriig5/tools/otzar/apps_script_examen.gs';

function cargar_() {
  if (globalThis.__examenTawil) return;
  let txt = '';
  try {
    const r = UrlFetchApp.fetch(CODIGO_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (r.getResponseCode() === 200) txt = r.getContentText('UTF-8');
  } catch (e) { Logger.log('no bajé el código: ' + e); }
  const props = PropertiesService.getScriptProperties();
  if (txt) {
    try { props.setProperty('codigo', txt); } catch (e) {}
  } else {
    txt = props.getProperty('codigo') || '';
  }
  if (!txt) throw new Error('No pude bajar el código del examen y no hay copia guardada.');
  txt = txt.replace(/^function doGet\(/m, 'function doGetReal_(')
           .replace(/^function instalar\(/m, 'function instalarReal_(')
           .replace(/^function rehacerExamen\(/m, 'function rehacerReal_(');
  (0, eval)(txt);
  globalThis.__examenTawil = true;
}

function doGet(e) { cargar_(); return doGetReal_(e); }
function instalar() { cargar_(); return instalarReal_(); }
function rehacerExamen() { cargar_(); return rehacerReal_(); }

/** Nunca se llama: solo para que Google pida los permisos que usa el código del repo. */
function permisos_() {
  FormApp.create('x'); DriveApp.getRootFolder(); SpreadsheetApp.create('x');
  MailApp.sendEmail('x', 'x', 'x'); UrlFetchApp.fetch('x'); ContentService.createTextOutput('x');
  PropertiesService.getScriptProperties(); Session.getEffectiveUser(); ScriptApp.getProjectTriggers();
}
