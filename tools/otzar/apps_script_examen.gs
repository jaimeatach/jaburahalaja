/**
 * Examen semanal de Rab Yosef Tawil → Google Forms (nov/2026, versión 2).
 *
 * Cada JUEVES en la mañana se arma solo en el repo el examen de la semana
 * (tools/otzar/examenes/tawil_<viernes>.json, 10 preguntas). El Motzaei Shabat, 30 min
 * después de Rabenu Tam, el piloto de la PC de Otzar le pide a ESTE script el link:
 * el script arma el Google Form (tipo cuestionario, con calificación y explicación) si
 * todavía no está, se lo da al piloto, el robot lo manda al grupo y entonces el script
 * te manda UN SOLO correo: la confirmación con el link del examen y el de los resultados.
 * No hay disparadores ni correos diarios.
 *
 * Instalar (una sola vez):
 *   1. script.google.com → Proyecto nuevo → borra lo que trae, pega TODO este archivo → Guardar.
 *   2. Arriba elige la función "instalar" → Ejecutar → acepta los permisos.
 *      (borra los disparadores viejos de este proyecto y arma el examen de esta semana;
 *      el link sale abajo, en el «Registro de ejecución». No manda correo.)
 *   3. Implementar → Nueva implementación → ⚙ Aplicación web →
 *      Ejecutar como: Yo · Quién tiene acceso: Cualquier usuario → Implementar.
 *      Copia la «URL de la aplicación web» (termina en /exec) y pásasela a Claude.
 *   Si Claude corrige el examen ya armado: ejecuta "rehacerExamen".
 */
const RAMA = 'claude/shiurim-halachot-shabbat-vriig5';
const BASE = 'https://raw.githubusercontent.com/jaimeatach/jaburahalaja/' + RAMA + '/tools/otzar/examenes/';
const CARPETA = 'Exámenes Rab Yosef Tawil';
const TZ = 'America/Mexico_City';

function instalar() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));   // nada automático aquí
  const r = examenDeLaSemana_();
  Logger.log(r.ok ? 'Examen listo: ' + r.link + '\nResultados: ' + r.resultados : r.error);
}

/** El piloto pregunta aquí:  …/exec            → {ok, examen, dias, link, resultados}
 *                            …/exec?enviado=1  → manda el correo de confirmación (una vez). */
function doGet(e) {
  let r;
  try {
    r = examenDeLaSemana_();
    if (r.ok && e && e.parameter && e.parameter.enviado) r.correo = confirmar_(r);
  } catch (ex) { r = { ok: false, error: String(ex) }; }
  return ContentService.createTextOutput(JSON.stringify(r)).setMimeType(ContentService.MimeType.JSON);
}

function fechaTexto_(d) { return Utilities.formatDate(d, TZ, 'yyyy-MM-dd'); }

/** El JSON de esta semana: lleva la fecha del viernes (vale también la del jueves).
 *  En Motzaei Shabat / domingo, el viernes que acaba de pasar. */
function bajarExamen_() {
  const hoy = new Date();
  const dia = Number(Utilities.formatDate(hoy, TZ, 'u'));      // 1=lunes … 7=domingo
  const alViernes = (5 - dia + 7) % 7;                        // 0 el viernes, 6 el sábado, 5 el domingo
  const candidatos = dia >= 6 ? [alViernes - 7, alViernes - 8] : [alViernes, alViernes - 1, alViernes - 7, alViernes - 8];
  for (const k of candidatos) {
    const nombre = 'tawil_' + fechaTexto_(new Date(hoy.getTime() + k * 86400000)) + '.json';
    const r = UrlFetchApp.fetch(BASE + encodeURI(nombre) + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (r.getResponseCode() === 200) {
      const texto = r.getContentText('UTF-8');
      return { nombre: nombre, datos: JSON.parse(texto), huella: huella_(texto) };
    }
  }
  return null;
}

function huella_(t) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, t, Utilities.Charset.UTF_8)
    .map(b => ('0' + (b & 255).toString(16)).slice(-2)).join('').slice(0, 10);
}

