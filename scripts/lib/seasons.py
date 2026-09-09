"""Per-season display rows, shared by the standings (History) and per-season
generators.

`season_rows` composes a season's standings with league overrides (co-champs),
heat colors, finish tags, and note bullets into the row shape the standings
table renders — so both generate_standings and generate_seasons build the same
structure from one place instead of importing it from each other.
"""

from .standings import get_standings, has_points, provisional_standings
from .render import heat_color
from .overrides import co_champions
from .state import state_of


def _tag(finish, team_count, is_co):
    if is_co:
        return "cochamp"
    if finish == 1:
        return "shiva"
    if finish == team_count:
        return "sacko"
    return None


def season_rows(season, franchises, overrides, notes, trade_note=True):
    rows = get_standings(season, franchises)
    # A live season (season/playoffs) shows a standings table even before any game
    # is played: fall back to a 0-0 provisional table in the current order, which
    # fills in with real records as games come in.
    if not rows and state_of(season) in ("season", "playoffs"):
        rows = provisional_standings(season, franchises, zero_points=True)
    points = has_points(rows)
    co = set(co_champions(season["season"], overrides))
    team_count = len(rows)
    pfs = [r["points_for"] for r in rows if r["points_for"] is not None]
    lo, hi = (min(pfs), max(pfs)) if pfs else (0, 0)

    out = []
    for r in rows:
        row = {
            "finish": r["finish"],
            "team": r["name"],
            "owner_id": r["id"] if r["id"] in franchises else None,
            "owner_name": franchises[r["id"]]["name"] if r["id"] in franchises else None,
            "record": r["record"],
            "tag": _tag(r["finish"], team_count, r["id"] in co),
        }
        if points:
            row["pf"] = r["points_for"]
            row["pf_color"] = heat_color(r["points_for"], lo, hi)
            row["pa"] = r["points_against"]
        out.append(row)
    # Hand-written notes, plus an auto "N trades completed" bullet when any went
    # through that season.
    season_notes = list(notes.get(season["season"]) or [])
    n_trades = len(season.get("trades") or [])
    if trade_note and n_trades:
        season_notes.append(f"{n_trades} trade{'s' if n_trades != 1 else ''} completed")

    return {
        "year": season["season"], "points": points, "rows": out,
        "notes": season_notes,
    }
