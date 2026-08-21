#!/usr/bin/env python3
"""Import one season from ESPN into data/seasons/<year>.yml.

This is a LOCAL dev tool, not part of the published site. It pulls a season
through `the_league_espn_api` — The League's own dependency-free ESPN client
(see requirements-dev.txt) — then writes:

  - data/seasons/<year>.yml  : matchups + standings order + season metadata
  - data/franchises.yml       : owner -> franchise mapping, merged by ESPN SWID

Nothing here runs at site-build time; the site only reads the YAML it produces.

Usage:
    python scripts/import_espn.py 2025            # write the files
    python scripts/import_espn.py 2025 --stdout   # preview YAML, write nothing

Private league? Put your two ESPN cookies in .espn-cookies (see
.espn-cookies.example). The client reads them from there — nothing to export.

Franchise identity: every team is keyed by its owner's ESPN SWID (`manager_id`),
so the same person keeps one franchise across seasons even as their team name
changes. The client returns owner names only when cookies are supplied.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

try:
    from the_league_espn_api import League, ApiError, merge_trades, load_cookies
except ImportError:
    sys.exit("the-league-espn-api is not installed. Run: pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parent.parent
SEASONS_DIR = ROOT / "data" / "seasons"
FRANCHISES_PATH = ROOT / "data" / "franchises.yml"
COOKIES_PATH = ROOT / ".espn-cookies"
# Extra managers' cookie files. ESPN reveals a trade's contents only to its
# participants, so merging several managers' accounts fills in more trades.
COOKIES_DIR = ROOT / ".cookies"


def cookie_files():
    """All cookie files to merge trades across: the default `.espn-cookies`
    plus every file in `.cookies/`. Returns absolute path strings; empty when
    none exist (the client then falls back to env vars)."""
    files = []
    if COOKIES_PATH.is_file():
        files.append(str(COOKIES_PATH))
    if COOKIES_DIR.is_dir():
        files += sorted(str(p) for p in COOKIES_DIR.iterdir()
                        if p.is_file() and "cookie" in p.name.lower())
    return files


def clean_name(text):
    """Collapse ESPN's stray double-spaces / trailing spaces in a team name."""
    return re.sub(r"\s+", " ", text or "").strip()


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "unknown"


def load_franchises():
    if FRANCHISES_PATH.exists():
        data = yaml.safe_load(FRANCHISES_PATH.read_text()) or []
        return data if isinstance(data, list) else []
    return []


def existing_draft_order(year):
    """The hand-edited `draft_order` already in a season's file, so re-imports
    preserve it (the importer owns every other field, but not this one)."""
    path = SEASONS_DIR / f"{year}.yml"
    if path.exists():
        data = yaml.safe_load(path.read_text()) or {}
        return data.get("draft_order") or []
    return []


def resolve_franchises(team_rows, registry):
    """Map each team_id -> franchise id, updating `registry` (list of dicts).

    Matches an existing franchise by SWID so the same owner keeps one id across
    seasons; records each season's team name as an alias. A brand-new owner is
    seeded with their first name (our public display convention).
    """
    by_swid = {f["espn_swid"]: f for f in registry if f.get("espn_swid")}
    used_ids = {f["id"] for f in registry}
    team_to_fid = {}

    for t in team_rows:
        swid = t.get("manager_id") or None
        team_name = clean_name(t.get("team_name"))
        display = (t.get("first_name") or "").strip() or clean_name(t.get("user_name")) or team_name
        entry = by_swid.get(swid) if swid else None

        if entry is None:
            base = slug(display or team_name)
            fid = base
            i = 2
            while fid in used_ids and not swid:
                fid, i = f"{base}-{i}", i + 1
            entry = {"id": fid, "name": display or team_name, "aliases": []}
            if swid:
                entry["espn_swid"] = swid
                by_swid[swid] = entry
            registry.append(entry)
            used_ids.add(fid)

        if display and (not entry.get("name") or entry["name"] == entry["id"]):
            entry["name"] = display
        if team_name and team_name not in entry.setdefault("aliases", []):
            entry["aliases"].append(team_name)

        team_to_fid[t["team_id"]] = entry["id"]

    return team_to_fid


def _pick_label(overall, team_count):
    """A traded draft pick as 'round.pick' (e.g. 1.11), from its overall number."""
    try:
        o = int(overall)
    except (TypeError, ValueError):
        return "draft pick"
    if team_count and team_count > 0:
        rnd, pir = (o - 1) // team_count + 1, (o - 1) % team_count + 1
        return f"{rnd}.{pir:02d} pick"
    return f"pick {o}"


