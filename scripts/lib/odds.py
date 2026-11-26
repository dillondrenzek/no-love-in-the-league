"""Season forecast: each team's chance to win the Shiva, finish top 3, earn a
first-round bye (a top-2 seed), make the playoffs, land in the Sacko bracket, or
take the Sacko itself.

Two halves:

1. **Team strength.** Each team's true scoring level is estimated with a
   normal-normal (shrinkage) model. The prior is centered on the league average,
   nudged by the team's ESPN starter projections; the games it has actually played
   pull the estimate toward its real average, more so as the season goes on. Early
   results are mostly noise — weekly scores swing ~20 points while teams' true
   levels differ by only ~8 — so three games move the needle far less than they
   seem to. The constants in `Params` are fitted by scripts/backtest_odds.py.

2. **Simulation.** Play out every remaining regular-season game and the three
   playoff weeks many times, drawing each team's weekly score around its
   (uncertain) strength. Each simulated season is seeded and bracketed by the
   league's own rules — lib.playoff_order.six_team_playoff, the same code that
   reconstructs real brackets — so the 6th-seed points wildcard, the reseed, and
   the Sacko bracket all behave exactly as they do for real.

Pure: plain data in, plain data out. Deterministic for a given seed.
"""

import math
import random
import statistics
from itertools import combinations
from dataclasses import dataclass

from .data import game_final, short_name_of
from .nfl_schedule import parse_kickoff
from .render import warm_heat, heat_color
from .playoff_order import six_team_playoff

OUTCOMES = ("sacko", "sacko_bracket", "playoffs", "bye", "top3", "shiva")
# Simulated too, but not backtested: a Sacko bye is a bottom-two regular-season
# finish (seed 11 or 12), which skips round 1 of the Sacko bracket and drops
# straight into round 2, one loss from the Sacko final.
SIM_OUTCOMES = OUTCOMES + ("sacko_bye",)
SACKO_BYE_SEEDS = (11, 12)
# What the season-page table shows: the Sacko bye on the left, then the playoffs
# and the first-round bye. Shiva, Sacko, top 3 and the Sacko bracket (just
# 1 - playoffs) are still simulated, and all but the Sacko bye are backtested.
TABLE_OUTCOMES = ("sacko_bye", "playoffs", "bye")


@dataclass(frozen=True)
class Params:
    """Model constants, chosen by scripts/backtest_odds.py (2018-2025 scoring for
    the fit; 2023-2025 outcomes for the grade):

    - sigma: within-team weekly score sd, ~20 pts in every recent season.
    - tau: spread of true team levels. Outcome Brier improves up to ~12 and is
      flat beyond; the score-level fit prefers ~4 when paired with projections,
      but that combination graded *worse* than a coin flip on real outcomes.
    - proj_weight: weight on ESPN starter projections. Every weight tried graded
      worse on outcomes than 0, so it's off until better (rest-of-season) data
      earns it a place.
    """
    sigma: float = 20.0
    tau: float = 12.0
    proj_weight: float = 0.0
    league_mean: float = 113.0  # fallback center before any games are played
    n_playoff: int = 6


def played_games(season, before_week=None):
    """Completed regular-season games (optionally only weeks < before_week)."""
    reg = season.get("weeks_in_regular_season") or 14
    out = []
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        if w > reg or m.get("playoff") or (before_week and w >= before_week):
            continue
        if m.get("home_score") is None or m.get("away_score") is None:
            continue
        if not game_final(m):
            continue
        out.append(m)
    return out


def complete_through(season):
    """The last regular-season week whose every game is final (0 if none)."""
    reg = season.get("weeks_in_regular_season") or 14
    last = 0
    for w in range(1, reg + 1):
        games = [m for m in season.get("matchups") or [] if m.get("week") == w]
        if games and all(m.get("home_score") is not None and game_final(m)
                         for m in games):
            last = w
        else:
            break
    return last


def team_scores(games):
    """{fid: [score, ...]} in week order."""
    out = {}
    for m in sorted(games, key=lambda m: m["week"]):
        out.setdefault(m["home"], []).append(m["home_score"])
        out.setdefault(m["away"], []).append(m["away_score"])
    return out


def starter_projection(rosters):
    """{fid: summed ESPN projection of the starting lineup} from one week's
    roster snapshot ({fid: [{starter, proj}, ...]})."""
    return {fid: round(sum(p.get("proj") or 0 for p in players if p.get("starter")), 2)
            for fid, players in (rosters or {}).items()}


def strengths(teams, scores, params, proj=None, partial=None):
    """{fid: (mean, sd)} — the posterior estimate of each team's true weekly
    scoring level. `scores` is {fid: [played scores]}; `proj` an optional
    {fid: projected starter total}, centered on its own league mean so only a
    team's projection *relative to the league* matters. `partial` is an optional
    {fid: (score, weight)}: one more game counted as a fraction of a game (the
    live week, worth as much of a game as has been played)."""
    played = [s for v in scores.values() for s in v]
    pw_total = sum(w for _, w in (partial or {}).values())
    if played or pw_total:
        center = ((sum(played) + sum(x * w for x, w in (partial or {}).values()))
                  / (len(played) + pw_total))
    else:
        center = params.league_mean
    proj = {f: p for f, p in (proj or {}).items() if f in teams and p}
    pbar = statistics.mean(proj.values()) if proj else 0.0
    t2, s2 = params.tau ** 2, params.sigma ** 2
    out = {}
    for f in teams:
        prior = center + params.proj_weight * (proj[f] - pbar) if f in proj else center
        xs = scores.get(f) or []
        px, pw = (partial or {}).get(f, (0.0, 0.0))
        prec = 1 / t2 + (len(xs) + pw) / s2
        mean = (prior / t2 + (sum(xs) + pw * px) / s2) / prec
        out[f] = (mean, prec ** -0.5)
    return out


