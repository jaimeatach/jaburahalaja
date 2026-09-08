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
  con una sola copia del archivo.
- Botón **Importar de archive.org**: lee la metadata del ítem, descarta los
  derivados que genera archive.org y arma las filas apuntando a sus URLs (sin
  `storagePath`, porque el archivo no es nuestro).
- Botón **Reordenar**: borra lo creado desde el catálogo y lo rearma. Reconoce
  también los títulos viejos en `CAT_LEGACY`, y no toca los simanim propios.
- `tools/subir_a_archive.py`: sube la carpeta del Drive a archive.org
  conservando las subcarpetas, de donde sale el reparto. Deduce por contenido la
  extensión de los archivos que en el Drive no la tienen.
