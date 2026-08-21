#!/usr/bin/env python3
"""Run every page generator in order. This is the one command to run after
editing anything under data/.

    .venv/bin/python scripts/build.py

To add a section: write a generate_<section>.py next to this file exposing a
main() function, then add it to GENERATORS below.
"""

import generate_records
import generate_standings
import generate_teams
import generate_seasons
import generate_rules

GENERATORS = [
    generate_records,
    generate_standings,
    generate_teams,
    generate_seasons,
    generate_rules,
]


def main():
    for gen in GENERATORS:
        gen.main()
    print("Build complete.")


if __name__ == "__main__":
    main()
