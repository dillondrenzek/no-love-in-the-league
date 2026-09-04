"""Standings for a single season.

A season carries its results in one of two forms:

  - `standings`: explicit final-standings rows (finish, team, W-L-T record) as
    pulled from ESPN's history page. Used when we don't have game scores yet.
  - `matchups`: individual games with scores. When present, standings are
    computed from them, which also unlocks points-for/against and the score
    record book.

`get_standings()` normalizes either form into the same list of rows so the
generators don't care which a season uses.
"""

from .data import regular_season_matchups, name_of, short_name_of


def parse_record(record):
    """'9-5-0' or '7-6-1' -> (wins, losses, ties)."""
    parts = [int(x) for x in record.split("-")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def record_string(row):
    """W-L, or W-L-T when there are ties."""
    if row.get("ties"):
        return f"{row['wins']}-{row['losses']}-{row['ties']}"
    return f"{row['wins']}-{row['losses']}"


def _from_matchups(season, franchises):
    stats = {}

    def team(fid):
        return stats.setdefault(
            fid,
            {"id": fid, "wins": 0, "losses": 0, "ties": 0,
             "points_for": 0.0, "points_against": 0.0},
        )

    for m in regular_season_matchups(season):
        home, away = team(m["home"]), team(m["away"])
        hs, as_ = m["home_score"], m["away_score"]
        home["points_for"] += hs
        home["points_against"] += as_
        away["points_for"] += as_
        away["points_against"] += hs
        if hs > as_:
            home["wins"] += 1
            away["losses"] += 1
        elif as_ > hs:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1

    rows = list(stats.values())
    rows.sort(key=lambda r: (r["wins"], r["points_for"]), reverse=True)

    final = season.get("final_standings")
    if final:
        order = {fid: i for i, fid in enumerate(final)}
        rows.sort(key=lambda r: order.get(r["id"], len(order)))

    season_teams = season.get("teams", {})
    for i, r in enumerate(rows, start=1):
        r["finish"] = i
        # Prefer this season's team name; fall back to the franchise's first name.
        r["name"] = season_teams.get(r["id"]) or short_name_of(r["id"], franchises)
        r["record"] = record_string(r)
        r["points_for"] = round(r["points_for"], 1)
        r["points_against"] = round(r["points_against"], 1)
    return rows


def _from_explicit(season):
    rows = []
    for e in season.get("standings", []):
        wins, losses, ties = parse_record(e["record"])
        rows.append({
            "id": e["team"], "name": e["team"], "finish": e["finish"],
            "wins": wins, "losses": losses, "ties": ties,
            "record": record_string({"wins": wins, "losses": losses, "ties": ties}),
            "points_for": None, "points_against": None,
        })
    rows.sort(key=lambda r: r["finish"])
    return rows


def get_standings(season, franchises=None):
    """Normalized standings rows for a season, best finish first.

    Row: {id, name, finish, wins, losses, ties, record, points_for, points_against}.
    points_for/against are None for seasons that only have explicit standings.
    """
    if season.get("matchups"):
        return _from_matchups(season, franchises or {})
    return _from_explicit(season)


def provisional_standings(season, franchises=None, zero_points=False):
    """Preseason rows for an in-progress season with no games yet: every team at
    0-0, ordered by the season's `final_standings` (its current order) and named
    from `teams`. Lets a not-yet-kicked-off season still list its owners.

    `zero_points=True` gives 0.0 points-for/against so the standings table shows
    PF/PA columns (at 0); the default leaves them None so the owner-profile
    season row renders "—" and doesn't skew that owner's PF heat scale.
    """
    pts = 0.0 if zero_points else None
    order = season.get("final_standings") or []
    teams = season.get("teams", {})
    rows = []
    for i, fid in enumerate(order, start=1):
        rows.append({
            "id": fid, "name": teams.get(fid) or short_name_of(fid, franchises or {}),
            "finish": i, "wins": 0, "losses": 0, "ties": 0, "record": "0-0",
            "points_for": pts, "points_against": pts,
        })
    return rows


def has_points(rows):
    """True when every row has points data (i.e. came from matchups)."""
    return bool(rows) and all(r.get("points_for") is not None for r in rows)
