"""Makes today's Instagram/X picture + caption from the freshest data.
Writes posts/latest.png, posts/latest.json and posts/YYYY-MM-DD.png. Theme rotates daily."""
import html, json, os, sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
stats = json.load(open("stats.json"))
players = stats["players"]
upd = (stats.get("updated") or "")[:10]
_age = datetime.now(timezone.utc) - datetime.fromisoformat((stats.get("updated") or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))
if _age > timedelta(hours=30) and not os.environ.get("ALLOW_STALE"):
    sys.exit(f"stats.json is {_age} old, not making a post from stale numbers")
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


# ---------------- chart posts ----------------
def nice_ticks(lo, hi, n=5):
    import math
    span = hi - lo or 1
    step = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 2.5, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    t = math.ceil(lo / step) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 6))
        t += step
    return out


def scatter_svg(pts, xt, yt, W=960, H=790, inv_y=False, hl=None, xref=None, yref=None, quad=None, pad=0.06, xfmt="{:g}", yfmt="{:g}"):
    """pts: list of dict(x,y,label,hi). Draws dots, labels for pts with label, reference lines."""
    L, R, T, B = 98, 18, 14, 66
    xs = [p["x"] for p in pts]; ys = [p["y"] for p in pts]
    xl, xh = min(xs), max(xs); yl, yh = min(ys), max(ys)
    xp = (xh - xl) * pad or 1; yp = (yh - yl) * pad or 1
    xl -= xp; xh += xp; yl -= yp; yh += yp
    sx = lambda v: L + (v - xl) / (xh - xl) * (W - L - R)
    sy = (lambda v: T + (v - yl) / (yh - yl) * (H - T - B)) if inv_y else (lambda v: H - B - (v - yl) / (yh - yl) * (H - T - B))
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter,Helvetica,Arial,sans-serif">']
    for v in nice_ticks(xl, xh):
        o.append(f'<line x1="{sx(v):.1f}" y1="{T}" x2="{sx(v):.1f}" y2="{H-B}" stroke="#ffffff" stroke-opacity=".07"/><text x="{sx(v):.1f}" y="{H-B+30}" fill="#8995ad" font-size="22" font-weight="600" text-anchor="middle">{xfmt.format(v)}</text>')
    for v in nice_ticks(yl, yh):
        o.append(f'<line x1="{L}" y1="{sy(v):.1f}" x2="{W-R}" y2="{sy(v):.1f}" stroke="#ffffff" stroke-opacity=".07"/><text x="{L-10}" y="{sy(v)+8:.1f}" fill="#8995ad" font-size="22" font-weight="600" text-anchor="end">{yfmt.format(v)}</text>')
    if xref is not None:
        o.append(f'<line x1="{sx(xref):.1f}" y1="{T}" x2="{sx(xref):.1f}" y2="{H-B}" stroke="#ff7a2f" stroke-opacity=".55" stroke-dasharray="7 7" stroke-width="2"/>')
    if yref is not None:
        o.append(f'<line x1="{L}" y1="{sy(yref):.1f}" x2="{W-R}" y2="{sy(yref):.1f}" stroke="#ff7a2f" stroke-opacity=".55" stroke-dasharray="7 7" stroke-width="2"/>')
    if hl:
        (x1, y1), (x2, y2) = hl
        o.append(f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" stroke="#8995ad" stroke-opacity=".7" stroke-width="2.5"/>')
    o.append(f'<text x="{(L+W-R)/2:.0f}" y="{H-8}" fill="#e9eef7" font-size="24" font-weight="700" text-anchor="middle">{html.escape(xt)}</text>')
    o.append(f'<text transform="translate(22 {(T+H-B)/2:.0f}) rotate(-90)" fill="#e9eef7" font-size="24" font-weight="700" text-anchor="middle">{html.escape(yt)}</text>')
    if quad:
        for (qx, qy, anchor, txt) in quad:
            o.append(f'<text x="{qx}" y="{qy}" fill="#ff7a2f" fill-opacity=".85" font-size="21" font-weight="800" text-anchor="{anchor}">{html.escape(txt)}</text>')
    # dots first
    for p in pts:
        if not p.get("label"):
            o.append(f'<circle cx="{sx(p["x"]):.1f}" cy="{sy(p["y"]):.1f}" r="6" fill="#5b7fc7" fill-opacity=".75"/>')
    boxes = [(sx(q["x"]) - 9, sy(q["y"]) - 9, sx(q["x"]) + 9, sy(q["y"]) + 9) for q in pts]
    def area(b):
        a = 0
        for c in boxes:
            ox = min(b[2], c[2]) - max(b[0], c[0]); oy = min(b[3], c[3]) - max(b[1], c[1])
            if ox > 0 and oy > 0:
                a += ox * oy
        if b[0] < L: a += (L - b[0]) * 400
        if b[2] > W - R: a += (b[2] - (W - R)) * 400
        if b[1] < T: a += (T - b[1]) * 400
        if b[3] > H - B: a += (b[3] - (H - B)) * 400
        return a
    placed = []
    for p in sorted([q for q in pts if q.get("label")], key=lambda q: -q.get("w", 0)):
        cx, cy = sx(p["x"]), sy(p["y"])
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="{p.get("c", "#ff7a2f")}" stroke="#0b1220" stroke-width="2.5"/>')
        fs = 22
        w = len(p["label"]) * fs * 0.6
        best = None
        cands = [(14, -10, "start"), (-14, -10, "end"), (14, 26, "start"), (-14, 26, "end"), (0, -20, "middle"), (0, 40, "middle"),
                 (14, 8, "start"), (-14, 8, "end"), (28, -26, "start"), (-28, -26, "end"), (28, 42, "start"), (-28, 42, "end"), (0, -44, "middle"), (0, 64, "middle")]
        for dx, dy, anc in cands:
            x0 = cx + dx - (0 if anc == "start" else w if anc == "end" else w / 2)
            b = (x0, cy + dy - fs, x0 + w, cy + dy + 6)
            a = area(b)
            if best is None or a < best[0]:
                best = (a, dx, dy, anc, b)
            if a == 0:
                break
        _, dx, dy, anc, b = best
        boxes.append(b)
        placed.append((cx, cy, dx, dy, anc, p["label"]))
    for cx, cy, dx, dy, anc, lab in placed:
        o.append(f'<text x="{cx+dx:.1f}" y="{cy+dy:.1f}" fill="#fff" font-size="22" font-weight="800" text-anchor="{anc}" stroke="#0b1220" stroke-width="5" paint-order="stroke">{html.escape(lab)}</text>')
    o.append("</svg>")
    return "".join(o)


def chart_page(title, sub, svg, take, foot):
    css = CSS + '.chart{position:absolute;left:60px;top:290px}.take{position:absolute;left:60px;right:60px;top:1112px;height:150px;border-radius:20px;background:rgba(255,122,47,.14);border:2px solid #ff7a2f;padding:18px 24px;font-size:28px;font-weight:700;line-height:1.28;display:flex;align-items:center}.take i{color:#ff7a2f;font-style:normal;font-weight:900;margin-right:10px}'
    return (f'<!doctype html><meta charset=utf-8><style>{css}</style><div class=bar></div><div class=brand>NEW-STAT</div>'
            f'<h1>{title}</h1><div class=sub>{sub}</div><div class=chart>{svg}</div><div class=take><div><i>TAKEAWAY</i>{html.escape(take)}</div></div>'
            f'<div class=ft><span>{foot}</span><b>newstat.app</b></div>')


from collections import Counter
_LN = Counter(p["PLAYER"].split(" ", 1)[-1] for p in players)


def last(p):
    ln = p["PLAYER"].split(" ", 1)[-1]
    return f'{p["PLAYER"][0]}. {ln}' if _LN[ln] > 1 else ln


def join_names(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def ch_teams():
    T = json.load(open("data/teams/2027.json"))["teams"]
    pts = [dict(x=t["ORTG"], y=t["DRTG"], label=t["TEAM"], w=abs(t["NRTG"]), c="#34d399" if t["NRTG"] > 0 else "#f87171") for t in T]
    ao = sum(t["ORTG"] for t in T) / len(T); ad = sum(t["DRTG"] for t in T) / len(T)
    by_o = sorted(T, key=lambda t: -t["ORTG"]); by_d = sorted(T, key=lambda t: t["DRTG"])
    ro = {t["TEAM"]: i + 1 for i, t in enumerate(by_o)}; rd = {t["TEAM"]: i + 1 for i, t in enumerate(by_d)}
    gap = max(T, key=lambda t: abs(ro[t["TEAM"]] - rd[t["TEAM"]]))
    best = max(T, key=lambda t: t["NRTG"]); worst = min(T, key=lambda t: t["NRTG"])
    take = (f'{best["TEAM"]} is the only team in elite territory on both ends ({best["NRTG"]:+.1f} net)' if ro[best["TEAM"]] <= 5 and rd[best["TEAM"]] <= 5 else
            f'{best["TEAM"]} leads the league at {best["NRTG"]:+.1f} net rating') + f'. Biggest split: {gap["TEAM"]} is #{ro[gap["TEAM"]]} on offense but #{rd[gap["TEAM"]]} on defense. {worst["TEAM"]} is last at {worst["NRTG"]:+.1f}.'
    svg = scatter_svg(pts, "Offense: points scored per 100 possessions (better →)", "Defense: points allowed per 100 (better ↑)", inv_y=True, xref=ao, yref=ad,
                      quad=[(930, 30, "end", "ELITE BOTH WAYS"), (95, 780 - 90, "start", "STRUGGLING")])
    return ("Every NBA team:<br>offense vs defense", "Green = positive net rating · dashed lines = league average", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "team ratings")


def ch_usage():
    pool = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and p["MIN"] >= 24 and isinstance(p.get("USG_PCT"), (int, float)) and isinstance(p.get("TS_PCT"), (int, float))]
    avg = sum(p["TS_PCT"] for p in pool) / len(pool)
    star = sorted(pool, key=lambda p: -p["PTS"])[:14]
    elite = [p for p in pool if p["USG_PCT"] >= 28 and p["TS_PCT"] >= avg + 4]
    pts = [dict(x=p["USG_PCT"], y=p["TS_PCT"], label=last(p) if p in star or p in elite else None, w=p["PTS"]) for p in pool]
    take = (f'{"Only " + str(len(elite)) + " players" if len(elite) > 1 else "Only 1 player"} use 28%+ of their team\'s plays and still shoot 4+ points above the group\'s average TS% ({avg:.0f}%): {join_names([last(p) for p in sorted(elite, key=lambda p: -p["TS_PCT"])[:5]])}.'
            if elite else 'High usage usually costs efficiency: the more plays a player uses, the harder the shots get.')
    svg = scatter_svg(pts, "Usage: share of team plays used while on the floor (%)", "True shooting % (efficiency)", xref=sum(p["USG_PCT"] for p in pool) / len(pool), yref=avg,
                      quad=[(930, 30, "end", "HIGH LOAD, HIGH EFFICIENCY"), (95, 780 - 90, "start", "LOW LOAD, LOW EFFICIENCY")], xfmt="{:g}%", yfmt="{:g}%")
    return ("Who carries the load<br>efficiently?", f"Players with 24+ MPG · dashed lines = average of this group", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "usage vs TS")


def ch_playmakers():
    pool = [p for p in qual if p["AST"] >= 4 and p["TOV"] > 0]
    top = sorted(pool, key=lambda p: -p["AST"])[:12]
    ratio = sorted([p for p in pool if p["AST"] >= 6], key=lambda p: -p["AST"] / p["TOV"])
    bad = max(pool, key=lambda p: p["TOV"])
    pts = [dict(x=p["AST"], y=p["TOV"], label=last(p) if (p in top or p in ratio[:3] or p is bad) else None, w=p["AST"]) for p in pool]
    take = (f'{ratio[0]["PLAYER"]} has the best assist-to-turnover ratio among 6+ assist players ({ratio[0]["AST"]/ratio[0]["TOV"]:.1f} to 1). '
            f'{bad["PLAYER"]} coughs it up the most ({bad["TOV"]:.1f}/game) but produces {bad["AST"]:.1f} assists.') if ratio else "Playmaking comes with giveaways."
    svg = scatter_svg(pts, "Assists per game", "Turnovers per game (lower is better)", inv_y=True, quad=[(930, 30, "end", "SAFE PLAYMAKERS"), (95, 780 - 90, "start", "RISKY")], pad=0.08)
    return ("Playmakers: assists<br>vs turnovers", "Players averaging 4+ assists · higher = fewer turnovers", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "ast vs tov")


def ch_bench():
    pool = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and 12 <= p["MIN"] <= 40 and isinstance(p.get("PER"), (int, float))]
    gems = sorted([p for p in pool if p["MIN"] < 26 and p["PER"] >= 18], key=lambda p: -p["PER"])[:6]
    stars = sorted(pool, key=lambda p: -p["PER"])[:6]
    pts = [dict(x=p["MIN"], y=p["PER"], label=last(p) if (p in gems or p in stars) else None, c="#34d399" if p in gems else "#ff7a2f", w=p["PER"]) for p in pool]
    take = (f'Producing in limited minutes: {join_names([f"{last(p)} ({p["PER"]:.0f} PER in {p["MIN"]:.0f} MPG)" for p in gems[:4]])}. The league average PER is 15.' if gems else 'No low-minute players are producing at a star level right now.')
    svg = scatter_svg(pts, "Minutes per game", "PER (player efficiency rating, 15 = average)", yref=15, quad=[(115, 30, "start", "UNDERUSED?")])
    return ("Who deserves<br>more minutes?", "Green = producing in under 26 minutes", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "minutes vs per")


