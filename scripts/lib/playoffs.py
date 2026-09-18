"""Reconstruct the league's playoff brackets for a season.

Every year the league plays two brackets over the three playoff weeks: a
**Shiva** (championship — the teams that finish in the top playoff seats) and a
**Sacko** (toilet bowl — everyone else, playing to avoid finishing last). The
field size has changed over the years (a 6-team championship in most seasons, an
8-team championship in 2017-2022, and 10-team leagues in 2014-2015), so this
module doesn't assume a fixed shape. It reads the *actual* ESPN matchups as the
real games, groups each bracket's teams by round, and captions the games from the
final standings — the authoritative placement — so the bracket always agrees with
how the season actually finished.

`playoff_bracket(season, franchises)` returns the two brackets as nested game
dicts, or None when the season has no usable playoff data. Pure — no network.
"""

from .data import regular_season_matchups, short_name_of


def _reg_stats(season):
    """{fid: {w,l,t,pf}} from countable regular-season games."""
    stats = {}
    for m in regular_season_matchups(season):
        hs, as_ = m["home_score"], m["away_score"]
        for fid, pf, pa in ((m["home"], hs, as_), (m["away"], as_, hs)):
            d = stats.setdefault(fid, {"w": 0, "l": 0, "t": 0, "pf": 0.0})
            d["pf"] += pf
            if pf > pa:
                d["w"] += 1
            elif pa > pf:
                d["l"] += 1
            else:
                d["t"] += 1
    return stats


def _reg_seeds(season):
    """{fid: seed} for the whole league, 1..N by regular-season record then PF.
    Used only for the small seed labels shown on the bracket."""
    stats = _reg_stats(season)
    order = sorted(stats, key=lambda f: (stats[f]["w"] + 0.5 * stats[f]["t"],
                                         stats[f]["pf"]), reverse=True)
    return {fid: i + 1 for i, fid in enumerate(order)}


def _playoff_weeks(season):
    """The playoff weeks actually played (weeks past the regular season with
    reported scores), in order."""
    reg = season.get("weeks_in_regular_season") or 14
    weeks = sorted({m["week"] for m in season.get("matchups") or []
                    if m.get("week", 0) > reg and m.get("home_score") is not None})
    return weeks


def _playoff_games(season, members, weeks):
    """Actual head-to-head games played *among* `members` in the playoff weeks,
    grouped by week: {week: [(home, away, home_score, away_score)...]}."""
    wset = set(weeks)
    by_week = {}
    for m in season.get("matchups") or []:
        w = m.get("week")
        if w not in wset or m.get("home_score") is None:
            continue
        if m["home"] in members and m["away"] in members:
            by_week.setdefault(w, []).append(
                (m["home"], m["away"], m["home_score"], m["away_score"]))
    return by_week


_ORD = {1: "1st", 3: "3rd", 5: "5th", 7: "7th", 9: "9th", 11: "11th",
        13: "13th", 15: "15th"}


