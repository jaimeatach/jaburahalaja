# Jabura Halaja (חבורת הלכה)

App web para una jabura (grupo de estudio de halajá). Permite gestionar simanim, materiales de estudio, shiurim (audio), exámenes con entregas, mare mekomot, preguntas con comentarios y likes, noticias y archivos compartidos. Interfaz bilingüe (hebreo/español), RTL.

## Arquitectura

- **Un solo archivo**: toda la app vive en `index.html` (~3000 líneas: HTML + CSS + JS vanilla). No hay build, no hay framework, no hay dependencias locales.
- **Backend**: Supabase (base de datos + storage), vía `@supabase/supabase-js@2` cargado por CDN.
- **Deploy**: Netlify, publica la raíz del repo tal cual (ver `netlify.toml`). El HTML se sirve sin caché (`max-age=0, must-revalidate`) para que los cambios se vean al instante.
- **Flujo de deploy**: commit + push a GitHub (`jaimeatach/jaburahalaja`) → Netlify despliega automáticamente.

## Credenciales Supabase (en index.html, líneas ~347-349)

- `SUPABASE_URL`: `https://enkofkroxudsblewxxos.supabase.co`
- `SUPABASE_ANON_KEY`: `sb_publishable_nAsf0qU7fPUOZ5K7OgqwYw_hUPgzOrZ` (clave publishable/anon, pública por diseño)
- Bucket de storage: `jabura` (archivos: PDFs, audios, imágenes)

## Tablas Supabase (mapa `T` en index.html línea ~358)

| Clave JS   | Tabla         | Uso |
|------------|---------------|-----|
| users      | `usuarios`    | usuarios con id, name, salt, hash, role (`admin`/`member`), photo. El primer usuario registrado es admin. |
| simanim    | `simanim`     | simanim con number, title, saifim, pinned (siman "Estudiando ahora"), kind (`halaja` default o `musar`; los musar son "temas/sijot" con secciones y solo tienen Contenido, Shiurim y Mis notas) |
| mare       | `mare`        | mare mekomot por siman |
| materials  | `materiales`  | materiales de estudio (archivos) |
| shiurim    | `shiurim`     | shiurim (audio) por siman |
| exams      | `examenes`    | exámenes |
| subs       | `entregas`    | entregas de exámenes por usuario |
| notes      | `notas`       | notas |
| news       | `news`        | noticias |
| shared     | `compartido`  | archivos compartidos (campo `files` con storagePaths) |
| questions  | `preguntas`   | preguntas de usuarios |
| comments   | `comentarios` | comentarios (targetType/targetId, soporta respuestas vía parentId, visibilidad) |
| likes      | `likes`       | likes (targetType/targetId/userId) |
| marks      | `marcas`      | marcadores/clips en shiurim: shiurId, userId, userName, time (segundos), note |

## Convenciones

- Autenticación propia (no Supabase Auth): login por nombre, con salt+hash guardados en la tabla `usuarios`.
- Constante `BUILD` en index.html (~línea 351) indica la versión; actualizarla al hacer cambios relevantes.
- Al borrar registros con archivos, también se eliminan sus paths del bucket `jabura`.
- Textos de UI duplicados en hebreo y español (objetos de traducción dentro del mismo archivo).

## Catálogo del Drive y archive.org

El contenido de la jabura vive en un ítem de archive.org, no en Supabase Storage
(el audio son ~4 GB y no entra en el plan). En `index.html`:

- `CATALOG`: los módulos (12 de halajá + 3 de musar) con los títulos de sus
  shiurim en orden. El módulo del שכ״א sale de tres carpetas del Drive
  (מעבד, טוחן, לש) y usa `groups` para que la numeración de cada carpeta se
  resuelva dentro de su tramo.
- `CAT_SEFARIM`: los PDFs no son módulos. Cada sefer declara el rango de
  simanim que abarca y se referencia desde el Contenido de cada siman cubierto,
  con una sola copia del archivo. Los marcados con `p:1` nombran los simanim en
  su título (מ״ב, כף החיים, שלמי יהונתן, ש״ע) y van a TODOS los simanim del
  rango; los generales solo a los que tienen shiurim, para no saturar los 93.
- `CAT_SPOTIFY`: mapa título de shiur → enlace del episodio en Spotify. Sale del
  RSS del show (`tools/spotify_lista.py` lo lee y deja `spotify_episodios.json`);
  el show se subió directo en Spotify for Podcasters, no con el bot de los otros
  repos. 40 de los 53 episodios tienen shiur en el Drive; los 13 restantes son
  solo de Spotify. Para agregar episodios nuevos: correr el script y emparejar.
  `SPOTIFY_SHOW` es el canal.
- Botón **Importar de archive.org**: lee la metadata del ítem, descarta los
  derivados que genera archive.org y arma las filas apuntando a sus URLs (sin
  `storagePath`, porque el archivo no es nuestro).
- Botón **Reordenar**: borra lo creado desde el catálogo y lo rearma. Reconoce
  también los títulos viejos en `CAT_LEGACY`, y no toca los simanim propios.
