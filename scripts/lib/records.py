"""The league record book.

Two kinds of records:

  - Standings-based (available now): best/worst regular-season record, most
    championships. Computed from each season's final standings.
  - Score-based (available once seasons have game scores): most points in a
    week, biggest blowout, etc. Computed from matchups when present.

Meaningless final-week consolation games (see lib/rulings) are excluded from the
score records. Co-champions each count as half a title.

`compute_records` returns whichever are available, so the record book grows
automatically as richer data (scores) is added.
"""

from .data import name_of, short_name_of
from .standings import get_standings, parse_record
from .rulings import co_champions, meaningless_keys, matchup_key


def _win_pct(w, l, t):
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def _title_count(seasons, franchises, overrides):
    """franchise id -> total titles (co-championships count 0.5), plus a display name."""
    titles = {}
    display = {}
    for season in seasons:
        year = season["season"]
        rows = {r["id"]: r for r in get_standings(season, franchises)}
        co = co_champions(year, overrides)
        champs = [(fid, 0.5) for fid in co] if co else \
                 [(fid, 1.0) for fid, r in rows.items() if r["finish"] == 1]
        for fid, share in champs:
            titles[fid] = titles.get(fid, 0) + share
            display[fid] = short_name_of(fid, franchises) if fid in franchises else rows.get(fid, {}).get("name", fid)
    return titles, display


def _fmt_titles(n):
    whole = int(n)
    half = (n - whole) >= 0.5
    if whole == 0:
        return "½" if half else "0"
    return f"{whole}½" if half else str(whole)


def _standings_row_entry(category, year, row, value, franchises):
    fid = row["id"]
    return {"category": category, "holder": row["name"], "value": value,
            "season": year, "week": None,
            "owner_id": fid if fid in franchises else None,
            "owner_name": short_name_of(fid, franchises),
            "team": row["name"]}


def _standings_records(seasons, franchises, overrides):
    all_rows = [(s["season"], r) for s in seasons for r in get_standings(s, franchises)]
    if not all_rows:
        return []

    best = max(all_rows, key=lambda sr: (_win_pct(sr[1]["wins"], sr[1]["losses"], sr[1]["ties"]), sr[1]["wins"]))
    worst = min(all_rows, key=lambda sr: (_win_pct(sr[1]["wins"], sr[1]["losses"], sr[1]["ties"]), -sr[1]["losses"]))

    records = [
        _standings_row_entry("Best Regular-Season Record", best[0], best[1], best[1]["record"], franchises),
        _standings_row_entry("Worst Regular-Season Record", worst[0], worst[1], worst[1]["record"], franchises),
    ]

    titles, display = _title_count(seasons, franchises, overrides)
    if titles:
        champ_id, champ_count = max(titles.items(), key=lambda kv: kv[1])
        # Only interesting once someone has more than a single title.
        if champ_count > 1:
            records.append({"category": "Most Championships", "holder": display.get(champ_id),
                            "value": _fmt_titles(champ_count), "season": None, "week": None,
                            "owner_id": champ_id if champ_id in franchises else None,
                            "owner_name": display.get(champ_id), "team": None})
    return records


def _team_games(seasons, overrides):
    for season in seasons:
        year = season["season"]
        skip = meaningless_keys(season, overrides)
        for m in season.get("matchups", []) or []:
            if matchup_key(m) in skip:
                continue
            hs, as_ = m["home_score"], m["away_score"]
            playoff = bool(m.get("playoff"))
            yield {"id": m["home"], "opp_id": m["away"], "score": hs, "opp_score": as_,
                   "margin": hs - as_, "combined": hs + as_,
                   "season": year, "week": m["week"], "playoff": playoff}
            yield {"id": m["away"], "opp_id": m["home"], "score": as_, "opp_score": hs,
                   "margin": as_ - hs, "combined": hs + as_,
                   "season": year, "week": m["week"], "playoff": playoff}


def _season_totals(games):
    """(season, franchise_id) -> total regular-season points, summed from `games`."""
    totals = {}
    for g in games:
        key = (g["season"], g["id"])
        totals[key] = totals.get(key, 0.0) + g["score"]
    return totals


def _score_records(seasons, franchises, overrides):
    games = list(_team_games(seasons, overrides))
    if not games:
        return []

    teams_by_year = {s["season"]: s.get("teams", {}) for s in seasons}

    def team_for(fid, year):
        return teams_by_year.get(year, {}).get(fid)

    def holder_for(fid, year):
        return team_for(fid, year) or short_name_of(fid, franchises)

    def entry(category, g, value, sub_value=None, with_opp=False):
        e = {"category": category, "holder": holder_for(g["id"], g["season"]),
             "value": value, "sub_value": sub_value,
             "season": g["season"], "week": g["week"],
             "owner_id": g["id"] if g["id"] in franchises else None,
             "owner_name": short_name_of(g["id"], franchises),
             "team": team_for(g["id"], g["season"]),
             "opp_owner_id": None, "opp_owner_name": None, "opp_team": None}
        if with_opp:
            oid = g["opp_id"]
            e["opp_owner_id"] = oid if oid in franchises else None
            e["opp_owner_name"] = short_name_of(oid, franchises)
            e["opp_team"] = team_for(oid, g["season"])
        return e

    def score_pair(g):
        hi, lo = sorted((g["score"], g["opp_score"]), reverse=True)
        return f"{hi:.1f}–{lo:.1f}"

    most = max(games, key=lambda g: g["score"])
    fewest = min(games, key=lambda g: g["score"])
    blowout = max(games, key=lambda g: g["margin"])
    combined = max(games, key=lambda g: g["combined"])

    # "Most Points in a Season" is regular-season points-for only, so playoff
    # games are excluded from the sum even though they still count toward the
    # per-week records above.
    totals = _season_totals(g for g in games if not g["playoff"])
    (top_year, top_fid), top_points = max(totals.items(), key=lambda kv: kv[1])
    season_leader = {
        "category": "Most Points in a Season", "holder": holder_for(top_fid, top_year),
        "value": f"{top_points:.2f}", "sub_value": None,
        "season": top_year, "week": None,
        "owner_id": top_fid if top_fid in franchises else None,
        "owner_name": short_name_of(top_fid, franchises),
        "team": team_for(top_fid, top_year),
        "opp_owner_id": None, "opp_owner_name": None, "opp_team": None,
    }

    return [
        entry("Most Points in a Week", most, f"{most['score']:.2f}"),
        season_leader,
        entry("Fewest Points in a Week", fewest, f"{fewest['score']:.2f}"),
        entry("Biggest Blowout", blowout, f"{blowout['margin']:.2f}",
              sub_value=score_pair(blowout), with_opp=True),
        entry("Highest Combined Score", combined, f"{combined['combined']:.2f}",
              sub_value=score_pair(combined), with_opp=True),
    ]


def compute_records(seasons, franchises=None, overrides=None):
    """All currently-computable record-book entries."""
    franchises = franchises or {}
    overrides = overrides or {}
    return (_standings_records(seasons, franchises, overrides)
            + _score_records(seasons, franchises, overrides))
