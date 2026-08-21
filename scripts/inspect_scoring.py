#!/usr/bin/env python3
"""History of scoring and roster-construction changes across the league.

A quick read-only diagnostic that hits ESPN live and prints, season by season,
every change in scoring (points per stat) and roster construction (lineup slot
counts), plus a consolidated change timeline. Shares its stat/slot labels and
diff logic with scripts/lib/rules.py, the same code that builds the rulebook.

For the *site* version of this data, use scripts/import_settings.py (writes
data/settings.yml) + scripts/build.py — see scripts/refresh_rules.sh. This
script just prints; it writes nothing.

    .venv/bin/python scripts/inspect_scoring.py
    .venv/bin/python scripts/inspect_scoring.py 2008 2026   # custom span
    .venv/bin/python scripts/inspect_scoring.py --full      # also dump each year
    .venv/bin/python scripts/inspect_scoring.py --raw=98    # raw item for a stat id
    .venv/bin/python scripts/inspect_scoring.py --raw       # raw for the defensive set

`--raw` prints each requested stat's raw ESPN scoring item (points,
pointsOverrides, isReverseItem) per season — handy for confirming where ESPN
stored a value (e.g. the post-2023 move of the value into pointsOverrides).
"""

import os
import sys
from pathlib import Path

try:
    from the_league_espn_api import League, ApiError
except ImportError:
    sys.exit("the-league-espn-api is not installed. Run: pip install -r requirements-dev.txt")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.rules import (scoring_map_from_settings, roster_map_from_settings,
                       format_from_settings, scoring_rows, roster_view,
                       stat_name, slot_name, _diff)

ROOT = Path(__file__).resolve().parent.parent
COOKIES = os.environ.get("ESPN_COOKIES_FILE") or str(ROOT / ".espn-cookies")


def fetch_settings(year):
    return (League(year=year, cookies_file=COOKIES)
            .league_json("mSettings") or {}).get("settings", {})


def fetch(year):
    settings = fetch_settings(year)
    return (scoring_map_from_settings(settings),
            roster_map_from_settings(settings),
            format_from_settings(settings))


# Defaults for --raw with no ids: the defensive/special-teams set most affected
# by ESPN's scoring-format change.
DEFAULT_RAW_IDS = [95, 96, 97, 98, 99, 106, 109]


def raw_dump(years, ids):
    ids = ids or DEFAULT_RAW_IDS
    for year in years:
        try:
            settings = fetch_settings(year)
        except ApiError as e:
            print(f"=== {year} === unavailable ({e})")
            continue
        items = {int(i["statId"]): i
                 for i in settings.get("scoringSettings", {}).get("scoringItems", [])}
        print(f"=== {year} ===")
        for sid in ids:
            it = items.get(sid)
            if it is None:
                print(f"  {sid:>3} {stat_name(sid)}: (not in scoringItems)")
            else:
                print(f"  {sid:>3} {stat_name(sid)}: points={it.get('points')} "
                      f"overrides={it.get('pointsOverrides')} "
                      f"reverse={it.get('isReverseItem')}")
        print()


def print_full(smap, rmap, ftype):
    print(f"  format: {ftype}")
    print("  scoring (non-zero):")
    for s in scoring_rows(smap):
        print(f"    {s['label']}: {s['points']}")
    print(f"  roster: {roster_view(rmap)['summary']}")


def season_years():
    d = ROOT / "data" / "seasons"
    if d.is_dir():
        ys = sorted(int(p.stem) for p in d.glob("*.yml") if p.stem.isdigit())
        if ys:
            return ys
    return list(range(2010, 2027))


def main():
    full = False
    raw_mode = False
    raw_ids = None
    argv = []
    for a in sys.argv[1:]:
        if a == "--full":
            full = True
        elif a == "--raw" or a.startswith("--raw="):
            raw_mode = True
            val = a.split("=", 1)[1] if "=" in a else ""
            raw_ids = [int(x) for x in val.split(",") if x.strip()] or None
        else:
            argv.append(a)
    years = list(range(int(argv[0]), int(argv[1]) + 1)) if len(argv) == 2 else season_years()

    if raw_mode:
        raw_dump(years, raw_ids)
        return

    prev = None
    timeline = []
    for year in years:
        try:
            smap, rmap, ftype = fetch(year)
        except ApiError as e:
            print(f"{year}: unavailable ({e})")
            continue

        if prev is None:
            print(f"=== {year} (baseline) ===")
            print_full(smap, rmap, ftype)
            print()
        else:
            py, psmap, prmap, pftype = prev
            changes = []
            if pftype != ftype:
                changes.append(f"scoring format: {pftype} -> {ftype}")
            changes += [i["text"] for i in _diff(psmap, smap, stat_name, "scoring")]
            changes += [i["text"] for i in _diff(prmap, rmap, slot_name, "roster")]
            print(f"=== {year}: changes from {py} ===")
            if changes:
                for ch in changes:
                    print(f"  {ch}")
                timeline.append((year, changes))
            else:
                print("  (no scoring or roster changes)")
            if full:
                print_full(smap, rmap, ftype)
            print()

        prev = (year, smap, rmap, ftype)

    print("=" * 48)
    print("CHANGE TIMELINE")
    if timeline:
        for year, changes in timeline:
            print(f"\n{year}:")
            for ch in changes:
                print(f"  {ch}")
    else:
        print("No scoring or roster changes across the scanned seasons.")


if __name__ == "__main__":
    main()
