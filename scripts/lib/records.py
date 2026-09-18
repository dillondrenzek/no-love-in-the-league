"""The league record book.

Two kinds of records:

  - Standings-based (available now): best/worst regular-season record, most
    championships. Computed from each season's final standings.
  - Score-based (available once seasons have game scores): most points in a
    week, biggest blowout, etc. Computed from matchups when present.

Meaningless final-week consolation games (see lib/overrides) are excluded from the
score records. Co-champions each count as half a title.

Every record carries a `leaders` list: the record holder first, then the next few
runners-up (up to `LEADER_N`), so the record book can render each record as a
short leaderboard table. The record's own top-level fields mirror `leaders[0]`.

`compute_records` returns whichever are available, so the record book grows
automatically as richer data (scores) is added.
"""

from .data import (name_of, short_name_of, season_trades_complete,
                   season_transactions_known, countable_matchups)
from .standings import get_standings, parse_record
from .overrides import co_champions, meaningless_keys, matchup_key

# Record-book sections, in display order. Each record carries a `section` so the
# records page can group the tables under headings.
SEC_TITLES = "Titles"
SEC_STANDINGS = "Standings"
SEC_SCORING = "Scoring"
SEC_MOVES = "Roster & Draft"
SECTION_ORDER = [SEC_TITLES, SEC_STANDINGS, SEC_SCORING, SEC_MOVES]

# How many rows each record's leaderboard shows: the holder plus runners-up.
LEADER_N = 5


def _win_pct(w, l, t):
    games = w + l + t
    return (w + 0.5 * t) / games if games else 0.0


def _leader(value, *, team=None, owner_name=None, owner_id=None, season=None,
            week=None, sub_value=None, opp_team=None, opp_owner_name=None,
            opp_owner_id=None):
    """One row of a record's leaderboard (the holder or a runner-up)."""
    return {"value": value, "team": team, "owner_name": owner_name,
            "owner_id": owner_id, "season": season, "week": week,
            "sub_value": sub_value, "opp_team": opp_team,
            "opp_owner_name": opp_owner_name, "opp_owner_id": opp_owner_id}


def _record(category, section, leaders):
    """A record whose top-level fields mirror its top leader, plus the full
    `leaders` list (holder + runners-up)."""
    top = leaders[0]
    return {"category": category, "section": section,
            # `tabular`: the holder has a team and/or season, so the record fits the
            # Team·Owner·Season·Value table. All-time franchise aggregates (Most
            # Championships, Most Trades, …) have neither and are hidden from the page.
            "tabular": bool(top.get("team") or top.get("season")),
            "holder": top.get("team") or top.get("owner_name"),
            "value": top["value"], "sub_value": top.get("sub_value"),
            "season": top.get("season"), "week": top.get("week"),
            "owner_id": top.get("owner_id"), "owner_name": top.get("owner_name"),
            "team": top.get("team"),
            "opp_owner_id": top.get("opp_owner_id"),
            "opp_owner_name": top.get("opp_owner_name"),
            "opp_team": top.get("opp_team"),
            "leaders": leaders}


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


def _sacko_count(seasons, franchises):
    """franchise id -> number of dead-last (Sacko) finishes, plus a display name.
    Seasons passed in are already complete, so every last place is awarded."""
    counts, display = {}, {}
    for season in seasons:
        rows = get_standings(season, franchises)
        team_count = len(rows)
        for r in rows:
            if r["finish"] == team_count:                # dead last = Sacko
                fid = r["id"]
                counts[fid] = counts.get(fid, 0) + 1
                display[fid] = short_name_of(fid, franchises) if fid in franchises else r["name"]
    return counts, display


