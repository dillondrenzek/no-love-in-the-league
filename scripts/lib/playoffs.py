"""Reconstruct the league's playoff brackets for a season.

The league runs its own bracket, seeded by league rules (not ESPN's): the top
five by regular-season record make it, the sixth seed is the highest-points-for
team among the remaining seven, and the other six are seeded 7-12 by record. Both
a **Shiva** (championship, seeds 1-6) and a **Sacko** (toilet bowl, seeds 7-12)
bracket are played over the three playoff weeks, each a 6-team bracket with byes
for the top two seeds. Advancement uses each team's actual score that week.

`playoff_bracket(season, franchises)` returns the two brackets as nested game
dicts, or None when the season isn't a 6-team-playoff season (the only format
these rules describe). Pure — no network, no rendering.
"""

from .data import regular_season_matchups, short_name_of, game_final


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


def _seeds(season):
    """League seeding 1-12: seeds 1-5 by record; seed 6 = highest PF of the rest;
    seeds 7-12 = the remaining, by record. Returns (seed_by_fid, shiva[6], sacko[6])
    or None if there aren't 12 ranked teams."""
    stats = _reg_stats(season)
    if len(stats) < 12:
        return None
    def rec_key(fid):
        d = stats[fid]
        return (d["w"] + 0.5 * d["t"], d["pf"])
    by_record = sorted(stats, key=rec_key, reverse=True)
    top5 = by_record[:5]
    rest = by_record[5:]
    seed6 = max(rest, key=lambda f: stats[f]["pf"])
    shiva = top5 + [seed6]
    sacko = [f for f in by_record if f not in shiva]     # remaining 6, record order
    seed = {}
    for i, fid in enumerate(shiva, 1):
        seed[fid] = i
    for i, fid in enumerate(sacko, 7):
        seed[fid] = i
    return seed, shiva, sacko


def _playoff_games(season, members, reg):
    """Actual head-to-head games played *among* `members` in the playoff weeks,
    grouped by week: {week: [(home, away, home_score, away_score)...]}."""
    by_week = {}
    for m in season.get("matchups") or []:
        w = m.get("week")
        if not w or w <= reg or m.get("home_score") is None:
            continue
        if m["home"] in members and m["away"] in members:
            by_week.setdefault(w, []).append(
                (m["home"], m["away"], m["home_score"], m["away_score"]))
    return by_week


def _bracket(season, franchises, members, seed, title, kind):
    """Reconstruct one bracket (Shiva or Sacko) from the *actual* games played
    among its six teams, so advancement follows real results — not a re-pairing.

    kind='shiva': winning advances; the team that wins all its games is champion.
    kind='sacko': losing advances toward last; the team that loses all its games
    is the Sacko. Returns {'title', 'rounds': [...]} or None if the six teams
    didn't play a recognizable three-week bracket among themselves."""
    reg = season.get("weeks_in_regular_season") or 14
    logos = season.get("team_logos") or {}
    weeks = [reg + 1, reg + 2, reg + 3]
    by_week = _playoff_games(season, members, reg)
    if not all(by_week.get(w) for w in weeks):
        return None

    def side(fid, score):
        return {"seed": seed.get(fid), "fid": fid,
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
    # seats (1-2, 3-4, ... 11-12) exactly when the game between them decides that
    # placement, so we caption a game from the seats of its two teams. Advancement
    # itself stays driven by the real results above.
    rank = {f: i for i, f in enumerate(season.get("final_standings") or [])}
    PLACE = {0: "Shiva", 2: "3rd Place", 4: "5th Place",
             6: "7th Place", 8: "9th Place", 10: "Sacko"}
    # Final-round order: the title game (Shiva / Sacko) on top, then the next
    # placement game down (3rd / 9th), then the rest.
    FINAL_ORDER = {"Shiva": 0, "3rd Place": 1, "5th Place": 2,
                   "Sacko": 0, "9th Place": 1, "7th Place": 2}

    def placement(h, a):
        if h not in rank or a not in rank:
            return None
        lo, hi = sorted((rank[h], rank[a]))
        return PLACE.get(lo) if lo % 2 == 0 and hi == lo + 1 else None

    # The two bye seeds (top of the Shiva, bottom of the Sacko) sit out round 1;
    # ESPN still schedules them a meaningless game, which we show as byes instead.
    ordered = sorted(members, key=lambda f: seed.get(f, 99))
    byes = set(ordered[:2]) if kind == "shiva" else set(ordered[-2:])

    # ESPN makes some pairs play twice (a placement game and a dead rematch the
    # next week). Keep only the standings-consistent copy — the one whose winner
    # actually finished ahead — so the bracket shows each result once, correctly.
    seen = {}                                    # frozenset(pair) -> chosen (week,h,a)
    for w in weeks:
        for h, a, hs, as_ in by_week[w]:
            pair = frozenset((h, a))
            winner = h if hs >= as_ else a
            loser = a if winner == h else h
            consistent = rank.get(winner, 99) < rank.get(loser, 99)
            prev = seen.get(pair)
            if prev is None or consistent:
                seen[pair] = (w, h, a)
    keep = set(seen.values())

    rounds = []
    for i, w in enumerate(weeks):
        games = []
        playing = set()
        wk_games = sorted(by_week[w],
                          key=lambda g: (seed.get(g[0], 99) + seed.get(g[1], 99)))
        for h, a, hs, as_ in wk_games:
            if i == 0 and h in byes and a in byes:
                continue                          # bye pairing: shown as byes below
            if (w, h, a) not in keep:
                continue                          # dead rematch of an earlier game
            playing.add(h)
            playing.add(a)
            games.append(make_game(w, h, a, hs, as_, placement(h, a)))
        if i == 0:                                # round 1: byes bookend the games
            top_bye = ordered[0] if kind == "shiva" else ordered[-2]
            bottom_bye = ordered[1] if kind == "shiva" else ordered[-1]
            middle = sorted(games, key=lambda g: g["home"]["seed"] or 99)
            games = [bye(w, top_bye)] + middle + [bye(w, bottom_bye)]
        elif i == len(weeks) - 1:                 # final round: title game on top
            games.sort(key=lambda g: FINAL_ORDER.get(g["label"], 99))
        rounds.append({"week": w, "label": "Round %d" % (i + 1),
                       "games": games, "consolation": []})
    return {"title": title, "rounds": rounds}


def playoff_bracket(season, franchises):
    """{'shiva': {...}, 'sacko': {...}, 'seeds': {fid: n}} or None.

    Each bracket is {'title', 'rounds': [{'week', 'label', 'games': [game...]}...]}
    where a game is {label, week, home/away: {seed, fid, name, score}, winner_fid,
    loser_fid, decided}. A bye is a game with away=None. Advancement mirrors the
    actual playoff results, so the brackets agree with the final standings."""
    seeded = _seeds(season)
    if not seeded:
        return None
    seed, shiva, sacko = seeded
    # Only handle the 6-team format these rules describe (12 teams, 6 in each half).
    if len(shiva) != 6 or len(sacko) != 6:
        return None
    shiva_b = _bracket(season, franchises, set(shiva), seed, "Shiva Bracket", "shiva")
    sacko_b = _bracket(season, franchises, set(sacko), seed, "Sacko Bracket", "sacko")
    if not shiva_b or not sacko_b:
        return None
    return {"shiva": shiva_b, "sacko": sacko_b, "seeds": seed}
