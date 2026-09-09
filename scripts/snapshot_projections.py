#!/usr/bin/env python3
"""Capture a week's ESPN projected scores into data/projections/<year>-week-<nn>.yml.

Run this BEFORE the week's games start (the workflow does it Thursday afternoon).
It's **write-once per week**: if the snapshot file already exists it's left
untouched, so the first pre-game capture is the durable "line" for that week even
if the job runs again later.

Independent of the season files — the importer never touches these, so a
projection is never lost to a later re-import. Each team's projected total is the
sum of its *starters'* ESPN projections, keyed by the owner's SWID (`manager_id`)
so it stays joinable to a franchise even if the team is renamed.

Cookies come from .espn-cookies or the ESPN_S2 / ESPN_SWID env vars, same as the
importer.

    python scripts/snapshot_projections.py          # current season, current week
    python scripts/snapshot_projections.py 2026      # a specific season
"""

import datetime
import sys
from pathlib import Path

import yaml

try:
    from the_league_espn_api import League, ApiError
except ImportError:
    sys.exit("the-league-espn-api is not installed. Run: pip install -r requirements-dev.txt")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "projections"


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else None
    lg = League(year=year)            # cookies auto-loaded; year defaults to current
    year = lg.year

    if not lg.authenticated:
        print("WARNING: no ESPN cookies found — projections need an authenticated "
              "league. Set ESPN_S2 / ESPN_SWID or fill in .espn-cookies.", file=sys.stderr)
    if not hasattr(lg, "rosters"):
        sys.exit("Installed the-league-espn-api has no rosters() — bump the pin in "
                 "requirements-dev.txt (needs >= v0.1.5).")

    try:
        rows = lg.rosters()           # current scoring period
    except ApiError as e:
        sys.exit(f"rosters() failed (ESPN {getattr(e, 'status', e)}).")
    if not rows:
        sys.exit("rosters() returned no rows — nothing to snapshot.")

    week = rows[0].get("week")
    out = OUT_DIR / f"{year}-week-{week:02d}.yml"
    if out.exists():
        print(f"{out.relative_to(ROOT)} already exists — keeping the pre-game line intact.")
        return

    teams = {t["team_id"]: t for t in lg.teams()}
    proj = {}
    for r in rows:
        if r.get("starter") and isinstance(r.get("projected"), (int, float)):
            proj[r["team_id"]] = round(proj.get(r["team_id"], 0.0) + r["projected"], 2)
    if not proj:
        sys.exit("No starter projections found — nothing to snapshot (too early?).")

    entries = []
    for tid, total in sorted(proj.items()):
        t = teams.get(tid, {})
        entries.append({
            "team_id": tid,
            "manager_id": t.get("manager_id", ""),
            "team_name": t.get("team_name", ""),
            "projected": total,
        })

    doc = {
        "season": year,
        "week": week,
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "projections": entries,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} — week {week}, {len(entries)} teams.")


if __name__ == "__main__":
    main()
