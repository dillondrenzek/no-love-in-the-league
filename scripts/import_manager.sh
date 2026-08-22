#!/usr/bin/env bash
#
# Import ONE manager's trade detail from their ESPN cookie and merge it into the
# season files, then rebuild. Cookies come in one at a time — this is additive:
# each run fills in the trades that account can see (by ESPN trade id) without
# dropping detail an earlier import already recorded.
#
# The manager's account only needs to be handed over once; you don't have to keep
# their cookie around afterward. (Whose count becomes "exact" is tracked per
# season in `trades_known_for`.)
#
# Usage:
#   scripts/import_manager.sh <cookie-file> [year ...]
#   scripts/import_manager.sh ~/zach-cookies           # default trade-era seasons
#   scripts/import_manager.sh ~/zach-cookies 2023 2024 # just these seasons

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COOKIE="${1:-}"
if [[ -z "$COOKIE" || ! -f "$COOKIE" ]]; then
  echo "usage: scripts/import_manager.sh <cookie-file> [year ...]" >&2
  echo "  (cookie-file must exist; it's read, never committed)" >&2
  exit 1
fi
shift

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

# ESPN only serves the transactions endpoint from ~2019 on, so default to the
# seasons that can actually have trade detail.
YEARS=("$@")
[[ ${#YEARS[@]} -gt 0 ]] || YEARS=(2019 2020 2021 2022 2023 2024 2025 2026)

for y in "${YEARS[@]}"; do
  echo "==================== $y  ($(basename "$COOKIE")) ===================="
  "$PY" scripts/import_espn.py "$y" --cookies "$COOKIE"
done

echo "==================== build ===================="
"$PY" scripts/build.py
echo "Done. Review with: git diff   (then commit & push)"
