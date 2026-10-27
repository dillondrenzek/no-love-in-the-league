#!/usr/bin/env python3
"""Emit docs/_data/halfway.yml for each live season's Halfway page at
/seasons/<year>/halfway/, and freeze its numbers once the halfway week is final.
The page and its prose file (data/halfway/<year>.yml) are scaffolded by
scripts/halfway_report.py, using the helpers here.

The Halfway page is a once-a-season special edition that sits in the week nav
between the last week of the first half and the first week of the second. Its
numbers are frozen at the halfway week (lib/halfway.snapshot): the standings and
the playoff forecast exactly as they stood then, so the page reads the same in
December as it did the week it published. The prose (an intro, a season outlook,
and a paragraph per team) is agent-written into data/halfway/<year>.yml from the
facts file scripts/halfway_report.py writes. The page shows whatever is final so
far (`as_of_week`). The first build after the halfway week is final writes the
page's numbers (standings, odds, team cards, names and logos) once to
data/halfway/<year>.snapshot.yml, and every build after that reads that file
instead of recomputing, so the page is static from then on. Only the prose
still updates. Delete the snapshot file to recompute it.

    .venv/bin/python scripts/generate_halfway.py
"""

from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, load_season_notes, load_halfway_prose,
                      load_halfway_snapshot)
from lib.halfway import (halfway_week, snapshot, first_half_complete, team_halves, card_chips,
                         freeze, thaw)
from lib.odds import Params, forecast, forecast_rows, complete_through
from lib.overrides import load_overrides
from lib.state import state_at_least
from generate_seasons import season_detail, season_no

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "_data" / "halfway.yml"
PAGE_DIR = ROOT / "docs" / "seasons"
PROSE_DIR = ROOT / "data" / "halfway"
FIRST_YEAR = 2026        # weekly pages (and so this one) start with 2026
SIMS = 10000

PAGE_TEMPLATE = """---
layout: page
title: Halfway Point · {year}
permalink: /seasons/{year}/halfway/
season_year: {year}
season_no: {no}
week: {nav_week}
nav_label: "½"
special: halfway
---
{{% assign h = site.data.halfway[page.season_year] %}}
{{% include sections/halfway_detail.html h=h %}}
"""

SNAPSHOT_HEADER = """# Halfway page numbers — {year}, frozen at the end of Week {week}.
# Written once by scripts/generate_halfway.py when the halfway week went final;
# every build reads this file instead of recomputing, so the page never moves.
# Don't edit it. Delete it to recompute (it's rewritten on the next build).
"""

PROSE_HEADER = """# Halfway report prose — {year}. Write it with the agent
# (agents/halfway-report.md) from recaps/{year}-halfway.data.md, then rebuild.
# Markdown is fine. Teams are keyed by franchise id; the comment shows the
# team's rank at the halfway point.
"""


def scaffold_page(year, through):
    """Create docs/seasons/<year>/halfway.md once; never overwrite."""
    path = PAGE_DIR / str(year) / "halfway.md"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE_TEMPLATE.format(year=year, no=season_no(year),
                                         nav_week=through + 0.5), encoding="utf-8")
    return True


def scaffold_prose(year, rows):
    """Create data/halfway/<year>.yml once (team keys in halfway-standings order);
    never overwrite. Returns True if created."""
    path = PROSE_DIR / f"{year}.yml"
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [PROSE_HEADER.format(year=year).rstrip("\n"), 'intro: ""', 'outlook: ""', "teams:"]
    for r in rows:
        lines.append(f'  {r["owner_id"]}: ""   # {r["finish"]}. {r["team"]}')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def freeze_snapshot(year, entry):
    """Write data/halfway/<year>.snapshot.yml once, from a complete entry; never
    overwrite. Returns True if written."""
    path = PROSE_DIR / f"{year}.snapshot.yml"
    if path.exists() or entry.get("state") != "complete":
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(freeze(entry), sort_keys=False, allow_unicode=True)
    path.write_text(SNAPSHOT_HEADER.format(year=year, week=entry["through_week"]) + body,
                    encoding="utf-8")
    return True


def halfway_entry(season, franchises, overrides, notes, prose, frozen=None):
    """The page record for one season: the frozen numbers plus the current
    prose when the season has a snapshot file, computed otherwise. Returns
    (entry, standings_rows)."""
    if frozen:
        entry = thaw(frozen, prose)
        return entry, entry["standings_rows"]
    year = season["season"]
    through = halfway_week(season)
    # Weeks final so far, capped at the halfway week. Live games in the halfway
    # week aren't final, so the standings and odds leave them out until they are.
    as_of = min(through, complete_through(season))
    entry = {"year": year, "through_week": through, "as_of_week": as_of,
             "state": "complete" if first_half_complete(season, through) else "in_progress",
             "intro": prose["intro"], "outlook": prose["outlook"]}
    snap = snapshot(season, through)
    detail = season_detail(snap, franchises, overrides, notes)
    rows = detail["standings_rows"]
    entry["points"] = detail["points"]
    entry["standings_rows"] = rows
    odds = {}
    if len(season.get("teams") or {}) == 12 and as_of >= 1:
        # Same seeds generate_odds used that week, so the snapshot matches what
        # the season page showed at the time.
        strength, result = forecast(snap, Params(), n=SIMS, seed=year * 100 + as_of)
        prev = forecast(snapshot(season, as_of - 1), Params(), n=SIMS,
                        seed=year * 100 + as_of - 1)
        frows = forecast_rows(snap, franchises, strength, result, prev)
        entry["odds"] = {"as_of_week": as_of, "sims": SIMS, "rows": frows}
        odds = {r["fid"]: r for r in frows}
    chips = card_chips(team_halves(season, as_of)) if as_of >= 1 else {}
    entry["teams"] = [{
        "fid": r["owner_id"], "rank": r["finish"], "team": r["team"],
        "owner": r["owner_name"], "logo": r.get("logo", ""), "record": r["record"],
        "pf": r.get("pf"), "pa": r.get("pa"),
        "playoffs": (odds.get(r["owner_id"]) or {}).get("cells", {}).get("playoffs"),
        "shiva": (odds.get(r["owner_id"]) or {}).get("cells", {}).get("shiva"),
        "all_play": (chips.get(r["owner_id"]) or {}).get("all_play"),
        "sos": (chips.get(r["owner_id"]) or {}).get("sos"),
        "blurb": prose["teams"].get(r["owner_id"]) or "",
    } for r in rows]
    return entry, rows


def main():
    franchises = load_franchises()
    overrides = load_overrides()
    notes = load_season_notes()
    out, frozen = {}, []
    for season in load_seasons(include_in_progress=True):
        year = season["season"]
        if year < FIRST_YEAR or not state_at_least(season, "season"):
            continue
        entry, _ = halfway_entry(season, franchises, overrides, notes,
                                    load_halfway_prose(year), load_halfway_snapshot(year))
        out[year] = entry
        # The page itself is created only by scripts/halfway_report.py, run by
        # hand: the scheduled site update runs this build and commits docs/, so
        # creating it here would publish an empty page before the prose exists.
        # Freezing does happen here, so the numbers lock on schedule either way.
        if freeze_snapshot(year, entry):
            frozen.append(year)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    print(f"Wrote {DATA_PATH.relative_to(ROOT)} ({', '.join(map(str, out)) or 'none'})"
          + (f"; froze {', '.join(map(str, frozen))} (data/halfway/<year>.snapshot.yml)"
             if frozen else ""))


if __name__ == "__main__":
    main()