def ch_age():
    pool = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and p["MIN"] >= 18 and isinstance(p.get("AGE"), (int, float))]
    young = sorted([p for p in pool if p["AGE"] <= 23], key=lambda p: -p["PTS"])[:6]
    old = sorted([p for p in pool if p["AGE"] >= 33], key=lambda p: -p["PTS"])[:3]
    pts = [dict(x=p["AGE"], y=p["PTS"], label=last(p) if (p in young or p in old) else None, c="#34d399" if p["AGE"] <= 23 else "#ff7a2f", w=p["PTS"]) for p in pool]
    take = (f'Best scorers 23 and under: {join_names([f"{last(p)} ({p["PTS"]:.1f})" for p in young[:4]])}. ' + (f'Best scorer 33 or older: {last(old[0])} ({old[0]["AGE"]:.0f}) at {old[0]["PTS"]:.1f}.' if old else ""))
    svg = scatter_svg(pts, "Age", "Points per game", quad=[], xfmt="{:g}")
    return ("Scoring by age:<br>youth vs experience", "Players with 18+ MPG · green = age 23 or younger", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "age vs pts")


def ch_luck():
    T = json.load(open("data/teams/2027.json"))["teams"]
    xs = [t["NRTG"] for t in T]; ys = [t["W"] / max(1, t["W"] + t["L"]) * 100 for t in T]
    n = len(T); mx = sum(xs) / n; my = sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); a = my - b * mx
    res = {t["TEAM"]: (t["W"] / max(1, t["W"] + t["L"]) * 100 - (a + b * t["NRTG"])) * (t["W"] + t["L"]) / 100 for t in T}
    lucky = sorted(T, key=lambda t: -res[t["TEAM"]])[:3]; unl = sorted(T, key=lambda t: res[t["TEAM"]])[:3]
    show = {t["TEAM"] for t in lucky + unl}
    pts = [dict(x=t["NRTG"], y=t["W"] / max(1, t["W"] + t["L"]) * 100, label=t["TEAM"] if t["TEAM"] in show or abs(t["NRTG"]) > 8 else None,
                c="#34d399" if t["TEAM"] in {l["TEAM"] for l in lucky} else "#f87171" if t["TEAM"] in {l["TEAM"] for l in unl} else "#ff7a2f", w=abs(res[t["TEAM"]])) for t in T]
    x1, x2 = min(xs), max(xs)
    take = (f'Winning more than their scoring margin says: {join_names([f"{t["TEAM"]} (+{res[t["TEAM"]]:.1f} wins)" for t in lucky])}. '
            f'Unlucky: {join_names([f"{t["TEAM"]} ({res[t["TEAM"]]:.1f})" for t in unl])}.')
    svg = scatter_svg(pts, "Net rating (points per 100 possessions)", "Win %", hl=((x1, a + b * x1), (x2, a + b * x2)), quad=[], xfmt="{:g}", yfmt="{:g}%")
    return ("Which teams are<br>lucky or unlucky?", "Green = beating their net rating · red = underperforming", svg, take, f"Stats: ESPN · 2026-27, through {upd}", "luck")