def build_trades(trade_rows, team_to_fid, team_count):
    """Group the client's per-asset trade rows into one entry per completed trade,
    franchise-keyed: {week, teams (participants), assets [{from, to, label}]}.

    ESPN only reveals a trade's contents to its participants, so trades the
    merged accounts didn't take part in come back with `contents_available:
    False`. We keep those too, marked `complete: false` with `assets: []` and
    only the accepting franchise in `teams` (the one side ESPN does tell us) —
    so the trade still counts, but downstream knows its details are unknown.
    Every entry has an explicit `complete` flag."""
    from collections import defaultdict
    groups = defaultdict(list)
    for r in trade_rows:
        groups[r["trade_id"]].append(r)

    trades = []
    for items in groups.values():
        week = items[0].get("scoring_period") or 0
        participants, assets = set(), []
        for r in items:
            if r.get("asset_type") not in ("player", "draft_pick"):
                continue  # 'unavailable' row — no item detail for this account
            f = team_to_fid.get(r.get("from_team_id"))
            t = team_to_fid.get(r.get("to_team_id"))
            for fid in (f, t):
                if fid:
                    participants.add(fid)
            if r.get("asset_type") == "player":
                label = r.get("player_name") or "player"
            else:
                label = _pick_label(r.get("draft_pick_overall"), team_count)
            assets.append({"from": f, "to": t, "label": label})

        if assets:
            # Fully detailed — no `complete` flag needed (absent == complete).
            trades.append({
                "week": week,
                "teams": sorted(participants),
                "assets": assets,
            })
        else:
            # Contents unknown to us: record it with just the accepting side so
            # the trade is still counted, flagged incomplete.
            acceptor = next((team_to_fid.get(r.get("to_team_id")) for r in items
                             if team_to_fid.get(r.get("to_team_id"))), None)
            trades.append({
                "week": week,
                "teams": [acceptor] if acceptor else [],
                "assets": [],
                "complete": False,
            })
    trades.sort(key=lambda x: (x["week"], x["teams"]))
    return trades


def build_matchups(matchup_rows, team_to_fid):
    """Franchise-keyed regular-season + playoff games, skipping byes and unplayed
    weeks. Home/away is cosmetic in fantasy, so it's assigned deterministically by
    team id to keep re-imports diff-clean."""
    out = []
    for m in matchup_rows:
        if m.get("winner") == "BYE":
            continue
        h_id, a_id = m.get("home_team_id"), m.get("away_team_id")
        if not h_id or not a_id:
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if not hs and not as_:      # unplayed / future week (0-0 never happens live)
            continue
        if a_id < h_id:             # normalize: lower team id is "home"
            h_id, a_id, hs, as_ = a_id, h_id, as_, hs
        out.append({
            "week": m["week"],
            "home": team_to_fid.get(h_id),
            "away": team_to_fid.get(a_id),
            "home_score": round(float(hs), 2),
            "away_score": round(float(as_), 2),
            "playoff": bool(m.get("is_playoff")),
        })
    out.sort(key=lambda x: (x["week"], x["home"] or ""))
    return out


