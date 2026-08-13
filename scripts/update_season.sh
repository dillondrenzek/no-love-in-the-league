#!/usr/bin/env bash
#
# Weekly in-season update: pull ONE season from ESPN and rebuild the site.
# Run this about once a week during the season to keep the standings current.
#
# Cookies are read straight from the .espn-cookies file by the importer, so you
# don't need to export anything into your shell. Set one up once:
#   cp .espn-cookies.example .espn-cookies   # then paste your two cookie values
#   .venv/bin/pip install -r requirements-dev.txt
#
# Usage:
#   scripts/update_season.sh          # the current calendar year
#   scripts/update_season.sh 2026     # a specific season
#
# A mid-season import is written with `status: in_progress`: it shows current
# standings on that season's page but is kept out of all-time stats until you
# re-run it after the season finishes (when ESPN posts final placements).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

YEAR="${1:-$(date +%Y)}"

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

echo "==================== import $YEAR ===================="
"$PY" scripts/import_espn.py "$YEAR"

echo "==================== build ===================="
"$PY" scripts/build.py

echo "Done. Review with: git diff   (then commit & push to publish)"
