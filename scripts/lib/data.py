"""Loading the source-of-truth YAML and resolving franchise ids to names.

This is the only module that touches the filesystem. Everything downstream works
on plain dicts/lists so it's easy to test with in-memory data.
"""

import yaml
from pathlib import Path

from .state import is_in_progress

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SEASONS_DIR = DATA_DIR / "seasons"


def _read_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_franchises(data_dir=DATA_DIR):
    """Return {id: franchise_dict} for quick lookup by id."""
    franchises = _read_yaml(Path(data_dir) / "franchises.yml") or []
    return {f["id"]: f for f in franchises}


def load_seasons(seasons_dir=SEASONS_DIR, include_in_progress=False):
    """Return a list of season dicts, most recent season first.

    In-progress seasons (anything whose lifecycle `state` isn't `complete` yet —
    see lib/state) are left out by default so partial results don't skew all-time
    standings, records, or owner profiles. The per-season pages pass
    include_in_progress=True to show the live season on its own page.
    """
    seasons = []
    for path in sorted(Path(seasons_dir).glob("*.yml")):
        season = _read_yaml(path)
        if not include_in_progress and is_in_progress(season):
            continue
        seasons.append(season)
    seasons.sort(key=lambda s: s["season"], reverse=True)
    return seasons


def name_of(franchise_id, franchises):
    """Full display name for a franchise id, falling back to the id itself."""
    f = franchises.get(franchise_id)
    return f["name"] if f else franchise_id


def owner_link(franchise_id, text, franchises):
    """Markdown link from `text` to the franchise's owner page.

    Falls back to plain text when there's no owner page (e.g. a level-1 season
    keyed by team name rather than a real franchise id).
    """
    if franchise_id in franchises:
        return f"[{text}]({{{{ '/teams/{franchise_id}/' | relative_url }}}})"
    return text


def owner_name_tag(franchise_id, franchises):
    """A small gray owner-name label to sit next to a team name."""
    if franchise_id in franchises:
        return f' <span class="owner-name">{franchises[franchise_id]["name"]}</span>'
    return ""


def short_name_of(franchise_id, franchises):
    """First name (or an explicit `short:` override) for a franchise id.

    Used for most on-site displays; `name_of` gives the full name for places
    like a team-page header.
    """
    f = franchises.get(franchise_id)
    if not f:
        return franchise_id
    return f.get("short") or f["name"].split()[0]


def game_final(matchup):
    """A game with a final result — the only kind that counts toward season stats
    (and only once its whole week is complete). Future fixtures (`played: false`,
    no scores) and live/in-progress games (`final: false`, live scores) are not
    final. A played row with neither flag is final (historical/finished games)."""
    return (matchup.get("played", True) is not False
            and matchup.get("final", True) is not False)


def game_has_score(matchup):
    """A game with a score to show — final OR live/in-progress. A future fixture
    carries no scores, so it's excluded."""
    return matchup.get("home_score") is not None


def _matchups_by_week(season):
    by_week = {}
    for m in season.get("matchups") or []:
        by_week.setdefault(m.get("week"), []).append(m)
    return by_week


def complete_weeks(season):
    """Week numbers whose games are ALL final. Season stats fold in a week only
    when it's complete — a week with any live/unplayed game stays out entirely
    (its live scores show on the week page but never touch standings)."""
    return {wk for wk, games in _matchups_by_week(season).items()
            if games and all(game_final(g) for g in games)}


def countable_matchups(season):
    """Games that count toward season standings / records / head-to-head: every
    game in a complete week (all such games are final by definition)."""
    complete = complete_weeks(season)
    return [m for m in (season.get("matchups") or []) if m.get("week") in complete]


def regular_season_matchups(season):
    """Countable regular-season games — what standings are computed from."""
    return [m for m in countable_matchups(season) if not m.get("playoff")]


def season_trades_complete(season):
    """True when this season's trade data is fully known.

    ESPN only reveals a trade's contents to its participants, so a single
    account can't see every trade (see the importer). The importer records
    `trades_complete: true` only when it fetched trades AND every one came back
    fully detailed. When some trades are still unknown, per-owner trade counts
    for anyone who played this season can't be trusted, so the site shows
    "unavailable" for them. Older season files without the explicit key are
    inferred from the per-trade `complete` flags (absent flag = complete)."""
    flag = season.get("trades_complete")
    if flag is not None:
        return bool(flag)
    return all(t.get("complete", True) for t in (season.get("trades") or []))
