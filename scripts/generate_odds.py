#!/usr/bin/env python3
"""Season forecast for the live season's page: each team's odds to win the Shiva,
finish top 3, make the playoffs, land in the Sacko bracket, or take the Sacko.

Writes docs/_data/odds.yml, keyed by year. Only the season in its regular season
gets a forecast, rebuilt from the weeks that are complete (a live week counts once
it's final). The model and its constants live in lib/odds; tune them with
scripts/backtest_odds.py.
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.odds import Params, complete_through, forecast, forecast_rows, truncate
from lib.state import state_of

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "odds.yml"
SIMS = 10000


def main():
    franchises = load_franchises()
    out = {}
    for season in load_seasons(include_in_progress=True):
        if state_of(season) != "season" or len(season.get("teams") or {}) != 12:
            continue
        year = season["season"]
        week = complete_through(season)
        if week >= (season.get("weeks_in_regular_season") or 14):
            continue
        # Fixed seed per (season, week): same inputs -> same numbers on every build.
        strength, result = forecast(season, Params(), n=SIMS, seed=year * 100 + week)
        # Last week's forecast, re-run from the season as it stood then (same seed
        # it had), for the trend arrows. None before any week is final.
        prev = None
        if week >= 1:
            prev = forecast(truncate(season, week - 1), Params(), n=SIMS,
                            seed=year * 100 + week - 1)
        out[year] = {"as_of_week": week, "sims": SIMS,
                     "rows": forecast_rows(season, franchises, strength, result, prev)}
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)} ({', '.join(map(str, out)) or 'no live season'})")


if __name__ == "__main__":
    main()
