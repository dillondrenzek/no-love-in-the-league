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


def load_seasons(seasons_dir=SEASONS_DIR):
    """Return a list of season dicts, most recent season first."""
    seasons = []
    for path in sorted(Path(seasons_dir).glob("*.yml")):
        seasons.append(_read_yaml(path))
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
    return [m for m in season.get("matchups", []) if not m.get("playoff")]
