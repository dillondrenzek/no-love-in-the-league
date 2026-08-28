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
from lib.teams import compute_profiles, empty_profile, win_pct, rec_str, fmt_titles, split_titles
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
    if s.get("in_progress"):     # nothing decided yet — no Shiva/Sacko tag
        return None
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
        "trades": p.get("trades", 0),
        "best_finish": _best_finish_data(p),
    }


def current_roster(seasons):
    """Franchise ids fielding a team in the most recent season on record —
    including an in-progress one — i.e. the league's current membership. This is
    what makes an owner 'active': a mid-season ownership change (a new manager in
    this year's `teams:`) flips who's active even before the season is final."""
    if not seasons:
        return set()
    latest = max(seasons, key=lambda s: s["season"])
    return set((latest.get("teams") or {}).keys())


def owners_data(profiles, roster):
    ranked = sorted_profiles(profiles)
    return {
        "active": [_owner_row(p) for p in ranked if p["id"] in roster],
        "inactive": [_owner_row(p) for p in ranked if p["id"] not in roster],
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
               "finish": ordinal(s["finish"]), "record": s["record"],
               "in_progress": s.get("in_progress", False)}
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
            "trades": p.get("trades", 0),
            "trades_known": p.get("trades_known", True),
            "seasons": p["seasons_count"],
            "best_finish": _best_finish_data(p),
        },
        "seasons": _season_rows(p),
        "h2h": _h2h_rows(p, profiles),
        "trades": p.get("trade_log", []),
        "trades_known": p.get("trades_known", True),
        "keepers": p.get("keeper_log", []),
    }


STUB = """---
layout: owner
title: {name}
permalink: /teams/{id}/
owner_id: {id}
---
{{% assign profile = site.data.owner_profiles[page.owner_id] %}}
{{% include owner_profile.html p=profile %}}
"""


def main():
    franchises = load_franchises()
    # Include the in-progress season: its live record counts toward all-time
    # totals and shows as a season-by-season row (compute_profiles awards no
    # title/sacko for it). Trades already counted from the same list.
    seasons = load_seasons(include_in_progress=True)
    overrides = load_overrides()
    profiles = compute_profiles(seasons, franchises, overrides)

    # A current owner with no season at all yet still lists as active via a
    # zero-stat profile (safety net; a rostered owner normally has a live row).
    roster = current_roster(seasons)
    for fid in roster:
        if fid not in profiles:
            profiles[fid] = empty_profile(fid, franchises)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "owners.yml").write_text(
        yaml.safe_dump(owners_data(profiles, roster), sort_keys=False, allow_unicode=True), encoding="utf-8")
    (DATA_DIR / "owner_profiles.yml").write_text(
        yaml.safe_dump({pid: _profile_data(p, profiles) for pid, p in profiles.items()},
                       sort_keys=False, allow_unicode=True), encoding="utf-8")

    # Owner pages are scaffolded once, then hand-editable: only create a stub
    # for an owner that doesn't have a page yet. Delete a page to regenerate it.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for pid, p in profiles.items():
        path = OUT_DIR / f"{pid}.md"
        if not path.exists():
            path.write_text(STUB.format(name=p["name"], id=pid), encoding="utf-8")
            created += 1

    print(f"Wrote docs/_data/owners.yml, owner_profiles.yml; "
          f"created {created} new owner page(s), kept {len(profiles) - created} as-is")


if __name__ == "__main__":
    main()
