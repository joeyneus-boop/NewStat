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


def page(title, sub, rows, foot, lineup=False, take=""):
    cls = "row lu" if lineup else "row"
    body = "".join(
        f'<div class="{cls}"><div class=rk>{i+1}</div><div class=nm><b>{html.escape(r[0])}</b><span>{html.escape(r[1])}</span></div>'
        f'<div class=v>{r[2]}<small>{html.escape(r[3])}</small></div></div>' for i, r in enumerate(rows))
    tk = (f'<div class=take><div><i>TAKEAWAY</i>{html.escape(take)}</div></div>' if take else "")
    css = CSS + '.take{position:absolute;left:60px;right:60px;top:1112px;height:150px;border-radius:20px;background:rgba(255,122,47,.14);border:2px solid #ff7a2f;padding:18px 24px;font-size:28px;font-weight:700;line-height:1.28;display:flex;align-items:center}.take i{color:#ff7a2f;font-style:normal;font-weight:900;margin-right:10px}'
    return (f'<!doctype html><meta charset=utf-8><style>{css}</style><div class=bar></div><div class=brand>NEW-STAT</div>'
            f'<h1>{title}</h1><div class=sub>{sub}</div><div class=list>{body}</div>{tk}'
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
            o.append(f'<circle cx="{sx(p["x"]):.1f}" cy="{sy(p["y"]):.1f}" r="6" fill="#8a96b5" fill-opacity=".75"/>')
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


# ---------------- fun / in-depth posts ----------------
FUN_CAP = {}
prev = {}
try:
    prev = {str(p["ID"]): p for p in json.load(open("data/2026.json"))["players"]}
except Exception:
    pass


def rows_html(rows):
    out = []
    for i, r in enumerate(rows):
        out.append(f'<div class=row><div class=rk>{i+1}</div><div class=nm><b>{html.escape(r[0])}</b><span>{html.escape(r[1])}</span></div>'
                   f'<div class=v>{r[2]}<small>{html.escape(r[3])}</small></div></div>')
    return '<div style="width:960px">' + "".join(out) + "</div>"


def fn_risers():
    pool = []
    for p in qual:
        q = prev.get(str(p["ID"]))
        if q and q["GP"] >= 30 and q["MIN"] >= 15:
            pool.append((p["PTS"] - q["PTS"], p, q))
    pool.sort(key=lambda x: -x[0])
    up, down = pool[:8], pool[-1]
    rows = [(p["PLAYER"], f'{p["TEAM"]} · {q["PTS"]:.1f} → {p["PTS"]:.1f} PPG', f"{d:+.1f}", "points per game vs last season") for d, p, q in up]
    take = (f'{up[0][1]["PLAYER"]} is up {up[0][0]:.1f} points per game on last season, the biggest jump in the league. '
            f'On the other side, {down[1]["PLAYER"]} is down {abs(down[0]):.1f}.')
    FUN_CAP["risers"] = (
        f"Who has jumped the most this season? \U0001F4C8\n\nBiggest scoring jumps vs last season:\n\n" + "\n".join(f"{i+1}. {r[0]} {r[2]} ({r[1].split(' · ')[1]})" for i, r in enumerate(rows[:5])) +
        f"\n\n{take}\n\nWho's your breakout player? Tell us below. Stats through {upd}, ESPN. More at newstat.app (link in bio).",
        "Biggest scoring jumps vs last season \U0001F4C8\n\n" + "\n".join(f"{i+1}. {r[0].split(' ', 1)[-1]} {r[2]}" for i, r in enumerate(rows[:3])) + "\n\nnewstat.app", "")
    return ("Biggest scoring<br>jumps this season", "Points per game, 2026-27 vs 2025-26 · min 30 games last year", rows_html(rows), take, f"Stats: ESPN · through {upd}", "risers")


def fn_twins():
    pool = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and p["MIN"] >= 22 and all(isinstance(p.get(k), (int, float)) for k in ("PTS40", "REB40", "AST40", "TS_PCT", "USG_PCT", "FG3A", "STL", "BLK"))]
    keys = ("PTS40", "REB40", "AST40", "TS_PCT", "USG_PCT", "FG3A", "STL", "BLK")
    import math
    sd = {k: (sum((p[k] - sum(q[k] for q in pool) / len(pool)) ** 2 for p in pool) / len(pool)) ** 0.5 or 1 for k in keys}
    pairs = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if a["TEAM"] == b["TEAM"]:
                continue
            d = math.sqrt(sum(((a[k] - b[k]) / sd[k]) ** 2 for k in keys))
            pairs.append((d, a, b))
    pairs.sort(key=lambda x: x[0])
    d, a, b = pairs[datetime.now(timezone.utc).date().toordinal() % 6]
    stats = [("Points / 36", "PTS40", "{:.1f}"), ("Rebounds / 36", "REB40", "{:.1f}"), ("Assists / 36", "AST40", "{:.1f}"), ("True shooting %", "TS_PCT", "{:.1f}%"),
             ("Usage %", "USG_PCT", "{:.1f}%"), ("3PA / game", "FG3A", "{:.1f}"), ("Steals / game", "STL", "{:.1f}"), ("Blocks / game", "BLK", "{:.1f}")]
    rows = "".join(f'<div style="display:grid;grid-template-columns:1fr 300px 1fr;align-items:center;height:78px;border-bottom:1px solid rgba(255,255,255,.08)">'
                   f'<div style="text-align:right;font-size:40px;font-weight:900;color:#fff">{f.format(a[k])}</div><div style="text-align:center;color:#8995ad;font-size:23px;font-weight:700">{lab}</div>'
                   f'<div style="font-size:40px;font-weight:900;color:#fff">{f.format(b[k])}</div></div>' for lab, k, f in stats)
    head = (f'<div style="display:grid;grid-template-columns:1fr 300px 1fr;align-items:center;height:140px">'
            f'<div style="text-align:right"><div style="font-size:42px;font-weight:900;color:#ff7a2f">{html.escape(a["PLAYER"])}</div><div style="font-size:24px;color:#8995ad;font-weight:600">{a["TEAM"]} · {a["MIN"]:.0f} MPG</div></div>'
            f'<div style="text-align:center;font-size:48px;font-weight:900;color:#8995ad">≈</div>'
            f'<div><div style="font-size:42px;font-weight:900;color:#ff7a2f">{html.escape(b["PLAYER"])}</div><div style="font-size:24px;color:#8995ad;font-weight:600">{b["TEAM"]} · {b["MIN"]:.0f} MPG</div></div></div>')
    body = f'<div style="width:960px">{head}{rows}</div>'
    take = f'{a["PLAYER"]} and {b["PLAYER"]} have nearly identical production once you adjust for minutes, even though they play for different teams. Would you have guessed it?'
    FUN_CAP["twins"] = (
        f"Statistical twins \U0001F46F\n\n{a['PLAYER']} ({a['TEAM']}) and {b['PLAYER']} ({b['TEAM']}) are almost the same player on paper this season: {a['PTS40']:.1f} vs {b['PTS40']:.1f} points per 36, {a['REB40']:.1f} vs {b['REB40']:.1f} rebounds, {a['AST40']:.1f} vs {b['AST40']:.1f} assists, {a['TS_PCT']:.0f}% vs {b['TS_PCT']:.0f}% true shooting.\n\nWe matched all {len(pool)} players with 22+ MPG on 8 stats. Who is your favorite twin pair? \U0001F447\n\nStats through {upd}, ESPN. More at newstat.app (link in bio).",
        f"Statistical twins \U0001F46F\n\n{a['PLAYER']} ≈ {b['PLAYER']}\n\nSame production, different teams. newstat.app", "")
    return ("Statistical twins:<br>who is the same player?", f"Closest match in the league across 8 per-minute stats · min 22 MPG", body, take, f"Stats: ESPN · through {upd}", "twins")