CHARTS = [ch_teams, ch_usage, ch_playmakers, ch_luck, ch_bench, ch_age]


def list_takeaway(rows, key):
    num = lambda x: float(x.replace("%", "").replace("+", ""))
    try:
        a, b, z = num(rows[0][2]), num(rows[1][2]), num(rows[-1][2])
        vals = [p[key] for p in qual if isinstance(p.get(key), (int, float))] if key in qual[0] else []
        if vals:
            avg = sum(vals) / len(vals)
            return (f'{rows[0][0]} leads at {rows[0][2]}, about {a / avg:.1f}x the average qualifying player ({avg:.1f}). '
                    f'The #1 spot is {abs(a - b):.1f} clear of #2, and #10 is {abs(a - z):.1f} behind.')
        return f'{rows[0][0]} is {abs(a - b):.1f} clear of #2, and the gap to #{len(rows)} is {abs(a - z):.1f}.'
    except Exception:
        return ""


def caption(title, rows, key, sub, take="", is_chart=False):
    t = title.replace("<br>", " ")
    if is_chart:
        long = (f"{t} \U0001F4CA\n\n{take}\n\nWho surprises you? Tell us in the comments.\n\nStats through {upd}. Source: ESPN. Every stat, every season, at newstat.app (link in bio).")
        short = f"{t} \U0001F4CA\n\n{take}\n\nnewstat.app"
        return long, short
    top3 = "\n".join(f"{i+1}. {r[0]} ({r[1].split(' · ')[0]}) {r[2]}" for i, r in enumerate(rows[:5]))
    ins = f"\n\n{take}" if take else ""
    long = f"{t} \U0001F3C0\n\n{top3}{ins}\n\n{sub}. Stats through {upd}. Every stat, every season, at newstat.app (link in bio)."
    short = f"{t} \U0001F3C0\n\n" + "\n".join(f"{i+1}. {r[0].split(' ', 1)[-1]} {r[2]}" for i, r in enumerate(rows[:3])) + "\n\nMore at newstat.app"
    return long, short


