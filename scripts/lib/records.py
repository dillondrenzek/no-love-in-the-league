"""The league record book.

Two kinds of records:

  - Standings-based (available now): best/worst regular-season record, most
    championships. Computed from each season's final standings.
  - Score-based (available once seasons have game scores): most points in a
    week, biggest blowout, etc. Computed from matchups when present.

`compute_records` returns whichever are available, so the record book grows
automatically as richer data (scores) is added.
"""

from .data import name_of
from .standings import get_standings, parse_record


def _win_pct(w, l, t):
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def _standings_records(seasons, franchises):
    all_rows = []          # (season, row)
    titles = {}            # franchise id -> count of finish==1
    title_display = {}     # franchise id -> a name to show
    for season in seasons:
        rows = get_standings(season, franchises)
        for r in rows:
            all_rows.append((season["season"], r))
            if r["finish"] == 1:
                titles[r["id"]] = titles.get(r["id"], 0) + 1
                title_display[r["id"]] = name_of(r["id"], franchises) if r["id"] in franchises else r["name"]

    if not all_rows:
        return []

    best = max(all_rows, key=lambda sr: (_win_pct(sr[1]["wins"], sr[1]["losses"], sr[1]["ties"]), sr[1]["wins"]))
    worst = min(all_rows, key=lambda sr: (_win_pct(sr[1]["wins"], sr[1]["losses"], sr[1]["ties"]), -sr[1]["losses"]))
    champ_id, champ_count = max(titles.items(), key=lambda kv: kv[1]) if titles else (None, 0)
    champ_name = title_display.get(champ_id)

    records = [
        {"category": "Best Regular-Season Record", "holder": best[1]["name"],
         "value": best[1]["record"], "season": best[0], "week": None},
        {"category": "Worst Regular-Season Record", "holder": worst[1]["name"],
         "value": worst[1]["record"], "season": worst[0], "week": None},
    ]
    # Only meaningful once a team name repeats as champion. Until owners are
    # linked across years (franchises.yml), every year's champion is a distinct
    # name, so a count of 1 tells us nothing — skip it.
    if champ_name and champ_count > 1:
        records.append({"category": "Most Championships", "holder": champ_name,
                        "value": str(champ_count), "season": None, "week": None})
    return records


def _team_games(seasons):
    for season in seasons:
        year = season["season"]
        for m in season.get("matchups", []):
            hs, as_ = m["home_score"], m["away_score"]
            yield {"id": m["home"], "score": hs, "opp_score": as_,
                   "margin": hs - as_, "combined": hs + as_, "season": year, "week": m["week"]}
            yield {"id": m["away"], "score": as_, "opp_score": hs,
                   "margin": as_ - hs, "combined": hs + as_, "season": year, "week": m["week"]}


def _score_records(seasons, franchises):
    games = list(_team_games(seasons))
    if not games:
        return []

    # franchise id -> that season's team name, per year, for display.
    teams_by_year = {s["season"]: s.get("teams", {}) for s in seasons}

    def holder_name(g):
        return teams_by_year.get(g["season"], {}).get(g["id"]) or name_of(g["id"], franchises)

    def entry(category, g, value):
        return {"category": category, "holder": holder_name(g),
                "value": value, "season": g["season"], "week": g["week"]}

    most = max(games, key=lambda g: g["score"])
    fewest = min(games, key=lambda g: g["score"])
    blowout = max(games, key=lambda g: g["margin"])
    combined = max(games, key=lambda g: g["combined"])
    return [
        entry("Most Points in a Week", most, f"{most['score']:.2f}"),
        entry("Fewest Points in a Week", fewest, f"{fewest['score']:.2f}"),
        entry("Biggest Blowout", blowout,
              f"{blowout['margin']:.2f} ({blowout['score']:.1f}-{blowout['opp_score']:.1f})"),
        entry("Highest Combined Score", combined, f"{combined['combined']:.2f}"),
    ]


def compute_records(seasons, franchises=None):
    """All currently-computable record-book entries."""
    franchises = franchises or {}
    return _standings_records(seasons, franchises) + _score_records(seasons, franchises)
