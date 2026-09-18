"""Reconstruct a season's playoff bracket from the *league's rules*, not from
ESPN's schedule, and derive the true final standings from it.

ESPN forces a game every week, so its playoff pairings and its cumulative-points
ranking often disagree with how our bracket actually works. Our rules win: we seed
by the league rule, walk the bracket, and decide each game by the two teams' actual
scores that week — even for a game ESPN never scheduled (e.g. a 9th-place game
where the two teams were each parked against an already-eliminated team). ESPN's
extra games are ignored.

Covered here:
  * Four-team Sacko (8-team-playoff era, 10-team leagues): a two-week single-elim
    toilet bowl; the final week is exhibition.
  * Six-team brackets from 2024 on: full rule-based reconstruction of both the
    Shiva (championship) and Sacko (toilet bowl) brackets, including the 2025+
    second-round reseed ("Luke's Rule").
  * 2023 and earlier six-team seasons decided every place in the final week under
    a different format, so they're left as ESPN recorded them.

Pure: takes and returns plain data, imports nothing.
"""


def _games_among(season, members, week):
    s = set(members)
    return [(m["home"], m["away"], m["home_score"], m["away_score"])
            for m in season.get("matchups") or []
            if m.get("week") == week and m.get("home_score") is not None
            and m["home"] in s and m["away"] in s]


def _winner_loser(game):
    h, a, hs, as_ = game
    return (h, a) if hs >= as_ else (a, h)


def _playoff_weeks(season):
    reg = season.get("weeks_in_regular_season") or 14
    return sorted({m["week"] for m in season.get("matchups") or []
                   if m.get("week", 0) > reg and m.get("home_score") is not None})


def _record_stats(season):
    """{fid: (wins, points_for)} over the countable regular season."""
    reg = season.get("weeks_in_regular_season") or 14
    stats = {}
    for m in season.get("matchups") or []:
        if m.get("week", 0) > reg or m.get("home_score") is None:
            continue
        hs, as_ = m["home_score"], m["away_score"]
        for f, pf, pa in ((m["home"], hs, as_), (m["away"], as_, hs)):
            d = stats.setdefault(f, [0, 0.0])
            if pf > pa:
                d[0] += 1
            d[1] += pf
    return stats


def _reg_seeds(season):
    """{fid: seed} 1..N by regular-season record then points-for."""
    stats = _record_stats(season)
    order = sorted(stats, key=lambda f: (stats[f][0], stats[f][1]), reverse=True)
    return {f: i + 1 for i, f in enumerate(order)}


def _league_seeds(season):
    """The league's playoff seeding for a 12-team season: seeds 1-5 by record, the
    6th seed is the highest-points-for team of the rest, then 7-12 by record.
    Returns {fid: seed} or None if there aren't 12 ranked teams."""
    stats = _record_stats(season)
    if len(stats) < 12:
        return None
    by_rec = sorted(stats, key=lambda f: (stats[f][0], stats[f][1]), reverse=True)
    shiva = by_rec[:5] + [max(by_rec[5:], key=lambda f: stats[f][1])]
    sacko = [f for f in by_rec if f not in shiva]
    seed = {f: i + 1 for i, f in enumerate(shiva)}
    seed.update({f: i + 7 for i, f in enumerate(sacko)})
    return seed


