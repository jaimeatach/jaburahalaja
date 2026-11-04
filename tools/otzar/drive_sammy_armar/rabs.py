import re
SHOW_RAB = {
 "abergel": "הרב ישראל אברג'ל", "abuhatzeira": "הרב רפאל אבוחצירא", "bensoussan": "Rabbi Duvi Bensoussan",
 "biderman": "הרב ירחמיאל יוסף בידרמן", "credi": "Rab David Credi", "davidpinto": "האדמו״ר רבי דוד חנניה פינטו",
 "davidsohn": "Rab Tzvi Jaim Davidsohn", "efshar": "Rab Igal Snertz (Efshar Letaken)", "golan": "הרבנית תאיר גולן",
 "grillak": "הרב יוחנן גרילק", "hilu": "Rab Joshua Hilu", "isaaccredi": "Sr. Isaac Credi", "kavas": "הרב אבנר קוואס",
 "meital": "הרבנית מיטל דאודי", "nacash": "Jajam Ezra Nacach", "ofirmalka": "הרב אופיר מלכא",
 "ravasherweiss": "הרב אשר וייס", "ravmeir": "Rab Meir Eliyahu", "ravmutzafi": "הרב בן ציון מוצפי",
 "ravshmueli": "הרב בניהו שמואלי", "ravyitzchakyosef": "הרב יצחק יוסף", "shaked": "הרב שקד בוהדנה",
 "tawil": "Rab Yosef Tawil", "tefila": "Rab Tofi Cherem", "yakobov": "Rabbi Israel Yakobov",
 "yechavedaat": "הרב דוד יוסף", "taamim": "Jajam Itzjak Batesh", "ahavatjesed": "Jafetz Jaim",
}
# rabanim que aparecen en los shows con varios rabanim (orden: el primero que pega)
RABANIM = [
 ("הרב אלימלך בידרמן", r"אלימלך\s*בידרמ|Elimelech\s*Biderman"),
 ("הרב ירחמיאל יוסף בידרמן", r"ירחמיאל.{0,8}בידרמן"),
 ("הרב זמיר כהן", r"זמיר\s*כהן|Zamir\s*Cohen"),
 ("הרב יגאל כהן", r"יגאל\s*כהן|Yigal\s*Cohen|Igal\s*Cohen"),
 ("הרב רונן שאולוב", r"רונן\s*שאולוב|Ronen\s*Shaulov"),
 ("הרב שניר גואטה", r"שניר\s*גואט|Snir\s*Gu?ata"),
 ("הרב ברוך רוזנבלום", r"רוזנבלום|Rosenblum"),
 ("הרב מאיר טוביה פולק", r"טוביה\s*(פולק|פאלק|פול)|Tuvia\s*Polak"),
 ("הרב יהונתן בן צור", r"(יהונתן|יונתן)\s*[בס]ן\s*צור|Ben\s*Tzur"),
 ("הרב יוסף צבי בן פורת", r"יוסף\s*צ(בי)?['׳\.]?\s*בן|בן\s*פורת|Ben\s*Porat"),
 ("הרב אייל עמרמי", r"(אייל|אייך)\s*(עמרמי|אמרמי)|Eyal\s*Amrami"),
 ("הרב משה שפירא", r"משה\s*שפיר[אה]|Moshe\s*Shapira"),
 ("מרן הרב עובדיה יוסף", r"(עובדיה|עבדיה)\s*יוסף|Ovadia\s*Yosef"),
 ("הרב שלום ארוש", r"שלום\s*ארוש|הרב\s*ארוש|Shalom\s*Arush"),
 ("הרב דוד אפללו", r"אפללו|Abergel\s*Apelo"),
 ("הרב שלמה לוינשטיין", r"לוינשטיין|Levenstein"),
 ("הרב בן ציון מוצפי", r"מוצפי|Mutzafi"),
 ("הרב בניהו שמואלי", r"בניהו\s*שמואלי|Shmueli"),
 ("הרב שקד בוהדנה", r"בוהדנה|Bohadana"),
 ("הרב ישראל אברג'ל", r"אברג['׳]?ל|Abergel"),
 ("הרב רפאל אבוחצירא", r"אבוחצירא|Abuhatzeira"),
 ("האדמו״ר רבי דוד חנניה פינטו", r"פינטו|Pinto"),
 ("הרב נתן רוטמן", r"רוטמן"),
 ("Rabbi Zecharia Wallerstein", r"Wallerstein"),
 ("Rabbi Paysach Krohn", r"Krohn"),
 ("Rabbi Joey Haber", r"Joey\s*Haber"),
 ("Rabbi Meir Simcha Sperling", r"Sperling"),
 ("Rabbi Don Jarashow", r"Jarashow"),
 ("Rabbi Duvi Bensoussan", r"Duvi\s*Bens"),
 ("Rabbi Yossi Mizrachi", r"(Yossi|Yosef)\s*Mizrachi"),
 ("Rabbi David Ashear", r"Ashear"),
 ("Rabbi YY Jacobson", r"YY\s*Jacobson"),
 ("Rabbi Yitzchak Oelbaum", r"Oelbaum"),
 ("Rabbi Ephraim Shapiro", r"Ephraim\s*(Eliyahu\s*)?Shapiro"),
 ("Rabbi Yaakov Rahimi", r"Rahimi"),
 ("Rabbi Israel Yakobov", r"Yakobov"),
 ("Rab Akiva Perets", r"Akiva\s*Peret"),
 ("Rab David Perets", r"David\s*Perets"),
 ("Rab Yosef Perets", r"Yosef\s*Perets"),
 ("Rab Meir Eliyahu", r"Meir\s*Eliyahu|מאיר\s*אליהו"),
]
VARIOS = {"musar": "Varios rabanim (Musar y Jasidut)", "chazaq": "Varios rabanim (CHAZAQ)",
          "torahanytime": "Varios rabanim (TorahAnytime)", "musayof": "Beit HaKnéset Musayof",
          "krohn": "Varios rabanim (CHAZAQ)", "peretz": "Familia Perets (varios)"}


def rab_de(x):
    if x["show"] in SHOW_RAB:
        return SHOW_RAB[x["show"]]
    t = x["t"]
    for nombre, rx in RABANIM:
        if re.search(rx, t, re.I):
            return nombre
    return VARIOS.get(x["show"], x["canal"])
