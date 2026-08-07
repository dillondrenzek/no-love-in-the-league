#!/usr/bin/env python3
"""Emit docs/_data/standings.yml — per-season final standings.

Rendered by docs/standings/index.md via _includes/season_standings.html. Python
computes every display value (record, PF heat color, finish tag); the template
only assembles markup.

    .venv/bin/python scripts/generate_standings.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.standings import get_standings, has_points
from lib.render import heat_color
from lib.rulings import load_overrides, co_champions

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "standings.yml"


def _tag(finish, team_count, is_co):
    if is_co:
        return "cochamp"
    if finish == 1:
        return "shiva"
    if finish == team_count:
        return "sacko"
    return None


def season_rows(season, franchises, overrides):
    rows = get_standings(season, franchises)
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
    return {"year": season["season"], "points": points, "rows": out}


def main():
    franchises = load_franchises()
    seasons = load_seasons()
    overrides = load_overrides()

    data = {"seasons": [season_rows(s, franchises, overrides) for s in seasons]}
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