def six_team_playoff(season):
    """Rule-based reconstruction of a 2024+ six-team-playoff season. Returns
    {'seeds', 'order', 'shiva', 'sacko'} or None when it doesn't apply.

    'order' is the final standings (12 fids, 1st..12th). 'shiva'/'sacko' are lists
    of rounds ({'label','week','games'}); a game is a dict with fids, scores, the
    winner/loser, an optional placement caption, and a bye flag."""
    fs = season.get("final_standings") or []
    n_playoff = len(season.get("playoff_teams") or [])
    weeks = _playoff_weeks(season)
    year = season.get("season") or 0
    if n_playoff != 6 or len(fs) != 12 or len(weeks) < 3 or year < 2024:
        return None
    seed = _league_seeds(season)
    if not seed:
        return None
    S = {s: f for f, s in seed.items()}                # seed number -> fid
    w1, w2, w3 = weeks[-3], weeks[-2], weeks[-1]
    reseed = year >= 2025

    score = {}
    for m in season.get("matchups") or []:
        w = m.get("week")
        if w and w > (season.get("weeks_in_regular_season") or 14) \
                and m.get("home_score") is not None:
            score[(w, m["home"])] = m["home_score"]
            score[(w, m["away"])] = m["away_score"]
    # Seeds 1-2 (Shiva) truly bye week 1; everyone else plays every playoff week.
    need = [(w1, s) for s in (3, 4, 5, 6, 7, 8, 9, 10)] \
        + [(w, s) for w in (w2, w3) for s in range(1, 13)]
    if any((w, S[s]) not in score for w, s in need):
        return None                                    # a team is missing a score

    def game(week, a, b, label=None):
        sa, sb = score[(week, a)], score[(week, b)]
        win, lose = (a, b) if sa >= sb else (b, a)
        return {"label": label, "week": week, "home": a, "away": b,
                "hs": sa, "as": sb, "winner": win, "loser": lose, "bye": False}

    def bye(week, a):
        return {"label": None, "week": week, "home": a, "away": None,
                "hs": None, "as": None, "winner": a, "loser": None, "bye": True}

    # ---- Shiva (win to advance) ----
    a1 = game(w1, S[3], S[6])
    a2 = game(w1, S[4], S[5])
    if reseed:                                         # 1 v weakest survivor, 2 v strongest
        strong, weak = sorted([a1["winner"], a2["winner"]], key=lambda f: seed[f])
        semi1 = game(w2, S[1], weak)
        semi2 = game(w2, S[2], strong)
    else:                                              # 1 v W(4/5), 2 v W(3/6)
        semi1 = game(w2, S[1], a2["winner"])
        semi2 = game(w2, S[2], a1["winner"])
    fifth = game(w2, a1["loser"], a2["loser"], "5th Place")
    final = game(w3, semi1["winner"], semi2["winner"], "Shiva")
    third = game(w3, semi1["loser"], semi2["loser"], "3rd Place")
    shiva_rounds = [
        {"week": w1, "games": [bye(w1, S[1]), a2, a1, bye(w1, S[2])]},
        {"week": w2, "games": [semi1, semi2, fifth]},
        {"week": w3, "games": [final, third]},
    ]
    shiva_order = [final["winner"], final["loser"], third["winner"], third["loser"],
                   fifth["winner"], fifth["loser"]]

    # ---- Sacko (lose to advance toward last) ----
    b1 = game(w1, S[7], S[10])
    b2 = game(w1, S[8], S[9])
    seventh = game(w2, b1["winner"], b2["winner"], "7th Place")
    if reseed:                                         # 12 v highest remaining seed, 11 v other
        high, low = sorted([b1["loser"], b2["loser"]], key=lambda f: seed[f])
        sink1 = game(w2, S[12], high)
        sink2 = game(w2, S[11], low)
    else:                                              # 12 v L(7/10), 11 v L(8/9)
        sink1 = game(w2, S[12], b1["loser"])
        sink2 = game(w2, S[11], b2["loser"])
    ninth = game(w3, sink1["winner"], sink2["winner"], "9th Place")
    sacko_final = game(w3, sink1["loser"], sink2["loser"], "Sacko")
    sacko_rounds = [
        {"week": w1, "games": [bye(w1, S[11]), b1, b2, bye(w1, S[12])]},
        {"week": w2, "games": [seventh, sink1, sink2]},
        {"week": w3, "games": [sacko_final, ninth]},
    ]
    sacko_order = [seventh["winner"], seventh["loser"], ninth["winner"], ninth["loser"],
                   sacko_final["winner"], sacko_final["loser"]]

    for n, r in enumerate(shiva_rounds, 1):
        r["label"] = "Round %d" % n
    for n, r in enumerate(sacko_rounds, 1):
        r["label"] = "Round %d" % n
    return {"seeds": seed, "order": shiva_order + sacko_order,
            "shiva": shiva_rounds, "sacko": sacko_rounds}


def _correct_four_team(season, fs, n_playoff, weeks):
    """Two-week single-elimination toilet bowl (4 consolation teams)."""
    sacko = fs[n_playoff:]
    g1 = _games_among(season, sacko, weeks[0])
    g2 = _games_among(season, sacko, weeks[1])
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
    tail = [uw, ul, lw, ll]                     # top consolation seat -> Sacko
    if set(tail) != set(sacko):
        return fs
    return fs[:n_playoff] + tail


def corrected_standings(season):
    """Return final_standings reordered to match the league's bracket. Unchanged
    for seasons the corrections don't apply to."""
    fs = list(season.get("final_standings") or [])
    n_playoff = len(season.get("playoff_teams") or [])
    weeks = _playoff_weeks(season)
    six = six_team_playoff(season)
    if six:
        return six["order"]
    if len(fs) - n_playoff == 4 and len(weeks) >= 2:
        return _correct_four_team(season, fs, n_playoff, weeks)
    return fs
