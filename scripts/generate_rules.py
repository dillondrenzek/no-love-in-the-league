#!/usr/bin/env python3
"""Emit docs/_data/rules.yml — the rulebook's current settings + change log.

Reads data/settings.yml (written by scripts/import_settings.py), labels the raw
ESPN ids and diffs consecutive seasons via lib.rules. Rendered by the rulebook
page through _includes/current_settings.html and _includes/rule_changes.html.

Degrades gracefully: if data/settings.yml is missing (settings never imported),
writes an empty structure so the build still succeeds and the rulebook simply
omits the generated blocks.

    .venv/bin/python scripts/generate_rules.py
"""

from pathlib import Path

import yaml

from lib.rules import compute_rules

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "data" / "settings.yml"
OUT_PATH = ROOT / "docs" / "_data" / "rules.yml"


def load_settings():
    if not SETTINGS_PATH.is_file():
        return []
    with open(SETTINGS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("seasons") or []


def main():
    rules = compute_rules(load_settings())
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        yaml.safe_dump(rules, sort_keys=False, allow_unicode=True),
        encoding="utf-8")
    if rules["current"]:
        print(f"Wrote {OUT_PATH.relative_to(ROOT)} "
              f"(current: {rules['current']['season']}, "
              f"{len(rules['changes'])} change-years)")
    else:
        print(f"Wrote {OUT_PATH.relative_to(ROOT)} (empty — run "
              f"scripts/import_settings.py to populate data/settings.yml)")


if __name__ == "__main__":
    main()
