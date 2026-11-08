/**
 * Examen semanal de Rab Yosef Tawil → Google Forms (nov/2026).
 *
 * Cada JUEVES en la mañana se arma solo en el repo el examen de la semana
 * (tools/otzar/examenes/tawil_<viernes>.json). Este script corre solo todos los días
 * a la 1 pm (nunca en Shabat): en cuanto aparece el examen nuevo lo convierte en un
 * Google Form tipo CUESTIONARIO (con calificación, respuestas correctas, puntos y
 * explicación) y te manda por correo el MENSAJE YA ARMADO para pegarlo en el grupo
 * el Motzaei Shabat. Cada examen se arma una sola vez.
 *
 * Cómo instalarlo (una sola vez, 2 minutos):
 *   1. script.google.com → Proyecto nuevo → pega TODO este archivo → Guardar.
 *   2. Arriba elige la función "instalar" → Ejecutar → acepta los permisos.
 *      Eso arma YA el examen de esta semana (te llega el correo) y deja programado
 *      que cada semana se arme solo el nuevo (el jueves a la 1 pm).
 *   Si quieres armarlo a mano: ejecuta "crearExamenTawil".
 */
const RAMA = 'claude/shiurim-halachot-shabbat-vriig5';
const BASE = 'https://raw.githubusercontent.com/jaimeatach/jaburahalaja/' + RAMA + '/tools/otzar/examenes/';
const CARPETA = 'Exámenes Rab Yosef Tawil';

function instalar() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'crearExamenTawil')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('crearExamenTawil').timeBased()
    .everyDays(1).atHour(13).inTimezone('America/Mexico_City').create();
  crearExamenTawil();
}

function fechaTexto_(d) {
  return Utilities.formatDate(d, 'America/Mexico_City', 'yyyy-MM-dd');
}

/** El JSON de esta semana (lleva la fecha del viernes; se acepta también la del jueves),
 *  o el de la semana pasada si el nuevo todavía no está. */