def _bracket_season(season, teams, reg, year):
    """A minimal season shell six_team_playoff accepts; matchups filled per sim."""
    return {"season": max(year, 2025), "weeks_in_regular_season": reg,
            "final_standings": list(teams), "playoff_teams": list(teams[:6]),
            "matchups": []}


# How long an NFL game's fantasy points take to land, for splitting a game in
# progress into points already scored and points still to come.
GAME_HOURS = 3.25


def _remaining_fraction(kickoff, now):
    """Share of a game's fantasy points still to come at `now`: all of them before
    kickoff, none once the game's over, a straight-line share in between."""
    elapsed = (now - kickoff).total_seconds() / 3600
    if elapsed <= 0:
        return 1.0
    return max(0.0, 1.0 - elapsed / GAME_HOURS)


def live_week(season, rosters, schedule, now):
    """The in-progress week, for a forecast that moves with live scores:

        {"week": 11, "teams": {fid: {"score": 64.2,    # live score so far
                                     "remaining": 51.3,  # projected points still to come
                                     "share": 0.44}}}     # of the team's projected total

    The live week is the first regular-season week that isn't final, once any of
    its games has a score. Each starter's projection counts toward `remaining`
    by how much of his NFL game is left at `now` (kickoff times from the
    schedule): all of it before kickoff, a shrinking share during the game, none
    after. A starter on bye, or with no NFL team on file, has nothing left.
    `rosters` is lib.data.load_week_rosters output for that week and `schedule`
    lib.data.load_nfl_schedule. None when there's no live week, or no rosters or
    kickoff times to split it with — the forecast then waits for the week to go
    final, as before."""
    reg = season.get("weeks_in_regular_season") or 14
    week = complete_through(season) + 1
    games = [m for m in season.get("matchups") or []
             if m.get("week") == week and not m.get("playoff")]
    if (week > reg or not games or not rosters or not schedule or now is None
            or not any(m.get("home_score") is not None for m in games)):
        return None
    kick = {}
    for g in schedule:
        if g.get("week") == week and g.get("kickoff"):
            for t in (g.get("away"), g.get("home")):
                if t:
                    kick[t.upper()] = parse_kickoff(g["kickoff"])
    if not kick:
        return None
    teams = {}
    for m in games:
        for f, score in ((m["home"], m.get("home_score")), (m["away"], m.get("away_score"))):
            starters = [p for p in rosters.get(f) or [] if p.get("starter")]
            total = rem = 0.0
            for p in starters:
                proj = float(p.get("proj") or 0.0)
                total += proj
                ko = kick.get((p.get("pro_team") or "").upper())
                if ko is not None:
                    rem += proj * _remaining_fraction(ko, now)
            teams[f] = {"score": float(score or 0.0), "remaining": round(rem, 2),
                        "share": round(rem / total, 4) if total else 0.0}
    return {"week": week, "teams": teams}


# League rule (from 2026): a team more than this many points-for per game left
# behind the 6th seed (the points wildcard) at the end of a week is out of the
# race for that seed for good. It can still make the top five by record.
WILDCARD_OUT_PPG = 50.0
WILDCARD_OUT_FROM = 2026


def wildcard_cut(wins, pf, left, out=()):
    """Apply the 50-points-per-game rule at the end of a week. `wins` and `pf`
    are each team's totals so far (a tie = half a win), `left` its regular-season
    games still to play, and `out` the teams already out of the 6th-seed race.
    Returns the new set of teams out: `out` plus every team more than
    WILDCARD_OUT_PPG per game left behind the 6th seed's points-for. The 6th
    seed is the top scorer outside the top five by record (points-for breaking
    level records) among the teams still in the race. A team with no games left
    isn't cut: the season is over and the seeding settles it."""
    out = set(out)
    order = sorted(pf, key=lambda f: (wins.get(f, 0.0), pf[f]), reverse=True)
    rest = [f for f in order[RECORD_SEEDS:] if f not in out]
    if not rest:
        return out
    holder = max(rest, key=lambda f: pf[f])
    for f in order:
        if (f != holder and f not in out and left.get(f)
                and (pf[holder] - pf[f]) / left[f] > WILDCARD_OUT_PPG):
            out.add(f)
    return out


def _week_totals(games, wins, pf):
    """Add one week's games to running wins / points-for totals (in place)."""
    for m in games:
        h, a, hs, as_ = m["home"], m["away"], m["home_score"], m["away_score"]
        pf[h] = pf.get(h, 0.0) + hs
        pf[a] = pf.get(a, 0.0) + as_
        if hs == as_:
            wins[h] = wins.get(h, 0.0) + 0.5
            wins[a] = wins.get(a, 0.0) + 0.5
        else:
            w = h if hs > as_ else a
            wins[w] = wins.get(w, 0.0) + 1


def _games_left_after(season, reg):
    """{week: {fid: regular-season games scheduled after that week}}."""
    sched = [m for m in season.get("matchups") or []
             if 1 <= (m.get("week") or 0) <= reg and not m.get("playoff")]
    out = {}
    for w in range(0, reg + 1):
        left = {}
        for m in sched:
            if m["week"] > w:
                left[m["home"]] = left.get(m["home"], 0) + 1
                left[m["away"]] = left.get(m["away"], 0) + 1
        out[w] = left
    return out


