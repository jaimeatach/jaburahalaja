"""Calendario de jazarot de la jabura (Mishná Berurá, por amudim), nov/2026 – abr/2027 (examen Lakewood 4/4).
Domingo a jueves. Amudim por siman: 317=4, 319=9, 320=9, 321=9, 340=10 (los de 319-321 son estimados
por el largo del texto en Sefaria; cambiar AMUDIM y volver a correr)."""
import datetime as dt

AMUDIM = {"שי״ז": 4, "שי״ט": 9, "ש״כ": 9, "שכ״א": 9, "ש״מ": 10}
NOMBRE = {"שי״ז": "Kosher", "שי״ט": "Borer", "ש״כ": "Sojet", "שכ״א": "Lash y otras melajot", "ש״מ": "Kotev, mojek y otras melajot"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
SIN_ESTUDIO = {dt.date(2027, 3, 23)}            # Purim


def dias(desde, hasta):
    d, L = desde, []
    while d <= hasta:
        if d.weekday() in (6, 0, 1, 2, 3) and d not in SIN_ESTUDIO:
            L.append(d)
        d += dt.timedelta(1)
    return L


def f(d):
    return f"{DIAS[d.weekday()]} {d.day}/{d.month}"


def amudim(simanim):
    return [(s, a) for s in simanim for a in range(1, AMUDIM[s] + 1)]


def tramo(a):
    (s0, a0), (s1, a1) = a[0], a[-1]
    if s0 == s1:
        return f"{s0} · amud {a0}" + (f"–{a1}" if a1 != a0 else "")
    return f"{s0} amud {a0} → {s1} amud {a1}"


def repartir(lista, n):
    """lista de amudim en n días, lo más parejo posible"""
    out, i = [], 0
    for k in range(n):
        j = round(len(lista) * (k + 1) / n)
        out.append(lista[i:j]); i = j
    return out


L = []
p = lambda *x: L.append(" ".join(x))
p("📚 *Jazarot de la Jabura · Mishná Berurá*")
p("Domingo a jueves · por amudim")
p("")
# 1. ש״מ hasta Janucá
p("*1) Siman ש״מ (10 amudim) · hasta Janucá*")
d1 = dias(dt.date(2026, 11, 17), dt.date(2026, 12, 3))
for d, (s, a) in zip(d1, amudim(["ש״מ"])):
    p(f"{f(d)} · {s} amud {a}")
p("🔁 Vuelta rápida:")
for d, t in zip(d1[10:], repartir(amudim(["ש״מ"]), 3)):
    p(f"{f(d)} · {tramo(t)}")
p("📝 Vie 4/12 · *Examen escrito de ש״מ* (se manda al grupo)")
p("🕎 Vie 4/12 en la noche · primera vela de Janucá")
p("")
# 2. Janucá y vacaciones: שי״ז dos vueltas, cada quien
p("*2) Janucá y vacaciones · Siman שי״ז (4 amudim) · cada quien en su casa*")
d2 = dias(dt.date(2026, 12, 6), dt.date(2027, 1, 3))
v = amudim(["שי״ז"])
for d, (s, a) in zip(d2, v + v):
    p(f"{f(d)} · {s} amud {a}" + ("  (1ª vuelta)" if d == d2[0] else "  (2ª vuelta)" if d == d2[4] else ""))
resto = d2[8:]
p(f"Del {f(resto[0])} al Dom 3/1 · vacaciones: repaso libre de שי״ז y ש״מ")
p("")
# 3. Regreso: 7/1
d3 = dias(dt.date(2027, 1, 4), dt.date(2027, 4, 1))
p("*3) Regreso · lunes 4 de enero*")
p(f"📝 {f(d3[0])} · *Examen de שי״ז* y empezamos שי״ט")
primera = amudim(["שי״ט", "ש״כ", "שכ״א"])
for d, (s, a) in zip(d3, primera):
    p(f"{f(d)} · {s} amud {a}")
k = len(primera)
todo = amudim(["שי״ז", "שי״ט", "ש״כ", "שכ״א", "ש״מ"])
n1 = (len(todo) + 1) // 2                 # vuelta 1 a 2 amudim por día
p("")
p(f"*4) Vuelta 1 de los 5 simanim ({len(todo)} amudim) · 2 amudim al día*")
for d, t in zip(d3[k:k + n1], repartir(todo, n1)):
    p(f"{f(d)} · {tramo(t)}")
d5 = d3[k + n1:]
p("")
p(f"*5) Vuelta 2 · repaso final ({len(todo)} amudim en {len(d5)} días)*")
for d, t in zip(d5, repartir(todo, len(d5))):
    p(f"{f(d)} · {tramo(t)}")
p("🎭 Mar 23/3 · Purim, sin estudio")
p("📝 Dom 4/4 · *Examen Lakewood*")
print("\n".join(L))
