"""Correct the consolation (Sacko) end of a season's final standings.

In the years with a four-team Sacko bracket (the 8-team-playoff era and the
10-team leagues), the toilet bowl was a two-week single-elimination bracket:
semifinals in the first playoff week, then a placement final in the second-to-last
week (the winners play for the top consolation seat, the losers play for last).
The final playoff week is exhibition. ESPN, however, ranked those teams by
cumulative points across all three weeks, which disagrees with the bracket — so
its 9th-11th (or 7th-9th) ordering is wrong. `corrected_standings` recomputes
that tail from the bracket. The last-place team (the Sacko) is unaffected.

Applied by the importer (scripts/import_espn.py) when it writes a completed
season, so the YAML on disk is already correct and survives re-imports — no manual
fix-ups. Pure: takes and returns plain data and imports nothing.
"""


def _sacko_games(season, members, week):
    s = set(members)
    return [(m["home"], m["away"], m["home_score"], m["away_score"])
            for m in season.get("matchups") or []
            if m.get("week") == week and m.get("home_score") is not None
            and m["home"] in s and m["away"] in s]


def _winner_loser(game):
    h, a, hs, as_ = game
    return (h, a) if hs >= as_ else (a, h)


def corrected_standings(season):
    """Return the season's final_standings with the four-team Sacko tail reordered
    to match its two-week bracket. Returns the original order unchanged for any
    season that isn't a clean four-team consolation."""
    fs = list(season.get("final_standings") or [])
    n_playoff = len(season.get("playoff_teams") or [])
    reg = season.get("weeks_in_regular_season") or 14
    sacko = fs[n_playoff:]
    if len(sacko) != 4:
        return fs
    weeks = sorted({m["week"] for m in season.get("matchups") or []
                    if m.get("week", 0) > reg and m.get("home_score") is not None})
    if len(weeks) < 2:
        return fs
    g1 = _sacko_games(season, sacko, weeks[0])
    g2 = _sacko_games(season, sacko, weeks[1])
    if len(g1) != 2 or len(g2) != 2:
        return fs
    winners, losers = set(), set()
    for g in g1:
        w, l = _winner_loser(g)
        winners.add(w)
        losers.add(l)
    upper = next((g for g in g2 if set(g[:2]) == winners), None)
    lower = next((g for g in g2 if set(g[:2]) == losers), None)
    if upper is None or lower is None:
        return fs
    uw, ul = _winner_loser(upper)
    lw, ll = _winner_loser(lower)
    tail = [uw, ul, lw, ll]                    # top consolation seat -> Sacko
    if set(tail) != set(sacko):
        return fs
    return fs[:n_playoff] + tail
