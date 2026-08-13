#!/usr/bin/env bash
#
# Import every season from ESPN and rebuild the site.
#
# Setup (once):
#   cp .espn-cookies.example .espn-cookies   # then paste your cookie values in
#   .venv/bin/pip install -r requirements-dev.txt
#
# Usage:
#   scripts/import_all.sh                 # import the default season range
#   scripts/import_all.sh 2023 2024 2025  # import only these seasons
#
# Cookies are read straight from `.espn-cookies` (git-ignored) by the importer,
# so nothing is exported into your shell or saved in shell history.

set -euo pipefail

# Repo root = parent of this script's directory, regardless of where it's run.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "${ESPN_COOKIES_FILE:-$ROOT/.espn-cookies}" ]]; then
  echo "No cookies file at ${ESPN_COOKIES_FILE:-$ROOT/.espn-cookies}." >&2
  echo "Copy .espn-cookies.example to .espn-cookies and fill it in (private league)," >&2
  echo "or continue without it if your league is public." >&2
fi

# Prefer the project venv's Python if it exists.
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python3"

# Seasons: use CLI args if given, otherwise the full range.
if [[ $# -gt 0 ]]; then
  SEASONS=("$@")
else
  SEASONS=(2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025)
fi

for year in "${SEASONS[@]}"; do
  echo "==================== $year ===================="
  "$PY" scripts/import_espn.py "$year"
done

echo "==================== build ===================="
"$PY" scripts/build.py
echo "Done. Review changes with: git diff"
