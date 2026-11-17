"""PDF del calendario de jazarot (a partir de calendario_jazarot.txt), con Chromium.
python calendario_pdf.py calendario_jazarot.txt salida.pdf"""
import html, re, sys, subprocess, json
src, out = sys.argv[1], sys.argv[2]
lineas = [l.rstrip() for l in open(src, encoding="utf-8")]
secs, cur = [], None
for l in lineas[3:]:
    if not l.strip():
        continue
    m = re.match(r"\*(\d)\)\s*(.+)\*$", l)
    if m:
        cur = {"n": m.group(1), "titulo": m.group(2), "filas": []}; secs.append(cur); continue
    m = re.match(r"(Dom|Lun|Mar|Mié|Jue|Vie) (\d+/\d+) · (.+)$", l)
    if m and not l.startswith(("📝", "🕎", "🎭")):
        cur["filas"].append(("dia", m.group(1), m.group(2), m.group(3))); continue
    cur["filas"].append(("nota", l))
E = html.escape
HEB = r"[\u05D0-\u05EA][\u05D0-\u05EA״׳]*"
def celda(t):
    t = E(t.replace("*", "")).replace(" · ", " ")
    t = re.sub(r"amud ([\d–]+)", r"<b>amud \1</b>", t)
    t = re.sub("(" + HEB + ")", r'<bdi class="sim">\1</bdi>', t)
    return t
def fila(f):
    if f[0] == "nota":
        t = f[1].replace("*", "")
        cls = "examen" if "Examen" in t else "nota"
        return f'<tr class="{cls}"><td colspan="2" dir="ltr">{celda(t)}</td></tr>'
    _, d, fe, t = f
    return f'<tr class="{"lun" if d=="Dom" else ""}"><td class="f"><span>{d}</span> {fe}</td><td dir="ltr">{celda(t)}</td></tr>'
cuerpo = ""
for s in secs:
    cuerpo += f'<section><h2><span class="num">{s["n"]}</span>{E(s["titulo"])}</h2><table>{"".join(fila(f) for f in s["filas"])}</table></section>'
doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@500;700;900&family=Assistant:wght@400;600;700&display=swap" rel="stylesheet">
<style>
@page {{ size: A4; margin: 14mm 13mm 14mm 13mm; }}
:root {{ --tinta:#1d2a44; --oro:#b08a2e; --suave:#f4efe2; --linea:#e3dccb; --rojo:#8a2a2a; }}
body {{ font-family:'Assistant',sans-serif; color:var(--tinta); font-size:10.5pt; margin:0; }}
header {{ text-align:center; border-bottom:2px solid var(--oro); padding-bottom:8px; margin-bottom:10px; }}
header .heb {{ font-family:'Frank Ruhl Libre',serif; font-size:13pt; color:var(--oro); letter-spacing:.04em; }}
h1 {{ font-family:'Frank Ruhl Libre',serif; font-size:24pt; margin:2px 0; }}
header p {{ margin:2px 0; color:#5b6378; font-size:10pt; }}
.columnas {{ column-count:2; column-gap:9mm; }}
section {{ break-inside:auto; margin-bottom:9px; }}
h2 {{ font-family:'Frank Ruhl Libre',serif; font-size:12pt; margin:6px 0 4px; display:flex; gap:6px; align-items:center; break-after:avoid; }}
.num {{ background:var(--tinta); color:#fff; border-radius:50%; width:18px; height:18px; font-size:9.5pt; display:inline-flex; align-items:center; justify-content:center; flex:none; }}
table {{ width:100%; border-collapse:collapse; }}
td {{ padding:2.3px 4px; border-bottom:1px solid var(--linea); vertical-align:top; }}
td.f {{ white-space:nowrap; width:58px; color:#5b6378; font-variant-numeric:tabular-nums; }}
td.f span {{ display:inline-block; width:30px; font-weight:600; color:var(--tinta); }}
tr.lun td {{ border-top:1.5px solid #c9bfa6; }}
tr.nota td {{ background:var(--suave); font-size:9.5pt; }}
tr.examen td {{ background:#fbe9d9; color:var(--rojo); font-weight:700; }}
b {{ color:var(--tinta); }} .sim {{ font-family:'Frank Ruhl Libre',serif; font-weight:700; color:var(--oro); font-size:11pt; }}
footer {{ margin-top:8px; text-align:center; font-size:9pt; color:#5b6378; border-top:1px solid var(--linea); padding-top:5px; }}
</style></head><body>
<header><div class="heb">חבורת הלכה · חזרות</div><h1>Calendario de Jazarot</h1>
<p>Mishná Berurá · simanim שי״ז · שי״ט · ש״כ · שכ״א · ש״מ</p>
<p>Se estudia de domingo a jueves · cada día dice qué amudim repasar</p></header>
<div class="columnas">{cuerpo}</div>
<footer>📝 Examen escrito de ש״מ: viernes 4 de diciembre · Examen de שי״ז: lunes 4 de enero · Examen Lakewood: domingo 4 de abril</footer>
</body></html>"""
open(out.replace(".pdf", ".html"), "w", encoding="utf-8").write(doc)
js = """const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage();
await p.goto('file://'+process.argv[1],{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);
await p.pdf({path:process.argv[2],format:'A4',printBackground:true,preferCSSPageSize:true});
await p.setViewportSize({width:900,height:1270});await p.screenshot({path:process.argv[2].replace('.pdf','.png'),fullPage:false});await b.close()})()"""
subprocess.run(["node", "-e", js, out.replace(".pdf", ".html"), out], check=True)
print(out)