def wildcard_out(season):
    """The teams already out of the 6th-seed race under the 50-points-per-game
    rule, checked at the end of every completed regular-season week (once out,
    always out). Empty before WILDCARD_OUT_FROM."""
    if (season.get("season") or 0) < WILDCARD_OUT_FROM:
        return set()
    reg = season.get("weeks_in_regular_season") or 14
    done = complete_through(season)
    left = _games_left_after(season, reg)
    teams = list(season.get("teams") or {})
    wins, pf = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)
    out = set()
    for w in range(1, done + 1):
        _week_totals([m for m in played_games(season) if m["week"] == w], wins, pf)
        out = wildcard_cut(wins, pf, left[w], out)
    return out


def simulate(season, strength, params, n=10000, seed=0, live=None, observe=None):
    """Run `n` simulated seasons from the current state. Returns
    {fid: {outcome: probability, 'wins': mean final wins, 'seed': mean seed}}.

    `live` (live_week output) plays out the in-progress week from where it
    stands: each team's final score is its live score plus its projected points
    still to come, give or take a spread that shrinks with how much is left (a
    full week's sigma scaled by the square root of the share remaining).

    `observe`, when given, is called once per simulated season with that
    season's games and its seeding result (six_team_playoff output) — how the
    rooting guide learns which results matter to whom. It doesn't change the
    simulation, so the same seed gives the same odds with or without it.

    The 50-points-per-game rule (wildcard_cut) is applied as each simulated
    week ends, starting from the teams already out (wildcard_out), and a team
    that's out can't take the 6th seed in that simulated season."""
    teams = sorted(season.get("teams") or {})
    reg = season.get("weeks_in_regular_season") or 14
    played = played_games(season)
    played_keys = {(m["week"], m["home"]) for m in played}
    remaining = [m for m in season.get("matchups") or []
                 if 1 <= (m.get("week") or 0) <= reg and not m.get("playoff")
                 and (m["week"], m["home"]) not in played_keys]
    base = [dict(m, playoff=False) for m in played]
    shell = _bracket_season(season, teams, reg, season.get("season") or 0)
    pweeks = (reg + 1, reg + 2, reg + 3)
    rng = random.Random(seed)
    live_wk = (live or {}).get("week")
    live_teams = (live or {}).get("teams") or {}
    tally = {f: dict.fromkeys(SIM_OUTCOMES, 0) for f in teams}
    wins = dict.fromkeys(teams, 0)
    seeds = dict.fromkeys(teams, 0)
    sigma = params.sigma
    rule = (season.get("season") or 0) >= WILDCARD_OUT_FROM
    done = complete_through(season)
    out0 = wildcard_out(season) if rule else set()
    left_after = _games_left_after(season, reg) if rule else {}
    base_wins, base_pf = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)
    _week_totals([m for m in played if m["week"] <= done], base_wins, base_pf)
    for _ in range(n):
        level = {f: rng.gauss(*strength[f]) for f in teams}
        sim = list(base)
        for m in remaining:
            h, a = m["home"], m["away"]
            if live_teams and m["week"] == live_wk and h in live_teams and a in live_teams:
                hs, as_ = (live_teams[x]["score"] + rng.gauss(
                    live_teams[x]["remaining"], sigma * math.sqrt(live_teams[x]["share"]))
                    for x in (h, a))
            else:
                hs, as_ = rng.gauss(level[h], sigma), rng.gauss(level[a], sigma)
            sim.append({"week": m["week"], "home": h, "away": a,
                        "home_score": hs, "away_score": as_})
        # Playoff weeks: every team plays (scores only matter per team).
        for w in pweeks:
            for i in range(0, len(teams), 2):
                h, a = teams[i], teams[i + 1]
                sim.append({"week": w, "home": h, "away": a,
                            "home_score": rng.gauss(level[h], sigma),
                            "away_score": rng.gauss(level[a], sigma)})
        shell["matchups"] = sim
        if rule:
            out, w_, p_ = set(out0), dict(base_wins), dict(base_pf)
            for w in range(done + 1, reg):        # no cut after the last week
                _week_totals([m for m in sim if m["week"] == w], w_, p_)
                out = wildcard_cut(w_, p_, left_after[w], out)
            shell["wildcard_out"] = out
        res = six_team_playoff(shell)
        order, seed_of = res["order"], res["seeds"]
        for f in teams:
            s = seed_of[f]
            seeds[f] += s
            t = tally[f]
            if s <= params.n_playoff:
                t["playoffs"] += 1
                if s <= 2:                     # top-2 seeds skip round 1
                    t["bye"] += 1
            else:
                t["sacko_bracket"] += 1
                if s in SACKO_BYE_SEEDS:       # bottom two skip Sacko round 1
                    t["sacko_bye"] += 1
        if observe:
            observe(sim, res)
        tally[order[0]]["shiva"] += 1
        for f in order[:3]:
            tally[f]["top3"] += 1
        tally[order[-1]]["sacko"] += 1
        for m in sim:
            if m["week"] > reg:
                continue
            if m["home_score"] == m["away_score"]:          # a tie is half a win each
                wins[m["home"]] += 0.5
                wins[m["away"]] += 0.5
            else:
                wins[m["home"] if m["home_score"] > m["away_score"] else m["away"]] += 1
    return {f: dict({k: v / n for k, v in tally[f].items()},
                    wins=wins[f] / n, seed=seeds[f] / n) for f in teams}