def dump_season_yaml(year, reg_count, final_order, matchups, teams, playoff_teams,
                     status=None, draft_order=None, trades=None, trades_complete=True,
                     trades_known_for=None):
    lines = [
        f"# {year} — imported from ESPN by scripts/import_espn.py. Re-run the importer",
        f"# to refresh; only the hand-edited `draft_order:` below is preserved across",
        f"# imports. See ../../ARCHITECTURE.md.",
        "",
        f"season: {year}",
        "source: the-league-espn-api",
        f"weeks_in_regular_season: {reg_count}",
    ]
    if status:
        lines += [
            "",
            "# Season still in progress: standings reflect the current order and this",
            "# season is left out of all-time stats until it's re-imported as final.",
            f"status: {status}",
        ]
    lines += [
        "",
        "# Draft order (1st overall pick first), franchise ids. Optional and HAND-",
        "# EDITED — preserved across re-imports; remove the block to hide the draft",
        "# table on the season page.",
    ]
    if draft_order:
        lines += ["draft_order:"] + [f"  - {fid}" for fid in draft_order]
    else:
        lines += ["draft_order: []"]
    lines += [
        "",
        "# This season's team name for each franchise (shown on per-season pages).",
        "teams:",
    ]
    lines += [f'  {fid}: "{name}"' for fid, name in teams.items()]
    lines += [
        "",
        "# Franchises seeded into the winners bracket (ESPN playoffSeed <= playoff",
        "# team count), in seed order. Used for the 'made the playoffs' count.",
    ]
    if playoff_teams:
        lines += ["playoff_teams:"] + [f"  - {fid}" for fid in playoff_teams]
    else:
        lines += ["playoff_teams: []  # not seeded yet"]
    lines += [
        "",
        "# Final placement (ESPN's rankCalculatedFinal), used for the finish column.",
    ]
    if final_order:
        lines += ["final_standings:"] + [f"  - {fid}" for fid in final_order]
    else:
        lines += ["final_standings: []"]
    if matchups:
        lines += ["", "matchups:"]
        for m in matchups:
            pf = "true" if m["playoff"] else "false"
            lines.append(
                f"  - {{ week: {m['week']:>2}, home: {m['home']}, away: {m['away']}, "
                f"home_score: {m['home_score']}, away_score: {m['away_score']}, playoff: {pf} }}"
            )
    else:
        lines += ["", "matchups: []  # no games played yet"]
    lines += [
        "",
        "# Completed trades this season (franchise-keyed). ESPN reveals a trade's",
        "# contents only to its participants, so trades no merged account was in",
        "# come through as `complete: false` with empty assets and just the",
        "# accepting franchise — counted (shown as 'Trade Accepted'), but the",
        "# players/picks are unknown. `trades_complete` is true only when every",
        "# trade this season is fully detailed. `trades_known_for` lists the",
        "# franchises whose manager cookie was merged: their count is EXACT even",
        "# in an incomplete season (an undetailed trade is one they weren't in),",
        "# while everyone else's count is a floor ('at least N'). Merge more",
        "# managers' cookies (.cookies/) to fill gaps.",
        f"trades_complete: {'true' if trades_complete else 'false'}",
    ]
    if trades_known_for:
        lines += ["trades_known_for:"] + [f"  - {fid}" for fid in trades_known_for]
    else:
        lines += ["trades_known_for: []  # no manager cookie tied to a franchise"]
    if trades:
        # Nested structure — let PyYAML format it rather than hand-align by string.
        lines.append(yaml.safe_dump({"trades": trades}, sort_keys=False,
                                    allow_unicode=True, default_flow_style=False).rstrip())
    else:
        lines += ["trades: []  # none this season"]
    return "\n".join(lines) + "\n"


