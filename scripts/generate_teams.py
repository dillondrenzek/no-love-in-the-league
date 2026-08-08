#!/usr/bin/env python3
"""Emit the owner data + thin per-owner stub pages.

  docs/_data/owners.yml          - owners-index rows (rendered by docs/teams/index.md)
  docs/_data/owner_profiles.yml  - per-owner profile data, keyed by franchise id
  docs/teams/<id>.md             - a stub page that includes _includes/owner_profile.html

Python computes every display value (records, chip colors, tags, honors, best
finish); the Liquid templates only assemble markup.

    .venv/bin/python scripts/generate_teams.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.teams import compute_profiles, win_pct, rec_str, fmt_titles, split_titles
from lib.rulings import load_overrides
from lib.render import warm_heat, heat_color

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "teams"
DATA_DIR = ROOT / "docs" / "_data"


def ordinal(n):
    if n is None:
        return "—"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def pct(x):
    return f"{x:.3f}".lstrip("0") or ".000"


def sorted_profiles(profiles):
    return sorted(
        profiles.values(),
        key=lambda p: (p["titles"], p["reg"]["win_pct"], p["reg"]["w"]),
        reverse=True,
    )


def _best_finish_data(p):
    outright, co = split_titles(p["champ_years"])
    if outright:
        return {"type": "shiva", "years": outright}
    if co:
        return {"type": "cochamp", "years": co}
    best = p["best_finish"]
    yrs = sorted(s["year"] for s in p["seasons"] if s["finish"] == best)
    return {"type": "place", "ordinal": ordinal(best), "years": yrs}


def _season_tag(s):
    if s["is_co"]:
        return "cochamp"
    if s["finish"] == 1:
        return "shiva"
    if s["finish"] == s["team_count"]:
        return "sacko"
    return None


# --- Owners index -----------------------------------------------------------

def _owner_row(p):
    reg = p["reg"]
    return {
        "id": p["id"], "name": p["name"], "seasons": p["seasons_count"],
        "record": rec_str(reg["w"], reg["l"], reg["t"]),
        "win_pct": pct(reg["win_pct"]), "win_color": heat_color(reg["win_pct"], 0.3, 0.7),
        "titles": fmt_titles(p["titles"]), "sackos": p["sackos"],
        "best_finish": _best_finish_data(p),
    }


def owners_data(profiles):
    ranked = sorted_profiles(profiles)
    latest = max(p["seasons"][0]["year"] for p in ranked)
    return {
        "active": [_owner_row(p) for p in ranked if p["seasons"][0]["year"] == latest],
        "inactive": [_owner_row(p) for p in ranked if p["seasons"][0]["year"] != latest],
    }


# --- Per-owner profile ------------------------------------------------------

def _honors(p):
    bits = []
    outright, co = split_titles(p["champ_years"])
    if outright:
        bits.append({"emoji": "🏆", "text": f"{len(outright)}× Shiva ({', '.join(map(str, outright))})", "strong": True})
    if co:
        bits.append({"emoji": "🤝", "text": f"Co-champ ({', '.join(map(str, co))})", "strong": True})
    if p["runner_ups"]:
        bits.append({"emoji": "🥈", "text": f"{p['runner_ups']}× Runner-Up", "strong": False})
    if p["thirds"]:
        bits.append({"emoji": "🥉", "text": f"{p['thirds']}× Third", "strong": False})
    if p["sackos"]:
        yrs = ", ".join(str(y) for y in sorted(p["sacko_years"]))
        bits.append({"emoji": "💩", "text": f"{p['sackos']}× Sacko ({yrs})", "strong": True})
    if p["berths"]:
        bits.append({"emoji": "", "text": f"{p['berths']}× Playoffs", "strong": False})
    return bits


def _season_rows(p):
    pfs = [s["pf"] for s in p["seasons"] if s["pf"] is not None]
    lo, hi = (min(pfs), max(pfs)) if pfs else (0, 0)
    rows = []
    for s in p["seasons"]:
        row = {"year": s["year"], "team": s["team"], "tag": _season_tag(s),
               "finish": ordinal(s["finish"]), "record": s["record"]}
        if s["pf"] is not None:
            row["pf"] = s["pf"]
            row["pf_color"] = heat_color(s["pf"], lo, hi)
            row["pa"] = s["pa"]
        rows.append(row)
    return rows


def _h2h_rows(p, profiles):
    opps = [(oid, r) for oid, r in p["h2h"].items() if oid in profiles]
    opps.sort(key=lambda kv: profiles[kv[0]]["short"].lower())
    rows = []
    for oid, r in opps:
        games = r["w"] + r["l"] + r["t"]
        wp = win_pct(r["w"], r["l"], r["t"])
        rows.append({
            "opp_id": oid, "opp_short": profiles[oid]["short"],
            "record": rec_str(r["w"], r["l"], r["t"]),
            "win_pct": pct(wp), "win_color": warm_heat(wp),
            "avg_pf": round(r["pf"] / games, 1), "avg_pa": round(r["pa"] / games, 1),
        })
    return rows


def _profile_data(p, profiles):
    reg = p["reg"]
    return {
        "name": p["name"],
        "nickname": p.get("nickname", ""),
        "honors": _honors(p),
        "resume": {
            "all_time": rec_str(reg["w"], reg["l"], reg["t"]),
            "win_pct": pct(reg["win_pct"]),
            "titles": fmt_titles(p["titles"]),
            "sackos": p["sackos"],
            "playoff_apps": p["berths"],
            "seasons": p["seasons_count"],
            "best_finish": _best_finish_data(p),
        },
        "seasons": _season_rows(p),
        "h2h": _h2h_rows(p, profiles),
    }


STUB = """---
layout: page
title: {name}
permalink: /teams/{id}/
owner_id: {id}
---
{{% assign profile = site.data.owner_profiles[page.owner_id] %}}
{{% include owner_profile.html p=profile %}}
"""


def main():
    franchises = load_franchises()
    seasons = load_seasons()
    overrides = load_overrides()
    profiles = compute_profiles(seasons, franchises, overrides)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "owners.yml").write_text(
        yaml.safe_dump(owners_data(profiles), sort_keys=False, allow_unicode=True), encoding="utf-8")
    (DATA_DIR / "owner_profiles.yml").write_text(
        yaml.safe_dump({pid: _profile_data(p, profiles) for pid, p in profiles.items()},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for pid, p in profiles.items():
        (OUT_DIR / f"{pid}.md").write_text(STUB.format(name=p["name"], id=pid), encoding="utf-8")

    print(f"Wrote docs/_data/owners.yml, owner_profiles.yml and {len(profiles)} stub pages")


if __name__ == "__main__":
    main()