def forecast(season, params, proj=None, n=10000, seed=0, live=None):
    """Strength estimate + simulation from the season's completed weeks, with an
    in-progress week played out from its live scores when `live` (live_week
    output) is given. The live week also feeds the ratings, as a fraction of a
    game: each team's projected final (live score plus points still to come),
    weighted by the share of its week already played — nothing before kickoff,
    a full game once it's over, so a finished-but-not-final week rates teams
    the same as the final one will."""
    teams = sorted(season.get("teams") or {})
    partial = {f: (t["score"] + t["remaining"], 1.0 - t["share"])
               for f, t in ((live or {}).get("teams") or {}).items()}
    st = strengths(teams, team_scores(played_games(season)), params, proj, partial)
    return st, simulate(season, st, params, n=n, seed=seed, live=live)


def pct_label(p):
    """Display a probability: '<1%' / '>99%' at the extremes (a simulation can't
    prove a clinch or an elimination), otherwise a whole percent."""
    if p < 0.005:
        return "<1%"
    if p > 0.995:
        return ">99%"
    # Round half up (Python's round() goes half-to-even, so 0.5% would read
    # "0%"), and keep the result inside 1..99 so it never contradicts the
    # '<1%' / '>99%' ends.
    return f"{min(99, max(1, int(p * 100 + 0.5)))}%"


# Cell fill for a '<1%' odds value: plain white, so a long-shot reads as "out of
# it" instead of blending into the cream low end of the heat ramp.
NEGLIGIBLE_COLOR = "#ffffff"


def is_negligible(p):
    """True for a probability that displays as '<1%' (including a flat 0)."""
    return pct_label(p) == "<1%"


def odds_color(p):
    """Cell fill for a probability: white when it displays as '<1%', otherwise the
    warm heat ramp scaled to the probability itself."""
    return NEGLIGIBLE_COLOR if is_negligible(p) else warm_heat(p)


def odds_cell(p):
    """A forecast table cell: {text, color, dim} — `dim` marks a '<1%' value so the
    template can mute its text along with the white fill."""
    return {"text": pct_label(p), "color": odds_color(p), "dim": is_negligible(p)}


# ---------------------------------------------------------------------------
# Clinches
# ---------------------------------------------------------------------------

# Seeds 1-5 go by record, so a spot there can be locked up mathematically; the 6th
# (a points wildcard) can't, since any team can still outscore anyone. Seeds 1-2
# get the first-round bye.
RECORD_SEEDS = 5
BYE_SEEDS = 2


def _can_all_reach(group, need, games):
    """Can every team in `group` pick up its `need` more wins from `games` — the
    remaining games played between two members of the group, each won by exactly
    one of them? Hall's condition: every subset A must need no more wins than
    there are games with at least one team from A."""
    inside = [(a, b) for a, b in games if a in group and b in group]
    members = sorted(group)
    for r in range(1, len(members) + 1):
        for sub in combinations(members, r):
            a_set = set(sub)
            want = sum(need[f] for f in sub)
            if want and want > sum(1 for a, b in inside if a in a_set or b in a_set):
                return False
    return True


def clinched_top(wins, games, k):
    """The teams guaranteed a top-`k` finish by record, whatever happens in the
    remaining `games` (a list of (team, team) pairs). For each team, take its worst
    case, losing every game it has left, and ask whether some k others could all
    still finish level with or above it, given who actually plays whom: games
    against the team itself or anyone outside the group go to the group, and a game
    between two group members can only go to one of them. A tie counts as a
    threat, since the points tiebreaker can't be known in advance. {fid: wins},
    where a tie already played counts as half a win; the remaining games are
    assumed to be decided (a future tie can't be counted on), so a team that needs
    half a game to draw level still needs a whole win."""
    left = dict.fromkeys(wins, 0)
    for a, b in games:
        left[a] = left.get(a, 0) + 1
        left[b] = left.get(b, 0) + 1
    out = set()
    for f, floor in wins.items():
        rivals = [g for g in wins if g != f and wins[g] + left[g] >= floor]
        locked = True
        for group in combinations(rivals, k):
            group = set(group)
            # Wins a member is sure of here: its games against `f` or outsiders.
            sure = {g: sum(1 for a, b in games if g in (a, b)
                           and (b if a == g else a) not in group) for g in group}
            need = {g: max(0, math.ceil(floor - wins[g] - sure[g])) for g in group}
            if _can_all_reach(group, need, games):
                locked = False
                break
        if locked:
            out.add(f)
    return out


def eliminated_top(wins, games, k):
    """Teams that can no longer finish in the top `k` by wins, whatever happens:
    at least `k` teams already have more wins than the team can reach by winning
    out. Strictly more, since a tie in wins goes to a tiebreaker nobody can
    promise. A sufficient check (it ignores who plays whom), so it never marks a
    team out that still has a path."""
    left = {}
    for a, b in games:
        left[a] = left.get(a, 0) + 1
        left[b] = left.get(b, 0) + 1
    out = set()
    for f in wins:
        best = wins[f] + left.get(f, 0)
        if sum(1 for g in wins if g != f and wins[g] > best) >= k:
            out.add(f)
    return out


