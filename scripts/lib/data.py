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
    """Display name for a franchise id, falling back to the id itself."""
    f = franchises.get(franchise_id)
    return f["name"] if f else franchise_id


def regular_season_matchups(season):
    """Matchups that count toward standings (i.e. not playoff games)."""
    return [m for m in season.get("matchups", []) if not m.get("playoff")]
