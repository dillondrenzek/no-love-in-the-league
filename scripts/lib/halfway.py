"""The halfway point of a regular season: a frozen snapshot of the season as it
stood after its middle week, plus each team's first-half résumé and second-half
road. Feeds the once-a-season Halfway page (scripts/generate_halfway.py) and the
agent's facts file (scripts/halfway_report.py).

Pure — no file I/O. "Through week" is always the last week of the first half;
every number here is as of that week, so the page doesn't drift as the second
half is played. Once the halfway week is final the page's numbers are frozen
for good (`freeze` / `thaw`, persisted by scripts/generate_halfway.py), so
nothing later in the season, or in the code, can move them.
"""

from .data import game_final
from .render import heat_color, warm_heat


PROSE_KEYS = ("intro", "outlook")


def freeze(entry):
    """The page record with the prose stripped out: just the numbers, ready to be
    written once and read back forever. Team blurbs are dropped too, so the
    frozen file never holds a stale copy of the prose."""
    out = {k: v for k, v in entry.items() if k not in PROSE_KEYS}
    out["teams"] = [{k: v for k, v in t.items() if k != "blurb"}
                    for t in entry.get("teams") or []]
    return out


def thaw(frozen, prose):
    """A frozen record plus the current prose ({intro, outlook, teams: {fid:
    str}}, lib.data.load_halfway_prose): the full page record."""
    prose = prose or {}
    blurbs = prose.get("teams") or {}
    out = dict(frozen, intro=prose.get("intro") or "", outlook=prose.get("outlook") or "")
    out["teams"] = [dict(t, blurb=blurbs.get(t["fid"]) or "") for t in frozen.get("teams") or []]
    return out


def halfway_week(season):
    """The last week of the first half: half the regular season, rounded down
    (a 14-week season breaks after Week 7)."""
    return (season.get("weeks_in_regular_season") or 14) // 2


def snapshot(season, through_week):
    """A copy of `season` as it stood after `through_week` regular-season weeks:
    later regular-season games lose their scores and playoff games are dropped.
    The lifecycle state is rewound to "season" (mid-regular-season), so once the
    real season is in the playoffs or complete, the standings builders still
    rank by record instead of the final finish (and add no Shiva/Sacko tags).
    Every other key (teams, logos, trades, rosters) is kept, so the season's
    own standings builders run on it unchanged."""
    reg = season.get("weeks_in_regular_season") or 14
    ms = []
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        if w > reg or m.get("playoff"):
            continue
        if w > through_week:
            m = dict(m, home_score=None, away_score=None, played=False)
            m.pop("winner", None)
        ms.append(m)
    return dict(season, matchups=ms, state="season")


def first_half_complete(season, through_week):
    """True once every regular-season game through `through_week` is final."""
    games = [m for m in season.get("matchups") or []
             if not m.get("playoff") and 1 <= (m.get("week") or 0) <= through_week]
    return bool(games) and all(
        m.get("home_score") is not None and m.get("away_score") is not None
        and game_final(m) for m in games)


def _results(season, through_week):
    """{fid: [{week, opp, pf, pa, res}]} for final regular-season games through
    `through_week`, in week order."""
    out = {}
    for m in sorted(season.get("matchups") or [], key=lambda m: m.get("week") or 0):
        w = m.get("week") or 0
        if m.get("playoff") or not 1 <= w <= through_week:
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None or not game_final(m):
            continue
        for f, o, a, b in ((m["home"], m["away"], hs, as_), (m["away"], m["home"], as_, hs)):
            res = "W" if a > b else "L" if b > a else "T"
            out.setdefault(f, []).append({"week": w, "opp": o, "pf": a, "pa": b, "res": res})
    return out


def _streak(games):
    """('W', 3) for the run the team is on after its last game, or None."""
    if not games:
        return None
    last, n = games[-1]["res"], 0
    for g in reversed(games):
        if g["res"] != last:
            break
        n += 1
    return (last, n)


def _longest(games, res):
    best = cur = 0
    for g in games:
        cur = cur + 1 if g["res"] == res else 0
        best = max(best, cur)
    return best


