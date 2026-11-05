/**
 * Examen semanal de Rab Yosef Tawil → Google Forms (nov/2026).
 *
 * Cada viernes (antes de Shabat) se arma solo en el repo el examen de la semana
 * (tools/otzar/examenes/tawil_<viernes>.json). Este script lo convierte en un
 * Google Form tipo CUESTIONARIO (con calificación, respuestas correctas, puntos y
 * explicación) y te manda el link por correo, listo para mandarlo al grupo el
 * Motzaei Shabat.
 *
 * Cómo instalarlo (una sola vez, 2 minutos):
 *   1. script.google.com → Proyecto nuevo → pega TODO este archivo → Guardar.
 *   2. Arriba elige la función "instalar" → Ejecutar → acepta los permisos.
 *      Eso arma YA el examen de esta semana (te llega el correo) y deja programado
 *      que cada viernes a las 12:00 se arme el nuevo.
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
    .onWeekDay(ScriptApp.WeekDay.FRIDAY).atHour(12).inTimezone('America/Mexico_City').create();
  crearExamenTawil();
}

function fechaTexto_(d) {
  return Utilities.formatDate(d, 'America/Mexico_City', 'yyyy-MM-dd');
}

/** El JSON del viernes de esta semana (o el último que haya). */
function bajarExamen_() {
  const hoy = new Date();
  const dia = Number(Utilities.formatDate(hoy, 'America/Mexico_City', 'u')); // 1=lunes … 7=domingo
  const haciaViernes = (5 - dia + 7) % 7;                 // días al viernes que viene
  const candidatos = [haciaViernes, haciaViernes - 7, haciaViernes - 14];
  for (const k of candidatos) {
    const f = new Date(hoy.getTime() + k * 86400000);
    const nombre = 'tawil_' + fechaTexto_(f) + '.json';
    const r = UrlFetchApp.fetch(BASE + nombre + '?t=' + Date.now(), { muteHttpExceptions: true });
    if (r.getResponseCode() === 200) return { nombre: nombre, datos: JSON.parse(r.getContentText('UTF-8')) };
  }
  return null;
}

function crearExamenTawil() {
  const ex = bajarExamen_();
  if (!ex) {
    MailApp.sendEmail(Session.getEffectiveUser().getEmail(), 'Examen Tawil: todavía no está',
      'Todavía no está el examen de esta semana en el repo. Vuelve a ejecutar crearExamenTawil más tarde.');
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
  const texto = '📝 *' + d.titulo + '*\n' + (d.descripcion || '') + '\n\n👉 ' + link;
  MailApp.sendEmail(Session.getEffectiveUser().getEmail(), '📝 Examen Tawil listo: ' + d.titulo,
    'Listo para mandar al grupo el Motzaei Shabat (copia y pega):\n\n' + texto +
    '\n\nPara ver las respuestas y calificaciones: ' + form.getEditUrl());
  Logger.log(texto);
  return link;
}