def main():
    day = datetime.now(timezone.utc).date()
    forced = sys.argv[1] if len(sys.argv) > 1 else None
    res = None
    if forced is not None and forced.startswith("c"):
        res = CHARTS[int(forced[1:])]()
    elif forced is not None:
        res = THEMES[int(forced)]()
    else:
        ordn = day.toordinal()
        use_chart = ordn % 2 == 1
        pool = CHARTS if use_chart else THEMES
        order = [(ordn // 2 + i) % len(pool) for i in range(len(pool))]
        for idx in order:
            try:
                r = pool[idx]()
                if use_chart or (r[2] and len(r[2]) >= 3):
                    res = r
                    break
            except Exception as e:
                print("theme", idx, "failed:", e)
        if not res and use_chart:
            res = THEMES[ordn % len(THEMES)]()
    if not res:
        sys.exit("no theme worked")
    is_chart = res[5] in ("team ratings", "usage vs TS", "ast vs tov", "luck", "minutes vs per", "age vs pts")
    title, sub, third, fourth, fifth, key = res
    if is_chart:
        svg, take, foot = third, fourth, fifth
        doc = chart_page(title, sub, svg, take, foot)
        rows = []
    else:
        rows, foot, lineup = third, fourth, fifth
        doc = page(title, sub, rows, foot, lineup)
        take = list_takeaway(rows, key)
    os.makedirs("posts", exist_ok=True)
    open("posts/_p.html", "w").write(doc)
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
    long, short = caption(title, rows, key, sub, take, is_chart)
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