def _standings_records(seasons, franchises, overrides, trade_seasons=None):
    all_rows = [(s["season"], r) for s in seasons for r in get_standings(s, franchises)]
    if not all_rows:
        return []

    def wp(r):
        return _win_pct(r["wins"], r["losses"], r["ties"])

    def std_leader(yr, r):
        return _leader(r["record"], team=r["name"],
                       owner_name=short_name_of(r["id"], franchises),
                       owner_id=r["id"] if r["id"] in franchises else None, season=yr)

    best = sorted(all_rows, key=lambda sr: (wp(sr[1]), sr[1]["wins"]), reverse=True)
    worst = sorted(all_rows, key=lambda sr: (wp(sr[1]), -sr[1]["losses"]))

    records = [
        _record("Best Regular-Season Record", SEC_STANDINGS,
                [std_leader(yr, r) for yr, r in best[:LEADER_N]]),
        _record("Worst Regular-Season Record", SEC_STANDINGS,
                [std_leader(yr, r) for yr, r in worst[:LEADER_N]]),
    ]

    titles, display = _title_count(seasons, franchises, overrides)
    if titles:
        ranked = sorted(titles.items(), key=lambda kv: kv[1], reverse=True)
        # Only interesting once someone has more than a single title.
        if ranked[0][1] > 1:
            leaders = [_leader(_fmt_titles(cnt), owner_name=display.get(fid),
                               owner_id=fid if fid in franchises else None)
                       for fid, cnt in ranked[:LEADER_N] if cnt > 0]
            records.append(_record("Most Championships", SEC_TITLES, leaders))

    sackos, sacko_names = _sacko_count(seasons, franchises)
    if sackos and max(sackos.values()) > 0:
        ranked = sorted(sackos.items(), key=lambda kv: kv[1], reverse=True)
        leaders = [_leader(str(cnt), owner_name=sacko_names.get(fid),
                           owner_id=fid if fid in franchises else None)
                   for fid, cnt in ranked[:LEADER_N] if cnt > 0]
        records.append(_record("Most Sackos", SEC_TITLES, leaders))

    trade_rec = _most_trades(trade_seasons if trade_seasons is not None else seasons, franchises)
    if trade_rec:
        records.append(trade_rec)

    first_overall = _most_first_overall(trade_seasons if trade_seasons is not None else seasons, franchises)
    if first_overall:
        records.append(first_overall)

    tx_pool = trade_seasons if trade_seasons is not None else seasons
    most_tx = _transaction_record(tx_pool, franchises, most=True)
    if most_tx:
        records.append(most_tx)
    most_tx_season = _most_transactions_in_season(tx_pool, franchises)
    if most_tx_season:
        records.append(most_tx_season)
    return records


def _franchise_leaders(counts, franchises, n=LEADER_N):
    """Top-n (fid, count) as leader rows, count rendered as a plain string."""
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for fid, c in ranked[:n]:
        name = short_name_of(fid, franchises) if fid in franchises else fid
        out.append(_leader(str(c), owner_name=name,
                           owner_id=fid if fid in franchises else None))
    return out


def _most_first_overall(seasons, franchises):
    """Franchise that has drafted from the 1.01 (first slot in a season's draft
    order) the most times, across every season on record including an in-progress
    one's projected order. None until someone's done it more than once."""
    counts = {}
    for season in seasons:
        order = season.get("draft_order") or []
        if order:
            counts[order[0]] = counts.get(order[0], 0) + 1
    if not counts:
        return None
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] < 2:
        return None
    leaders = _franchise_leaders({fid: c for fid, c in counts.items() if c >= 1}, franchises)
    return _record("Most Times Drafting 1.01", SEC_MOVES, leaders)


def _most_trades(seasons, franchises):
    """Franchise with the most trades participated in (both sides count), over
    every recorded trade."""
    counts = {}
    for season in seasons:
        for trade in season.get("trades") or []:
            for fid in trade.get("teams") or []:
                counts[fid] = counts.get(fid, 0) + 1
    if not counts:
        return None
    return _record("Most Trades", SEC_MOVES, _franchise_leaders(counts, franchises))


def _transaction_totals(seasons, franchises):
    """{fid: total waiver/FA moves} over the seasons whose transactions are known.
    Transaction data starts in 2018 (older seasons 404 on ESPN), so this is a
    total over the available years — the accepted baseline for these records."""
    totals = {}
    for season in seasons:
        if not season_transactions_known(season):
            continue
        txmap = season.get("transactions") or {}
        for fid in {r["id"] for r in get_standings(season, franchises)}:
            totals[fid] = totals.get(fid, 0) + (txmap.get(fid) or {}).get("moves", 0)
    return totals


def _transaction_record(seasons, franchises, most):
    """Most (or least) waiver/FA moves over the years we have data for (2018+).
    Every owner with at least one known-transaction season is ranked."""
    totals = _transaction_totals(seasons, franchises)
    if not totals:
        return None
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=most)
    leaders = []
    for fid, c in ranked[:LEADER_N]:
        name = short_name_of(fid, franchises) if fid in franchises else fid
        leaders.append(_leader(str(c), owner_name=name,
                               owner_id=fid if fid in franchises else None))
    return _record("Most Transactions" if most else "Fewest Transactions",
                   SEC_MOVES, leaders)


