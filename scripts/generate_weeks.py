#!/usr/bin/env python3
"""Emit docs/_data/weeks.yml and scaffold the weekly pages at
/seasons/<year>/week-<n>/.

Weekly pages are a 2026-and-beyond feature: once a season is live (state >=
season), every regular-season week gets a page and a data entry keyed
"<year>-<week>", carrying the week's state (future / in_progress / complete), its
scoreboard, and — only for a complete week — the computed highlights. The AI
recap is hand-written into the page markdown; this generator provides the factual
layer, refreshed from imported matchups each build. Playoff weeks are handled
separately (a later pass).

    .venv/bin/python scripts/generate_weeks.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.state import state_at_least
from lib.weeks import week_summary
from weekly_recap import scaffold_page

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "weeks.yml"
FIRST_WEEKLY_YEAR = 2026


def main():
    franchises = load_franchises()
    seasons = load_seasons(include_in_progress=True)

    detail = {}
    created = 0
    for season in seasons:
        year = season["season"]
        if year < FIRST_WEEKLY_YEAR or not state_at_least(season, "season"):
            continue
        for wk in range(1, (season.get("weeks_in_regular_season") or 0) + 1):
            detail[f"{year}-{wk}"] = week_summary(season, wk, franchises)
            _, was_created = scaffold_page(year, wk)
            if was_created:
                created += 1

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        yaml.safe_dump(detail, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)} ({len(detail)} week(s)); "
          f"scaffolded {created} new week page(s)")


if __name__ == "__main__":
    main()