def clinch_status(season):
    """Who has mathematically settled what, given the actual remaining schedule:

        {'playoffs': {fids}, 'bye': {fids},      # clinched: a top-5 / top-2 seed
         'no_bye': {fids},                       # can't reach the top 2
         'no_playoffs': {fids},                  # out of the playoffs
         'no_sacko_bye': {fids}}                 # can't fall to 11th or 12th

    A Sacko bye is a bottom-two finish, so a team is safe from it once it has
    clinched a top-10 spot by record. A team is out of the playoffs once it can't
    reach the top five by record and is out of the 6th-seed race under the
    50-points-per-game rule (wildcard_out)."""
    reg = season.get("weeks_in_regular_season") or 14
    played = played_games(season)
    played_keys = {(m["week"], m["home"]) for m in played}
    wins = dict.fromkeys(season.get("teams") or {}, 0)
    for m in played:
        if m["home_score"] == m["away_score"]:              # a tie is half a win each
            for f in (m["home"], m["away"]):
                wins[f] = wins.get(f, 0) + 0.5
        else:
            w = m["home"] if m["home_score"] > m["away_score"] else m["away"]
            wins[w] = wins.get(w, 0) + 1
    games = [(m["home"], m["away"]) for m in season.get("matchups") or []
             if 1 <= (m.get("week") or 0) <= reg and not m.get("playoff")
             and (m["week"], m["home"]) not in played_keys]
    for g in (x for pair in games for x in pair):
        wins.setdefault(g, 0)
    n = len(wins)
    return {"playoffs": clinched_top(wins, games, RECORD_SEEDS),
            "bye": clinched_top(wins, games, BYE_SEEDS),
            "no_bye": eliminated_top(wins, games, BYE_SEEDS),
            "no_playoffs": eliminated_top(wins, games, RECORD_SEEDS) & wildcard_out(season),
            "no_sacko_bye": (clinched_top(wins, games, n - len(SACKO_BYE_SEEDS))
                             if n > len(SACKO_BYE_SEEDS) else set())}


def clinched_cell():
    """The cell for a spot a team has locked up: a checkmark at the top of the
    ramp, with 'Clinched' as its tooltip."""
    return {"text": "✓", "title": "Clinched", "color": warm_heat(1.0), "dim": False,
            "clinched": True}


def wildcard_gaps(season):
    """How much more per remaining regular-season game each team must score to
    catch the 6th seed's points-for, as things stand today. The 6th seed is the
    points wildcard: the top scorer outside the top five by record (a tie
    counting as half a win, points-for breaking level records).

    {fid: {"text", "total", "ppg", "title", "dim", "gap", "pf_gap"}} where
    `pf_gap` is the points-for gap to the 6th seed (negative when ahead) and
    `gap` that gap spread over the team's remaining games, assuming the 6th seed
    keeps scoring at the same rate (None when it doesn't apply). Teams behind
    show '−61.9 (−12.4)': the total deficit, then the deficit per game left. The
    wildcard holder shows 'WC'. The top five by record get the same numbers, as
    a fallback in case they lose their way out of the top five: usually a
    cushion, '105.1 (+21.0)' (they could score 21 less per game and still pass
    the 6th seed), dimmed since they're in on record for now. With no games
    left the gap is fixed, so it shows '—'."""
    reg = season.get("weeks_in_regular_season") or 14
    played = played_games(season)
    played_keys = {(m["week"], m["home"]) for m in played}
    teams = list(season.get("teams") or {})
    wins = dict.fromkeys(teams, 0.0)
    pf = dict.fromkeys(teams, 0.0)
    left = dict.fromkeys(teams, 0)
    for m in played:
        for f, a, b in ((m["home"], m["home_score"], m["away_score"]),
                        (m["away"], m["away_score"], m["home_score"])):
            wins[f] = wins.get(f, 0.0) + (1.0 if a > b else 0.5 if a == b else 0.0)
            pf[f] = pf.get(f, 0.0) + a
    for m in season.get("matchups") or []:
        if (1 <= (m.get("week") or 0) <= reg and not m.get("playoff")
                and (m["week"], m["home"]) not in played_keys):
            for f in (m["home"], m["away"]):
                left[f] = left.get(f, 0) + 1
    order = sorted(pf, key=lambda f: (wins.get(f, 0.0), pf[f]), reverse=True)
    top, rest = order[:RECORD_SEEDS], order[RECORD_SEEDS:]
    if not rest:
        return {}
    holder = max(rest, key=lambda f: pf[f])
    out = {}
    for f in order:
        if f == holder:
            out[f] = {"text": "WC", "title": "Holds the 6th seed (the points wildcard)",
                      "dim": False, "gap": None, "holder": True}
            continue
        in_top = f in top
        if not left.get(f):
            out[f] = {"text": "—", "title": "No regular-season games left",
                      "dim": True, "gap": None}
            continue
        diff = pf[holder] - pf[f]
        gap = round(diff / left[f], 1)
        games = f"{left[f]} game{'s' if left[f] != 1 else ''} left"
        side = (f"{-diff:.1f} PF ahead of" if diff < 0 else f"{diff:.1f} PF behind")
        title = f"{side} the 6th seed with {games}"
        if in_top:
            title = f"Top five by record. If it drops out: {title}"
        # Signed from the team's side, like the total: behind is −, ahead is +.
        ppg = f"({'−' if gap > 0 else '+' if gap < 0 else ''}{abs(gap):.1f})"
        total = f"{'−' if diff > 0 else ''}{abs(diff):.1f}"   # behind: −45.9
        out[f] = {"text": f"{total} {ppg}", "total": total, "ppg": ppg,
                  "title": title, "dim": in_top, "gap": gap, "pf_gap": round(diff, 1)}
    return out


def eliminated_cell(title):
    """The cell for an outcome that can no longer happen: an ✕ on the white
    'negligible' fill with dimmed text, so it reads as settled rather than as a
    long shot ('<1%')."""
    return {"text": "✕", "title": title, "color": NEGLIGIBLE_COLOR, "dim": True,
            "eliminated": True}


# ---------------------------------------------------------------------------
# Rooting guide: what each team should be rooting for this week
# ---------------------------------------------------------------------------

