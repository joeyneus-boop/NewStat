"""One-off helper: checks whether ESPN's play-by-play data can give us 5-man lineups.
It saves a small sample in data/probe_pbp/. Nothing on the website uses this."""
import json
import os
import subprocess

import fetch_stats as fs

OUT = os.path.join("data", "probe_pbp")
SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"


def save(name, data, limit=250000):
    raw = json.dumps(data, separators=(",", ":"))
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        f.write(raw[:limit])
    return len(raw)


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {}
    sb = fs.get_json(f"{SITE}/scoreboard?dates=20261113", tries=2)
    if not sb:
        sb = fs.get_json(f"{SITE}/scoreboard", tries=2)
    rep["scoreboard"] = bool(sb)
    if sb:
        save("scoreboard", sb, 60000)
        # look for anything that mentions the NBA Cup
        rep["cup_hits"] = [e.get("name") for e in sb.get("events", [])
                           if "cup" in json.dumps(e).lower()][:10]
        events = [e for e in sb.get("events", []) if e.get("status", {}).get("type", {}).get("completed")]
        for e in events[:2]:
            gid = e["id"]
            summ = fs.get_json(f"{SITE}/summary?event={gid}", tries=2)
            rep[f"summary_{gid}"] = bool(summ)
            if summ:
                rep[f"summary_{gid}_keys"] = list(summ.keys())
                rep[f"summary_{gid}_plays"] = len(summ.get("plays") or [])
                save(f"summary_{gid}", summ)
            pbp = fs.get_json(f"{CORE}/events/{gid}/competitions/{gid}/plays?limit=1000", tries=2)
            rep[f"core_plays_{gid}"] = bool(pbp)
            if pbp:
                rep[f"core_plays_{gid}_n"] = pbp.get("count")
                save(f"core_plays_{gid}", pbp)
            for tag, url in (("core_comp", f"{CORE}/events/{gid}/competitions/{gid}"),
                             ("core_roster", f"{CORE}/events/{gid}/competitions/{gid}/competitors")):
                d = fs.get_json(url, tries=2)
                rep[f"{tag}_{gid}"] = bool(d)
                if d:
                    save(f"{tag}_{gid}", d, 80000)
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1)[:2000])
    if os.environ.get("GITHUB_ACTIONS"):
        sh = lambda *a: subprocess.run(a, capture_output=True, text=True)
        sh("git", "config", "user.name", "stats-bot")
        sh("git", "config", "user.email", "stats-bot@users.noreply.github.com")
        sh("git", "add", OUT)
        if sh("git", "diff", "--staged", "--quiet").returncode != 0:
            sh("git", "commit", "-m", "Play-by-play probe results")
            for _ in range(4):
                sh("git", "pull", "--rebase", "--autostash", "origin", "main")
                if sh("git", "push").returncode == 0:
                    break


if __name__ == "__main__":
    main()
