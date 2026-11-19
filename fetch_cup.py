"""Builds NBA Cup-only player stats (per game) from ESPN box scores. Saves data/cup/<season>.json
in the same shape as stats.json so the Leaders page can show it like any other season.
Rebuilt from scratch every run (about 20 games), so it never drifts."""
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone

import fetch_lineups as fl
import fetch_stats as fs

SEASON = fl.SEASON
START = fl.SEASON_START
OUT = os.path.join("data", "cup", f"{SEASON}.json")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_box(summ, acc):
    for tb in (summ.get("boxscore") or {}).get("players") or []:
        team = (tb.get("team") or {}).get("abbreviation")
        for grp in tb.get("statistics") or []:
            labels = grp.get("labels") or []
            for a in grp.get("athletes") or []:
                st = a.get("stats") or []
                if not st or len(st) != len(labels):
                    continue
                d = dict(zip(labels, st))
                mins = num(d.get("MIN"))
                if not mins:
                    continue
                aid = str(a["athlete"]["id"])
                r = acc.setdefault(aid, {"name": a["athlete"].get("displayName"), "team": team, "gp": 0, "gs": 0,
                                         "dd": 0, "td": 0, **{k: 0.0 for k in
                                         ("MIN", "PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF",
                                          "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "PM")}})
                r["gp"] += 1
                r["gs"] += 1 if a.get("starter") else 0
                r["team"] = team
                r["MIN"] += mins
                for k, lab in (("PTS", "PTS"), ("REB", "REB"), ("OREB", "OREB"), ("DREB", "DREB"), ("AST", "AST"),
                               ("STL", "STL"), ("BLK", "BLK"), ("TOV", "TO"), ("PF", "PF")):
                    r[k] += num(d.get(lab)) or 0
                for k, lab in (("FG", "FG"), ("FG3", "3PT"), ("FT", "FT")):
                    m, _, t = str(d.get(lab, "0-0")).partition("-")
                    r[k + "M"] += num(m) or 0
                    r[k + "A"] += num(t) or 0
                r["PM"] += num((d.get("+/-") or "0").replace("+", "")) or 0
                big = sum(1 for k in ("PTS", "REB", "AST", "STL", "BLK") if (num(d.get({"PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "STL", "BLK": "BLK"}[k])) or 0) >= 10)
                r["dd"] += 1 if big >= 2 else 0
                r["td"] += 1 if big >= 3 else 0


def main():
    t0 = time.time()
    day = datetime.strptime(START, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    acc, games = {}, 0
    while day <= today and time.time() - t0 < 25 * 60:
        sb = fs.get_json(f"{fl.SITE}/scoreboard?dates={day.strftime('%Y%m%d')}", tries=2) or {}
        for ev in sb.get("events", []):
            if not (ev.get("status") or {}).get("type", {}).get("completed"):
                continue
            if not any("cup" in h.lower() for h in fl.find_notes(ev)):
                continue
            summ = fs.get_json(f"{fl.SITE}/summary?event={ev['id']}", tries=3)
            if summ:
                parse_box(summ, acc)
                games += 1
        day += timedelta(days=1)
    meta = {}
    try:
        for p in json.load(open("stats.json"))["players"]:
            meta[str(p["ID"])] = p
    except Exception:
        pass
    cols = ["GP", "MIN", "PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG_PCT", "FG3M",
            "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "TS_PCT", "EFG_PCT", "PLUS_MINUS", "AST_TO", "GS", "DD2", "TD3"]
    pct = lambda m, a: round(100 * m / a, 2) if a else None
    players = []
    for aid, r in acc.items():
        g = r["gp"]
        m = meta.get(aid, {})
        row = {"ID": aid, "PLAYER": r["name"], "TEAM": m.get("TEAM") or r["team"], "GP": g,
               "GS": r["gs"], "DD2": r["dd"], "TD3": r["td"]}
        for k in ("POS", "AGE", "DRAFT"):
            if m.get(k) is not None:
                row[k] = m[k]
        for k in ("MIN", "PTS", "REB", "OREB", "DREB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"):
            row[k] = round(r[k] / g, 3)
        row["PLUS_MINUS"] = round(r["PM"] / g, 2)
        row["FG_PCT"] = pct(r["FGM"], r["FGA"]); row["FG3_PCT"] = pct(r["FG3M"], r["FG3A"]); row["FT_PCT"] = pct(r["FTM"], r["FTA"])
        den = 2 * (r["FGA"] + 0.44 * r["FTA"])
        row["TS_PCT"] = round(100 * r["PTS"] / den, 2) if den else None
        row["EFG_PCT"] = round(100 * (r["FGM"] + 0.5 * r["FG3M"]) / r["FGA"], 2) if r["FGA"] else None
        row["AST_TO"] = round(r["AST"] / r["TOV"], 2) if r["TOV"] else None
        players.append(row)
    players.sort(key=lambda x: -x["PTS"])
    out = {"season": f"{SEASON - 1}-{str(SEASON)[2:]} NBA Cup games only", "games": games,
           "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "columns": cols, "players": players}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print(f"cup games {games}, players {len(players)}")
    if os.environ.get("GITHUB_ACTIONS"):
        sh = lambda *a: subprocess.run(a, capture_output=True, text=True)
        sh("git", "config", "user.name", "stats-bot"); sh("git", "config", "user.email", "stats-bot@users.noreply.github.com")
        sh("git", "add", "data/cup")
        if sh("git", "diff", "--staged", "--quiet").returncode != 0:
            sh("git", "commit", "-m", "Update NBA Cup stats")
            for _ in range(4):
                sh("git", "pull", "--rebase", "--autostash", "origin", "main")
                if sh("git", "push").returncode == 0:
                    break


if __name__ == "__main__":
    main()
