#!/usr/bin/env bash
#
# Fetch ONE manager's trade detail from their ESPN cookie and merge it into every
# season on record, then rebuild. Trades are the only data ESPN scopes to a single
# account, so this is all a manager's cookie can add — and because it touches
# nothing else in the season file, it runs safely across COMPLETED seasons too
# (a full import deliberately skips finished history to avoid rewriting it).
#
# Additive by ESPN trade id: each manager's cookie fills in the trades that account
# can see without dropping detail an earlier import recorded, and marks that
# franchise "known" (their count becomes exact) per season. Hand the cookie over
# once; you don't need to keep it afterward.
#
# Usage:
#   scripts/import_manager_trades.sh <cookie-file> [year ...]
#   scripts/import_manager_trades.sh ~/jack-cookies            # all trade-era seasons
#   scripts/import_manager_trades.sh ~/jack-cookies 2023 2024  # just these seasons

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COOKIE="${1:-}"
if [[ -z "$COOKIE" || ! -f "$COOKIE" ]]; then
  echo "usage: scripts/import_manager_trades.sh <cookie-file> [year ...]" >&2
  echo "  (cookie-file must exist; it's read, never committed)" >&2
  exit 1
fi
shift

PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

# ESPN only serves the transactions/trades endpoint from ~2019 on, so default to
# the seasons that can actually have trade detail.
YEARS=("$@")
[[ ${#YEARS[@]} -gt 0 ]] || YEARS=(2019 2020 2021 2022 2023 2024 2025 2026)

for y in "${YEARS[@]}"; do
  echo "==================== $y  ($(basename "$COOKIE")) ===================="
  "$PY" scripts/import_espn.py "$y" --cookies "$COOKIE" --trades-only
done

echo "==================== build ===================="
"$PY" scripts/build.py
echo "Done. Review with: git diff   (then commit & push)"
