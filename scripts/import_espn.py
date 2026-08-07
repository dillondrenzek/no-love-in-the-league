#!/usr/bin/env python3
"""Import one season of scores from ESPN into data/seasons/<year>.yml.

This is a LOCAL dev tool, not part of the published site. It uses the `espn-api`
library (see requirements-dev.txt) to pull a season, then writes:

  - data/seasons/<year>.yml : final_standings + every matchup with scores
  - data/franchises.yml      : owner -> franchise mapping, merged by ESPN SWID

Nothing here runs at site-build time; the site only reads the YAML it produces.

Usage:
    python scripts/import_espn.py 2025            # write the files
    python scripts/import_espn.py 2025 --stdout   # preview YAML, write nothing

Private league? Export your ESPN cookies first (they're only used locally to
authenticate the read request):
    export ESPN_S2='...'      # the espn_s2 cookie value
    export ESPN_SWID='{...}'  # the SWID cookie value, braces included

Franchise identity: teams get a stable id from their owner's ESPN SWID, so the
same person keeps one franchise across seasons even as their team name changes.
Owner names only come through when cookies are supplied; without them the tool
falls back to that season's team name and can't link owners across years.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

try:
    from espn_api.football import League
except ImportError:
    sys.exit("espn-api is not installed. Run: pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parent.parent
SEASONS_DIR = ROOT / "data" / "seasons"
FRANCHISES_PATH = ROOT / "data" / "franchises.yml"
LEAGUE_ID = 236302


def clean_name(text):
    """Collapse ESPN's stray double-spaces / trailing spaces in a team name."""
    return re.sub(r"\s+", " ", text or "").strip()


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "unknown"


def owner_of(team):
    """(swid, display_name) for a team's primary owner, or (None, None)."""
    owners = getattr(team, "owners", []) or []
    if not owners:
        return None, None
    o = owners[0]
    if isinstance(o, dict):
        name = o.get("displayName") or " ".join(
            filter(None, [o.get("firstName"), o.get("lastName")])
        ).strip()
        return o.get("id"), (name or None)
    return str(o), None  # older payloads: bare id string


def load_franchises():
    if FRANCHISES_PATH.exists():
        data = yaml.safe_load(FRANCHISES_PATH.read_text()) or []
        return data if isinstance(data, list) else []
    return []


def resolve_franchises(teams, registry):
    """Map each team_id -> franchise id, updating `registry` (list of dicts).

    Matches an existing franchise by SWID so the same owner keeps one id across
    seasons; records each season's team name as an alias.
    """
    by_swid = {f["espn_swid"]: f for f in registry if f.get("espn_swid")}
    used_ids = {f["id"] for f in registry}
    team_to_fid = {}

    for team in teams:
        swid, name = owner_of(team)
        team_name = clean_name(team.team_name)
        entry = by_swid.get(swid) if swid else None

        if entry is None:
            base = slug(name or team_name)
            fid = base
            i = 2
            while fid in used_ids and (not swid):
                fid, i = f"{base}-{i}", i + 1
            entry = {"id": fid, "name": name or team_name, "aliases": []}
            if swid:
                entry["espn_swid"] = swid
                by_swid[swid] = entry
            registry.append(entry)
            used_ids.add(fid)

        if name and (not entry.get("name") or entry["name"] == entry["id"]):
            entry["name"] = name
        if team_name not in entry.setdefault("aliases", []):
            entry["aliases"].append(team_name)

        team_to_fid[team.team_id] = entry["id"]

    return team_to_fid


def build_matchups(teams, team_to_fid, reg_season_count):
    seen = set()
    matchups = []
    for team in teams:
        for wk_idx, opp in enumerate(team.schedule):
            week = wk_idx + 1
            if opp is None or opp.team_id == team.team_id:
                continue
            key = (week, frozenset((team.team_id, opp.team_id)))
            if key in seen:
                continue
            ts, os_ = team.scores[wk_idx], opp.scores[wk_idx]
            if not ts and not os_:  # unplayed / bye (0-0 never happens in fantasy)
                continue
            seen.add(key)
            # home/away is meaningless for fantasy scoring; assign deterministically.
            home, away = (team, opp) if team.team_id < opp.team_id else (opp, team)
            hs = home.scores[wk_idx]
            as_ = away.scores[wk_idx]
            matchups.append({
                "week": week,
                "home": team_to_fid[home.team_id],
                "away": team_to_fid[away.team_id],
                "home_score": round(hs, 2),
                "away_score": round(as_, 2),
                "playoff": week > reg_season_count,
            })
    matchups.sort(key=lambda m: (m["week"], m["home"]))
    return matchups