function diasDe_(d) {
  const m = String(d.titulo || '').match(/#(\d+)\s*[–-]\s*#(\d+)/);
  if (m) return m[1] + ' al ' + m[2];
  const s = (d.shiurim || []).map(Number).sort((a, b) => a - b);
  return s.length ? s[0] + ' al ' + s[s.length - 1] : '';
}

/** Arma el Form de esta semana si falta (si Claude corrigió el JSON, arma uno nuevo). */
function examenDeLaSemana_() {
  const ex = bajarExamen_();
  if (!ex) return { ok: false, error: 'No está el examen de esta semana en el repo' };
  const props = PropertiesService.getScriptProperties();
  const clave = ex.nombre + '#' + ex.huella;
  let info = JSON.parse(props.getProperty(clave) || 'null');
  if (!info) {
    info = crearForm_(ex.datos);
    props.setProperty(clave, JSON.stringify(info));
  }
  return { ok: true, examen: ex.nombre, clave: clave, dias: diasDe_(ex.datos),
           preguntas: (ex.datos.preguntas || []).length, link: info.link,
           resultados: info.hoja || info.editar, editar: info.editar };
}

// (22/11) Google no deja poner desde el script «Publicar calificación: inmediatamente» ni «ver
// respuestas correctas»: el examen nuevo sale COPIA del de la semana #51-#56 (que ya tiene esos
// ajustes puestos a mano) y se le cambian las preguntas. Si la copia falla, se crea uno nuevo.
const PLANTILLA = '1O0AUOVaQexiVT7A66C1UP_Vj9yo0rt6Prk22tLhb8JU';

function formNuevo_(titulo) {
  try {
    const id = DriveApp.getFileById(PLANTILLA).makeCopy(titulo).getId();
    const f = FormApp.openById(id);
    try { f.removeDestination(); } catch (e) {}
    try { f.deleteAllResponses(); } catch (e) {}
    f.getItems().forEach(it => f.deleteItem(it));
    f.setTitle(titulo);
    return f;
  } catch (e) {
    Logger.log('plantilla: ' + e);
    return FormApp.create(titulo);
  }
}

function crearForm_(d) {
  const form = formNuevo_(d.titulo);
  form.setIsQuiz(true)
      .setDescription(d.descripcion || '')
      .setCollectEmail(false)
      .setProgressBar(true);
  form.addTextItem().setTitle('Nombre completo').setRequired(true);
  d.preguntas.forEach((p, i) => {
    const it = form.addMultipleChoiceItem();
    it.setTitle((i + 1) + '. ' + p.pregunta)
      .setHelpText('Shiur #' + p.shiur)   // sin decir si es fácil o difícil (lo pidió el usuario)
      .setPoints(1)                        // todas valen 1 punto
      .setRequired(true)
      .setChoices(p.opciones.map((o, j) => it.createChoice(o, j === p.correcta)));
    if (p.explicacion) {
      it.setFeedbackForCorrect(FormApp.createFeedback().setText('✅ ' + p.explicacion).build());
    }
    // (20/11) al terminar ven al instante cuál tuvieron mal y CUÁL era la correcta
    it.setFeedbackForIncorrect(FormApp.createFeedback().setText('❌ La correcta era: «' + p.opciones[p.correcta] + '»' +
      (p.explicacion ? '\n📖 ' + p.explicacion : '')).build());
  });
  try { form.setRequireLogin(false); } catch (e) { Logger.log('setRequireLogin: ' + e); }
  try { form.setLimitOneResponsePerUser(false); } catch (e) {}
  form.setConfirmationMessage('¡Gracias por participar! Tizku lemitzvot 🙏\n\n' +
    'Toca «Ver puntuación»: ahí ves tu calificación, cuáles tuviste bien y, en las que fallaste, cuál era la correcta.');
  let carpeta = null;
  try {
    const cs = DriveApp.getFoldersByName(CARPETA);
    carpeta = cs.hasNext() ? cs.next() : DriveApp.createFolder(CARPETA);
    DriveApp.getFileById(form.getId()).moveTo(carpeta);
  } catch (e) {}
  let hoja = '';
  try {
    const ss = SpreadsheetApp.create('Resultados · ' + d.titulo);
    form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
    try { if (carpeta) DriveApp.getFileById(ss.getId()).moveTo(carpeta); } catch (e) {}
    hoja = ss.getUrl();
  } catch (e) { Logger.log('hoja: ' + e); }
  let link = form.getPublishedUrl();
  try { link = form.shortenFormUrl(link); } catch (e) {}
  return { id: form.getId(), link: link, hoja: hoja, editar: form.getEditUrl() };
}

/** UN correo por examen, cuando el robot ya lo mandó al grupo. */
function confirmar_(r) {
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('correo:' + r.clave)) return 'ya se había mandado';
  const correo = Session.getEffectiveUser().getEmail();
  MailApp.sendEmail(correo, '✅ Examen Tawil enviado al grupo · días ' + r.dias,
    'Ya se mandó al grupo el examen de los días ' + r.dias + ' (' + r.preguntas + ' preguntas).\n\n' +
    'Link del examen (el que recibió el grupo):\n' + r.link + '\n\n' +
    'Resultados y calificación de todos (se llena sola conforme contestan):\n' + r.resultados + '\n\n' +
    'También en el Form, pestaña «Respuestas»:\n' + r.editar + '\n\n' +
    'Todo queda en tu Drive, carpeta «' + CARPETA + '».');
  props.setProperty('correo:' + r.clave, new Date().toISOString());
  return 'enviado';
}

/** Claude corrigió el examen ya armado: Ejecutar → rehacerExamen (arma un Form nuevo). */
function rehacerExamen() {
  const ex = bajarExamen_(); if (!ex) { Logger.log('No encontré el examen'); return; }
  PropertiesService.getScriptProperties().deleteProperty(ex.nombre + '#' + ex.huella);
  instalar();
}