def validation_table(matchups):
    """Regular-season W-L-PF tally from the matchups, for eyeballing vs ESPN."""
    tally = {}
    for m in matchups:
        if m["playoff"]:
            continue
        h, a, hs, as_ = m["home"], m["away"], m["home_score"], m["away_score"]
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
    ap.add_argument("--league-id", type=int, default=None,
                    help="override the default league id")
    ap.add_argument("--stdout", action="store_true", help="print YAML, write nothing")
    args = ap.parse_args()

    cookies_file = os.environ.get("ESPN_COOKIES_FILE") or str(COOKIES_PATH)
    lg_kwargs = {"year": args.year, "cookies_file": cookies_file}
    if args.league_id:
        lg_kwargs["league_id"] = args.league_id
    lg = League(**lg_kwargs)

    team_rows = lg.teams()
    season = lg.season()                    # {complete, standings, matchups}
    settings = lg.league_json("mSettings").get("settings", {})
    sched = settings.get("scheduleSettings", {})
    complete = season["complete"]
    standings = season["standings"]

    registry = load_franchises()
    team_to_fid = resolve_franchises(team_rows, registry)
    matchups = build_matchups(season["matchups"], team_to_fid)

    # Trades: ESPN reveals a trade's contents only to its participants, so merge
    # across every managers' cookie file we have — more accounts detail more
    # trades. The transactions endpoint 404s for very old seasons; treat that as
    # "trades unknown this year" rather than failing the whole import.
    files = cookie_files() or [cookies_file]
    # SWID -> franchise id, so a manager's cookie can be tied to their franchise.
    # ESPN returns the owner SWID (manager_id) and the cookie's ESPN_SWID in the
    # same braced form; normalise both just in case.
    def _norm_swid(s):
        return (s or "").strip().strip("{}").upper()
    swid_to_fid = {}
    for t in team_rows:
        swid = _norm_swid(t.get("manager_id"))
        if swid and t.get("team_id") in team_to_fid:
            swid_to_fid[swid] = team_to_fid[t["team_id"]]

    trade_lists, fetched = [], False
    known_for = set()   # franchises whose manager cookie detailed this season
    for cf in files:
        tkw = {"year": args.year, "cookies_file": cf}
        if args.league_id:
            tkw["league_id"] = args.league_id
        try:
            trade_lists.append(League(**tkw).trades())
            fetched = True
        except ApiError as e:
            print(f"NOTE: trades for {args.year} via {os.path.basename(cf)} "
                  f"unavailable (ESPN {e.status}).", file=sys.stderr)
            continue
        # This cookie's owner participated in nothing they couldn't see, so their
        # count is exact for this season — record their franchise as "known".
        _, cf_swid = load_cookies(cf)
        fid = swid_to_fid.get(_norm_swid(cf_swid))
        if fid:
            known_for.add(fid)
    trade_rows = merge_trades(*trade_lists) if trade_lists else []
    trades = build_trades(trade_rows, team_to_fid, len(team_to_fid))
    # Complete only if we fetched trades AND every one came back fully detailed.
    trades_complete = fetched and all(t.get("complete", True) for t in trades)
    incomplete = sum(1 for t in trades if not t.get("complete", True))

    reg_count = (sched.get("matchupPeriodCount")
                 or max((m["week"] for m in matchups if not m["playoff"]), default=0))

    # Final placement when complete; otherwise the current standing (wins, PF).
    if complete:
        ordered = sorted(standings, key=lambda r: r.get("final_rank") or 999)
    else:
        ordered = sorted(standings, key=lambda r: (-(r.get("wins") or 0),
                                                   -(r.get("points_for") or 0.0)))
    final_order = [team_to_fid.get(r["team_id"]) for r in ordered]

    season_teams = {team_to_fid[t["team_id"]]: clean_name(t["team_name"]) for t in team_rows}

    # Winners-bracket seeds = ESPN playoffSeed within 1..playoffTeamCount.
    playoff_count = sched.get("playoffTeamCount") or 0
    seeded = sorted(
        (r for r in standings if 0 < (r.get("playoff_seed") or 0) <= playoff_count),
        key=lambda r: r["playoff_seed"],
    )
    playoff_ids = [team_to_fid.get(r["team_id"]) for r in seeded]

    season_yaml = dump_season_yaml(args.year, reg_count, final_order, matchups,
                                   season_teams, playoff_ids,
                                   status=None if complete else "in_progress",
                                   draft_order=existing_draft_order(args.year),
                                   trades=trades, trades_complete=trades_complete,
                                   trades_known_for=sorted(known_for))

    if not lg.authenticated:
        print("WARNING: no ESPN cookies found — a private league won't return owner "
              "names/SWIDs, so franchises can't link across seasons. Fill in "
              ".espn-cookies.\n", file=sys.stderr)

    trade_note = ("all detailed" if trades_complete
                  else f"{incomplete} unavailable — merge more cookies" if fetched
                  else "not fetched for this season")
    print(f"Parsed {args.year}: {len(team_rows)} teams, {len(matchups)} matchups, "
          f"{len(trades)} trades ({trade_note}), {reg_count} regular-season weeks — "
          f"{'COMPLETE' if complete else 'IN PROGRESS (ordered by current standing)'}.\n",
          file=sys.stderr)
    print("Computed regular-season standings (verify against ESPN's final standings):",
          file=sys.stderr)
    print(validation_table(matchups) + "\n", file=sys.stderr)

    if args.stdout:
        print(season_yaml)
        return

    out_path = SEASONS_DIR / f"{args.year}.yml"
    out_path.write_text(season_yaml, encoding="utf-8")
    FRANCHISES_PATH.write_text(
        "# Owner -> franchise mapping, maintained by scripts/import_espn.py.\n"
        "# `id` is stable across seasons (keyed off the owner's ESPN SWID). Names are\n"
        "# first-name-only by choice — no last names on the public site. Edit `name`\n"
        "# and `nickname` freely; `nickname` shows as the tagline on the owner's\n"
        "# profile. Add `aliases` if a team name is missing.\n\n"
        + yaml.safe_dump(registry, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote {out_path.relative_to(ROOT)} and updated data/franchises.yml", file=sys.stderr)
    print("Next: python scripts/build.py  (then git diff to review)", file=sys.stderr)


if __name__ == "__main__":
    main()
