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
const ETIQUETA = { facil: '🟢 Fácil', media: '🟡 Media', medio_dificil: '🟠 Medio difícil', muy_dificil: '🔴 Muy difícil' };

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

function crearExamenTawil() {
  const dia = Number(Utilities.formatDate(new Date(), 'America/Mexico_City', 'u'));
  if (dia === 6) return;                                   // Shabat: nada
  const ex = bajarExamen_();
  if (!ex) {
    if (dia === 5) MailApp.sendEmail(Session.getEffectiveUser().getEmail(), 'Examen Tawil: todavía no está',
      'Todavía no está el examen de esta semana en el repo. Avísale a Claude.');
    return;
  }
  const props = PropertiesService.getScriptProperties();
  const ya = props.getProperty(ex.nombre);
  if (ya) { Logger.log('Ya estaba: ' + ya); return ya; }

  const d = ex.datos;
  const form = FormApp.create(d.titulo);
  form.setIsQuiz(true)
      .setDescription(d.descripcion || '')
      .setCollectEmail(false)
      .setProgressBar(true)
      .setConfirmationMessage('¡Gracias por participar! Tizku lemitzvot 🙏');
  form.addTextItem().setTitle('Nombre completo').setRequired(true);
  d.preguntas.forEach((p, i) => {
    const it = form.addMultipleChoiceItem();
    it.setTitle((i + 1) + '. ' + p.pregunta)
      .setHelpText((ETIQUETA[p.nivel] || '') + ' · Shiur #' + p.shiur + ' · ' + (p.puntos || 1) + (p.puntos > 1 ? ' puntos' : ' punto'))
      .setPoints(p.puntos || 1)
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

  let link = form.getPublishedUrl();
  try { link = form.shortenFormUrl(link); } catch (e) {}
  props.setProperty(ex.nombre, link);
  const texto = mensajeGrupo_(d, link);
  const cuerpo =
    'Ya quedó el examen de esta semana en Google Forms.\n\n' +
    '👇 MENSAJE PARA EL GRUPO (Motzaei Shabat). Copia desde la línea de abajo hasta "hatzlajá" y pégalo en WhatsApp:\n' +
    '────────────────────────\n' + texto + '\n────────────────────────\n\n' +
    'Respuestas y calificaciones de cada uno: ' + form.getEditUrl() + '  (pestaña «Respuestas»)\n' +
    'El Form quedó en tu Drive, carpeta «' + CARPETA + '».';
  MailApp.sendEmail(Session.getEffectiveUser().getEmail(), '📝 Examen Tawil listo para el grupo · ' + (d.shiurim_txt || d.titulo), cuerpo);
  Logger.log(cuerpo);
  return link;
}

/** El mensaje que se pega en el grupo de WhatsApp. */
function mensajeGrupo_(d, link) {
  const tema = String(d.descripcion || '').split('. ')[0].replace(/\.$/, '');
  const m = String(d.titulo || '').match(/#\d+\s*[–-]\s*#\d+/);
  const rango = m ? 'Shiurim ' + m[0].replace(/\s*[–-]\s*/, ' al ') : '';
  const n = (d.preguntas || []).length || 6;
  return '📝 *Examen semanal · Rab Yosef Tawil*\n' +
    (rango ? rango + (tema ? ' · ' + tema : '') + '\n' : (tema ? tema + '\n' : '')) +
    '\nEste es el examen de las clases de esta semana. Contéstalo aquí 👇\n' + link + '\n\n' +
    'Son ' + n + ' preguntas (3 fáciles, 1 media, 1 medio difícil y 1 muy difícil). Pon tu nombre completo; ' +
    'al terminar ves tu calificación y la explicación de cada respuesta.\n\n¡Mucha hatzlajá! 💪';
}
