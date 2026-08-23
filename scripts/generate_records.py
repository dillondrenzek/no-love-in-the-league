#!/usr/bin/env python3
"""Emit docs/_data/records.yml — the league record book.

Rendered by docs/records/index.md via _includes/records_cards.html (or the
legacy records_table.html). Each row carries: category, value, season, week,
holder (the display name — team when applicable), and owner_id/owner_name/team
so the card view can link the person and show the team as context.

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
    trade_seasons = load_seasons(include_in_progress=True)  # trades count mid-season
    overrides = load_overrides()

    keep = ("category", "value", "sub_value", "season", "week", "holder",
            "owner_id", "owner_name", "team",
            "opp_owner_id", "opp_owner_name", "opp_team")
    records = [{k: r.get(k) for k in keep}
               for r in compute_records(seasons, franchises, overrides, trade_seasons=trade_seasons)]
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump({"records": records}, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
