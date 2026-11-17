"""Builds 5-man lineup data (who was on the floor, points for/against, estimated possessions)
from ESPN's free play-by-play feed. Saves data/lineups/<season>.json.

  python fetch_lineups.py            -> every finished regular-season game not saved yet (safe to re-run)

Each game is only ever added once. To rebuild from scratch, delete data/lineups/<season>.json.
Games whose substitutions don't add up (or whose points don't match the final score) are
skipped and listed under "bad" so wrong numbers never reach the website.
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import fetch_stats as fs

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
OUT_DIR = os.path.join("data", "lineups")
SEASON = int(os.environ.get("LINEUP_SEASON", "2027"))          # ESPN names 2026-27 as 2027
SEASON_START = os.environ.get("LINEUP_START", "2026-10-01")
TIME_BUDGET = 40 * 60
WORKERS = 6
VERSION = 2


def rid(ref, key):
    m = re.search(key + r"/(\d+)", ref or "")
    return m.group(1) if m else None


def period_len(n):
    return 720 if n <= 4 else 300


def period_start(n):
    return 720 * (n - 1) if n <= 4 else 2880 + 300 * (n - 5)


def simulate(plays, teams):
    """plays: ESPN play list. teams: {tid: {home:bool, starters:set}}. Returns (agg, problems, end_time).
    agg[tid][frozenset(player ids)] = [seconds, pts_for, pts_against, poss_for, poss_against]"""
    tids = list(teams)
    home = next(t for t in tids if teams[t]["home"])
    away = next(t for t in tids if not teams[t]["home"])
    floor = {t: set(teams[t]["starters"]) for t in tids}
    agg = {t: {} for t in tids}
    problems = []
    last_t = 0.0
    last_period = 1
    pa_, ph_ = 0, 0

    def row(t):
        k = frozenset(floor[t])
        return agg[t].setdefault(k, [0.0, 0, 0, 0.0, 0.0])

    def other(t):
        return away if t == home else home

    def order(x):
        c = (x.get("clock") or {}).get("value")
        return ((x.get("period") or {}).get("number") or 1, -(c if c is not None else 0), int(x.get("sequenceNumber") or 0))

    pending = []   # sub-outs whose player wasn't on the floor yet (ESPN logged the plays out of order)

    def settle():
        for item in pending[:]:
            t_, a_ = item
            if a_ in floor[t_]:
                floor[t_].discard(a_)
                pending.remove(item)

    for p in sorted(plays, key=order):
        per = (p.get("period") or {}).get("number") or last_period
        clock = (p.get("clock") or {}).get("value")
        if clock is None:
            clock = 0
        el = period_start(per) + period_len(per) - float(clock)
        if el < last_t:
            el = last_t
        dt = el - last_t
        if dt > 0:
            settle()
            if pending:
                problems.append("sub out player not on floor")
                pending.clear()
            for t in tids:
                if len(floor[t]) != 5:
                    problems.append(f"lineup of {len(floor[t])} at {el:.0f}s")
                row(t)[0] += dt
        last_t = el
        last_period = per
        # points
        ta, th = p.get("awayScore"), p.get("homeScore")
        if isinstance(ta, (int, float)) and isinstance(th, (int, float)):
            da, dh = ta - pa_, th - ph_
            da, dh = max(0, da), max(0, dh)   # a late-logged play can carry an older score; ignore it
            if da or dh:
                row(away)[1] += da; row(away)[2] += dh
                row(home)[1] += dh; row(home)[2] += da
            pa_, ph_ = max(pa_, ta), max(ph_, th)
        typ = ((p.get("type") or {}).get("text") or "")
        tl = typ.lower()
        t = rid((p.get("team") or {}).get("$ref"), "teams")
        if t in teams:
            n = 0.0
            if "free throw" in tl:
                n = 0.44
            elif "offensive rebound" in tl:
                n = -1.0
            elif "turnover" in tl or tl == "traveling":
                n = 1.0
            elif p.get("shootingPlay") and "foul" not in tl:
                n = 1.0
            if n:
                row(t)[3] += n; row(other(t))[4] += n
        if tl == "substitution":
            ins, outs = [], []
            for x in p.get("participants") or []:
                a = rid((x.get("athlete") or {}).get("$ref"), "athletes")
                (ins if x.get("type") == "subin" else outs).append(a)
            if t in teams:
                for a in outs:
                    if a in floor[t]:
                        floor[t].discard(a)
                    else:
                        pending.append((t, a))
                for a in ins:
                    floor[t].add(a)
                settle()
    settle()
    if pending:
        problems.append("sub out player not on floor")
    end = period_start(last_period) + period_len(last_period)
    if end > last_t:
        for t in tids:
            row(t)[0] += end - last_t
    return agg, problems, end


def find_notes(o):
    out = []
    if isinstance(o, dict):
        if o.get("headline") and o.get("type") == "event":
            out.append(o["headline"])
        for v in o.values():
            out += find_notes(v)
    elif isinstance(o, list):
        for v in o:
            out += find_notes(v)
    return out


def get_plays(gid):
    items, page = [], 1
    while True:
        d = fs.get_json(f"{CORE}/events/{gid}/competitions/{gid}/plays?limit=1000&page={page}", tries=3)
        if not d:
            return None
        items += d.get("items") or []
        if page >= (d.get("pageCount") or 1):
            return items
        page += 1


def process_game(ev):
    gid = ev["id"]
    summ = fs.get_json(f"{SITE}/summary?event={gid}", tries=3)
    if not summ:
        return gid, None, "no summary"
    comp = ((summ.get("header") or {}).get("competitions") or [{}])[0]
    teams, names, abbr, final = {}, {}, {}, {}
    for c in comp.get("competitors") or []:
        tid = str(c["team"]["id"])
        teams[tid] = {"home": c.get("homeAway") == "home", "starters": set()}
        abbr[tid] = c["team"].get("abbreviation") or tid
        names[tid] = c["team"].get("displayName") or abbr[tid]
        try:
            final[tid] = int(c.get("score"))
        except (TypeError, ValueError):
            final[tid] = None
    pnames = {}
    for tb in (summ.get("boxscore") or {}).get("players") or []:
        tid = str(tb["team"]["id"])
        if tid not in teams:
            continue
        for grp in tb.get("statistics") or []:
            for a in grp.get("athletes") or []:
                aid = str(a["athlete"]["id"])
                pnames[aid] = a["athlete"].get("displayName") or aid
                if a.get("starter"):
                    teams[tid]["starters"].add(aid)
                teams[tid].setdefault("roster", set()).add(aid)
    if len(teams) != 2 or any(len(t["starters"]) != 5 for t in teams.values()):
        return gid, None, "starters not found"
    plays = get_plays(gid)
    if not plays:
        return gid, None, "no plays"
    agg, problems, end = simulate(plays, teams)
    if problems:
        return gid, None, "; ".join(sorted(set(problems))[:3])
    for t, a in agg.items():
        pts = sum(r[1] for r in a.values())
        if final.get(t) is not None and pts != final[t]:
            return gid, None, f"points {pts} != final {final[t]}"
    types = {}
    for p in plays:
        k = (p.get("type") or {}).get("text") or "?"
        types[k] = types.get(k, 0) + 1
    cup = any("cup" in h.lower() for h in find_notes(ev))
    return gid, {"agg": agg, "abbr": abbr, "names": names, "pnames": pnames, "cup": cup,
                 "secs": end, "types": types}, None


def merge(store, res, date):
    for tid, lu in res["agg"].items():
        T = store["teams"].setdefault(tid, {"abbr": res["abbr"][tid], "name": res["names"][tid],
                                            "players": [], "lineups": {}, "cup": {}})
        idx = {p[0]: i for i, p in enumerate(T["players"])}
        for k, v in lu.items():
            for a in k:
                if a not in idx:
                    idx[a] = len(T["players"])
                    T["players"].append([a, res["pnames"].get(a, a)])
            key = ".".join(str(i) for i in sorted(idx[a] for a in k))
            for bucket in ([T["lineups"], T["cup"]] if res["cup"] else [T["lineups"]]):
                r = bucket.setdefault(key, [0, 0, 0, 0, 0])
                for j in range(5):
                    r[j] += v[j]
    store["games"][res["gid"]] = {"d": date, "cup": res["cup"]}


def finish(store):
    for T in store["teams"].values():
        for b in ("lineups", "cup"):
            for r in T[b].values():
                r[0] = int(round(r[0])); r[3] = round(r[3], 1); r[4] = round(r[4], 1)


def save(store, path):
    out = json.loads(json.dumps(store))
    for T in out["teams"].values():
        for b in ("lineups", "cup"):
            for r in T[b].values():
                r[0] = int(round(r[0])); r[3] = round(r[3], 1); r[4] = round(r[4], 1)
    out["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))


def git_push(msg):
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    sh = lambda *a: subprocess.run(a, capture_output=True, text=True)
    sh("git", "config", "user.name", "stats-bot")
    sh("git", "config", "user.email", "stats-bot@users.noreply.github.com")
    sh("git", "add", OUT_DIR)
    if sh("git", "diff", "--staged", "--quiet").returncode != 0:
        sh("git", "commit", "-m", msg)
        for _ in range(4):
            sh("git", "pull", "--rebase", "--autostash", "origin", "main")
            if sh("git", "push").returncode == 0:
                break


def main():
    t0 = time.time()
    path = os.path.join(OUT_DIR, f"{SEASON}.json")
    store = {"season": SEASON, "games": {}, "bad": {}, "teams": {}, "types": {}}
    if os.path.exists(path):
        store = json.load(open(path))
        # restore float precision is not needed; sums stay valid
    if store.get("v") != VERSION:      # counting rules changed: start over so all games use the same rules
        store = {"season": SEASON, "games": {}, "bad": {}, "teams": {}, "types": {}}
    store["v"] = VERSION
    store.setdefault("bad", {}); store.setdefault("types", {})
    day = datetime.strptime(SEASON_START, "%Y-%m-%d").date()
    if store["games"]:
        day = max(day, datetime.strptime(max(g["d"] for g in store["games"].values()), "%Y-%m-%d").date() - timedelta(days=2))
    today = datetime.now(timezone.utc).date()
    added = 0
    while day <= today and time.time() - t0 < TIME_BUDGET:
        sb = fs.get_json(f"{SITE}/scoreboard?dates={day.strftime('%Y%m%d')}", tries=2) or {}
        evs = [e for e in sb.get("events", [])
               if (e.get("status") or {}).get("type", {}).get("completed")
               and ((e.get("season") or {}).get("type") in (2, None))
               and e["id"] not in store["games"]
               and store["bad"].get(e["id"], {}).get("tries", 0) < 3]
        with ThreadPoolExecutor(WORKERS) as ex:
            results = list(ex.map(process_game, evs))
        for ev, (gid, res, err) in zip(evs, results):
            if err:
                b = store["bad"].setdefault(gid, {"d": str(day), "tries": 0})
                b["tries"] += 1; b["err"] = err
                print("skip", gid, err)
                continue
            res["gid"] = gid
            merge(store, res, str(day))
            store["bad"].pop(gid, None)
            for k, v in res["types"].items():
                store["types"][k] = store["types"].get(k, 0) + v
            added += 1
        if evs:
            print(day, "games:", len(evs), "added so far:", added)
            save(store, path)
        day += timedelta(days=1)
    save(store, path)
    print(f"done: {added} new games, {len(store['games'])} total, {len(store['bad'])} skipped")
    git_push("Update lineup data")


if __name__ == "__main__":
    main()
