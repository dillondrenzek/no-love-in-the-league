#!/usr/bin/env python3
"""Generates docs/history/index.md from data/history/*.yml.

Run this after editing the YAML data files:
    .venv/bin/python scripts/generate_history.py
"""

import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "history"
OUTPUT_PATH = ROOT / "docs" / "history" / "index.md"


def load_yaml(name):
    with open(DATA_DIR / name) as f:
        return yaml.safe_load(f) or []


def render_champions_table(champions):
    rows = sorted(champions, key=lambda c: c["season"], reverse=True)
    lines = [
        "| Season | Champion | Runner-Up | Record | Points For |",
        "|---|---|---|---|---|",
    ]
    for c in rows:
        lines.append(
            f"| {c['season']} | {c['champion']} | {c['runner_up']} | "
            f"{c['record']} | {c['points_for']} |"
        )
    return "\n".join(lines)


def render_records_table(records):
    lines = [
        "| Category | Holder | Value | Season | Week |",
        "|---|---|---|---|---|",
    ]
    for r in records:
        lines.append(
            f"| {r['category']} | {r['holder']} | {r['value']} | "
            f"{r['season']} | {r.get('week', '—')} |"
        )
    return "\n".join(lines)


def main():
    champions = load_yaml("champions.yml")
    records = load_yaml("records.yml")

    content = f"""---
layout: page
title: League History
permalink: /history/
---

## Champions

{render_champions_table(champions)}

## Record Book

{render_records_table(records)}
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
