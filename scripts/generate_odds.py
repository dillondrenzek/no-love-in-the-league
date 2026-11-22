#!/usr/bin/env python3
"""Season forecast for the live season's page: each team's odds to win the Shiva,
finish top 3, make the playoffs, land in the Sacko bracket, or take the Sacko.

Writes docs/_data/odds.yml, keyed by year. Only the season in its regular season
gets a forecast. Team ratings come from the weeks that are complete; a week in
progress is played out from its live scores (lib.odds.live_week: live score plus
the projected points of starters still to play), so the odds move as each import
brings new scores. The model and its constants live in lib/odds; tune them with
scripts/backtest_odds.py.

Each year's record: {as_of_week, live_week, now_week, updated_at, sims, rows}
(`now_week`: the live week whose games in progress the table's record, PF and
seeds count at their current scores, as if the season ended now) plus, during
a live week, `settled_rows` — the forecast from completed weeks only, which is
what the weekly recap's facts file quotes.
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons, load_week_rosters, load_nfl_schedule
from lib.nfl_schedule import parse_kickoff
from lib.odds import (Params, as_of_now, complete_through, forecast, forecast_rows,
                      live_week, truncate)
from lib.state import state_of
from lib.weeks import _fmt_updated as fmt_updated

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
        updated = season.get("updated_at")
        now = parse_kickoff(updated) if updated else None
        live = live_week(season, load_week_rosters(year, week + 1, franchises),
                         load_nfl_schedule(year), now)
        # Fixed seed per (season, week): same inputs -> same numbers on every build.
        seed = year * 100 + week
        settled = forecast(season, Params(), n=SIMS, seed=seed)
        # Last week's forecast, re-run from the season as it stood then (same seed
        # it had), for the trend arrows. None before any week is final.
        before = None
        if week >= 1:
            before = forecast(truncate(season, week - 1), Params(), n=SIMS,
                              seed=seed - 1)
        # The table's standings columns read "if the season ended right now".
        now_season, now_week = as_of_now(season)
        entry = {"as_of_week": week, "live_week": live["week"] if live else None,
                 "now_week": now_week, "updated_at": fmt_updated(updated), "sims": SIMS}
        if live:
            # Mid-week, the arrows show how far the live scores have moved each
            # team since the week began (the settled forecast).
            strength, result = forecast(season, Params(), n=SIMS, seed=seed, live=live)
            entry["rows"] = forecast_rows(season, franchises, strength, result, settled,
                                          now=now_season)
            entry["settled_rows"] = forecast_rows(season, franchises, *settled, before)
        else:
            entry["rows"] = forecast_rows(season, franchises, *settled, before,
                                          now=now_season)
        out[year] = entry
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)} ({', '.join(map(str, out)) or 'no live season'})")


if __name__ == "__main__":
    main()
