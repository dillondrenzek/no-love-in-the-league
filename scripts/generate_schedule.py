#!/usr/bin/env python3
"""Generate a fresh, fair regular-season schedule for a year and print it.

The league reshuffles its schedule every year (see the rulebook). This builds a
balanced one — full round-robin plus 3 rematch weeks, everyone plays everyone at
least once and exactly three opponents twice — using the franchises in that
season's data file. It only prints; entering it into ESPN is a manual (or
browser-driven) step.

    .venv/bin/python scripts/generate_schedule.py            # current year
    .venv/bin/python scripts/generate_schedule.py 2026
    .venv/bin/python scripts/generate_schedule.py 2026 --seed 7   # reroll
    .venv/bin/python scripts/generate_schedule.py 2026 --csv schedule.csv

The seed defaults to the year, so a year is reproducible; pass --seed to reroll.
"""

import argparse
import csv
import datetime
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.schedule import generate_schedule, validate, per_team

ROOT = Path(__file__).resolve().parent.parent
SEASONS_DIR = ROOT / "data" / "seasons"
FRANCHISES_PATH = ROOT / "data" / "franchises.yml"
WEEKS_DEFAULT = 14


def short_names():
    fr = yaml.safe_load(open(FRANCHISES_PATH)) or []
    out = {}
    for f in fr:
        out[f["id"]] = f.get("short") or f["name"].split()[0]
    return out


def season_teams(year):
    path = SEASONS_DIR / f"{year}.yml"
    if not path.is_file():
        sys.exit(f"No season file at {path.relative_to(ROOT)} — need its team list.")
    d = yaml.safe_load(open(path)) or {}
    teams = list((d.get("teams") or {}).keys())
    if len(teams) < 2:
        sys.exit(f"{path.name} has no teams to schedule.")
    weeks = d.get("weeks_in_regular_season") or WEEKS_DEFAULT
    return teams, weeks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("year", nargs="?", type=int, default=datetime.date.today().year)
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed (default: the year). Change it to reroll.")
    ap.add_argument("--weeks", type=int, default=None,
                    help="override regular-season week count")
    ap.add_argument("--csv", type=str, default=None,
                    help="also write the schedule to this CSV (week,home,away)")
    args = ap.parse_args()

    teams, weeks = season_teams(args.year)
    weeks = args.weeks or weeks
    seed = args.seed if args.seed is not None else args.year
    names = short_names()
    name = lambda fid: names.get(fid, fid)

    schedule = generate_schedule(teams, weeks=weeks, seed=seed)
    validate(schedule, teams, weeks)

    print(f"{args.year} schedule — {len(teams)} teams, {weeks} weeks, seed {seed}\n")
    for wi, wk in enumerate(schedule, 1):
        print(f"Week {wi:>2}")
        for home, away in wk:
            print(f"    {name(home):<9} vs {name(away)}")
    print("\nEach team's rematches (opponents played twice):")
    stats = per_team(schedule)
    for fid in sorted(teams, key=name):
        twice = ", ".join(name(o) for o in stats[fid]["twice"])
        print(f"  {name(fid):<9} plays twice: {twice}")

    print(f"\nBalanced: every team plays {weeks} games, "
          f"{weeks - (len(teams) - 1)} opponents twice, the rest once.")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["week", "home", "away", "home_owner", "away_owner"])
            for wi, wk in enumerate(schedule, 1):
                for home, away in wk:
                    w.writerow([wi, home, away, name(home), name(away)])
        print(f"\nWrote {args.csv}")


if __name__ == "__main__":
    main()
