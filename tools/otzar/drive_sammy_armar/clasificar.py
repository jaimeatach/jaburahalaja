"""Clasifica todos los shiurim (todos_shiurim.json) en carpetas por tema, al estilo del
Drive de Rab Shweke: Parashá / Jaguim / Halajá (por Shulján Aruj) / Musar / Tanaj / ..."""
import json, re, sys, collections, importlib.util, unicodedata
from pathlib import Path

AQUI = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("py", str(AQUI.parent / "parasha_youtube.py"))
sys.argv = ["x"]
py = importlib.util.module_from_spec(spec); spec.loader.exec_module(py)

LIBROS = [("1. Bereshit", "Bereshit Noach Lech-Lecha Vayera|Chayei Sara|Toldot|Vayetzei|Vayishlach|Vayeshev|Miketz|Vayigash|Vayechi"),
          ("2. Shemot", "Shemot|Vaera|Bo|Beshalach|Yitro|Mishpatim|Terumah|Tetzaveh|Ki Tisa|Vayakhel|Pekudei"),
          ("3. Vayikra", "Vayikra|Tzav|Shmini|Tazria|Metzora|Achrei Mot|Kedoshim|Emor|Behar|Bechukotai"),
          ("4. Bamidbar", "Bamidbar|Nasso|Beha'alotcha|Sh'lach|Korach|Chukat|Balak|Pinchas|Matot|Masei"),
          ("5. Devarim", "Devarim|Vaetchanan|Eikev|Re'eh|Shoftim|Ki Teitzei|Ki Tavo|Nitzavim|Vayeilech|Ha'azinu|Vezot Haberakhah")]
ORDEN = list(py.PARASHIOT.keys())
LIBRO_DE = {}
for i, k in enumerate(ORDEN):
    LIBRO_DE[k] = LIBROS[0][0] if i < 12 else LIBROS[1][0] if i < 23 else LIBROS[2][0] if i < 33 else LIBROS[3][0] if i < 43 else LIBROS[4][0]
NUM_EN_LIBRO = {}
cnt = collections.Counter()
for k in ORDEN:
    cnt[LIBRO_DE[k]] += 1
    NUM_EN_LIBRO[k] = cnt[LIBRO_DE[k]]
ESP = {"Noach": ["Noaj"], "Lech-Lecha": ["Lej Leja", "Lej Lejá", "Lech Lechá"], "Vayera": ["Vayerá", "Vaiera", "Vayeira"],
       "Chayei Sara": ["Jaye Sara", "Jayé Sará", "Haye Sara"], "Toldot": ["Toldot", "Toledot"], "Vayetzei": ["Vayetse", "Vayetsé", "Vaietze"],
       "Vayishlach": ["Vayishlaj"], "Vayeshev": ["Vayeshev"], "Miketz": ["Mikets", "Mikkets"], "Vayechi": ["Vayeji", "Vaieji"],
       "Shemot": ["Shemot", "Shmot"], "Vaera": ["Vaerá"], "Beshalach": ["Beshalaj", "Beshalach"], "Yitro": ["Itro", "Yitró"],
       "Terumah": ["Terumá"], "Tetzaveh": ["Tetzavé", "Tezave", "Tetsave"], "Ki Tisa": ["Ki Tisá"], "Vayakhel": ["Vayakel"],
       "Pekudei": ["Pekudé"], "Tzav": ["Zav", "Tsav"], "Shmini": ["Sheminí"], "Tazria": ["Tazriá"], "Metzora": ["Metsorá", "Metzorá"],
       "Achrei Mot": ["Ajaré Mot", "Ajare Mot", "Ajrei Mot"], "Kedoshim": ["Kedoshim"], "Emor": ["Emor"], "Behar": ["Behar"],
       "Bechukotai": ["Bejukotai", "Bejukotay"], "Bamidbar": ["Bamidbar"], "Nasso": ["Nasó", "Naso"],
       "Beha'alotcha": ["Behaalotja", "Behaalotejá", "Beaalotja"], "Sh'lach": ["Shelaj", "Shlaj"], "Korach": ["Koraj", "Kóraj"],
       "Chukat": ["Jukat", "Jukat"], "Pinchas": ["Pinjás", "Pinjas"], "Matot": ["Matot"], "Masei": ["Masé", "Maséi"],
       "Vaetchanan": ["Vaetjanan", "Vaetjanán"], "Eikev": ["Ekev", "Ekeb", "Ekev"], "Re'eh": ["Reé", "Ree"],
       "Shoftim": ["Shofetim"], "Ki Teitzei": ["Ki Tetsé", "Ki Tetze", "Ki Tetzé", "Ki Tese"], "Ki Tavo": ["Ki Tabó", "Ki Tavó"],
       "Nitzavim": ["Nitsavim", "Nitzabim"], "Vayeilech": ["Vayelej"], "Ha'azinu": ["Haazinu", "Haazinú"],
       "Vezot Haberakhah": ["Vezot Haberajá", "Vezot Haberaja"]}
