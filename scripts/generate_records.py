#!/usr/bin/env python3
"""Emit docs/_data/records.yml — the league record book.

Rendered by docs/records/index.md via _includes/records_table.html.

    .venv/bin/python scripts/generate_records.py
"""

from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons
from lib.records import compute_records
from lib.rulings import load_overrides

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "records.yml"


def main():
    franchises = load_franchises()
    seasons = load_seasons()
    overrides = load_overrides()

    records = [
        {"category": r["category"], "holder": r["holder"],
         "value": r["value"], "season": r["season"]}
        for r in compute_records(seasons, franchises, overrides)
    ]
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump({"records": records}, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
