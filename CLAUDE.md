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
- `הלכות מוקצה`: la carpeta "שיעורים מוקצה" que Saúl comparte aparte (31
  shiurim numerados al FINAL del nombre, `tail:true`). Sus ítems son objetos
  `{ t, s, saif }`: cada uno va a su propio siman (רע״ט, ש״ח–שי״ב) y a su saif
  (`catItemDestino`). Reemplaza al módulo viejo `מוקצה` de 3 shiurim, cuyos
  archivos se retiran al importar (`CAT_RETIRADOS`). En el publicador entra por
  `carpetas_extra` (config de la jabura), con `titulos.json` (los mismos títulos
  y simanim, los escribe el instalador en el paso [29]), `ignorar_carpetas`
  (la מוקצה vieja), `ignorar` (el הקדמה duplicado de 2024) y `al_fondo`: sus
  episodios toman fechas anteriores a todo, así en Spotify quedan hasta abajo y
  el robot no los anuncia como nuevos.

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
   publica con la API de GitHub (`github_token.txt`) en el repo que diga
   `config.json`: para la jabura es ESTE repo (`jaimeatach/jaburahalaja`), así
   que `feed.xml`, `fechas.json` y `portada.jpg` viven en la raíz y los sirve
   Netlify. El RSS es `https://jaburahalajasaul.netlify.app/feed.xml`
   (`feed_url` en el config; sin él usaría GitHub Pages y crearía el repo).
   El primer feed se generó desde el entorno de desarrollo con `length="0"`;
   la primera corrida en la PC pone los tamaños reales. El show existente de
   Spotify (`SPOTIFY_SHOW`) se redirige a ese RSS desde Spotify for Creators
   ("redirect to a new host"); al hacerlo, los episodios pasan a ser los del
   feed. El publicador, con las llaves de la API (`spotify_keys.txt`, las del
   robot), publica `spotify_episodios.json` junto al feed y la app
   (`spotifyCargar`/`spotifyDe`) enlaza cada shiur con su episodio por título,
   con chequeo de ida y vuelta y de número final; `CAT_SPOTIFY` queda de respaldo.
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
   "🎧 *título* / 📲 App / link directo / 🎵 Spotify", `sin_audio` (el audio
   ya está en el grupo), `sin_whatsapp`, y `sin_spotify` hasta que el show lea
   el feed nuevo. El link directo es el `<link>` de cada item del feed
   (`#/s/<siman>/<título>`), que la app resuelve en `resolveShiurTitulo`
   (por número y título; si el admin abre el link y el shiur aún no está,
   lo importa de archive.org al vuelo). Los flags son parches al robot
   (`sinAudio()`, `appLink`, `armarMensaje(..., app)`). `ANUNCIAR.bat` corre
   `tools/otzar/mantenimiento.py` antes de mandar la orden al robot: alinea la
   carpeta de cada bot con la del robot y marca lo ya publicado, publica la
   jabura y cada show con `modo_whatsapp` (Peretz, Nacach, Ofir, Tefila),
   espeja nacach y aplica `solo_ultimos` (por show en `anunciar`): memoriza
   todo el feed salvo los últimos N, así nunca se arrastra un rezago. Ese
   botón es el único disparador; el usuario no quiere tareas programadas.
   El robot lee el feed de la jabura de `anunciar.jabura.feed` (el raw de
   GitHub: netlify.app no siempre abre en esa PC); parche `feedDeShow()`.
   Nacach anuncia "título + link" a varios grupos (`invite` en lista) sin
   audio; sin show en Spotify va el link directo al mp3 (`link_audio`).
   Las notas de voz (.ogg) se convierten a mp3 (`convertidos\`) antes de subir.
5. `tools/otzar/instalar_otzar.py` (o `INSTALAR_OTZAR.bat`) hace todo en la PC
   de Otzar de un tirón: parcha el robot (con respaldo), agrega la jabura al
   `config_whatsapp.json`, arma `C:\OTZAR\jabura`, espeja el feed de Nacach
   al repo viejo `nacash` (el que lee Spotify) y deja listo el show `tefila`
   (Rab Tofi Cherem, grupo "Clases Tefila Habitat", estilo Peretz: el robot
   guarda en `C:\OTZAR\tefila\audios_whatsapp`, `podcast_bot.py` publica desde
   `ANUNCIAR.bat`; el grupo se registra mandando `!otzar tefila` en el grupo;
   `--tefila-spotify=LINK` activa el anuncio). `--ver` es prueba en seco.
6. Fuentes: cada show toma audios SOLO de su grupo fuente (`escuchar.<show>`,
   registrado como `escucha:<show>` en `grupos_registrados.json`); `reg[show]` a
   secas es el grupo de anuncios y lo que manden ahí no se sube. El robot ubica
   la fuente por el link de invitación al arrancar, si no por `nombre` del
   config (`NOMBRES_FUENTE` en el instalador: tefila = "Clases Tefila Habitat"),
   y si no, mandando `!otzar <show>` dentro del grupo. El paso [25] del
   instalador dice de qué grupo toma audios cada show y cuál falta ubicar.
   Nacach toma audios de su grupo "Shiurim jajam ezra nacach" (por nombre,
   `FUENTES_NUEVAS`) además del chat directo. Los grupos de ANUNCIO cuyo link
   da `bad-request` se ubican por nombre con `grupos_nombre` en el config
   (`GRUPOS_NOMBRE`: "3 Solo Shiurim", "Clases Tefila Habitat").
8. Shows nuevos: `--nuevo=clave --nuevo-nombre --nuevo-rss --nuevo-spotify
   --nuevo-grupo` (paso [18]) arma carpeta, repo + Pages, portada y canal del
   show que ya existe en Spotify (RSS de anchor), rescata sus episodios y
   configura el robot: fuente = grupo del Rab, anuncia en su grupo (con link
   del grupo) + los generales, sin audio. Así entraron hilu y credi (David
   Credi, "Halajot Generales"). El nombre del Rab al frente del título va en
   `PREFIJOS`; el título por defecto en `TITULOS_DEFECTO`; `SHOWS_REDIRECT`
   lista los que esperan el redirect. Shows sin fuente de WhatsApp (efshar,
   mishlei) llevan el nombre en el MENSAJE (`SUFIJOS_ANUNCIO` →
   `sufijo_anuncio`, `tituloAnuncio()` en el robot). `REGLAS_TITULO`
   (`quitar_lineas`, `unir_lineas`, `sufijo_titulo` en `escuchar.<show>`)
   arma el título al guardar: Isaac Credi manda "1151 Siman 639" + tema en
   1-2 líneas y sale "tema1, tema2 - Sr. Isaac Credi". Nunca se manda el
   link al mp3 (`link_audio` siempre False).
9. Parashá semanal: `tools/otzar/parasha_youtube.py` (el instalador lo deja en
   `C:\OTZAR\jabura\`, junto a `mantenimiento.py`, que lo corre en cada ANUNCIAR).
   Para los shows con `"parasha_semanal": true` en su `config.json`
   (`--parasha=chazaq`, paso [33]) calcula la parashá del Shabat que viene
   (diáspora, con `@hebcal/core` del robot vía `node`; si no, pyluach o la API de
   hebcal), busca en el canal de YouTube del show un video que la nombre con
   cualquier grafía (`PARASHIOT`: Ki Tavo/Ki Savo/כי תבוא), primero entre los
   últimos subidos y si no entre los más vistos de otros años, baja hasta
   `parasha_max` (2) de mínimo `parasha_min_minutos` (5), y publica con
   `podcast_bot.py apartar/subir/feed`; el robot lo anuncia en ese mismo
   ANUNCIAR. Candado semanal `parasha_ultimo.json` en la carpeta del show; sin
   resultados reintenta en el próximo ANUNCIAR (3 h de calma). En semana de jag
   no hace nada. El mismo paso pone `"parasha": {"auto": true, "dia": 0}` en el robot:
   las dos parashot salen con el ANUNCIAR del lunes (`dia` 0; si no se aprieta,
   con el primero de la semana hasta el viernes, nunca sábado ni domingo):
   `mantenimiento.py` corre el script y deja `parasha.ahora` para el módulo
   `parasha_semanal.js` del usuario (Rav Asher Weiss, con su propio candado).
   Audios por correo: `tools/otzar/correo_shiurim.py` (también en
   `C:\OTZAR\jabura\`, lo corre `mantenimiento.py` antes de publicar). Para los
   shows con `"correo"` en su `config.json` (`--correo=show:buzón:remitente`,
   paso [34]; contraseña de aplicación en `<show>\correo_clave.txt`, nunca en el
   repo) entra por IMAP al buzón, toma adjuntos de audio y links de Google Drive
   de esos remitentes, pone título (nombre del archivo, o el asunto si el nombre
   es genérico), descarta lo que ya está en el feed, ordena parashá → Tehilim →
   Rut → Ester → resto (`clasificar`) y los deja en `audios_whatsapp` con fechas
   seguidas después de lo último del feed; `podcast_bot.py` los publica en ese
   orden. Candado `correo_procesados.json`. Así entró `taamim` (טעמי המקרא, חכם
   יצחק בטיש; show creado con `--nuevo ... --nuevo-sin-grupos`: solo Spotify).
   La PC de Otzar tiene el filtro Techloq, que intercepta imap.gmail.com y no
   deja entrar por IMAP: por eso `taamim` usa el MODO CARPETA
   (`--correo-carpeta=show:RUTA`): `tools/otzar/apps_script_correo.gs` (Apps
   Script en la cuenta del buzón, disparador cada 10 min) guarda los adjuntos y
   links de Drive del remitente en `Mi unidad\OTZAR\taamim`, Drive lo baja a la
   PC y `correo_shiurim.py` los toma de ahí (mismo orden, mismos candados;
   `clave_titulo` iguala "פרשת בשלח" con "בשלח" al descartar repetidos).
   Robot de fiestas (`robot_fiestas.py`, `FIESTA_*.bat`): `apartar_no_fiesta`
   solo borra mp3 que bajaron las corridas de ESA fiesta (fecha de creación
   posterior al arranque de la corrida, leído de `fiestas.log`; los shows que
   terminaron en "(ya los tenia todos)" se saltan). Nunca toca material anterior.
   Cada fiesta en `FIESTAS` lleva `dias` (cuánto dura). `mantenimiento.py`
   (`fiestas_pasadas`) marca en `estado_anuncios.json` como ya anunciados los
   episodios de los últimos 45 días cuyo título nombra una fiesta que ya
   terminó: así un shiur de Sukot que Spotify tardó en tomar no sale cuando
   Sukot ya pasó. `--fiestas` lo corre solo; `--fiestas-rehacer` vuelve al
   respaldo y repite. Las palabras latinas se comparan como palabra entera y
   las comillas se quitan (ר״ה no pega en "מו״ר הרב").
   No repetir: el robot guarda en `estado_titulos.json` los títulos ya vistos
   de cada show (los aprende del propio feed) y no manda un shiur cuyo título
   ya salió aunque vuelva con otro guid; `permitir_repetidos: true` por show
   lo apaga. Parche del instalador (`normTitulo`, `titulosVistos`).
   Si en un grupo fuente llega un video, documento o link (SoundCloud, Drive…)
   en vez de audio, el robot lo escribe en el log ("SIN AUDIO en la fuente de
   <show>") en lugar de callarse. `tools/otzar/diagnostico.py <show> [días]`
   (en `C:\OTZAR\jabura\`) junta lo que vio el robot de ese show, su carpeta,
   lo que espera título y lo último del feed, sin tocar nada.
   Una sola ventana: dos robots abiertos se roban la sesión (código 440) y lo
   que llega en ese rato se pierde (así se perdió una clase de Hilu el viernes
   9/10). `robot.lock` (PID, refrescado cada 30 s) hace que una segunda
   ventana no se conecte (`otroRobotVivo`).
   Rescate: `--rescatar=hilu,jabura[:días]` (paso [41]) deja `rescatar.json`
   en el robot; éste le pide a WhatsApp los últimos mensajes del grupo fuente
   (`fetchMessageHistory`, anclado al último mensaje visto en ese grupo, que
   guarda en `anclas.json`) y procesa en `messaging-history.set` los audios
   posteriores al último audio de la carpeta del show (nunca duplica). Un audio
   que esperaba título y sobrevivía a un reinicio caía en la carpeta de Peretz;
   ahora va a la de su show.
   Plataformas: cada anuncio lleva, además de Spotify, el link del episodio en
   Apple Podcasts (API pública de iTunes por `apple_id`; si el episodio aún no
   aparece, el del show) y el del show en Amazon Music / SoundCloud.
   `tools/otzar/plataformas.py` (lo corre `mantenimiento.py` cada 3 h, solo pregunta por los que faltan;
   `--revisar` en el instalador da el reporte completo) busca cada show en Apple,
   dice cuál no tiene grupo o lleva >14 días sin nada y deja `plataformas.json`.
   Amazon y SoundCloud no tienen API: `--amazon=show:LINK`, `--soundcloud=show:LINK`.
   SoundCloud no lee RSS: `tools/otzar/soundcloud_subir.py` sube cada audio con la
   API oficial (llaves de una app registrada en `C:\OTZAR\jabura\soundcloud_app.txt`,
   nunca en el repo; `autorizar <show>` hace OAuth con PKCE y deja
   `<show>\soundcloud_token.json`). `mantenimiento.py` (`soundcloud`) corre `subir` en
   cada ANUNCIAR: la primera vez memoriza lo existente, luego sube lo nuevo (4 por vez)
   y deja `soundcloud_episodios.json` en el robot, que pone el link del episodio.
   Guía para el usuario: `tools/otzar/GUIA_PLATAFORMAS.pdf`.
   Link de Apple corto (oct/2026): `appleCorto` quita el nombre del episodio
   (`podcasts.apple.com/podcast/id…?i=…`) y `acortarLink` lo pasa por is.gd (sin publicidad;
   TinyURL NO: mete un redirect de viglink); caché en `links_cortos.json`, si is.gd falla va el
   normal; `"acortar_links": false` en el config lo apaga. Spotify ya va en su forma mínima.
   `spotify_espera_horas` (`--spotify-espera=show:H`): si Spotify no toma el
   episodio en H horas sale con el link del show (TorahAnytime se trababa).
   `plantilla` en anunciar.<show>: bloques con {fecha_hebrea} {fecha} {titulo}
   {spotify} {apple} {amazon} {soundcloud} {whatsapp} {dedicatoria}; el bloque
   cuyo dato falta no sale. `esperar_fecha`: no se anuncia antes de su pubDate.
10. Rab Yosef Tawil (`--tawil`, paso [42]): Yehuda Avi Ezri manda cada semana los
   audios con "Dia 21. Domingo" al grupo fuente (`escuchar.tawil`, link
   KE2AgbfPaGaElrVS8kwdJt; el robot tiene que ser miembro). Con
   `temas: true` el título sale del tema de la semana ("#21 Encendido de Velas (1)")
   y la fecha del archivo es la de ese día de la semana. Temas en
   `tools/otzar/temas/tawil.json` (los actualizo yo cuando el usuario avisa el
   domingo; el robot los relee cada 30 min) o "!tema tawil 27 Tema" por WhatsApp
   (`<show>\temas.json` en la PC, manda sobre el del repo). Se anuncia cada uno SU
   día (`esperar_fecha`) en los 2 grupos de Tawil y en los generales 3 y 6, con la
   plantilla: fecha hebrea / civil, título + "Rab Yosef Tawil", plataformas, L"N
   Moshe Ben Sara / Miriam Bat Lea Luisa, link del grupo.
   Calendario (paso [47]): `calendario` {"n": 21, "fecha": "2026-10-11"} en
   `anunciar.tawil` da la fecha de cada shiur por su número (uno por día, sin sábado
   ni Yom Tov de la diáspora: `@hebcal/core` del robot o la lista `_YOM_TOV`);
   `no_shabat` no manda nada ese día; lo de un día ya pasado se marca en silencio.
   Sale desde las 00:00 de su día (el usuario aprieta ANUNCIAR a las 5:30).
   En Spotify/Apple se ven YA: el robot no pone fecha futura al archivo y
   `mantenimiento.py` (`sin_fechas_futuras`) cambia por la de hoy cualquier pubDate futuro
   de los shows con `calendario` (en orden de número, mismo guid); solo el ANUNCIO espera su día.
   Va con el audio (`sin_audio: false`). El título del anuncio sale del tema
   ("#22- Encendido de Velas (2)", `tituloDeTema`). La dedicatoria cambia cada semana:
   `{"desde": N, "dedicatoria": "..."}` en `temas/tawil.json` (`dedicatoriaDe`); sin
   ella va la del config (L"N Moshe Ben Sara...). El usuario avisa los domingos el
   tema y el donador. Lo puede mandar él mismo por WhatsApp (chat privado
   con el robot o dentro del grupo fuente "Shiurim rab yosi"; ahí el robot ignora
   sus propias respuestas ✅/❌ para que no se vuelvan título de un audio): "!tawil 27" (sin número: el shiur del domingo que viene) y abajo
   "tema: Kidush" / "donador: L\"N ..." (el donador puede ocupar varias líneas); se
   guarda en `C:\OTZAR\tawil\temas.json` (manda sobre el repo) y el robot contesta
   cómo va a salir. Si una semana se avisa el MISMO tema que venía, la cuenta sigue
   (`temasDe` junta temas iguales seguidos: #27 = Encendido de Velas (7), no (1)); si el
   título guardado quedó con otra cuenta, el robot busca en Spotify también con el
   título corregido. Spotify del show:
   1gVVXZw6fNyrcqadB5pmLC; para que lea nuestro feed sin perder #1-#26 hace falta
   su RSS de Spotify for Creators (`--tawil-rss=https://anchor.fm/s/1171db72c/podcast/rss`).
   Estadísticas: al rescatar, podcast_bot pone guids nuevos (nombre del archivo; así
   quedaron hilu y credi). `guids_originales` (paso [45], `--guids-originales=show`,
   automático con `--tawil-rss`) le devuelve a cada episodio rescatado el guid y la
   fecha que tiene en Spotify, y los guarda en `ids_spotify` del config.json del
   show; `mantenimiento.py` (`ids_spotify`) los vuelve a poner si un feed los pierde.
   Mismo guid = mismo episodio para Spotify: conserva reproducciones y horas.
   No hacer el redirect hasta que diga "N de N episodios con su MISMO ID".
   Encabezado igual al de Spotify (paso [50], `CANALES`): `tools/otzar/canales/tawil.json`
   (nombre "Harav Yosef Tawil Shlit”a", descripción "Shiurim Rab Yosi Tawil", autor
   "otzar hatorah", Religion & Spirituality › Judaism) + la foto ORIGINAL en base64
   (`tawil_portada.b64`, con sha256): la portada que bajó la PC salió con la cara tapada
   (filtro Techloq), así que nunca se baja como imagen en esa PC. Se sube con nombre
   fechado y queda en `config.json` → `canal`; `mantenimiento.py` (`canal_feed`) la vuelve a
   poner en el feed en cada corrida. `revisar_spotify.py <show>` dice si el redirect quedó
   (el RSS de anchor tiene que llevar a nuestro feed) y qué episodios le faltan a Spotify;
   el 18/10/2026 el redirect de Tawil NO estaba hecho (Spotify seguía en #26).
11. Mekorot y títulos de la jabura: con `guardar_documentos` en `escuchar.jabura`
   (paso [46], siempre) el robot guarda los PDF/Word del grupo como
   "מקורות · nombre.pdf" en la carpeta del siman (no se anuncian); el publicador
   los sube a archive.org, la app los importa como material y `renderMare` los
   muestra arriba de מראי מקומות. `--rescatar=jabura:N` trae también los
   documentos (`documentos: true`). Títulos corregidos: `tools/otzar/jabura_titulos.json`
   (nombre de archivo → {"t": título}); `mantenimiento.py` (`titulos_jabura`) lo
   suma a `jabura\titulos.json` (el publicador cambia el título en el feed sin
   cambiar el guid) y la app (`arcTitulosCurados`, admin) corrige el shiur ya importado.
   Emparejar con Spotify: si el parecido de letras no llega a 0.90, `elegirPorPalabras`
   compara solo las palabras que dicen de qué trata (sin relleno, sin nombre del Rab
   y sin las que salen en >30% de los episodios del show), con el mismo candado de
   números de serie, y no adivina si dos empatan.
12. Frenar un show (paso [48], `--frenar=show`): pausa su anuncio, aparta su
   `podcast_bot.py` (queda `podcast_bot.py.pausado` y en su lugar uno que no hace nada,
   así ni ACTUALIZAR ni ANUNCIAR publican), aparta sus `canales_youtube` (el robot de
   fiestas buscaba en TODOS los canales y metía otros rabinos) y, con
   `tools/otzar/limpieza_<show>.json`, quita esos episodios del feed en GitHub (los mp3
   quedan en archive.org; el feed de antes queda en la carpeta del show). `--reanudar=show`
   lo deshace; `--nuevo-host=show:RSS` (el show pasó a Spotify for Creators) pone
   `<itunes:new-feed-url>` en el feed viejo. Así se frenó `ravyitzchakyosef` (13/10/2026):
   de 170 episodios, 109 no eran del Rab Yitzjak Yosef (otros rabinos, Rab Ovadia zt"l,
   una descarga de otro canal del 9/8); el usuario lo sube a mano desde Creators.
   `--pausar=show` / `--despausar=show` (paso [49]) solo pausan el ANUNCIO del robot
   (`anunciar.<show>.pausado`), sin tocar feeds ni bots. Mishlei quedó en pausa el
   13/10/2026 (la gente se saturó; luego viene otro curso).
   `--quitar-del-robot=show` (paso [51]) lo saca de `config_whatsapp.json` (anunciar,
   escuchar, escuchar_directo) y de `grupos_registrados.json`, con respaldo, sin tocar
   archivos ni feed: así salió `ravyitzchakyosef` (18/10/2026). En los anuncios armados con
   `armarMensaje`, `conPlataformas` mete Apple/Amazon/SoundCloud DESPUÉS de Spotify y ANTES
   del grupo de WhatsApp (orden pedido: Spotify, Apple, WhatsApp).
   Amud Yomi (paso [52], siempre): `daf_diario.js` del usuario manda el amud de MAÑANA;
   `amud_cuando` le pone arriba "📅 Mañana · Tomorrow · מחר" (o "Hoy · Today · היום" si la
   fecha del renglón es hoy). Con respaldo y `node --check`; si el archivo cambió, no lo toca.
13. Piloto automático (oct/2026; el usuario pidió dejar de apretar botones):
   `tools/otzar/piloto.py` (en `C:\OTZAR\jabura\`, se abre con `PILOTO.bat` junto al robot).
   Cada 5 min: si el robot guardó un audio nuevo en cualquier carpeta fuente, corre
   `mantenimiento.py` (lo de ANUNCIAR.bat); si no, una vez por hora. Cada 30 min corre
   `podcast_bot.py` de los shows de YouTube (lo de ACTUALIZAR; salta pausados/manuales y
   los de `--frenar`). Después de publicar y cada 15 min escribe `comando.txt` = anunciar
   (solo de 5:30 a 22:00). Nada en Shabat/Yom Tov: desde las 16:00 de la víspera hasta la
   puesta del sol + 50 min del último día (`puestaSol`/`puesta_sol`, NOAA para CDMX, ±1 min de
   hebcal), así Motzaei Shabat ya se anuncia; el robot tiene el mismo candado
   (`bloqueoSagrado` en `anunciarInterno`, también para el botón y el vigilante). `PILOTO_PAUSA.txt`
   lo pausa; ajustes en `jabura\piloto.json`; log en `C:\OTZAR\piloto.log`. Necesita la PC
   prendida: para que funcione con la PC apagada hay que llevarlo a un servidor.
14. Vigilancia y mudanza (oct/2026): el piloto vuelve a abrir el robot si `robot.lock` no
   se refresca en 3 min (máx. una vez cada 10 min), escribe `C:\OTZAR\piloto_reporte.txt`
   y deja avisos en `<robot>\avisos\*.txt` (reporte de las 7:00, disco < 5 GB, mantenimiento
   o anuncio que falla 3 veces); el robot los manda al chat que se registró con "!reporte"
   (privado; el primero que lo manda, después solo ese) y no los manda en Shabat/Yom Tov.
   Desde ese chat: "!estado", "!pausa" (crea `PILOTO_PAUSA.txt`), "!sigue". `PILOTO.bat` se
   reabre solo si el piloto se cae. `tools/otzar/mudanza.py empacar|desempacar|revisar` pasa
   `C:\robotwhats` (con `sesion_baileys`) y `C:\OTZAR` a la HP que queda prendida: copia sin
   borrar, inventario de Node/Python/ffmpeg/pip, instala lo que falte con winget/pip, pone
   `OTZAR_inicio.cmd` en la carpeta Inicio de Windows (robot y piloto al prender) y powercfg
   (sin suspender con corriente, tapa = nada, CPU 85% para menos calor).
15. Audios fuera de la PC (oct/2026; el usuario no quiere guardarlos, "no quiero perder shiurim"):
   `tools/otzar/espacio.py` (en `C:\OTZAR\jabura\`). Sin argumentos: cuánto ocupa cada show,
   cuántos ya están en archive.org con el mismo tamaño, y manda al repo (`tools/otzar/bots/`)
   cada `podcast_bot.py` distinto (revisando que no lleve llaves) y `espacio_reporte.txt`.
   El 20/10/2026: 70 GB en la PC, 66 GB ya en archive.org, disco con 703 GB libres.
   `limpiar` lista; `limpiar --si` aparta a `C:\OTZAR\_papelera\<fecha>` (14 días y se borra)
   solo lo que tiene en archive.org el MISMO md5 y ya está en el feed (shows frenados: sin
   feed), y los originales de WhatsApp ya en `procesados_whatsapp.txt` con su mp3 en archive.org;
   deja los de los últimos 7 días y los 3 más nuevos de cada carpeta; antes pone
   `solo_agregar: true` (sin eso `generar_feed` rearma el feed con la carpeta y perdería
   episodios). Los bots saben qué bajaron por `ya_descargados.txt`/`procesados_whatsapp.txt`
   (no por los mp3) y el robot baja el audio del anuncio de archive.org, así que no dependen
   de la carpeta. Nunca la jabura (G:, Drive compartido de Saúl) ni nada fuera de C:\OTZAR.
   Con `limpieza_auto.json` `mantenimiento.py` (`limpieza`) lo corre una vez al día.
7. Tefila y Hilu anuncian con link del show + audio directo (`sin_spotify`,
   `link_audio`) hasta que el show de Spotify lea nuestro feed; el redirect
   lo hace el usuario en Spotify for Creators y luego corre
   `--redirigido=tefila,hilu` (paso [26]), que activa el link exacto.
   Si un parche del robot no entra, el instalador reemplaza el robot entero
   por `tools/otzar/robot_whatsapp.js` (que es el mismo robot parchado), con
   respaldo `.bak_<fecha>`.