# A game has to move a team's goal by at least this much to be worth rooting for.
ROOT_MIN_SWING = 0.03
ROOT_MAX = 2
# Below this playoff chance, a team still in the Sacko-bye race chases that instead.
PLAYOFF_LONG_SHOT = 0.05


def rooting_goal(p, b, s):
    """The one goal still in play for a team, from its playoff (p), bye (b) and
    Sacko-bye (s) odds: 'bye' once the playoffs are all but certain and a bye
    isn't, 'playoffs' while a playoff spot is in doubt, 'avoid_sacko_bye' for a
    team that could still fall into the bottom two and is (all but) out of the
    playoff race — a playoff long shot under PLAYOFF_LONG_SHOT chases the Sacko
    bye race instead, where more is at stake — and None when nothing is left to
    decide (a team that's all but locked in, out, or stuck)."""
    lo, hi = 0.005, 0.995
    if p >= hi and lo < b < hi:
        return "bye"
    sacko_live = lo < s < hi
    if lo < p < hi and not (p < PLAYOFF_LONG_SHOT and sacko_live):
        return "playoffs"
    if p < PLAYOFF_LONG_SHOT and sacko_live:
        return "avoid_sacko_bye"
    return None


GOAL_LABEL = {"bye": "A first-round bye", "playoffs": "A playoff spot",
              "avoid_sacko_bye": "Staying out of the Sacko bye"}


def rooting_guide(season, strength, params, franchises, n=10000, seed=0, live=None,
                  now=None):
    """What each team should be rooting for in the week about to be played (or in
    progress), read from the same simulation as the forecast (same seed, same
    odds):

        {"week": 12, "rows": [{fid, owner, team, logo, goal, label, now,
                               win, lose, root: [str], note, settled}]}

    For each team: the one goal still in play (rooting_goal), its odds now, if
    the team wins this week and if it loses, and up to two other games this week
    whose result moves those odds most ("Nate over Shawnee"), each worth at least
    ROOT_MIN_SWING. The odds for 'avoid_sacko_bye' are the chance of staying out
    of it, so higher is always better. Points-wildcard contenders get a `note`
    on the points gap, since every point counts in that race. A team with
    nothing left to decide gets `settled` text instead. {} after the regular
    season's last week."""
    reg = season.get("weeks_in_regular_season") or 14
    week = (live or {}).get("week") or complete_through(season) + 1
    if week > reg:
        return {}
    games = [(m["home"], m["away"]) for m in season.get("matchups") or []
             if m.get("week") == week and not m.get("playoff")]
    teams = sorted(season.get("teams") or {})
    goals = ("playoffs", "bye", "sacko_bye")
    base = {f: dict.fromkeys(goals, 0) for f in teams}
    seen = {(i, side): 0 for i in range(len(games)) for side in (0, 1)}
    hit = {f: {g: dict.fromkeys(seen, 0) for g in goals} for f in teams}
    index = {pair: i for i, pair in enumerate(games)}

    def observe(sim, res):
        winners = {}
        for m in sim:
            i = index.get((m["home"], m["away"])) if m["week"] == week else None
            if i is not None and m["home_score"] != m["away_score"]:
                winners[i] = 0 if m["home_score"] > m["away_score"] else 1
        for i, side in winners.items():
            seen[(i, side)] += 1
        for f, sd in res["seeds"].items():
            flags = {"playoffs": sd <= params.n_playoff, "bye": sd <= 2,
                     "sacko_bye": sd in SACKO_BYE_SEEDS}
            for g, on in flags.items():
                if on:
                    base[f][g] += 1
                    for i, side in winners.items():
                        hit[f][g][(i, side)] += 1

    simulate(season, strength, params, n=n, seed=seed, live=live, observe=observe)

    def chance(f, g, key=None):
        if key is None:
            v = base[f][g] / n
        else:
            v = hit[f][g][key] / seen[key] if seen[key] else None
            if v is None:
                return None
        return 1 - v if g == "sacko_bye" else v

    gaps = wildcard_gaps(now or season)
    holder = next((f for f, gp in gaps.items() if gp.get("holder")), None)
    chasers = sorted((gp["pf_gap"], f) for f, gp in gaps.items()
                     if gp.get("pf_gap") is not None and gp["pf_gap"] > 0)
    teams_map = season.get("teams") or {}
    logos = season.get("team_logos") or {}
    rows = []
    for f in teams:
        p, b, s = (base[f][g] / n for g in goals)
        goal = rooting_goal(p, b, s)
        key = {"bye": "bye", "playoffs": "playoffs", "avoid_sacko_bye": "sacko_bye"}.get(goal)
        own = next(((i, 0 if h == f else 1) for i, (h, a) in enumerate(games)
                    if f in (h, a)), None)
        opp = None
        if own:
            h, a = games[own[0]]
            opp = a if h == f else h
        row = {"fid": f, "owner": short_name_of(f, franchises),
               "team": teams_map.get(f) or short_name_of(f, franchises),
               "logo": logos.get(f, ""), "goal": goal,
               "label": GOAL_LABEL.get(goal), "now": None, "win": None, "lose": None,
               "now_p": None, "win_p": None, "lose_p": None,
               "root": [], "note": None, "settled": None}
        if goal is None:
            if p >= 0.995 and b >= 0.995:
                row["settled"] = "The bye is all but locked"
            elif p >= 0.995:
                row["settled"] = "In; the bye is out of reach"
            elif s >= 0.995:
                row["settled"] = "The Sacko bye is all but locked"
            else:
                row["settled"] = "Out of the playoffs, clear of the Sacko bye"
            if opp:
                row["note"] = f"Play spoiler against {short_name_of(opp, franchises)}"
            rows.append(row)
            continue
        row["now_p"] = round(chance(f, key), 4)
        row["now"] = pct_label(row["now_p"])
        if own:
            win, lose = chance(f, key, own), chance(f, key, (own[0], 1 - own[1]))
            if win is not None:
                row["win_p"], row["win"] = round(win, 4), pct_label(win)
            if lose is not None:
                row["lose_p"], row["lose"] = round(lose, 4), pct_label(lose)
        swings = []
        for i, (h, a) in enumerate(games):
            if own and i == own[0]:
                continue
            ph, pa = chance(f, key, (i, 0)), chance(f, key, (i, 1))
            if ph is None or pa is None or abs(ph - pa) < ROOT_MIN_SWING:
                continue
            fav, other = (h, a) if ph > pa else (a, h)
            swings.append((abs(ph - pa), fav, other))
        swings.sort(reverse=True)
        row["root"] = [f"{short_name_of(w, franchises)} over {short_name_of(l, franchises)}"
                       for _, w, l in swings[:ROOT_MAX]]
        if goal == "playoffs" and f in gaps:
            if f == holder and chasers:
                row["note"] = (f"6th seed: {chasers[0][0]:.1f} ahead of "
                               f"{short_name_of(chasers[0][1], franchises)}")
            elif (gaps[f].get("pf_gap") or 0) > 0 and holder:
                row["note"] = (f"6th seed: {gaps[f]['pf_gap']:.1f} behind "
                               f"{short_name_of(holder, franchises)}")
        rows.append(row)
    return {"week": week, "rows": rows}


