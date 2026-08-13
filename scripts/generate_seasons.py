#!/usr/bin/env python3
"""Emit one page per season at /seasons/<year>/, plus the data behind them.

One page per season file in data/seasons/. A completed season shows its final
standings; a still-in-progress season shows current standings. Any season may
carry an optional hand-edited `draft_order:` list, which renders as a draft
table (managers + this year's team). Seasons without one simply omit it.

Writes:
  docs/_data/seasons.yml   - {list: [newest-first summaries], detail: {year: ...}}
  docs/seasons/<year>.md   - a thin stub page per season

Season number counts from the first season (2014 = 1), so 2026 = season 13.

    .venv/bin/python scripts/generate_seasons.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons, name_of
from lib.rulings import load_overrides
from generate_standings import season_rows, load_season_notes

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "seasons"
DATA_PATH = ROOT / "docs" / "_data" / "seasons.yml"

FIRST_SEASON = 2014


def season_no(year):
    return year - FIRST_SEASON + 1


def draft_rows(fids, franchises, teams=None):
    """[{pick, owner_id, owner_name, team}] for franchise ids in pick order.

    `teams` is the season's franchise-id -> team-name map (when known), used to
    show each manager's current team name alongside their pick.
    """
    teams = teams or {}
    rows = []
    for i, fid in enumerate(fids or [], start=1):
        rows.append({
            "pick": i,
            "owner_id": fid if fid in franchises else None,
            "owner_name": name_of(fid, franchises),
            "team": teams.get(fid),
        })
    return rows


def season_detail(season, franchises, overrides, notes):
    """Page data for one season — completed or still in progress."""
    year = season["season"]
    in_progress = season.get("status") == "in_progress"
    sr = season_rows(season, franchises, overrides, notes)  # year, points, rows, notes
    rows = sr["rows"]
    if in_progress:
        for r in rows:      # nothing is decided yet — no Shiva/Sacko tags
            r["tag"] = None
    weeks = [m["week"] for m in (season.get("matchups") or []) if not m.get("playoff")]
    return {
        "year": year,
        "season_no": season_no(year),
        "status": "in_progress" if in_progress else "complete",
        "points": sr["points"],
        "rows": rows,
        "notes": sr["notes"],
        "weeks_played": max(weeks) if weeks else 0,
        "draft_order": draft_rows(season.get("draft_order"), franchises, season.get("teams")),
        "champ": None if in_progress else (rows[0] if rows else None),
        "sacko": None if in_progress else (rows[-1] if rows else None),
    }


STUB = """---
layout: page
title: Season {no} · {year}
permalink: /seasons/{year}/
season_year: {year}
---
{{% assign d = site.data.seasons.detail[page.season_year] %}}
{{% include season_detail.html d=d %}}
"""


def main():
    franchises = load_franchises()
    seasons = load_seasons(include_in_progress=True)  # newest first, live season included
    overrides = load_overrides()
    notes = load_season_notes()

    detail = {s["season"]: season_detail(s, franchises, overrides, notes) for s in seasons}

    # Newest year first, whatever its status (in_progress → complete).
    years = sorted(detail.keys(), reverse=True)
    index = [{"year": y, "season_no": season_no(y), "status": detail[y]["status"]}
             for y in years]

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        yaml.safe_dump({"list": index, "detail": detail}, sort_keys=False, allow_unicode=True),
        encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for y in years:
        (OUT_DIR / f"{y}.md").write_text(
            STUB.format(no=season_no(y), year=y), encoding="utf-8")

    print(f"Wrote {DATA_PATH.relative_to(ROOT)} and {len(years)} season pages")


if __name__ == "__main__":
    main()
