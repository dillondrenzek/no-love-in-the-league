#!/usr/bin/env python3
"""Emit docs/_data/standings.yml — per-season final standings.

Rendered by docs/standings/index.md via _includes/sections/season_standings.html. Python
computes every display value (record, PF heat color, finish tag); the template
only assembles markup.

    .venv/bin/python scripts/generate_standings.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons, load_season_notes
from lib.overrides import load_overrides
from lib.seasons import season_rows

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "standings.yml"


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
