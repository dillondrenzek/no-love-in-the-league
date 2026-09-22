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

Then point your agent at agents/weekly-power.md; it reads the facts file plus the
season's prior editions and returns a blurb per team. Paste each blurb into the
data/power file, then rebuild — the week page renders rank + movement (computed) +
your blurbs.
"""

import argparse
import sys
from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, short_name_of,
                      load_power_blurbs, load_projections)
from lib.power import power_rankings, _metrics_before
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


def _facts(season, week, franchises, rows):
    year = season["season"]
    metrics = _metrics_before(season, week)
    lines = [
        f"# Power Rankings facts — {year} Week {week}",
        "",
        "Computed order and movement are FINAL — do not reorder. Write one short,",
        "punchy blurb per team justifying its spot and its move. Read the season's",
        "prior editions in docs/seasons/ for continuity and running bits.",
        "",
    ]
    for r in rows:
        avg, last3, winpct = metrics.get(r["fid"], (0, 0, 0))
        opp = _opponent(season, franchises, r["fid"], week)
        lines.append(
            f"{r['rank']}. {r['team']} ({r['owner']}) — {_move_str(r)}; "
            f"avg {avg:.1f} PF, last-3 avg {last3:.1f}, win% {winpct:.3f}; "
            f"this week vs {opp}. [fid: {r['fid']}]")
    return "\n".join(lines) + "\n"


def _scaffold_blurbs(year, week, rows):
    POWER_DIR.mkdir(parents=True, exist_ok=True)
    path = POWER_DIR / f"{year}-week-{week:02d}.yml"
    existing = load_power_blurbs(year, week)
    lines = [
        f"# Power-ranking blurbs — {year} week {week}. One line per team, in the",
        "# computed rank order. Fill from the agent (agents/weekly-power.md), then",
        "# rebuild. Keyed by franchise id; the comment shows rank + team.",
        "blurbs:",
    ]
    for r in rows:
        val = existing.get(r["fid"], "")
        dumped = yaml.safe_dump(val, default_flow_style=True).strip()
        lines.append(f"  {r['fid']}: {dumped}   # {r['rank']}. {r['team']}")
    path.write_text("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser(description="Prep a week's power rankings.")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season data for {args.year}.")

    rows = power_rankings(season, args.week, franchises,
                          load_power_blurbs(args.year, args.week))
    if not rows:
        sys.exit(f"Week {args.week} can't be ranked yet (no completed games "
                 "before it).")

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    facts = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.power.data.md"
    facts.write_text(_facts(season, args.week, franchises, rows))
    blurbs = _scaffold_blurbs(args.year, args.week, rows)

    print(f"Wrote {facts.relative_to(ROOT)}")
    print(f"Scaffolded {blurbs.relative_to(ROOT)}")
    print(f"Next: have your agent ({AGENT_SPEC.relative_to(ROOT)}) write the "
          "blurbs, paste them into the data/power file, and rebuild.")


if __name__ == "__main__":
    main()
