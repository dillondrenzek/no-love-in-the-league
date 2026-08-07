"""Per-owner (franchise) profiles aggregated across every season.

Everything here is derived from the season data + franchise mapping: all-time
regular-season and playoff records, trophy case, season-by-season history, and
head-to-head vs every other owner. This only produces meaningful output for
seasons that have matchups (level 2).
"""

from .data import name_of, short_name_of
from .standings import get_standings


def _blank(fid, franchises):
    return {
        "id": fid,
        "name": name_of(fid, franchises),
        "short": short_name_of(fid, franchises),
        "seasons": [],                                  # one entry per year played
        "reg": {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0},
        "playoff": {"w": 0, "l": 0, "t": 0},
        "titles": 0, "runner_ups": 0, "thirds": 0, "berths": 0,
        "champ_years": [],
        "h2h": {},                                      # opp id -> {w,l,t,pf,pa}
    }


def _apply_game(profiles, fid, opp, pts, opp_pts):
    rec = profiles[fid]["h2h"].setdefault(opp, {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0})
    rec["pf"] += pts
    rec["pa"] += opp_pts
    if pts > opp_pts:
        rec["w"] += 1
    elif opp_pts > pts:
        rec["l"] += 1
    else:
        rec["t"] += 1


def compute_profiles(seasons, franchises):
    """Return {franchise_id: profile}, richest first is up to the caller."""
    profiles = {}

    def prof(fid):
        if fid not in profiles:
            profiles[fid] = _blank(fid, franchises)
        return profiles[fid]

    for season in sorted(seasons, key=lambda s: s["season"], reverse=True):
        year = season["season"]
        teams_map = season.get("teams", {})
        rows = {r["id"]: r for r in get_standings(season, franchises)}

        for fid, r in rows.items():
            p = prof(fid)
            p["seasons"].append({
                "year": year, "team": teams_map.get(fid) or r["name"],
                "finish": r["finish"], "record": r["record"],
                "pf": r["points_for"], "pa": r["points_against"],
            })
            p["reg"]["w"] += r["wins"]; p["reg"]["l"] += r["losses"]; p["reg"]["t"] += r["ties"]
            if r["points_for"] is not None:
                p["reg"]["pf"] += r["points_for"]; p["reg"]["pa"] += r["points_against"]
            if r["finish"] == 1:
                p["titles"] += 1; p["champ_years"].append(year)
            elif r["finish"] == 2:
                p["runner_ups"] += 1
            elif r["finish"] == 3:
                p["thirds"] += 1

        in_playoffs = set()
        for m in season.get("matchups", []):
            h, a = m["home"], m["away"]
            hs, as_ = m["home_score"], m["away_score"]
            prof(h); prof(a)
            _apply_game(profiles, h, a, hs, as_)
            _apply_game(profiles, a, h, as_, hs)
            if m.get("playoff"):
                in_playoffs.update((h, a))
                for x, xs, ys in ((h, hs, as_), (a, as_, hs)):
                    pp = profiles[x]["playoff"]
                    if xs > ys:
                        pp["w"] += 1
                    elif ys > xs:
                        pp["l"] += 1
                    else:
                        pp["t"] += 1
        for fid in in_playoffs:
            prof(fid)["berths"] += 1

    for p in profiles.values():
        p["reg"]["pf"] = round(p["reg"]["pf"], 1)
        p["reg"]["pa"] = round(p["reg"]["pa"], 1)
        finishes = [s["finish"] for s in p["seasons"]]
        p["best_finish"] = min(finishes) if finishes else None
        p["worst_finish"] = max(finishes) if finishes else None
        p["seasons_count"] = len(p["seasons"])
        p["reg"]["win_pct"] = win_pct(p["reg"]["w"], p["reg"]["l"], p["reg"]["t"])
        for rec in p["h2h"].values():
            rec["pf"] = round(rec["pf"], 1)
            rec["pa"] = round(rec["pa"], 1)

    return profiles


def win_pct(w, l, t):
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def rec_str(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")