def _most_transactions_in_season(seasons, franchises):
    """Single-season high for waiver/FA moves by one owner (over 2018+ data)."""
    rows = []      # (moves, year, fid)
    for season in seasons:
        if not season_transactions_known(season):
            continue
        for fid, c in (season.get("transactions") or {}).items():
            moves = c.get("moves", 0)
            if moves > 0:
                rows.append((moves, season["season"], fid))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0], reverse=True)
    leaders = []
    for moves, year, fid in rows[:LEADER_N]:
        name = short_name_of(fid, franchises) if fid in franchises else fid
        leaders.append(_leader(str(moves), owner_name=name,
                               owner_id=fid if fid in franchises else None, season=year))
    return _record("Most Transactions in a Season", SEC_MOVES, leaders)


def _team_games(seasons, overrides):
    for season in seasons:
        year = season["season"]
        skip = meaningless_keys(season, overrides)
        for m in countable_matchups(season):    # complete-week games only
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

    def game_leader(g, value, sub_value=None, with_opp=False):
        opp = {}
        if with_opp:
            oid = g["opp_id"]
            opp = {"opp_team": team_for(oid, g["season"]),
                   "opp_owner_name": short_name_of(oid, franchises),
                   "opp_owner_id": oid if oid in franchises else None}
        return _leader(value, team=team_for(g["id"], g["season"]),
                       owner_name=short_name_of(g["id"], franchises),
                       owner_id=g["id"] if g["id"] in franchises else None,
                       season=g["season"], week=g["week"], sub_value=sub_value, **opp)

    def score_pair(g):
        hi, lo = sorted((g["score"], g["opp_score"]), reverse=True)
        return f"{hi:.1f}–{lo:.1f}"

    most = sorted(games, key=lambda g: g["score"], reverse=True)
    fewest = sorted(games, key=lambda g: g["score"])
    blowout = sorted(games, key=lambda g: g["margin"], reverse=True)

    # Combined score is identical for both sides of a game, so de-dupe by matchup
    # before ranking (otherwise every top game would appear twice).
    seen, combined = set(), []
    for g in sorted(games, key=lambda g: g["combined"], reverse=True):
        key = (g["season"], g["week"], frozenset((g["id"], g["opp_id"])))
        if key in seen:
            continue
        seen.add(key)
        combined.append(g)

    # "Most Points in a Season" is regular-season points-for only, so playoff
    # games are excluded from the sum even though they still count per-week above.
    totals = _season_totals(g for g in games if not g["playoff"])
    season_ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    season_leaders = [
        _leader(f"{pts:.2f}", team=team_for(fid, yr),
                owner_name=short_name_of(fid, franchises),
                owner_id=fid if fid in franchises else None, season=yr)
        for (yr, fid), pts in season_ranked[:LEADER_N]]

    return [
        _record("Most Points in a Week", SEC_SCORING,
                [game_leader(g, f"{g['score']:.2f}") for g in most[:LEADER_N]]),
        _record("Most Points in a Season", SEC_SCORING, season_leaders),
        _record("Fewest Points in a Week", SEC_SCORING,
                [game_leader(g, f"{g['score']:.2f}") for g in fewest[:LEADER_N]]),
        _record("Biggest Blowout", SEC_SCORING,
                [game_leader(g, f"{g['margin']:.2f}", sub_value=score_pair(g), with_opp=True)
                 for g in blowout[:LEADER_N]]),
        _record("Highest Combined Score", SEC_SCORING,
                [game_leader(g, f"{g['combined']:.2f}", sub_value=score_pair(g), with_opp=True)
                 for g in combined[:LEADER_N]]),
    ]


def compute_records(seasons, franchises=None, overrides=None, trade_seasons=None):
    """All currently-computable record-book entries. Standings/score records use
    `seasons` (finished only); the trades record uses `trade_seasons` (defaults to
    `seasons`) so in-progress trades still count.

    Each record includes a `leaders` list (holder first, then runners-up)."""
    franchises = franchises or {}
    overrides = overrides or {}
    records = _standings_records(seasons, franchises, overrides, trade_seasons)
    return records + _score_records(seasons, franchises, overrides)