AMBIGUAS_HEB = {"נח", "בא", "ראה", "צו", "אמור", "שמות", "דברים", "עקב", "בהר", "במדבר", "שופטים", "תרומה", "משפטים", "קדושים", "שמיני", "מקץ"}
AMBIGUAS_LAT = {"Bo", "Emor", "Behar", "Tzav", "Zav", "Noach", "Noaj", "Ekev", "Eikev", "Reeh", "Re'eh", "Ree", "Masei", "Naso", "Nasso"}
PALABRA_PARASHA = r"(?:פרשת|פרשה|פר['׳’]|parash[ao]t|parsha[st]?|perash[ao]t|perasha|parashat|parasha|parshas|parshat|parasha)"


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[֑-ׇ]", "", s)
    return s


def plano_lat(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().replace("’", "'")


def parasha_de(t):
    tn = norm(t)
    tl = plano_lat(t)
    tiene_palabra = re.search(PALABRA_PARASHA, tn, re.I) is not None
    hallados = []
    for k, (graf, heb) in py.PARASHIOT.items():
        # hebreo
        m = re.search(rf"(?<![א-ת]){re.escape(heb)}(?![א-ת])", tn)
        if m and (heb not in AMBIGUAS_HEB or re.search(PALABRA_PARASHA + rf"\s*{re.escape(heb)}(?![א-ת])", tn)
                  or re.match(rf"^\s*{re.escape(heb)}\s*[-–|｜:]", tn)):
            if re.search(rf"{re.escape(heb)}\s*(?:-|–)?\s*פרק", tn):
                continue                              # "שופטים פרק ו": el libro, no la parashá
            hallados.append((m.start(), k)); continue
        for g in graf + ESP.get(k, []):
            gl = plano_lat(g)
            m = re.search(rf"(?<![a-z']){re.escape(gl)}(?![a-z'])", tl)
            if m and (g not in AMBIGUAS_LAT or re.search(PALABRA_PARASHA + rf"\s*{re.escape(gl)}(?![a-z])", tl, re.I)):
                hallados.append((m.start(), k)); break
    if not hallados:
        return None
    hallados.sort()
    return hallados[0][1]


JAGUIM = [
    ("01. Elul, Selijot y Rosh Hashaná", r"אלול|סליחות|ראש השנה|ר[\"״]ה(?![א-ת])|עשרת ימי תשובה|שופר|elul|selij|selich|rosh hashan|shofar|10 d[ií]as de teshuba|ten days of repentance|תשרי"),
    ("02. Yom Kipur", r"כיפור|כפור|kip+ur|yom kip|כפרות"),
    ("03. Sukot y Simjat Torá", r"סוכות|סוכה|סוכת|ארבעת המינים|הושענא|שמיני עצרת|שמחת תורה|sukot|sukkot|sucot|suca |sukkah|simjat tor|simchat tor|hoshana|lulav"),
    ("04. Jánuca", r"חנוכה|חנוכת|janu[ck]|chanuk|hanuk"),
    ("05. Tu Bishvat", r"ט[\"״]ו בשבט|טו בשבט|tu bishvat|tu b'shvat"),
    ("06. Purim", r"פורים|מגילת אסתר|purim|meguilat esther|megillat esther"),
    ("07. Pésaj", r"פסח|הגדה של פסח|חמץ|מצה|ליל הסדר|pesaj|pesach|passover|seder|jamets|chametz|matza"),
    ("08. Sefirat HaÓmer y Lag BaÓmer", r"ספירת העומר|העומר|ל[\"״]ג בעומר|omer|lag ba"),
    ("09. Shavuot", r"שבועות|מתן תורה|shavuot|shavuos"),
    ("10. Bein HaMetzarim y Tishá BeAv", r"תשעה באב|ט['׳] באב|בין המצרים|י[\"״]ז בתמוז|חורבן|tisha|tishá|9 de av|three weeks|bein hamets|bein hamitz|17 de tamuz|jurb[aá]n"),
    ("11. Rosh Jódesh y otras fechas", r"ראש חודש|rosh jodesh|rosh chodesh|יום ירושלים|יום העצמאות|הילולת|hilulat|hilula|יארצייט|yahrzeit"),
]

HALAJA_TEMAS = [  # (sección, tema, regex)
    ("1. Óraj Jaim", "01. Hashkamat HaBóker, Tzitzit y Tefilín (1-45)", r"השכמת הבוקר|ציצית|תפילין|tzitzit|tsitsit|tefil[ií]n|netilat yadayim shajarit"),
    ("1. Óraj Jaim", "02. Tefilá y Keriat Shemá (46-135)", r"קריאת שמע|ק[\"״]ש|שמונה עשרה|עמידה|תפילה|תפלה|מנין|מניין|קדיש|קדושה|חזרת הש[\"״]ץ|אמן|tefil[aá]|amid[aá]|minyan|minian|kadish|kaddish|shema"),
    ("1. Óraj Jaim", "03. Keriat HaTorá y Beit HaKnéset (135-156)", r"קריאת התורה|ספר תורה|בית הכנסת|בית כנסת|ההפטרה|הפטרה|sefer tor|beit hakneset|keriat hator"),
    ("1. Óraj Jaim", "04. Netilat Yadáyim, Seudá y Birkat HaMazón (157-201)", r"נטילת ידיים|ברכת המזון|זימון|סעודה|מים אחרונים|netilat|birkat hamaz|zimun|bircat hamazon|table manners"),
    ("1. Óraj Jaim", "05. Brajot (202-231)", r"ברכ|ברכות|עיקר וטפל|שהכל|מזונות|העץ|האדמה|הגומל|ברכת הלבנה|שהחיינו|beraj|braj|bracha|beracha|blessing|hagomel|amen"),
    ("1. Óraj Jaim", "06. Shabat (242-344)", r"שבת|מוקצה|טלטול|בורר|בישול|הבערה|כיבוי|עירוב|קידוש|הבדלה|נרות שבת|הדלקת נרות|מלאכ|shabat|shabbat|shabbos|muktze|bishul|kidush|kiddush|havdal|encendido de velas|erev shabat|candle"),
    ("1. Óraj Jaim", "07. Moadim (Jaguim en halajá)", r"פסח|חמץ|מצה|ליל הסדר|jametz|jamets|matz|סוכ|חנוכה|פורים|ראש השנה|כיפור|יום טוב|שבועות|ספירת העומר|תענית|תשעה באב|ט['׳] באב|pesaj|pesach|sukot|janu|purim|kipur|yom tov|shavuot|omer|taanit|tisha"),
    ("2. Yoré Deá", "01. Kashrut y Basar BeJalav", r"כשרות|בשר בחלב|חלבי|בשרי|שחיטה|טריפה|תולעים|בדיקת (?:ירקות|תולעים|ביצים)|בישול עכו[\"״]ם|פת עכו[\"״]ם|טבילת כלים|kashrut|kosher|basar bejalav|meat and milk|tevilat kelim|bishul akum"),
    ("2. Yoré Deá", "02. Kibud Av VaEm", r"כיבוד אב|כבוד אב|kibud av|av vaem|honoring parents|padres"),
    ("2. Yoré Deá", "03. Tzedaká, Ribit y Jalá", r"צדקה|מעשר|ריבית|הפרשת חלה|חלה|tzedak|tsedak|maaser|ribit|interest"),
    ("2. Yoré Deá", "04. Nidá y Taharat HaMishpajá", r"נדה|טהרת המשפחה|מקוה|מקווה|טבילה|nid[aá]|taharat|mikve"),
    ("2. Yoré Deá", "05. Avelut, Bikur Jolim y Kevurá", r"אבלות|אבל|שבעה|קבורה|ביקור חולים|לוויה|avelut|shiv[aá]|duelo|mourning|bikur jolim"),
    ("2. Yoré Deá", "06. Mezuzá, Talmud Torá y otros", r"מזוזה|תלמוד תורה|כבוד רבו|נדרים|שבועה|mezuz|talmud tor"),
    ("3. Even HaEzer", "01. Kidushín, Jupá y Shalom Bait", r"קידושין|חופה|נישואין|שבע ברכות|כתובה|גיטין|kidushin|jup[aá]|chuppah|boda|matrimonio|ketub"),
    ("4. Jóshen Mishpat", "01. Dinim de Mamonot y Bein Adam LaJaveró", r"ממון|נזיקין|גזל|השבת אבידה|דיני ממונות|הלוואה|שכירות|עסק|בית דין|mamon|nezik|robo|business|partnership"),
]
SHMIRAT = r"שמירת הלשון|לשון הרע|רכילות|חפץ חיים|אהבת חסד|shemirat halashon|shmirat halashon|lashon hara|chafetz|jafetz"
HALAJA_SHOWS = {"ofirmalka", "isaaccredi", "credi", "mishnaberura", "yalkutyosef", "yechavedaat", "ravasherweiss", "ravyitzchakyosef", "tawil"}
HALAJA_PAL = r"הלכות|הלכה|דיני |דין |סימן|סעיף|שו[\"״]ת|halaj|halach|halak|siman|jewish law|ley(?:es)? de|permitido|prohibido|está permitido|se permite|mitzvá de"
TANAJ_LIBROS = ["בראשית", "שמות", "ויקרא", "במדבר", "דברים", "יהושע", "שופטים", "שמואל א", "שמואל ב", "מלכים א", "מלכים ב", "ישעיהו", "ירמיהו", "יחזקאל",
                "הושע", "יואל", "עמוס", "עובדיה", "יונה", "מיכה", "נחום", "חבקוק", "צפניה", "חגי", "זכריה", "מלאכי",
                "תהילים", "משלי", "איוב", "שיר השירים", "רות", "איכה", "קהלת", "אסתר", "דניאל", "עזרא", "נחמיה", "דברי הימים א", "דברי הימים ב"]
TANAJ_LAT = {"tehilim": "תהילים", "tehillim": "תהילים", "mishlei": "משלי", "meguilat esther": "אסתר", "megilat esther": "אסתר", "rut": "רות", "kohelet": "קהלת", "iyov": "איוב", "shir hashirim": "שיר השירים"}

RAB_HEB = re.compile(r"(?:מו[\"״]ר |הגאון |הגה[\"״]צ |מרן )?(?:ה?רב|הרבנית|האדמו[\"״]ר|רבי|חכם)\s+((?:[א-ת'\"״׳]+\s?){1,3})")
RAB_LAT = re.compile(r"(?:Rabbi|Rab|Rav|R\.|Rabbanit|Harav|Jajam|Hajam|Sr\.)\s+((?:[A-Z][\w'’\.]+\s?){1,3})")


sys.path.insert(0, str(AQUI))
from rabs import rab_de, SHOW_RAB  # noqa: E402
FUERA = [("musar", r"עמוד\s*ה?יומי|Amud\s*Ha?\s*Yomi"), ("musar", r"שער\s*הבי?טחון|Sha'?ar\s*Ha?\s*Bitach?j?on")]


def limpiar(s, n=150):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s).replace("‏", "").replace("‎", "")
    s = re.sub(r"[⁦-⁩]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    while len(s.encode("utf-8")) > n:
        s = s[:-1]
    return s.strip(" .")


def carpeta(x):
    t = norm(x["t"]); tl = plano_lat(x["t"]); show = x["show"]
    # series que van enteras
    if show == "mishnaberura":
        m = re.search(r"חלק\s+([א-ו])", t)
        return ["3. Halajá", "1. Óraj Jaim", "00. Mishná Berurá (shiur por shiur)", ("Jélek " + m.group(1)) if m else "Varios"]
    if show == "yalkutyosef":
        return ["3. Halajá", "1. Óraj Jaim", "00. Yalkut Yosef (shiur por shiur)"]
    if show == "taamim":
        return ["5. Tanaj", "Taamé HaMikrá - Jajam Itzjak Batesh"]
    if show == "podcast":
        libro = next((l for l in sorted(TANAJ_LIBROS, key=len, reverse=True) if t.startswith(l)), "Varios")
        return ["5. Tanaj", "HaTanaj HaMevoar", libro]
    if show == "ahavatjesed" or re.search(SHMIRAT, t + " " + tl, re.I):
        return ["6. Shmirat HaLashon y Ahavat Jésed", rab_de(x)]
    for k, v in TANAJ_LAT.items():
        if re.search(rf"\b{k}\b\s*(?:cap[ií]tulo|perek|perec|\d)", tl):
            return ["5. Tanaj", v, rab_de(x)]
    pa = parasha_de(x["t"])
    jag = next((n for n, rx in JAGUIM if re.search(rx, t, re.I) or re.search(rx, tl, re.I)), None)
    t = re.sub(r"מוצאי שבת|מוצ[\"״]?ש(?![א-ת])|שבת שובה|שבת הגדול|שבת זכור|שבת חזון|שבת נחמו", " ", t)
    tl = re.sub(r"motza[eé]i shab\w*|shabb?[ao]s shuva|shabbat shuva|shabbat hagadol", " ", tl)
    es_halaja = show in HALAJA_SHOWS or re.search(HALAJA_PAL, t + " " + tl, re.I)
    if es_halaja and (show in HALAJA_SHOWS or not pa):
        tema = next(((sec, tem) for sec, tem, rx in HALAJA_TEMAS if re.search(rx, t, re.I) or re.search(rx, tl, re.I)), None)
        if tema:
            return ["3. Halajá", tema[0], tema[1]]
        if show in HALAJA_SHOWS and (pa or jag):
            pass                                        # halajá de un show de halajá sin tema claro: por parashá/jag
        elif show in HALAJA_SHOWS:
            return ["3. Halajá", "9. Varios temas", rab_de(x)]
    if pa and (re.search(PALABRA_PARASHA, t + " " + tl, re.I) or not jag):
        k = pa
        return ["1. Parashá", LIBRO_DE[k], f"{NUM_EN_LIBRO[k]:02d}. {k} · {py.PARASHIOT[k][1]}"]
    if jag:
        return ["2. Jaguim", jag]
    if pa:
        return ["1. Parashá", LIBRO_DE[pa], f"{NUM_EN_LIBRO[pa]:02d}. {pa} · {py.PARASHIOT[pa][1]}"]
    return ["4. Musar y Emuná", rab_de(x)]


def nombre_archivo(x, ruta):
    rab = rab_de(x)
    t = x["t"]
    sin_rab = rab.startswith(("Varios", "Familia", "Beit", "Jafetz"))
    base = t if (sin_rab or rab.split()[-1].strip("()") in t or ruta[0] in ("5. Tanaj",) or x["show"] in {"mishnaberura", "yalkutyosef", "taamim", "podcast"}) else f"{rab} · {t}"
    ext = Path(x["u"].split("?")[0]).suffix.lower() or ".mp3"
    return limpiar(base) + (ext if ext in (".mp3", ".m4a", ".ogg", ".wav") else ".mp3")


SHABAT_SUB = [
    ("01. Erev Shabat y Kabalat Shabat", r"ערב שבת|הכנה לשבת|הכנות לשבת|קבלת שבת|תוספת שבת|preparativ|erev shab|horarios|kabalat shab"),
    ("02. Encendido de velas", r"נרות|הדלקת|לאור הנר|\bנר\b|velas|candle|ner shab"),
    ("03. Kidush y Havdalá", r"קידוש|הבדלה|kidush|kiddush|havdal"),
    ("04. Seudot de Shabat", r"סעודה|סעודות|לחם משנה|כיסוי החלות|זמירות|עונג שבת|seud|zemirot|oneg"),
    ("05. Bishul y comida caliente", r"בישול|חימום|פלטה|הטמנה|סיר|bishul|plata|calentar|hot food|cholent|jamin"),
    ("06. Muktzé", r"מוקצה|טלטול|muktz|muktse"),
    ("07. Melajot", r"מלאכ|בורר|טוחן|לש |כותב|מוחק|קושר|צובע|בונה|סותר|צידה|תולש|קוצר|מכה בפטיש|כיבוי|הבערה|ממרח|סחיטה|melaj|melach|borer|trabajos prohibidos|acciones prohibidas"),
    ("08. Electricidad", r"חשמל|electric|eléctric|elevador|elevator|מעלית"),
    ("09. Amirá LeNojrí", r"אמירה לנכרי|לגוי|נכרי|goy|nojri|gentile"),
    ("10. Eruvín y Hotzaá", r"עירוב|הוצאה|רשות הרבים|eruv|hotza|cargar"),
    ("11. Refuá y pikúaj néfesh en Shabat", r"רפואה|חולה|תרופ|פיקוח נפש|medicin|enfermo|doctor"),
]
SHABAT_SIMAN = [(242, 252, "01. Erev Shabat y Kabalat Shabat"), (253, 259, "05. Bishul y comida caliente"),
                (260, 270, "02. Encendido de velas"), (271, 273, "03. Kidush y Havdalá"), (274, 300, "04. Seudot de Shabat"),
                (301, 307, "09. Amirá LeNojrí"), (308, 312, "06. Muktzé"), (313, 344, "07. Melajot"),
                (345, 365, "10. Eruvín y Hotzaá")]
MUSAR_TEMAS = [
    ("01. Emuná y Bitajón", r"אמונה|ביטחון|בטחון|השגחה|hashgaj|emun[aá]|bitaj|bitach|faith|trust in hashem|fe en|confianza"),
    ("02. Tefilá", r"תפילה|תפלה|להתפלל|תהילים|tefil|prayer|rezo|rezar|tehilim"),
    ("03. Teshuvá", r"תשובה|חזרה בתשובה|teshuv|repent|arrepent"),
    ("04. Shalom Bait, pareja y familia", r"שלום בית|זוגיות|נישואין|אשתו|בעל ואשה|זיווג|shalom bait|shalom bayit|marriage|matrimonio|pareja|esposa|marido|wife|husband|zivug|shiduj|shidduch"),
    ("05. Jinuj y padres e hijos", r"חינוך|ילדים|הורים|כיבוד אב|jinuj|chinuch|parenting|children|hijos|padres"),
    ("06. Midot (gaavá, kaas, envidia…)", r"מידות|גאווה|ענווה|כעס|קנאה|שנאה|גאוה|מידה|middot|midot|anger|enojo|ira|humildad|humility|arrogan|envidia|jealous|ego"),
    ("07. Shmirat Einaim y kedushá", r"שמירת עיניים|שמירת העיניים|קדושה|צניעות|יצר הרע|kedush|tzniut|tsniut|einaim|yetzer|yetser"),
    ("08. Torá y limud", r"לימוד תורה|תלמוד תורה|ללמוד|limud|torah study|estudio de tor"),
    ("09. Parnasá", r"פרנסה|עושר|כסף|ממון|parnas|money|dinero|riqueza|business|negocio"),
    ("10. Simjá y avodat Hashem", r"שמחה|simj|simch|happiness|alegr|felicidad"),
    ("11. Sufrimiento, salud y refuá", r"ייסורים|יסורים|סבל|רפואה|חולה|refu|sufrimiento|suffering|illness|enfermedad|salud"),
    ("12. Mashíaj y Gueulá", r"משיח|גאולה|mashiach|mashiaj|moshiach|geul|gueul|redemption|redenci"),
    ("13. Historias y relatos", r"סיפור|מעשה ב|story|stories|historia|relato|cuento"),
]
ELUL_SUB = [("1. Elul y Selijot", r"אלול|סליחות|elul|selij|selich"),
            ("3. Aseret Yemé Teshuvá", r"עשרת ימי תשובה|10 d[ií]as de teshuba|ten days of repentance|shuva|שובה"),
            ("2. Rosh Hashaná", r".")]
GEM = {c: v for c, v in zip("אבגדהוזחטיכלמנסעפצקרשת", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200, 300, 400])}


