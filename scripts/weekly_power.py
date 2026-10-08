#!/usr/bin/env python3
"""Prep a week's *power rankings*: the computed order + movement, plus a facts
file for the agent that writes the one-line blurbs.

Companion to weekly_preview.py — publish it around the same time. The order and
week-over-week movement are computed (lib/power); the agent only writes the blurb
for each team. This script:

  1. writes recaps/<year>-week-NN.power.data.md — the facts the agent works from,
  2. scaffolds data/power/<year>-week-NN.yml — the blurbs file, in rank order with
     empty blurbs (never overwrites one that already has content).

    python scripts/weekly_power.py 2026 2

Run it shortly before the week's Thursday kickoff: it refuses unless the prior
week is final and this week hasn't started (pass --force to override). The week
page shows the rankings as soon as the data/power file exists, so generating them
*is* publishing them on the next build.

Then point your agent at agents/weekly-power.md; it reads the facts file plus the
season's prior editions and returns a blurb per team. Paste each blurb into the
data/power file, then rebuild — the week page renders rank + movement (computed) +
your blurbs.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, short_name_of,
                      load_power_blurbs, load_power_order, load_projections,
                      load_week_rosters)
from lib.context import week_roster_context, bye_note
from lib.power import week_power_rankings, prep_window_problem, _metrics_before
from lib.weeks import _games_in_week

ROOT = Path(__file__).resolve().parent.parent
AGENT_SPEC = ROOT / "agents" / "weekly-power.md"
PROMPT_DIR = ROOT / "recaps"
POWER_DIR = ROOT / "data" / "power"


def _move_str(r):
    if r["is_new"]:
        return "NEW"
    if r["movement"] > 0:
        return f"up {r['movement']}"
    if r["movement"] < 0:
        return f"down {-r['movement']}"
    return "even"


def _opponent(season, franchises, fid, week):
    for m in _games_in_week(season, week):
        if m["home"] == fid:
            return short_name_of(m["away"], franchises)
        if m["away"] == fid:
            return short_name_of(m["home"], franchises)
    return "—"


def _facts(season, week, franchises, rows, injuries=None, byes=None):
    year = season["season"]
    metrics = _metrics_before(season, week)
    injuries = injuries or {}
    byes = byes or {}
    lines = [
        f"# Power Rankings facts — {year} Week {week}",
        "",
        "Computed order and movement are FINAL — do not reorder. Write one short,",
        "punchy blurb per team justifying its spot and its move. Read the season's",
        "prior editions in docs/seasons/ for continuity and running bits.",
        "The ranking comes only from games already played; this week's opponent",
        "is listed so a blurb can mention it, never as a reason for the rank.",
        "Credit players by what they actually did: an OUT/IR player listed below did",
        "not contribute, so don't praise a team for his production.",
        "Byes: players whose NFL team is off this week are listed per team — a",
        "fair mention (a thin week ahead), never a reason for the rank.",
        "",
    ]
    for r in rows:
        avg, last3, winpct = metrics.get(r["fid"], (0, 0, 0))
        opp = _opponent(season, franchises, r["fid"], week)
        inj = injuries.get(r["fid"]) or []
        inj_note = ("; OUT/inactive: "
                    + ", ".join(f"{p['player']} ({p['status']})" for p in inj)
                    ) if inj else ""
        bn = bye_note(byes.get(r["fid"]))
        bye_str = f"; on bye this week: {bn}" if bn else ""
        lines.append(
            f"{r['rank']}. {r['team']} ({r['owner']}) — {_move_str(r)}; "
            f"avg {avg:.1f} PF, last-3 avg {last3:.1f}, win% {winpct:.3f}; "
            f"this week vs {opp}{inj_note}{bye_str}. [fid: {r['fid']}]")
    return "\n".join(lines) + "\n"


def _scaffold_blurbs(year, week, rows):
    POWER_DIR.mkdir(parents=True, exist_ok=True)
    path = POWER_DIR / f"{year}-week-{week:02d}.yml"
    # Never clobber a hand-authored editorial file: if it sets its own `order:`,
    # the rank is the author's call (e.g. the preseason board), not the computed
    # one, and re-scaffolding would reorder and reformat it. Leave it as-is.
    if load_power_order(year, week):
        print(f"  {path.relative_to(ROOT)} has an editorial order: — left untouched.",
              file=sys.stderr)
        return path
    existing = load_power_blurbs(year, week)
    lines = [
        f"# Power-ranking blurbs — {year} week {week}. One line per team, in the",
        "# computed rank order. Fill from the agent (agents/weekly-power.md), then",
        "# rebuild. Keyed by franchise id; the comment shows rank + team.",
        "blurbs:",
    ]
    for r in rows:
        val = existing.get(r["fid"], "")
        # A JSON string is a valid one-line YAML scalar; yaml.safe_dump would wrap
        # a long blurb onto a second line, which breaks the trailing # comment.
        dumped = json.dumps(val, ensure_ascii=False)
        lines.append(f"  {r['fid']}: {dumped}   # {r['rank']}. {r['team']}")
    path.write_text("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description="Prep a week's power rankings.")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("--force", action="store_true",
                    help="generate even outside the pre-kickoff window")
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season data for {args.year}.")

    problem = prep_window_problem(season, args.week)
    if problem and not args.force:
        sys.exit(f"{problem} (Use --force to generate anyway.)")

    rows = week_power_rankings(season, args.week, franchises)
    if not rows:
        sys.exit(f"Week {args.week} can't be ranked yet (no completed games "
                 "before it).")

    # Current injury/inactive context, from the freshest roster snapshot available
    # (this week's if captured, else last week's). Lets blurbs credit players by who
    # actually suited up and flag a manager's IR/Out burden.
    wr = (load_week_rosters(args.year, args.week, franchises)
          or load_week_rosters(args.year, args.week - 1, franchises))
    # Bye weeks are static per player, so last week's snapshot can still say who's
    # off this week.
    inj_ctx = week_roster_context(wr, want_actual=True, week=args.week) if wr else {}
    injuries = {fid: e.get("injured") or [] for fid, e in inj_ctx.items()}

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    facts = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.power.data.md"
    facts.write_text(_facts(season, args.week, franchises, rows, injuries, inj_ctx))
    blurbs = _scaffold_blurbs(args.year, args.week, rows)

    print(f"Wrote {facts.relative_to(ROOT)}")
    print(f"Scaffolded {blurbs.relative_to(ROOT)}")
    print(f"Next: have your agent ({AGENT_SPEC.relative_to(ROOT)}) write the "
          "blurbs, paste them into the data/power file, and rebuild.")


if __name__ == "__main__":
    main()