function bajarExamen_() {
  const hoy = new Date();
  const dia = Number(Utilities.formatDate(hoy, 'America/Mexico_City', 'u')); // 1=lunes … 7=domingo
  const haciaViernes = (5 - dia + 7) % 7;                 // días al viernes que viene
  const candidatos = [haciaViernes, haciaViernes - 1, haciaViernes - 7, haciaViernes - 8];
  for (const k of candidatos) {
    const f = new Date(hoy.getTime() + k * 86400000);
    const nombre = 'tawil_' + fechaTexto_(f) + '.json';
    const r = UrlFetchApp.fetch(BASE + nombre + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (r.getResponseCode() === 200) return { nombre: nombre, datos: JSON.parse(r.getContentText('UTF-8')) };
  }
  return null;
}

function crearExamenTawil(e) {
  const dia = Number(Utilities.formatDate(new Date(), 'America/Mexico_City', 'u'));
  // Shabat: el disparador automático no hace nada (a mano, p. ej. en Motzaei Shabat, sí corre)
  if (dia === 6 && e && e.triggerUid) { Logger.log('Shabat: el automático no hace nada'); return; }
  const ex = bajarExamen_();
  Logger.log(ex ? 'Examen encontrado: ' + ex.nombre : 'No encontré el examen en GitHub');
  if (!ex) {
    if (dia === 5 || !(e && e.triggerUid)) MailApp.sendEmail(Session.getEffectiveUser().getEmail(), 'Examen Tawil: todavía no está',
      'Todavía no está el examen de esta semana en el repo. Avísale a Claude.');
    return;
  }
  const props = PropertiesService.getScriptProperties();
  const ya = props.getProperty(ex.nombre);
  if (ya) {
    // ya estaba: solo se le aplican los ajustes (abierto a todos + respuestas al final)
    const f = formDe_(props.getProperty(ex.nombre + '_id'));
    if (f) ajustar_(f, ex.datos);
    Logger.log('Ya estaba: ' + ya); return ya;
  }

  const d = ex.datos;
  const form = FormApp.create(d.titulo);
  form.setIsQuiz(true)
      .setDescription(d.descripcion || '')
      .setCollectEmail(false)
      .setProgressBar(true)
      .setConfirmationMessage('¡Gracias por participar! Tizku lemitzvot 🙏');
  props.setProperty(ex.nombre + '_id', form.getId());
  form.addTextItem().setTitle('Nombre completo').setRequired(true);
  d.preguntas.forEach((p, i) => {
    const it = form.addMultipleChoiceItem();
    it.setTitle((i + 1) + '. ' + p.pregunta)
      .setHelpText('Shiur #' + p.shiur)   // sin decir si es fácil o difícil (lo pidió el usuario)
      .setPoints(1)                  // todas valen 1 punto (lo pidió el usuario)
      .setRequired(true)
      .setChoices(p.opciones.map((o, j) => it.createChoice(o, j === p.correcta)));
    if (p.explicacion) {
      it.setFeedbackForCorrect(FormApp.createFeedback().setText('✅ ' + p.explicacion).build());
      it.setFeedbackForIncorrect(FormApp.createFeedback().setText('📖 ' + p.explicacion).build());
    }
  });
  // a su carpeta en tu Drive
  try {
    const cs = DriveApp.getFoldersByName(CARPETA);
    const carpeta = cs.hasNext() ? cs.next() : DriveApp.createFolder(CARPETA);
    DriveApp.getFileById(form.getId()).moveTo(carpeta);
  } catch (e) { /* si no se puede mover, queda en Mi unidad */ }

  ajustar_(form, d);
  // hoja con las respuestas y la calificación de todos, junto al Form
  let hoja = '';
  try {
    const ss = SpreadsheetApp.create('Respuestas · ' + d.titulo);
    form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
    try {
      const cs2 = DriveApp.getFoldersByName(CARPETA);
      if (cs2.hasNext()) DriveApp.getFileById(ss.getId()).moveTo(cs2.next());
    } catch (e) {}
    hoja = ss.getUrl();
  } catch (e) { Logger.log('hoja: ' + e); }
  let link = form.getPublishedUrl();
  try { link = form.shortenFormUrl(link); } catch (e) {}
  props.setProperty(ex.nombre, link);
  const texto = mensajeGrupo_(d, link);
  const cuerpo =
    'Ya quedó el examen de esta semana en Google Forms.\n\n' +
    '👇 MENSAJE PARA EL GRUPO (Motzaei Shabat). Copia desde "Shavua Tov" hasta "Hatzlajá a todos" y pégalo en WhatsApp:\n' +
    '────────────────────────\n' + texto + '\n────────────────────────\n\n' +
    'Las respuestas y la calificación de TODOS:\n' +
    (hoja ? '  • En una hoja de cálculo: ' + hoja + '\n' : '') +
    '  • En el Form, pestaña «Respuestas»: ' + form.getEditUrl() + '\n' +
    'Cada quien, al terminar, ve su calificación y cuáles tuvo bien y cuáles no («Ver puntuación»).\n' +
    'El Form quedó en tu Drive, carpeta «' + CARPETA + '».';
  const correo = Session.getEffectiveUser().getEmail() || Session.getActiveUser().getEmail();
  Logger.log('Form listo: ' + link + '  · mandando correo a ' + correo);
  MailApp.sendEmail(correo, '📝 Examen Tawil listo para el grupo · ' + (d.shiurim_txt || d.titulo), cuerpo);
  Logger.log(cuerpo);
  return link;
}

/** El mensaje que se pega en el grupo de WhatsApp (con el estilo que usa el usuario). */
function mensajeGrupo_(d, link) {
  let tema = String(d.descripcion || '').split('. ')[0].replace(/\.$/, '').trim();
  if (tema) tema = tema.charAt(0).toLowerCase() + tema.slice(1);
  const m = String(d.titulo || '').match(/#(\d+)\s*[–-]\s*#(\d+)/);
  const dias = m ? ' (días ' + m[1] + ' al ' + m[2] + ')' : '';
  return 'Shavua Tov!\n\n' +
    'Les compartimos la autoevaluación de esta semana' + (tema ? ' sobre ' + tema : '') + dias + '. ' +
    'Es un pequeño examen para repasar lo que aprendimos.\n\n' +
    'Este examen es sin premio. El examen con premio será en Kahoot, una vez al mes.\n\n' +
    'Al terminar verán su calificación y las respuestas correctas.\n\n' +
    '👉 ' + link + '\n\n' +
    '¡Hatzlajá a todos! 🙌';
}

/** Ajustes que el examen necesita siempre:
 *  - que lo pueda abrir CUALQUIERA con el link (en una cuenta de empresa, Google lo
 *    deja por omisión solo para la gente de la empresa y los del grupo no entran);
 *  - al terminar, solo la calificación (lo pidió el usuario, 8/11): cuáles tuvo bien y
 *    cuáles no, en «Ver puntuación» del propio Form. */
function ajustar_(form, d) {
  try { form.setRequireLogin(false); } catch (e) { Logger.log('setRequireLogin: ' + e); }
  try { form.setLimitOneResponsePerUser(false); } catch (e) {}
  // Al final solo la calificación: Google enseña cuáles tuvo bien y cuáles no (con la
  // explicación de cada una) en «Ver puntuación». No se listan las respuestas aquí.
  form.setConfirmationMessage('¡Gracias por participar! Tizku lemitzvot 🙏\n\n' +
    'Toca «Ver puntuación» para ver tu calificación y cuáles tuviste bien y cuáles no.');
}

function formDe_(id) {
  try { if (id) return FormApp.openById(id); } catch (e) {}
  // los creados antes de guardar su id: el más nuevo de la carpeta
  try {
    const cs = DriveApp.getFoldersByName(CARPETA);
    if (!cs.hasNext()) return null;
    const fs = cs.next().getFilesByType(MimeType.GOOGLE_FORMS);
    let mejor = null;
    while (fs.hasNext()) { const f = fs.next(); if (!mejor || f.getDateCreated() > mejor.getDateCreated()) mejor = f; }
    return mejor ? FormApp.openById(mejor.getId()) : null;
  } catch (e) { return null; }
}

/** Para arreglar a mano el examen que ya se armó (Ejecutar → arreglarExamen). */
function arreglarExamen() {
  const ex = bajarExamen_(); if (!ex) return;
  const props = PropertiesService.getScriptProperties();
  const f = formDe_(props.getProperty(ex.nombre + '_id'));
  if (!f) { Logger.log('No encontré el Form en la carpeta ' + CARPETA); return; }
  ajustar_(f, ex.datos);
  Logger.log('Listo: ' + f.getPublishedUrl());
}

/** Vuelve a armar el examen de esta semana desde cero (cuando Claude lo corrigió):
 *  Ejecutar → rehacerExamen. Crea un Form NUEVO y te manda el correo con el link nuevo. */
function rehacerExamen() {
  const ex = bajarExamen_(); if (!ex) { Logger.log('No encontré el examen'); return; }
  const props = PropertiesService.getScriptProperties();
  props.deleteProperty(ex.nombre); props.deleteProperty(ex.nombre + '_id');
  return crearExamenTawil();
}
