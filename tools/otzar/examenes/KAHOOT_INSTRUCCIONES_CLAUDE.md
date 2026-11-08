# Subir el Kahoot de Rab Yosef Tawil (para Claude con la computadora)

Copiar y pegar TODO lo de abajo en Claude (app de escritorio con "uso de la computadora"
o Claude en Chrome). El usuario no tiene que hacer nada más que iniciar sesión en Kahoot
si Claude se lo pide.

---

Hola Claude. Necesito que subas a Kahoot un examen que ya está listo y me des el link para
mandarlo a un grupo de WhatsApp. Hazlo tú todo, sin pedirme que lo haga yo, salvo iniciar
sesión si hace falta.

1. Descarga este Excel (es la plantilla oficial de importación de Kahoot, ya llena):
   https://raw.githubusercontent.com/jaimeatach/jaburahalaja/claude/shiurim-halachot-shabbat-vriig5/tools/otzar/examenes/kahoot_tawil.xlsx
   Guárdalo en Descargas como `kahoot_tawil.xlsx`.
2. Abre https://create.kahoot.it en el navegador. Si no hay sesión iniciada, pídeme que
   inicie sesión (o que cree una cuenta gratis) y espera a que te diga "listo".
3. Si ya existe un kahoot llamado "Rab Yosef Tawil" de antes, NO lo borres: haz uno nuevo.
4. Crea uno nuevo: botón **Create** → **Kahoot**.
5. En la columna de preguntas: **Add question** → **Import spreadsheet** (o "Import" →
   "Spreadsheet"). Sube `kahoot_tawil.xlsx`, revisa la vista previa y aprieta
   **Add questions**. Si queda una pregunta vacía de ejemplo al principio, bórrala.
6. Revisa que haya el mismo número de preguntas que filas tiene el Excel, que cada una
   tenga 4 respuestas y una marcada como correcta. Si Kahoot marca alguna con error, dime
   cuál y su texto.
7. Título: **Rab Yosef Tawil · Examen Kahoot** (si pide descripción: "Velas de Shabat,
   recibir Shabat, Arvit y Kidush"). Guarda: **Save** / **Done**.
8. Para que cada quien lo haga desde su celular cuando pueda: abre el kahoot → **Assign**
   (o "Assign as self-paced" / "Challenge") → fecha límite: el domingo siguiente a las
   23:00 → crea el link y cópialo. Si "Assign" pide pagar, no pagues: dime que "Assign"
   no está en la cuenta gratis y dame el link para compartir el kahoot (Share → Copy link).
9. Al final escríbeme solo esto, listo para pegar en el grupo:

   Shavua Tov! 🎉 Les compartimos el Kahoot de los shiurim del Rab Yosef Tawil.
   Entra aquí y contesta desde tu celular: <LINK>
   ¡Mucha hatzlajá!

Si el importador de Excel pide pagar (Kahoot Premium), no pagues nada: avísame y crea las
preguntas a mano copiándolas de este archivo (pregunta, 4 respuestas, la correcta y el
tiempo en segundos):
https://raw.githubusercontent.com/jaimeatach/jaburahalaja/claude/shiurim-halachot-shabbat-vriig5/tools/otzar/examenes/kahoot_tawil.json
(en el JSON "correcta" es 1 a 4 y "tiempo" son los segundos).