def _bracket(season, franchises, members, seeds, weeks, kind, n_teams):
    """Reconstruct one bracket from the *actual* games played among its teams.

    kind='shiva' (championship, top finishers) or 'sacko' (consolation, bottom
    finishers). Advancement follows the real ESPN results; games are captioned
    from the final standings. Returns {'title', 'rounds': [...]} or None if the
    bracket didn't play a recognizable set of games."""
    logos = season.get("team_logos") or {}
    # A 4-team Sacko (the 8-team-playoff and 10-team-league eras) settled 9th and
    # the Sacko in the second-to-last week; the final week is just exhibition, so
    # we don't show it.
    if kind == "sacko" and len(members) == 4 and len(weeks) >= 3:
        weeks = weeks[:-1]
    by_week = _playoff_games(season, members, weeks)
    played_weeks = [w for w in weeks if by_week.get(w)]
    if len(played_weeks) < 2 or len(members) < 2:
        return None
    weeks = played_weeks

    def side(fid, score):
        return {"seed": seeds.get(fid), "fid": fid,
                "name": (season.get("teams", {}).get(fid) or short_name_of(fid, franchises)),
                "logo": logos.get(fid, ""), "score": score}

    def make_game(week, h, a, hs, as_, label=None):
        winner, loser = (h, a) if hs >= as_ else (a, h)
        return {"label": label, "week": week, "decided": True,
                "home": side(h, hs), "away": side(a, as_),
                "winner_fid": winner, "loser_fid": loser}

    def bye(week, fid):
        return {"label": None, "week": week, "decided": False, "bye": True,
                "home": side(fid, None), "away": None,
                "winner_fid": fid, "loser_fid": None}

    # Final standings are the authoritative placement. Two teams sit in adjacent
    # seats (1-2, 3-4, ...) exactly when the game between them decides that
    # placement; caption a game from the seats of its two teams. The top seat is
    # the Shiva (champion), the very last seat is the Sacko.
    rank = {f: i for i, f in enumerate(season.get("final_standings") or [])}

    def placement(h, a, winner):
        # Caption a game only when it truly decided a placement: the two teams
        # sit in adjacent final seats AND the team that won the game finished
        # ahead. In the old round-robin consolations, order came from cumulative
        # record, not one game, so those games stay uncaptioned rather than wrong.
        if h not in rank or a not in rank:
            return None
        lo, hi = sorted((rank[h], rank[a]))
        if lo % 2 != 0 or hi != lo + 1 or rank[winner] != lo:
            return None
        if lo == 0:
            return "Shiva"
        if hi == n_teams - 1:
            return "Sacko"
        return _ORD.get(lo + 1, "%dth" % (lo + 1)) + " Place"

    # Round-1 byes go to the strongest championship seeds / the weakest Sacko
    # seeds; the count is whatever a standard bracket needs (size minus the
    # largest power of two that fits). ESPN still schedules them a meaningless
    # game that week, so we render byes instead of that game.
    size = len(members)
    pow2 = 1
    while pow2 * 2 <= size:
        pow2 *= 2
    n_byes = size - pow2
    ordered = sorted(members, key=lambda f: seeds.get(f, 99))   # best seed first
    if kind == "shiva":
        bye_fids = ordered[:n_byes]
    else:                                                       # Sacko: worst seeds bye
        bye_fids = ordered[len(ordered) - n_byes:] if n_byes else []
    byes = set(bye_fids)

    # ESPN makes some pairs play twice (a placement game plus a dead rematch the
    # next week). Keep only the standings-consistent copy — the one whose winner
    # actually finished ahead — so each result shows once, correctly.
    seen = {}
    for w in weeks:
        for h, a, hs, as_ in by_week[w]:
            pair = frozenset((h, a))
            winner = h if hs >= as_ else a
            loser = a if winner == h else h
            consistent = rank.get(winner, 99) < rank.get(loser, 99)
            if pair not in seen or consistent:
                seen[pair] = (w, h, a)
    keep = set(seen.values())

    def order_key(g):                                 # title game first each round
        lab = g["label"]
        if lab == ("Shiva" if kind == "shiva" else "Sacko"):
            return -1
        pair = (g["home"]["fid"], g["away"]["fid"] if g["away"] else None)
        base = min(rank.get(pair[0], 99), rank.get(pair[1], 99))
        return base if kind == "shiva" else -base

    rounds = []
    last = len(weeks) - 1
    for i, w in enumerate(weeks):
        games = []
        playing = set()
        for h, a, hs, as_ in by_week[w]:
            if i == 0 and h in byes and a in byes:
                continue                              # bye pairing: shown as byes
            if (w, h, a) not in keep:
                continue                              # dead rematch
            playing.add(h)
            playing.add(a)
            winner = h if hs >= as_ else a
            games.append(make_game(w, h, a, hs, as_, placement(h, a, winner)))
        if i == 0 and n_byes:                         # round 1: byes bookend
            tops = [f for f in bye_fids if f not in playing]
            middle = sorted(games, key=lambda g: g["home"]["seed"] or 99)
            half = (len(tops) + 1) // 2
            games = ([bye(w, f) for f in tops[:half]] + middle
                     + [bye(w, f) for f in tops[half:]])
        elif i == last:                               # final round: title on top
            games.sort(key=order_key)
        else:
            games.sort(key=lambda g: (g["home"]["seed"] or 99) + (g["away"]["seed"] or 99)
                       if g["away"] else 99)
        rounds.append({"week": w, "games": games, "consolation": []})
    rounds = [r for r in rounds if r["games"]]     # drop rounds with no games
    if len(rounds) < 2:
        return None
    for n, r in enumerate(rounds, 1):
        r["label"] = "Round %d" % n
    return {"title": title_for(kind), "rounds": rounds}


def title_for(kind):
    return "Shiva Bracket" if kind == "shiva" else "Sacko Bracket"


def playoff_bracket(season, franchises):
    """{'shiva': {...}, 'sacko': {...}, 'seeds': {fid: n}} or None.

    Membership comes from the final standings: the championship bracket is the
    teams that finished in the top playoff seats, the Sacko is everyone else.
    That needs no seeding rules and works for every era's field size."""
    fs = season.get("final_standings") or []
    weeks = _playoff_weeks(season)
    n_playoff = len(season.get("playoff_teams") or [])
    if len(fs) < 4 or len(weeks) < 2 or n_playoff not in (6, 8):
        return None
    n = len(fs)
    shiva_members = set(fs[:n_playoff])
    sacko_members = set(fs[n_playoff:])
    seeds = _reg_seeds(season)
    shiva_b = _bracket(season, franchises, shiva_members, seeds, weeks, "shiva", n)
    sacko_b = _bracket(season, franchises, sacko_members, seeds, weeks, "sacko", n)
    if not shiva_b or not sacko_b:
        return None
    return {"shiva": shiva_b, "sacko": sacko_b, "seeds": seeds}
