#!/usr/bin/env python3
"""Emit docs/_data/weeks.yml — per-week scoreboards + highlights for the weekly
recap pages at /seasons/<year>/week-<n>/.

A week gets data when either (a) its season is in progress (so scoreboard +
highlights appear the moment a page is scaffolded), or (b) a week page already
exists for it (so a recap written for a now-finished season keeps its data). Each
played week becomes one entry keyed "<year>-<week>". The AI recap itself is
hand-written into the week's page markdown (scaffolded by weekly_recap.py) — this
generator only provides the factual layer, refreshed from imported matchups.

    .venv/bin/python scripts/generate_weeks.py
"""

import re
from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.weeks import week_summary, played_weeks

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "weeks.yml"
SEASON_PAGE_DIR = ROOT / "docs" / "seasons"


def _page_weeks():
    """(year, week) pairs that already have a docs/seasons/<year>/week-<n>.md page."""
    pairs = set()
    for p in SEASON_PAGE_DIR.glob("*/week-*.md"):
        m = re.match(r"week-(\d+)\.md$", p.name)
        if not m:
            continue
        try:
            pairs.add((int(p.parent.name), int(m.group(1))))
        except ValueError:
            continue
    return pairs


def main():
    franchises = load_franchises()
    by_year = {s["season"]: s for s in load_seasons(include_in_progress=True)}

    # Weeks to emit: every played week of an in-progress season, plus any week
    # that already has a page (union), so nothing a page relies on disappears.
    targets = set()
    for year, season in by_year.items():
        if season.get("status") == "in_progress":
            targets.update((year, wk) for wk in played_weeks(season))
    targets.update((y, w) for (y, w) in _page_weeks() if y in by_year)

    detail = {}
    for year, wk in sorted(targets):
        summary = week_summary(by_year[year], wk, franchises)
        if summary["played"]:
            detail[f"{year}-{wk}"] = summary

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        yaml.safe_dump(detail, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)} ({len(detail)} week(s))")


if __name__ == "__main__":
    main()