def _rec(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")


def team_halves(season, through_week, close_margin=10.0):
    """Each team's first half and what's left, keyed by fid:

        {"record": "4-3", "pf": 860.1, "pa": 801.0, "avg": 122.9,
         "pf_rank": 2,                       # 1 = most points scored
         "all_play": "48-29",                # vs every team, every week
         "best": {week, opp, pf, pa, res},   # highest score
         "worst": {...},                     # lowest score
         "big_win": {...} | None,            # widest winning margin
         "bad_loss": {...} | None,           # widest losing margin
         "close": "2-1",                     # games decided by < close_margin
         "streak": "W3" | None, "longest_win": 3, "longest_loss": 2,
         "remaining": [{week, opp}],         # the second-half schedule
         "remaining_opp_avg": 118.4,         # those opponents' first-half avg
         "games": [{week, opp, pf, pa, res}], # the first half, in week order
         "wins": 4.0}                        # ties count as half a win

    `remaining_opp_avg` is a rough strength-of-schedule: the mean first-half
    points per game of the opponents still to play (one entry per meeting)."""
    reg = season.get("weeks_in_regular_season") or 14
    results = _results(season, through_week)
    # Every team's score per week, for the all-play record.
    by_week = {}
    for f, games in results.items():
        for g in games:
            by_week.setdefault(g["week"], []).append((f, g["pf"]))
    avg = {f: sum(g["pf"] for g in gs) / len(gs) for f, gs in results.items() if gs}
    pf_total = {f: sum(g["pf"] for g in gs) for f, gs in results.items()}
    ranked = sorted(pf_total, key=lambda f: -pf_total[f])
    remaining = {}
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        if m.get("playoff") or not through_week < w <= reg:
            continue
        remaining.setdefault(m["home"], []).append({"week": w, "opp": m["away"]})
        remaining.setdefault(m["away"], []).append({"week": w, "opp": m["home"]})

    out = {}
    for f, games in results.items():
        w = sum(g["res"] == "W" for g in games)
        l = sum(g["res"] == "L" for g in games)
        t = sum(g["res"] == "T" for g in games)
        aw = al = at = 0
        for g in games:
            for o, score in by_week.get(g["week"], []):
                if o == f:
                    continue
                aw += g["pf"] > score
                al += g["pf"] < score
                at += g["pf"] == score
        close = [g for g in games if abs(g["pf"] - g["pa"]) < close_margin]
        wins = [g for g in games if g["res"] == "W"]
        losses = [g for g in games if g["res"] == "L"]
        rem = sorted(remaining.get(f, []), key=lambda r: r["week"])
        opp_avgs = [avg[r["opp"]] for r in rem if r["opp"] in avg]
        st = _streak(games)
        out[f] = {
            "record": _rec(w, l, t),
            "pf": round(pf_total[f], 1),
            "pa": round(sum(g["pa"] for g in games), 1),
            "avg": round(avg[f], 1),
            "pf_rank": ranked.index(f) + 1,
            "all_play": _rec(aw, al, at),
            "best": max(games, key=lambda g: g["pf"]),
            "worst": min(games, key=lambda g: g["pf"]),
            "big_win": max(wins, key=lambda g: g["pf"] - g["pa"]) if wins else None,
            "bad_loss": max(losses, key=lambda g: g["pa"] - g["pf"]) if losses else None,
            "close": _rec(sum(g["res"] == "W" for g in close),
                          sum(g["res"] == "L" for g in close),
                          sum(g["res"] == "T" for g in close)),
            "streak": f"{st[0]}{st[1]}" if st else None,
            "longest_win": _longest(games, "W"),
            "longest_loss": _longest(games, "L"),
            "remaining": rem,
            "remaining_opp_avg": round(sum(opp_avgs) / len(opp_avgs), 1) if opp_avgs else None,
            "games": games,
            "wins": w + t / 2,
        }
    return out


def second_half_slate(halves, fid, race=0.5):
    """`fid`'s remaining games with what makes each one worth watching:

        [{"week": 9, "opp": "b", "opp_record": "4-2",
          "rematch": {week, opp, pf, pa, res} | None,  # the first-half meeting
          "twice": True,           # they meet more than once in the second half
          "gap": -1.0,             # opponent's wins minus fid's (+ = ahead)
          "race": True}]           # within `race` wins (same record or a tie apart)

    "Race" games are the six-pointers: a win also costs a team in the same
    part of the standings one."""
    me = halves.get(fid) or {}
    rem = me.get("remaining") or []
    counts = {}
    for r in rem:
        counts[r["opp"]] = counts.get(r["opp"], 0) + 1
    out = []
    for r in rem:
        opp = halves.get(r["opp"]) or {}
        met = [g for g in me.get("games") or [] if g["opp"] == r["opp"]]
        gap = (opp.get("wins") or 0) - (me.get("wins") or 0)
        out.append({"week": r["week"], "opp": r["opp"], "opp_record": opp.get("record"),
                    "rematch": met[-1] if met else None,
                    "twice": counts[r["opp"]] > 1,
                    "gap": gap, "race": abs(gap) <= race})
    return out


def schedule_ranks(halves):
    """{fid: 1..n} ranking each team's remaining schedule, 1 = toughest (highest
    `remaining_opp_avg`). Teams with no remaining games are left out."""
    have = [f for f, h in halves.items() if h.get("remaining_opp_avg") is not None]
    order = sorted(have, key=lambda f: -halves[f]["remaining_opp_avg"])
    return {f: i + 1 for i, f in enumerate(order)}


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _pct(rec):
    w, l, t = (list(map(int, rec.split("-"))) + [0])[:3]
    games = w + l + t
    return (w + t / 2) / games if games else 0.0


def card_chips(halves):
    """The two résumé chips on each team's Halfway card, shaded on the warm heat
    ramp like the odds chips beside them:

        {fid: {"all_play": {"text": "52-14", "color": hex},  # hotter = better
               "sos": {"text": "1st (123.1 ppg)", "color": hex,  # hotter = tougher
                       "rank": "1st", "record": "27-20-1",
                       "of": 12, "opp_avg": 123.1} | None}}

    All-play is shaded across the league's range of all-play win percentages;
    the remaining schedule by its toughness rank (schedule_ranks), labeled with
    the remaining opponents' average first-half points per game, the number the
    rank comes from. `record` is their combined first-half record (one entry
    per meeting), for context."""
    pcts = {f: _pct(h["all_play"]) for f, h in halves.items()}
    lo, hi = (min(pcts.values()), max(pcts.values())) if pcts else (0, 0)
    ranks = schedule_ranks(halves)
    n = len(ranks)
    out = {}
    for f, h in halves.items():
        sos = None
        if f in ranks:
            r = ranks[f]
            wlt = [0, 0, 0]
            for g in h["remaining"]:
                rec = (halves.get(g["opp"]) or {}).get("record")
                if rec:
                    for i, v in enumerate((list(map(int, rec.split("-"))) + [0])[:3]):
                        wlt[i] += v
            record = _rec(*wlt)
            sos = {"text": f"{_ordinal(r)} ({h['remaining_opp_avg']:.1f} ppg)",
                   "rank": _ordinal(r), "record": record,
                   "of": n, "opp_avg": h["remaining_opp_avg"],
                   "color": warm_heat((n - r) / (n - 1) if n > 1 else 0.0)}
        out[f] = {"all_play": {"text": h["all_play"], "color": heat_color(pcts[f], lo, hi)},
                  "sos": sos}
    return out


def bye_load(rosters_by_week, through_week):
    """Each team's bye weeks, behind it and ahead: {fid: {"past": {week:
    [player]}, "ahead": {week: [player]}}}.

    `rosters_by_week` is {week: {fid: [{player, bye_week}]}} (lib.data.
    load_week_rosters per week). "Past" is who was rostered *that week* and off,
    weeks 1..through_week; "ahead" is the latest snapshot's roster, by bye week
    after through_week. Early snapshots predate ESPN's bye data, so a player's
    bye is taken from any snapshot that has it. Weeks with no one off are left
    out."""
    bye_of = {}
    for wk in (rosters_by_week or {}).values():
        for players in (wk or {}).values():
            for pl in players or []:
                if isinstance(pl.get("bye_week"), int):
                    bye_of.setdefault(pl["player"], pl["bye_week"])
    out = {}
    for w in sorted(rosters_by_week or {}):
        if w > through_week:
            continue
        for fid, players in (rosters_by_week[w] or {}).items():
            off = [pl["player"] for pl in players or [] if bye_of.get(pl["player"]) == w]
            team = out.setdefault(fid, {"past": {}, "ahead": {}})
            if off:
                team["past"][w] = off
    if rosters_by_week:
        latest = rosters_by_week[max(rosters_by_week)] or {}
        for fid, players in latest.items():
            team = out.setdefault(fid, {"past": {}, "ahead": {}})
            for pl in players or []:
                b = bye_of.get(pl["player"])
                if b is not None and b > through_week:
                    team["ahead"].setdefault(b, []).append(pl["player"])
            team["ahead"] = dict(sorted(team["ahead"].items()))
    return out


def starter_points(rosters_by_week):
    """Points each player scored *as a starter* for each team, summed over the
    weekly roster snapshots: {fid: {player: points}}. `rosters_by_week` is
    {week: {fid: [{player, starter, actual}]}} (lib.data.load_week_rosters per
    week). Bench points don't count — this is what a player actually gave the team,
    which is how a pickup or a trade is judged."""
    out = {}
    for wk_rosters in (rosters_by_week or {}).values():
        for fid, players in (wk_rosters or {}).items():
            for p in players or []:
                act = p.get("actual")
                if p.get("starter") and isinstance(act, (int, float)):
                    tally = out.setdefault(fid, {})
                    tally[p["player"]] = round(tally.get(p["player"], 0.0) + act, 1)
    return out


def best_moves(players, points, limit=4):
    """The players from `players` (names a team acquired) who gave it the most
    starter points, best first: [(player, points)] with points > 0, at most
    `limit`."""
    scored = [(p, points.get(p, 0.0)) for p in dict.fromkeys(players)]
    scored = [x for x in scored if x[1] > 0]
    return sorted(scored, key=lambda x: -x[1])[:limit]
