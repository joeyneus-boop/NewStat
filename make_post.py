"""Makes today's Instagram/X picture + caption from the freshest data.
Writes posts/latest.png, posts/latest.json and posts/YYYY-MM-DD.png. Theme rotates daily."""
import html, json, os, sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
stats = json.load(open("stats.json"))
players = stats["players"]
upd = (stats.get("updated") or "")[:10]
maxgp = max(p["GP"] for p in players)
qual = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and p["MIN"] >= 15]

CSS = '''@import url(https://fonts.googleapis.com/css2?family=Inter:wght@600;800;900&display=swap);*{box-sizing:border-box;margin:0}body{width:1080px;height:1350px;background:linear-gradient(#0b1220,#142241);font-family:Inter,"Helvetica Neue",Arial,sans-serif;color:#e9eef7;position:relative;overflow:hidden}
.bar{height:10px;background:#ff7a2f}.brand{position:absolute;left:60px;top:44px;color:#ff7a2f;font-weight:800;font-size:30px}
h1{position:absolute;left:60px;top:84px;font-size:64px;line-height:1.02;font-weight:900;width:960px}
.sub{position:absolute;left:60px;top:236px;color:#8995ad;font-size:27px;font-weight:600;width:960px;white-space:nowrap}
.list{position:absolute;left:60px;right:60px;top:296px}
.row{display:flex;align-items:center;height:84px;margin-bottom:8px;border-radius:20px;background:rgba(255,255,255,.06);padding:0 24px}
.row:nth-child(1){background:rgba(255,122,47,.16);border:2px solid #ff7a2f}
.rk{width:48px;height:48px;border-radius:50%;background:#26365a;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:24px;margin-right:20px;flex:none}
.row:nth-child(-n+3) .rk{background:#ff7a2f;color:#1a0d03}
.nm{flex:1;min-width:0}.nm b{display:block;font-size:34px;font-weight:800;white-space:nowrap}.nm span{color:#8995ad;font-size:22px;font-weight:600;white-space:nowrap}
.v{font-size:42px;font-weight:900;color:#34d399;text-align:right;flex:none;margin-left:14px}.v small{display:block;font-size:18px;color:#8995ad;font-weight:600;margin-top:-2px}
.ft{position:absolute;left:60px;right:60px;bottom:36px;display:flex;justify-content:space-between;align-items:flex-end;color:#8995ad;font-size:21px;font-weight:600}.ft b{color:#ff7a2f;font-size:28px;font-weight:800}
.lu b{font-size:27px!important;white-space:normal!important;line-height:1.15}.lu{height:98px!important}'''


def page(title, sub, rows, foot, lineup=False):
    cls = "row lu" if lineup else "row"
    body = "".join(
        f'<div class="{cls}"><div class=rk>{i+1}</div><div class=nm><b>{html.escape(r[0])}</b><span>{html.escape(r[1])}</span></div>'
        f'<div class=v>{r[2]}<small>{html.escape(r[3])}</small></div></div>' for i, r in enumerate(rows))
    return (f'<!doctype html><meta charset=utf-8><style>{CSS}</style><div class=bar></div><div class=brand>NEW-STAT</div>'
            f'<h1>{title}</h1><div class=sub>{sub}</div><div class=list>{body}</div>'
            f'<div class=ft><span>{foot}</span><b>newstat.app</b></div>')


def top(key, n=10, rev=True, pool=None, extra=None, fmt="{:.1f}"):
    pool = pool if pool is not None else qual
    pool = [p for p in pool if isinstance(p.get(key), (int, float))]
    pool.sort(key=lambda p: p[key], reverse=rev)
    out = []
    for p in pool[:n]:
        out.append((p["PLAYER"], f'{p["TEAM"]} · {extra(p)}' if extra else p["TEAM"], fmt.format(p[key]), ""))
    return out


FOOT = f"Stats: ESPN · 2026-27, through {upd}"


def th_stat(title, key, unit, sub, pool_fn=None, fmt="{:.1f}", extra=None, rev=True):
    def f():
        pool = pool_fn() if pool_fn else None
        rows = top(key, 10, rev, pool, extra, fmt)
        rows = [(a, b, c, unit) for a, b, c, _ in rows]
        return title, sub, rows, FOOT, False, key
    return f


gp = lambda p: f'{p["GP"]:.0f} games · {p["MIN"]:.1f} MPG'
THEMES = [
    th_stat("NBA scoring<br>leaders", "PTS", "points / game", "Points per game · min 60% of games played", extra=gp),
    th_stat("NBA assist<br>leaders", "AST", "assists / game", "Assists per game · min 60% of games played", extra=gp),
    th_stat("NBA rebounding<br>leaders", "REB", "rebounds / game", "Rebounds per game · min 60% of games played", extra=gp),
    th_stat("Most efficient<br>scorers in the NBA", "TS_PCT", "true shooting %", "True shooting % · min 15 points per game",
            pool_fn=lambda: [p for p in qual if p["PTS"] >= 15], extra=lambda p: f'{p["PTS"]:.1f} points per game'),
]