- `tools/subir_a_archive.py`: sube la carpeta del Drive a archive.org
  conservando las subcarpetas, de donde sale el reparto. Deduce por contenido la
  extensión de los archivos que en el Drive no la tienen.

## Simanim de הלכות שבת

- `SA_SHABAT` en `index.html`: los 93 simanim רנ״ב–שד״מ (el חלק ג del משנה ברורה)
  con su título y su cantidad de סעיפים. **Cargado de memoria**: desde el entorno
  de desarrollo no se puede consultar Sefaria ni alhatorah, así que conviene
  repasarlo contra la fuente (ya se corrigieron של״ה y שמ״א). Volver a apretar
  **Abrir jelek ג** actualiza los títulos de los simanim que ya existen.
- Botón **Abrir jelek ג**: crea los que faltan y a los que ya existen les pone el
  título del שולחן ערוך y les completa los סעיפים, sin tocar su contenido.
- Cada shiur se ubica en su saif en tres pasos: `catSaifDe(titulo)` lee el saif
  del propio nombre ("סעיף ב־ג־ד" son tres, "סעיף א עד ג" es un rango); si no lo
  dice, `CAT_SAIF` lo ubica según el contenido del saif; y si tampoco, queda en
  el primero porque es un shiur de הקדמה, סיכום o חזרה.
- `CAT_SAIF` se armó con el catálogo temático del ש״ע con משנה ברורה que aportó
  el Rav. De 131 shiurim, 12 dicen el saif, 62 se ubicaron por contenido y 57
  quedan en el primer saif por no tratar de un saif concreto.
- Los módulos que comparten siman se unen: מעבד·טוחן·לש en שכ״א y
  גוזז·כותב ומוחק en ש״מ, cada uno con `groups` para resolver la numeración.

## WhatsApp → archive.org → Spotify (el flujo de Otzar, para la jabura)

Los shiurim nuevos llegan a un grupo de WhatsApp y terminan en la app, en
archive.org y en Spotify sin subir nada a mano. Todo corre en la PC de Otzar:

1. `robot_whatsapp.js` (Baileys, `C:\OTZAR`) escucha el grupo `escuchar.jabura`
   y guarda cada audio en `carpetaDestino`, que es la subcarpeta del siman que
   se estudia AHORA dentro del Drive de la jabura (`…\שיעורים בהלכה\<módulo>`).
   Los nombra numerados ("03 título.m4a") para conservar el orden. Al cambiar
   de siman se cambia esa línea del `config_whatsapp.json`
   (`tools/otzar/config_whatsapp_FRAGMENTO.json`). `tools/otzar/robot_whatsapp.js`
   es el robot del usuario con dos parches: JIDs `@lid` (busca el teléfono en
   `senderPn`/`participantPn`) y la numeración de la jabura.
2. `tools/jabura_publicar.py` (con `config.json` de `tools/otzar/`) sube a
   archive.org solo lo que falta, conservando las subcarpetas, NUNCA borra del
   Drive, arma `feed.xml` (título = "módulo · nombre", orden por fecha) y lo
   publica en `rabmeireliyahu/jabura` (GitHub Pages); si el repo no existe lo
   crea y prende Pages con el `github_token.txt`. El RSS es
   `https://rabmeireliyahu.github.io/jabura/feed.xml`. El show existente de
   Spotify (`SPOTIFY_SHOW`) se redirige a ese RSS desde Spotify for Creators
   ("redirect to a new host"); al hacerlo, los episodios pasan a ser los del
   feed y hay que rehacer `CAT_SPOTIFY` con `tools/spotify_lista.py`.
   El feed va en el orden de la app (`ORDEN`): musar y חגים primero, luego los
   simanim por número, ש״מ al final; las fechas se reparten la primera vez y
   quedan fijas en `fechas.json` (junto al script), lo nuevo toma fecha de hoy.
3. La app, al entrar un admin, corre `arcAutoImport()`: lee el ítem de
   archive.org (una vez por hora) y agrega lo nuevo. Un archivo en una carpeta
   del `CATALOG` va a ese módulo; una carpeta nueva que nombra su siman
   ("סימן שמא") va a ese siman por número (`catSimanDeCarpeta`, lo crea con el
   título del ש״ע si falta); el título es el nombre sin el número
   (`catTituloLibre`). Sefarim se procesan al final y en modo automático no
   crean módulos.
4. `anunciar.jabura` en el config del robot manda el aviso al mismo grupo:
   título + link a la app (`app`), `sin_audio` (el audio ya está en el grupo),
   `sin_whatsapp`, y `sin_spotify` hasta que el show lea el feed nuevo. Los
   tres flags son parches al robot (`sinAudio()`, `datos.app`). `ANUNCIAR.bat`
   corre `jabura_publicar.py` antes de mandar la orden al robot.
5. `tools/otzar/instalar_otzar.py` (o `INSTALAR_OTZAR.bat`) hace todo en la PC
   de Otzar de un tirón: parcha el robot (con respaldo), agrega la jabura al
   `config_whatsapp.json`, arma `C:\OTZAR\jabura` y rescata los audios de
   Nacach que quedaron sin publicar. `--ver` es prueba en seco.
