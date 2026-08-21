#!/usr/bin/env bash
#
# Yearly: refresh the rulebook's scoring & roster settings from ESPN, then
# rebuild the site. Run this once in the offseason (after any rule changes are
# in place on ESPN) so the rulebook's "Scoring & rosters" block and "Rule
# changes" log stay current.
#
# Cookies are read straight from the .espn-cookies file by the importer, so you
# don't need to export anything into your shell. Set one up once:
#   cp .espn-cookies.example .espn-cookies   # then paste your two cookie values
#   .venv/bin/pip install -r requirements-dev.txt
#
# Usage:
#   scripts/refresh_rules.sh              # every season in data/seasons/
#   scripts/refresh_rules.sh 2008 2026    # a custom span (e.g. to reach further back)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

echo "==================== import settings ===================="
"$PY" scripts/import_settings.py "$@"

echo "==================== build ===================="
"$PY" scripts/build.py

echo "Done. Review with: git diff data/settings.yml docs/_data/rules.yml"
echo "Then commit & push to publish the updated rulebook."
