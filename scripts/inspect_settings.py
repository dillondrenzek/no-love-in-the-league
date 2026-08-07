#!/usr/bin/env python3
"""Print each season's roster (lineup slot) composition and flag year-over-year
changes — to help write the roster-change bullets in data/season_notes.yml.

This is a LOCAL dev tool (like import_espn.py); it queries ESPN and prints a
report. It writes nothing.

Usage (private league needs cookies, same as the importer):
    export ESPN_S2='...'; export ESPN_SWID='{...}'
    python scripts/inspect_settings.py            # default season range
    python scripts/inspect_settings.py 2016 2017  # only these seasons
"""

import os
import sys

try:
    from espn_api.football import League
except ImportError:
    sys.exit("espn-api is not installed. Run: pip install -r requirements-dev.txt")

LEAGUE_ID = 236302
DEFAULT_YEARS = list(range(2014, 2026))

# Bench/IR aren't "roster composition" in the interesting sense; list them apart.
NON_STARTER = {"BE", "IR"}


def lineup(year, espn_s2, swid):
    lg = League(league_id=LEAGUE_ID, year=year, espn_s2=espn_s2, swid=swid)
    slots = {k: v for k, v in lg.settings.position_slot_counts.items() if v}
    scoring = lg.settings.scoring_type if hasattr(lg.settings, "scoring_type") else None
    return slots, scoring


def fmt(slots):
    starters = {k: v for k, v in slots.items() if k not in NON_STARTER}
    bench = {k: v for k, v in slots.items() if k in NON_STARTER}
    s = " ".join(f"{k}:{v}" for k, v in starters.items())
    b = " ".join(f"{k}:{v}" for k, v in bench.items())
    return s, b


def diff(prev, cur):
    keys = sorted(set(prev) | set(cur))
    changes = []
    for k in keys:
        a, b = prev.get(k, 0), cur.get(k, 0)
        if a != b:
            changes.append(f"{k} {a}->{b}")
    return changes


def main():
    years = [int(a) for a in sys.argv[1:]] or DEFAULT_YEARS
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")

    prev_slots = None
    for year in years:
        try:
            slots, scoring = lineup(year, espn_s2, swid)
        except Exception as e:  # noqa: BLE001
            print(f"{year}: ERROR {e}", file=sys.stderr)
            continue
        starters, bench = fmt(slots)
        print(f"\n{year}  scoring={scoring}")
        print(f"  starters: {starters}")
        print(f"  bench:    {bench}")
        if prev_slots is not None:
            changes = diff(prev_slots, slots)
            if changes:
                print(f"  >> CHANGES vs prior year: {', '.join(changes)}")
        prev_slots = slots


if __name__ == "__main__":
    main()