def fn_mystery():
    cand = sorted([p for p in qual if p["MIN"] >= 25], key=lambda p: -p["PER"])[:25]
    p = cand[datetime.now(timezone.utc).date().toordinal() % len(cand)]
    tiles = [("PPG", f'{p["PTS"]:.1f}'), ("RPG", f'{p["REB"]:.1f}'), ("APG", f'{p["AST"]:.1f}'), ("TS%", f'{p["TS_PCT"]:.1f}'), ("3P%", f'{p["FG3_PCT"]:.1f}' if isinstance(p.get("FG3_PCT"), (int, float)) else "–"), ("MPG", f'{p["MIN"]:.1f}')]
    tiles_html = "".join(f'<div style="background:rgba(255,255,255,.07);border-radius:24px;padding:26px 10px;text-align:center"><div style="font-size:72px;font-weight:900;color:#fff;line-height:1">{v}</div><div style="color:#8995ad;font-size:26px;font-weight:700;margin-top:6px">{l}</div></div>' for l, v in tiles)
    pos = {"G": "Guard", "F": "Forward", "C": "Center"}.get(p.get("POS"), "Player")
    hints = [f'Age {p["AGE"]:.0f}' if p.get("AGE") else None, f'Position: {pos}', f'Drafted {p["DRAFT"]}' if p.get("DRAFT") else None, f'Plays in the {"East" if p["TEAM"] in EAST else "West"}']
    hints_html = "".join(f'<div style="background:rgba(255,122,47,.16);border:2px solid #ff7a2f;border-radius:999px;padding:10px 24px;font-size:28px;font-weight:800;color:#fff">{html.escape(h)}</div>' for h in hints if h)
    body = (f'<div style="width:960px"><div style="font-size:150px;font-weight:900;color:#ff7a2f;text-align:center;line-height:1;margin:6px 0 10px">?</div>'
            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">{tiles_html}</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin-top:30px">{hints_html}</div></div>')
    take = "Drop your guess in the comments. Post the answer as a reply tomorrow."
    FUN_CAP["mystery"] = (
        f"Guess the player \U0001F575️\n\n{p['PTS']:.1f} PPG, {p['REB']:.1f} RPG, {p['AST']:.1f} APG on {p['TS_PCT']:.0f}% true shooting this season.\n\nWho is it? Drop your guess below \U0001F447 (answer in the comments tomorrow).\n\nStats through {upd}, ESPN. More at newstat.app (link in bio).",
        f"Guess the player \U0001F575️\n\n{p['PTS']:.1f} / {p['REB']:.1f} / {p['AST']:.1f} on {p['TS_PCT']:.0f}% TS. Who is it?\n\nnewstat.app", p["PLAYER"])
    return ("Guess the player:<br>who has this line?", "2026-27 season so far · one of the top 25 by PER", body, take, f"Stats: ESPN · through {upd}", "mystery")


EAST = {"ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET", "IND", "MIA", "MIL", "NY", "NYK", "ORL", "PHI", "TOR", "WSH", "WAS"}


def fn_five():
    pool = [p for p in players if p["GP"] >= max(5, 0.6 * maxgp) and p["MIN"] >= 25 and isinstance(p.get("PER"), (int, float))]
    pick = []
    for pos, n in (("G", 2), ("F", 2), ("C", 1)):
        pick += sorted([p for p in pool if p.get("POS") == pos], key=lambda p: -p["PER"])[:n]
    rows = [(p["PLAYER"], f'{p["TEAM"]} · {p["PTS"]:.1f} pts · {p["REB"]:.1f} reb · {p["AST"]:.1f} ast', f'{p["PER"]:.1f}', "PER") for p in pick]
    tp = sum(p["PTS"] for p in pick); tr = sum(p["REB"] for p in pick); ta = sum(p["AST"] for p in pick)
    take = f'This lineup would average {tp:.0f} points, {tr:.0f} rebounds and {ta:.0f} assists per game. How many teams are represented? {len({p["TEAM"] for p in pick})} of 5 different.'
    FUN_CAP["five"] = (
        "The All-Stat Five so far this season \U0001F3C6\n\nBest player by PER at each spot:\n\n" + "\n".join(f"{p['PLAYER']} ({p['TEAM']}) PER {p['PER']:.1f}" for p in pick) +
        f"\n\n{take}\n\nWho would you swap out? \U0001F447 Stats through {upd}, ESPN. More at newstat.app (link in bio).",
        "The All-Stat Five \U0001F3C6\n\n" + "\n".join(p["PLAYER"] for p in pick) + "\n\nBest PER at each spot. newstat.app", "")
    return ("The All-Stat Five<br>so far this season", "Best PER at each spot · min 25 MPG · 2 guards, 2 forwards, 1 center", rows_html(rows), take, f"Stats: ESPN · through {upd}", "five")


FUN = [fn_risers, fn_twins, fn_mystery, fn_five]
FUN_KEYS = ("risers", "twins", "mystery", "five")

PALETTES = [
    ("#ff7a2f", "255,122,47", "#0b1220", "#142241"),
    ("#22d3ee", "34,211,238", "#061a22", "#0e3140"),
    ("#a78bfa", "167,139,250", "#120d26", "#241a4a"),
    ("#f472b6", "244,114,182", "#1f0b19", "#3b1730"),
    ("#fbbf24", "251,191,36", "#1a1405", "#33270a"),
    ("#fb7185", "251,113,133", "#1c0a0e", "#381420"),
    ("#60a5fa", "96,165,250", "#08142a", "#10284f"),
]


def recolor(doc, ordn):
    acc, rgb, b1, b2 = PALETTES[ordn % len(PALETTES)]
    return doc.replace("#ff7a2f", acc).replace("255,122,47", rgb).replace("#0b1220", b1).replace("#142241", b2)


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
    ordn = day.toordinal()
    forced = sys.argv[1] if len(sys.argv) > 1 else None
    res = None
    if forced is not None and forced.startswith("c"):
        res = CHARTS[int(forced[1:])]()
    elif forced is not None and forced.startswith("f"):
        res = FUN[int(forced[1:])]()
    elif forced is not None:
        res = THEMES[int(forced)]()
    else:
        kind = ("chart", "fun", "chart", "list")[ordn % 4]
        pool = {"chart": CHARTS, "fun": FUN, "list": THEMES}[kind]
        base = ordn // 2 if kind == "chart" else ordn // 4
        order = [(base + i) % len(pool) for i in range(len(pool))]
        for idx in order:
            try:
                r = pool[idx]()
                if kind != "list" or (r[2] and len(r[2]) >= 3):
                    res = r
                    break
            except Exception as e:
                print("theme", idx, "failed:", e)
        if not res:
            res = THEMES[ordn % len(THEMES)]()
    if not res:
        sys.exit("no theme worked")
    title, sub, third, fourth, fifth, key = res
    is_chart = key in ("team ratings", "usage vs TS", "ast vs tov", "luck", "minutes vs per", "age vs pts")
    is_fun = key in FUN_KEYS
    answer = ""
    if is_chart or is_fun:
        doc = chart_page(title, sub, third, fourth, fifth)
        rows = []
        take = fourth
    else:
        rows, foot, lineup = third, fourth, fifth
        take = list_takeaway(rows, key)
        doc = page(title, sub, rows[:8], foot, lineup, take)
    doc = recolor(doc, ordn)
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
    if is_fun:
        long, short, answer = FUN_CAP[key]
    else:
        long, short = caption(title, rows, key, sub, take, is_chart)
    meta = {"date": ds, "title": title.replace("<br>", " "), "long": long, "short": short}
    if answer:
        meta["answer"] = answer
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
