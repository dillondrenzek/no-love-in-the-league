#!/usr/bin/env bash
#
# Bulk import: pull EVERY season from ESPN (or just the years you list) and
# rebuild the site once at the end. Handy for a first-time backfill or after a
# change to the importer (e.g. capturing a new field like team logos) that you
# want reflected across all of league history.
#
# Uses --patch, so completed seasons are re-imported too: import_espn.py skips a
# season marked `complete` by default (so routine runs don't rewrite history),
# and --patch overrides that. Hand-maintained bits like `draft_order:` are still
# preserved verbatim across re-imports.
#
# Cookies are read from .espn-cookies (and .cookies/) by the importer — nothing to
# export into your shell. Set them up once:
#   cp .espn-cookies.example .espn-cookies    # paste your two cookie values
#   .venv/bin/pip install -r requirements-dev.txt
#
# Usage:
#   scripts/import_all.sh                 # every season in data/seasons/
#   scripts/import_all.sh 2023 2024 2025  # just these years
#
# A year that fails (ESPN hiccup, expired cookies, an endpoint 404ing on an old
# season) is reported and skipped; the remaining years still import and the site
# still builds. Review with `git diff`, then commit & push to publish.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

# Years to import: the ones passed on the command line, else every season file
# on disk (so this stays correct as new seasons are added).
if [[ $# -gt 0 ]]; then
  YEARS=("$@")
else
  YEARS=()
  for f in data/seasons/*.yml; do
    [[ -e "$f" ]] || continue
    YEARS+=("$(basename "$f" .yml)")
  done
fi

if [[ ${#YEARS[@]} -eq 0 ]]; then
  echo "No seasons to import (no data/seasons/*.yml and no years given)." >&2
  exit 1
fi

failed=()
for y in "${YEARS[@]}"; do
  echo "==================== import $y ===================="
  if ! "$PY" scripts/import_espn.py "$y" --patch; then
    echo "!! import failed for $y — skipping" >&2
    failed+=("$y")
  fi
done

echo "==================== build ===================="
"$PY" scripts/build.py

echo
echo "Done: attempted ${#YEARS[@]} season(s)."
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "Failed (re-run individually, e.g. scripts/import_espn.py <year> --patch): ${failed[*]}" >&2
fi
echo "Review with: git diff   (then commit & push to publish)"
