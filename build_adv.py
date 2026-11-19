"""Turns the raw NBA.com pulls (nbad_all.json) into data/adv/<year>.json keyed by the site's own player IDs.
Usage: python build_adv.py RAW.json REPO_DIR"""
import json, os, re, sys, unicodedata

def norm(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[.'’`\-]", " ", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"[^a-z ]", "", n).split()
def key(n):
    t = norm(n); return " ".join(t)
def key2(n):  # first initial + last name (fallback)
    t = norm(n); return (t[0][0] + " " + t[-1]) if t else ""

RENAME = {"OPP_FGA":"DEF_FGA","OPP_3_FGA":"DEF_3_FGA","OPP_2_FGA":"DEF_2_FGA","OPP_15_FGA":"DEF_15_FGA"}
UNSCALE = {"TM_TOV_PCT"}   # NBA.com already gives this one as a percent
ALIAS = {}  # NBA-style name -> site-style name, filled in if mismatches show up

def site_rows(repo, Y):
    p = os.path.join(repo, "stats.json") if Y == 2027 else os.path.join(repo, "data", f"{Y}.json")
    if not os.path.exists(p): return None
    return json.load(open(p))["players"]

def main(raw, repo):
    allraw = json.load(open(raw))
    os.makedirs(os.path.join(repo, "data", "adv"), exist_ok=True)
    index = {}
    for Y in sorted(allraw, key=int, reverse=True):
        d = allraw[Y]; Y = int(Y)
        rows = site_rows(repo, Y)
        if rows is None:
            print(Y, "no site file, skipped"); continue
        by_name, by_k2 = {}, {}
        for r in rows:
            by_name.setdefault(key(r["PLAYER"]), []).append(r)
            by_k2.setdefault(key2(r["PLAYER"]), []).append(r)
        out, miss = {}, []
        for row in d["p"]:
            nid, name, team = row[0], row[1], row[2]
            c = by_name.get(key(ALIAS.get(name, name)))
            if not c:
                c = by_k2.get(key2(name))
            if not c: miss.append((name, team, row[3])); continue
            if len(c) > 1:
                t = [x for x in c if x["TEAM"] == team]; c = t or c
            vals = row[3:]
            for i, cn in enumerate(d["cols"]):
                if cn in UNSCALE and vals[i] is not None: vals[i] = round(vals[i] / 100, 3)
            out[str(c[0]["ID"])] = vals
        data = {"y": Y, "season": d["season"], "cols": [RENAME.get(c, c) for c in d["cols"]], "p": out}
        json.dump(data, open(os.path.join(repo, "data", "adv", f"{Y}.json"), "w"), separators=(",", ":"))
        index[Y] = {"season": d["season"], "players": len(out), "cols": len(d["cols"])}
        print(Y, d["season"], "matched", len(out), "of", len(d["p"]), "unmatched", len(miss), miss[:4])
    json.dump(index, open(os.path.join(repo, "data", "adv", "index.json"), "w"), separators=(",", ":"))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