def th_lineups():
    L = json.load(open("data/lineups/2027.json"))
    best = []
    for T in L["teams"].values():
        for k, v in T["lineups"].items():
            sec, pf, pa, pp, qa = v
            avg = (pp + qa) / 2
            if sec / 60 < 60 or avg <= 0:
                continue
            best.append(((pf - pa) / avg * 100, sec / 60, T["abbr"], [T["players"][int(i)][1].split(" ", 1)[-1] for i in k.split(".")]))
    best.sort(key=lambda x: -x[0])
    rows = [(", ".join(x[3]), f"{x[2]} · {x[1]:.0f} minutes together", f"{x[0]:+.1f}", "net rating") for x in best[:8]]
    return ("Best five-man<br>lineups in the NBA", "Net rating (per 100 possessions) · min 60 minutes together", rows,
            "Stats: ESPN play-by-play · estimated possessions<br>Early-season samples are small", True, "lineups")


def th_cup():
    d = json.load(open("data/cup/2027.json"))
    pool = [p for p in d["players"] if p["GP"] >= 2 and p["MIN"] >= 15]
    rows = [(p["PLAYER"], f'{p["TEAM"]} · {p["GP"]:.0f} Cup games · {p["REB"]:.1f} reb · {p["AST"]:.1f} ast', f'{p["PTS"]:.1f}', "points / game")
            for p in sorted(pool, key=lambda p: -p["PTS"])[:10]]
    return ("NBA Cup scoring<br>leaders", "Points per game in NBA Cup games only · min 2 games", rows,
            f'Stats: ESPN · NBA Cup games, through {upd}', False, "cup")


THEMES += [
    th_stat("NBA steals<br>leaders", "STL", "steals / game", "Steals per game · min 60% of games played", extra=gp),
    th_lineups,
    th_stat("Best three-point<br>shooters", "FG3_PCT", "3-point %", "3-point % · min 5 attempts per game",
            pool_fn=lambda: [p for p in qual if p["FG3A"] >= 5], extra=lambda p: f'{p["FG3M"]:.1f} of {p["FG3A"]:.1f} per game'),
    th_stat("NBA block<br>leaders", "BLK", "blocks / game", "Blocks per game · min 60% of games played", extra=gp),
    th_cup,
    th_stat("Highest usage<br>players in the NBA", "USG_PCT", "usage %", "Share of team plays used while on the floor · min 25 MPG",
            pool_fn=lambda: [p for p in qual if p["MIN"] >= 25], extra=lambda p: f'{p["PTS"]:.1f} points per game'),
]


def caption(title, rows, key, sub):
    t = title.replace("<br>", " ")
    top3 = "\n".join(f"{i+1}. {r[0]} ({r[1].split(' · ')[0]}) {r[2]}" for i, r in enumerate(rows[:5]))
    long = (f"{t} 🏀\n\n{top3}\n\n{sub}. Stats through {upd}. Every stat, every season, at newstat.app (link in bio).")
    short = f"{t} 🏀\n\n" + "\n".join(f"{i+1}. {r[0].split(' ', 1)[-1]} {r[2]}" for i, r in enumerate(rows[:3])) + "\n\nMore at newstat.app"
    return long, short


def main():
    day = datetime.now(timezone.utc).date()
    forced = sys.argv[1] if len(sys.argv) > 1 else None
    n = len(THEMES)
    order = [(day.toordinal() + i) % n for i in range(n)]
    if forced is not None:
        order = [int(forced)]
    res = None
    for idx in order:
        try:
            res = THEMES[idx]()
            if res[2] and len(res[2]) >= 3:
                break
        except Exception as e:
            print("theme", idx, "failed:", e)
    if not res:
        sys.exit("no theme worked")
    title, sub, rows, foot, lineup, key = res
    os.makedirs("posts", exist_ok=True)
    open("posts/_p.html", "w").write(page(title, sub, rows, foot, lineup))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto("file://" + os.path.abspath("posts/_p.html"))
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        pg.wait_for_timeout(600)
        pg.screenshot(path="posts/latest.png")
        b.close()
    os.remove("posts/_p.html")
    ds = day.isoformat()
    import shutil
    shutil.copy("posts/latest.png", f"posts/{ds}.png")
    long, short = caption(title, rows, key, sub)
    meta = {"date": ds, "title": title.replace("<br>", " "), "long": long, "short": short}
    hist = []
    try:
        hist = json.load(open("posts/index.json"))
    except Exception:
        pass
    hist = [h for h in hist if h["date"] != ds]
    hist.insert(0, meta)
    hist = hist[:14]
    json.dump(hist, open("posts/index.json", "w"), indent=1, ensure_ascii=False)
    keep = {h["date"] for h in hist}
    for f in os.listdir("posts"):
        if f.endswith(".png") and f != "latest.png" and f[:-4] not in keep:
            os.remove("posts/" + f)
    print("made", meta["title"])


main()
