#!/usr/bin/env python3
"""Emit docs/_data/standings.yml — per-season final standings.

Rendered by docs/standings/index.md via _includes/season_standings.html. Python
computes every display value (record, PF heat color, finish tag); the template
only assembles markup.

    .venv/bin/python scripts/generate_standings.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons, DATA_DIR
from lib.standings import get_standings, has_points, provisional_standings
from lib.render import heat_color
from lib.rulings import load_overrides, co_champions
from lib.state import state_of

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "standings.yml"
NOTES_PATH = DATA_DIR / "season_notes.yml"  # hand-edited: year -> [bullets]


def load_season_notes():
    if NOTES_PATH.exists():
        return yaml.safe_load(NOTES_PATH.read_text()) or {}
    return {}


def _tag(finish, team_count, is_co):
    if is_co:
        return "cochamp"
    if finish == 1:
        return "shiva"
    if finish == team_count:
        return "sacko"
    return None


def season_rows(season, franchises, overrides, notes, trade_note=True):
    rows = get_standings(season, franchises)
    # A live season (season/playoffs) shows a standings table even before any game
    # is played: fall back to a 0-0 provisional table in the current order, which
    # fills in with real records as games come in.
    if not rows and state_of(season) in ("season", "playoffs"):
        rows = provisional_standings(season, franchises, zero_points=True)
    points = has_points(rows)
    co = set(co_champions(season["season"], overrides))
    team_count = len(rows)
    pfs = [r["points_for"] for r in rows if r["points_for"] is not None]
    lo, hi = (min(pfs), max(pfs)) if pfs else (0, 0)

    out = []
    for r in rows:
        row = {
            "finish": r["finish"],
            "team": r["name"],
            "owner_id": r["id"] if r["id"] in franchises else None,
            "owner_name": franchises[r["id"]]["name"] if r["id"] in franchises else None,
            "record": r["record"],
            "tag": _tag(r["finish"], team_count, r["id"] in co),
        }
        if points:
            row["pf"] = r["points_for"]
            row["pf_color"] = heat_color(r["points_for"], lo, hi)
            row["pa"] = r["points_against"]
        out.append(row)
    # Hand-written notes, plus an auto "N trades completed" bullet when any went
    # through that season.
    season_notes = list(notes.get(season["season"]) or [])
    n_trades = len(season.get("trades") or [])
    if trade_note and n_trades:
        season_notes.append(f"{n_trades} trade{'s' if n_trades != 1 else ''} completed")

    return {
        "year": season["season"], "points": points, "rows": out,
        "notes": season_notes,
    }


def main():
    franchises = load_franchises()
    seasons = load_seasons()
    overrides = load_overrides()
    notes = load_season_notes()

    data = {"seasons": [season_rows(s, franchises, overrides, notes) for s in seasons]}
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
