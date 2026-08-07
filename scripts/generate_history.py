#!/usr/bin/env python3
"""Emit docs/_data/history.yml — champions and the record book.

Rendered by docs/history/index.md via _includes/champions_table.html and
records_table.html. Python computes everything; templates assemble markup.

    .venv/bin/python scripts/generate_history.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.standings import get_standings
from lib.records import compute_records
from lib.rulings import load_overrides, co_champions

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "history.yml"


def _person(r, franchises):
    if not r:
        return None
    return {
        "team": r["name"],
        "owner_id": r["id"] if r["id"] in franchises else None,
        "owner_name": franchises[r["id"]]["name"] if r["id"] in franchises else None,
    }


def champions(seasons, franchises, overrides):
    out = []
    for season in seasons:
        rows = {r["id"]: r for r in get_standings(season, franchises)}
        by_finish = {r["finish"]: r for r in rows.values()}
        co = co_champions(season["season"], overrides)
        if co:
            out.append({
                "year": season["season"], "co": True,
                "champs": [_person(rows[fid], franchises) for fid in co],
                "runner_up": None,
                "third": _person(by_finish.get(3), franchises),
                "record": None,
            })
        else:
            champ = by_finish.get(1)
            out.append({
                "year": season["season"], "co": False,
                "champs": [_person(champ, franchises)] if champ else [],
                "runner_up": _person(by_finish.get(2), franchises),
                "third": _person(by_finish.get(3), franchises),
                "record": champ["record"] if champ else None,
            })
    return out


def records(seasons, franchises, overrides):
    return [
        {"category": r["category"], "holder": r["holder"],
         "value": r["value"], "season": r["season"]}
        for r in compute_records(seasons, franchises, overrides)
    ]


def main():
    franchises = load_franchises()
    seasons = load_seasons()
    overrides = load_overrides()

    data = {
        "champions": champions(seasons, franchises, overrides),
        "records": records(seasons, franchises, overrides),
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
