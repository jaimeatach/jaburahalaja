import re, html, json, urllib.request, concurrent.futures as cf
from email.utils import parsedate_to_datetime as p
SHOWS = "abergel abuhatzeira ahavatjesed bensoussan chazaq davidpinto golan kavas krohn meital musar musayof podcast ravasherweiss ravmeir ravmutzafi ravshmueli shaked torahanytime yakobov yechavedaat credi hilu isaaccredi nacash ofirmalka peretz taamim tawil tefila efshar mishnaberura yalkutyosef grillak davidsohn biderman ravyitzchakyosef".split()
def una(show):
    x = urllib.request.urlopen(urllib.request.Request(f"https://rabmeireliyahu.github.io/{show}/feed.xml", headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read().decode("utf-8", "replace")
    canal = html.unescape((re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", x.split("<item>")[0], re.S) or [None, show])[1]).strip()
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
        e = re.search(r'<enclosure url="([^"]+)"(?: length="(\d+)")?', it)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it)
        try: f = p(d.group(1)).strftime("%Y-%m-%d") if d else ""
        except Exception: f = ""
        if t and e:
            out.append({"show": show, "canal": canal, "t": html.unescape(t.group(1)).strip(), "u": e.group(1).replace("https://op3.dev/e/", ""), "b": int(e.group(2) or 0), "f": f})
    return out
todo = []
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(una, SHOWS): todo += r
json.dump(todo, open("todos_shiurim.json", "w"), ensure_ascii=False)
import collections
por = collections.defaultdict(lambda: [0, 0])
for x in todo: por[x["show"]][0] += 1; por[x["show"]][1] += x["b"]
for s, (n, b) in sorted(por.items(), key=lambda kv: -kv[1][1]): print(f"{s:17} {n:5}  {b/1e9:6.1f} GB")
print("TOTAL", len(todo), round(sum(x["b"] for x in todo)/1e9, 1), "GB")