# Smallest playoff-odds move worth an arrow: at 10,000 runs the odds carry ~0.5 pt
# of simulation noise, so anything under 2 pts could be chance.
PLAYOFF_MOVE_MIN = 0.02


def trend(now, before, threshold, scale=1, digits=0):
    """{dir: 'up'|'down', text: '▲4'} for a move of at least `threshold`, else
    None (no prior week, or too small to mean anything)."""
    if before is None:
        return None
    d = now - before
    if abs(d) < threshold:
        return None
    mag = abs(d) * scale
    mag = f"{mag:.{digits}f}" if digits else str(round(mag))
    return {"dir": "up" if d > 0 else "down", "text": ("▲" if d > 0 else "▼") + mag}


def as_of_now(season):
    """The season as if it ended this second: a copy in which every regular-season
    game with a live score (either side on the board) counts as final at its
    current score, so the leader has the win. Games nobody has scored in yet stay
    unplayed, so a 0-0 game before kickoff isn't a tie. Returns (season, week),
    `week` being the live week counted (None when no game is in progress, in which
    case the season comes back unchanged)."""
    reg = season.get("weeks_in_regular_season") or 14
    week, ms = None, []
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        hs, as_ = m.get("home_score"), m.get("away_score")
        if (1 <= w <= reg and not m.get("playoff") and hs is not None
                and as_ is not None and not game_final(m) and (hs or as_)):
            m = {k: v for k, v in m.items() if k not in ("final", "played")}
            week = w if week is None else min(week, w)
        ms.append(m)
    return (dict(season, matchups=ms), week) if week else (season, None)


def as_projected(season, live):
    """The season as if the live week finishes as projected right now: a copy in
    which each of that week's games counts as final at both teams' live projected
    finals — points scored so far plus the projections of starters still to play
    (live_week's `score` + `remaining`). Every game in the week counts once it's
    under way, including ones that haven't kicked off yet (at their full
    projections), so the table never mixes projected and untouched games. ESPN's
    stored `home_proj`/`away_proj` aren't used: they're the starters' pre-game
    projections summed, blind to what's already been scored. Returns (season,
    week); without a live week (or the rosters and kickoff times to project it)
    it falls back to as_of_now, current scores."""
    if not live:
        return as_of_now(season)
    wk, teams = live["week"], live["teams"]
    ms = []
    for m in season.get("matchups") or []:
        if (m.get("week") == wk and not m.get("playoff")
                and m["home"] in teams and m["away"] in teams):
            m = {k: v for k, v in m.items() if k not in ("final", "played")}
            for side in ("home", "away"):
                t = teams[m[side]]
                m[side + "_score"] = round(t["score"] + t["remaining"], 2)
        ms.append(m)
    return dict(season, matchups=ms), wk


