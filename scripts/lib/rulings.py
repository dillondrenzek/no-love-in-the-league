"""League rulings that override or augment the ESPN-imported data.

Loaded from data/overrides.yml (which the importer never touches), so these
survive re-imports. Two rulings today:

  - co-champions: a tied championship game ruled a shared title.
  - meaningless games: final-week consolation games between 5th-8th place teams
    in our 6-team double-elimination seasons, which don't count for anything.
"""

import yaml

from .data import DATA_DIR

OVERRIDES_PATH = DATA_DIR / "overrides.yml"

# The four consolation places whose final-week games don't matter.
_MID_PLACES = {5, 6, 7, 8}


def load_overrides(path=OVERRIDES_PATH):
    if path.exists():
        return yaml.safe_load(path.read_text()) or {}
    return {}


def co_champions(year, overrides):
    """List of franchise ids ruled co-champions for `year` (empty if none)."""
    return (overrides.get("co_champions") or {}).get(year, [])


def finish_map(season):
    """franchise id -> final placement (1-based) from the season's final_standings."""
    return {fid: i + 1 for i, fid in enumerate(season.get("final_standings") or [])}


def meaningless_keys(season, overrides):
    """Set of matchup keys (week, frozenset(ids)) that don't count this season.

    A game is meaningless when the season uses our 6-team double-elimination
    bracket, the game is in the final playoff week, and BOTH teams finished
    5th-8th (their placement was already locked the week before).
    """
    if season["season"] not in set(overrides.get("double_elim_6") or []):
        return set()
    playoff_weeks = [m["week"] for m in season.get("matchups", []) if m.get("playoff")]
    if not playoff_weeks:
        return set()
    final_week = max(playoff_weeks)
    fm = finish_map(season)
    keys = set()
    for m in season.get("matchups", []):
        if m.get("playoff") and m["week"] == final_week:
            if fm.get(m["home"]) in _MID_PLACES and fm.get(m["away"]) in _MID_PLACES:
                keys.add((m["week"], frozenset((m["home"], m["away"]))))
    return keys


def matchup_key(m):
    return (m["week"], frozenset((m["home"], m["away"])))