def gematria(s):
    return sum(GEM.get(c, 0) for c in s)


def sub_de(lista, x):
    t = norm(x["t"]); tl = plano_lat(x["t"])
    return next((n for n, rx in lista if re.search(rx, t, re.I) or re.search(rx, tl, re.I)), None)


def afinar(rutas, todo):
    """Carpetas que quedaron muy llenas se dividen otra vez (para que todo quede bien ordenado)."""
    cuenta = collections.Counter(tuple(r) for r in rutas)
    con_tema = collections.Counter(tuple(r) for r, x in zip(rutas, todo) if sub_de(MUSAR_TEMAS, x))
    cubre = {k: con_tema[k] / n for k, n in cuenta.items()}     # Musar por tema solo si casi todo tiene tema claro
    for r, x in zip(rutas, todo):
        clave = tuple(r)
        if clave == ("2. Jaguim", "01. Elul, Selijot y Rosh Hashaná"):
            r.append(sub_de(ELUL_SUB, x))
        elif clave == ("3. Halajá", "1. Óraj Jaim", "07. Moadim (Jaguim en halajá)"):
            r.append(next((n for n, rx in JAGUIM if re.search(rx, norm(x["t"]), re.I) or re.search(rx, plano_lat(x["t"]), re.I)),
                          "12. Varios"))
        elif clave == ("3. Halajá", "1. Óraj Jaim", "06. Shabat (242-344)"):
            m = re.search(r"סימן\s+([א-ת\"״׳']+)", norm(x["t"]))
            n = gematria(m.group(1)) if m else 0
            r.append(next((nom for a, b, nom in SHABAT_SIMAN if a <= n <= b), None) or sub_de(SHABAT_SUB, x) or "12. Varios")
        elif clave[-1].startswith("00. Yalkut Yosef"):
            m = re.search(r"שיעור\s+([א-ת\"״׳']+)", norm(x["t"]))
            n = gematria(m.group(1)) if m else 0
            r.append(f"Shiurim {((n - 1) // 100) * 100 + 1:03d}-{((n - 1) // 100 + 1) * 100:03d}" if n else "Varios")
        elif cuenta[clave] > 60 and clave[0] == "4. Musar y Emuná" and cubre.get(clave, 0) >= 0.6:
            r.append(sub_de(MUSAR_TEMAS, x) or "14. Varios temas")
    return rutas