def forecast_rows(season, franchises, strength, result, prev=None, now=None):
    """Display rows for the season-page forecast table, in standings order: best
    record first (win pct, a tie counting as half a win, like the standings
    table), points-for breaking level records, then playoff odds — except that
    the rows follow the league's seeding as it stands today: seeds 1-5 by
    record, the 6th seed the points wildcard holder (top scorer outside the top
    five), then seeds 7-12 by record. Each row carries its current `seed`.
    Each: {fid, team, owner, logo, record, pf, rating, proj_wins, cells},
    where `cells` is {outcome: {text, color}} — the colour on the same warm heat
    ramp as every other table, scaled to the probability itself (0% cream .. 100%
    red-orange). `pf` is points scored so far — the 6th seed is a points
    wildcard, so it matters to the odds — with `pf_color` shaded across the league
    exactly as the season standings table shades it. `prev` is last week's (strength, result);
    when given, the playoff cell carries a trend ({dir, text}) for meaningful moves.
    A playoff spot or bye a team has mathematically clinched shows a checkmark
    instead of '>99%' (see clinch_status). `wc_gap` is the team's points-per-game
    chase of the 6th seed (see wildcard_gaps).

    `now` (as_projected / as_of_now output's season) drives everything the table
    shows apart from the odds — record, points-for, PF Back, the seeds and row
    order, and the ✓ / ✕ — so it reads as "if the live week finishes as
    projected": a team that would clinch on those results gets its ✓."""
    prev_res = (prev or ({}, {}))[1]
    table = now or season
    clinched = clinch_status(table)
    gaps = wildcard_gaps(table)
    teams = season.get("teams") or {}
    logos = season.get("team_logos") or {}
    rec, pf = {}, {}
    for m in played_games(table):
        for f, a, b in ((m["home"], m["home_score"], m["away_score"]),
                        (m["away"], m["away_score"], m["home_score"])):
            r = rec.setdefault(f, [0, 0, 0])
            r[0 if a > b else 1 if b > a else 2] += 1
            pf[f] = pf.get(f, 0.0) + a
    pfs = [pf.get(f, 0.0) for f in result]
    lo, hi = (min(pfs), max(pfs)) if pfs else (0, 0)
    rows = []
    for f, res in result.items():
        w, l, t = rec.get(f, [0, 0, 0])
        rows.append({
            "fid": f,
            "team": teams.get(f) or short_name_of(f, franchises),
            "owner": short_name_of(f, franchises),
            "logo": logos.get(f, ""),
            "record": f"{w}-{l}" + (f"-{t}" if t else ""),
            "pf": f"{pf.get(f, 0.0):.1f}",
            "pf_color": heat_color(pf.get(f, 0.0), lo, hi),
            "rating": round(strength[f][0], 1),
            "proj_wins": round(res["wins"], 1),
            "cells": {o: odds_cell(res[o]) for o in TABLE_OUTCOMES},
            "wc_gap": gaps.get(f),
            "_key": (-((w + t / 2) / (w + l + t) if w + l + t else 0.0),
                     -pf.get(f, 0.0), -res["playoffs"]),
        })
    for r in rows:
        for o in ("playoffs", "bye"):
            if r["fid"] in clinched[o]:
                r["cells"][o] = clinched_cell()
        if r["fid"] in clinched["no_playoffs"]:
            r["cells"]["playoffs"] = eliminated_cell(
                "Out: can't reach the top five by record, and more than 50 points "
                "per game behind the 6th seed")
        if r["fid"] in clinched["no_bye"]:
            r["cells"]["bye"] = eliminated_cell("Can't finish in the top two")
        if r["fid"] in clinched["no_sacko_bye"] and "sacko_bye" in r["cells"]:
            r["cells"]["sacko_bye"] = eliminated_cell("Can't finish in the bottom two")
        before = prev_res.get(r["fid"], {}).get("playoffs")
        r["cells"]["playoffs"]["trend"] = trend(
            result[r["fid"]]["playoffs"], before, PLAYOFF_MOVE_MIN, scale=100)
    rows.sort(key=lambda r: r.pop("_key"))
    wc = next((i for i, r in enumerate(rows) if (r["wc_gap"] or {}).get("holder")), None)
    if wc is not None and wc > RECORD_SEEDS:
        rows.insert(RECORD_SEEDS, rows.pop(wc))
    for i, r in enumerate(rows, start=1):
        r["seed"] = i
    return rows


# ---------------------------------------------------------------------------
# Backtesting helpers
# ---------------------------------------------------------------------------

def truncate(season, through_week):
    """A copy of `season` as it stood after `through_week` regular-season weeks:
    later games lose their scores, the playoffs haven't happened."""
    reg = season.get("weeks_in_regular_season") or 14
    ms = []
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        if w > reg or m.get("playoff"):
            continue
        m = dict(m)
        if w > through_week:
            m["home_score"] = m["away_score"] = None
            m["played"] = False
        ms.append(m)
    return {"season": season.get("season"), "teams": season.get("teams"),
            "weeks_in_regular_season": reg, "matchups": ms}


def actual_outcomes(season, final_order):
    """{fid: {outcome: 0/1}} from a finished season and its true final order
    (lib.playoff_order.corrected_standings)."""
    seeded = season.get("playoff_teams") or []         # in seed order
    made, byes = set(seeded), set(seeded[:2])
    out = {}
    for i, f in enumerate(final_order):
        out[f] = {"shiva": int(i == 0), "top3": int(i < 3), "bye": int(f in byes),
                  "playoffs": int(f in made), "sacko_bracket": int(f not in made),
                  "sacko": int(i == len(final_order) - 1)}
    return out


def brier(pred, actual, outcome):
    """Mean squared error of one outcome's probabilities across teams."""
    fs = [f for f in actual if f in pred]
    return sum((pred[f][outcome] - actual[f][outcome]) ** 2 for f in fs) / len(fs)


def rest_of_season_errors(season, through_week, params, proj=None):
    """How well the strength model, fit on the first `through_week` weeks, predicts
    each team's *actual* average over the rest of the regular season. Returns a
    list of (predicted - actual) per team — the score-level fitting signal, which
    uses every past season (no bracket needed)."""
    reg = season.get("weeks_in_regular_season") or 14
    teams = sorted(season.get("teams") or {})
    before = team_scores(played_games(season, before_week=through_week + 1))
    after = {}
    for m in played_games(season):
        if m["week"] > through_week:
            after.setdefault(m["home"], []).append(m["home_score"])
            after.setdefault(m["away"], []).append(m["away_score"])
    st = strengths(teams, before, params, proj)
    return [st[f][0] - statistics.mean(after[f]) for f in teams if after.get(f)]