def dump_season_yaml(year, reg_count, final_order, matchups, teams):
    lines = [
        f"# {year} — imported from ESPN by scripts/import_espn.py. Do not hand-edit;",
        f"# re-run the importer to refresh. See ../../ARCHITECTURE.md.",
        "",
        f"season: {year}",
        "source: espn-api",
        f"weeks_in_regular_season: {reg_count}",
        "",
        "# This season's team name for each franchise (shown on per-season pages).",
        "teams:",
    ]
    lines += [f'  {fid}: "{name}"' for fid, name in teams.items()]
    lines += [
        "",
        "# Final placement (ESPN's rankCalculatedFinal), used for the finish column.",
        "final_standings:",
    ]
    lines += [f"  - {fid}" for fid in final_order]
    lines += ["", "matchups:"]
    for m in matchups:
        pf = "true" if m["playoff"] else "false"
        lines.append(
            f"  - {{ week: {m['week']:>2}, home: {m['home']}, away: {m['away']}, "
            f"home_score: {m['home_score']}, away_score: {m['away_score']}, playoff: {pf} }}"
        )
    return "\n".join(lines) + "\n"


def validation_table(matchups, team_to_fid):
    tally = {}
    for m in matchups:
        if m["playoff"]:
            continue
        h, a = m["home"], m["away"]
        hs, as_ = m["home_score"], m["away_score"]
        for fid in (h, a):
            tally.setdefault(fid, {"w": 0, "l": 0, "t": 0, "pf": 0.0})
        tally[h]["pf"] += hs
        tally[a]["pf"] += as_
        if hs > as_:
            tally[h]["w"] += 1; tally[a]["l"] += 1
        elif as_ > hs:
            tally[a]["w"] += 1; tally[h]["l"] += 1
        else:
            tally[h]["t"] += 1; tally[a]["t"] += 1
    rows = sorted(tally.items(), key=lambda kv: (kv[1]["w"], kv[1]["pf"]), reverse=True)
    out = ["  reg-season record   PF      franchise"]
    for fid, r in rows:
        rec = f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
        out.append(f"  {rec:<12} {r['pf']:>8.1f}   {fid}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Import an ESPN season into season YAML.")
    ap.add_argument("year", type=int)
    ap.add_argument("--league-id", type=int, default=LEAGUE_ID)
    ap.add_argument("--stdout", action="store_true", help="print YAML, write nothing")
    args = ap.parse_args()

    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")
    league = League(league_id=args.league_id, year=args.year, espn_s2=espn_s2, swid=swid)

    reg_count = league.settings.reg_season_count
    teams = league.teams

    registry = load_franchises()
    team_to_fid = resolve_franchises(teams, registry)
    matchups = build_matchups(teams, team_to_fid, reg_count)

    final_sorted = sorted(teams, key=lambda t: getattr(t, "final_standing", 0) or 999)
    final_order = [team_to_fid[t.team_id] for t in final_sorted]
    season_teams = {team_to_fid[t.team_id]: clean_name(t.team_name) for t in teams}

    season_yaml = dump_season_yaml(args.year, reg_count, final_order, matchups, season_teams)

    if not any(o for _, o in map(owner_of, teams)):
        print("WARNING: no owner names/SWIDs found — franchise ids fell back to team "
              "names and won't link across seasons. Set ESPN_S2 / ESPN_SWID for a "
              "private league.\n", file=sys.stderr)

    print(f"Parsed {args.year}: {len(teams)} teams, {len(matchups)} matchups, "
          f"{reg_count} regular-season weeks.\n", file=sys.stderr)
    print("Computed regular-season standings (verify against the ESPN final standings):",
          file=sys.stderr)
    print(validation_table(matchups, team_to_fid) + "\n", file=sys.stderr)

    if args.stdout:
        print(season_yaml)
        return

    out_path = SEASONS_DIR / f"{args.year}.yml"
    out_path.write_text(season_yaml, encoding="utf-8")
    FRANCHISES_PATH.write_text(
        "# Owner -> franchise mapping, maintained by scripts/import_espn.py.\n"
        "# `id` is stable across seasons (keyed off the owner's ESPN SWID). Edit\n"
        "# `name` freely; add `aliases` if a team name is missing.\n\n"
        + yaml.safe_dump(registry, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {out_path.relative_to(ROOT)} and updated data/franchises.yml", file=sys.stderr)
    print("Next: python scripts/build.py  (then git diff to review)", file=sys.stderr)


if __name__ == "__main__":
    main()