if __name__ == "__main__":
    todo = json.load(open(AQUI / "todos_shiurim.json"))
    plan, usados = [], set()
    arbol = collections.Counter()
    todo = [x for x in todo if not any(x['show'] == sh and re.search(rx, x['t'], re.I) for sh, rx in FUERA)]
    print('shiurim:', len(todo), 'GB:', round(sum(x['b'] or 0 for x in todo)/1e9, 1))
    rutas = afinar([[limpiar(p, 120) for p in carpeta(x)] for x in todo], todo)
    for x, ruta in zip(todo, rutas):
        nom = nombre_archivo(x, ruta)
        clave = "/".join(ruta + [nom]).lower()
        k = 2
        while clave in usados:
            nom2 = re.sub(r"(\.[a-z0-9]+)$", f" ({k})\\1", nom); clave = "/".join(ruta + [nom2]).lower(); k += 1
            if clave not in usados:
                nom = nom2
        usados.add(clave)
        plan.append({"u": x["u"], "r": ruta, "n": nom, "b": x["b"], "f": x["f"], "show": x["show"]})
        for i in range(1, len(ruta) + 1):
            arbol[tuple(ruta[:i])] += 1
    json.dump(plan, open(AQUI / "plan_drive.json", "w"), ensure_ascii=False)
    for k in sorted(arbol):
        if len(k) <= 2:
            print("   " * (len(k) - 1) + f"{k[-1]}  ({arbol[k]})")
