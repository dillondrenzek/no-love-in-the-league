"""Loading the source-of-truth YAML and resolving franchise ids to names.

This is the only module that touches the filesystem. Everything downstream works
on plain dicts/lists so it's easy to test with in-memory data.
"""

import yaml
from pathlib import Path

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

    In-progress seasons (`status: in_progress`, written by the importer mid-year)
    are left out by default so partial results don't skew all-time standings,
    records, or owner profiles. The per-season pages pass include_in_progress=True
    to show the live season on its own page.
    """
    seasons = []
    for path in sorted(Path(seasons_dir).glob("*.yml")):
        season = _read_yaml(path)
        if not include_in_progress and season.get("status") == "in_progress":
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


def regular_season_matchups(season):
    """Matchups that count toward standings (i.e. not playoff games)."""
    return [m for m in (season.get("matchups") or []) if not m.get("playoff")]


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
