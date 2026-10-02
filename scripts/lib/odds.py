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

import random
import statistics
from dataclasses import dataclass

from .data import game_final, short_name_of
from .render import warm_heat, heat_color
from .playoff_order import six_team_playoff

OUTCOMES = ("sacko", "sacko_bracket", "playoffs", "bye", "top3", "shiva")
# What the season-page table shows. The Sacko bracket is just 1 - playoffs, so it's
# simulated and backtested but not displayed.
TABLE_OUTCOMES = ("sacko", "playoffs", "bye", "top3", "shiva")


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


def strengths(teams, scores, params, proj=None):
    """{fid: (mean, sd)} — the posterior estimate of each team's true weekly
    scoring level. `scores` is {fid: [played scores]}; `proj` an optional
    {fid: projected starter total}, centered on its own league mean so only a
    team's projection *relative to the league* matters."""
    played = [s for v in scores.values() for s in v]
    center = statistics.mean(played) if played else params.league_mean
    proj = {f: p for f, p in (proj or {}).items() if f in teams and p}
    pbar = statistics.mean(proj.values()) if proj else 0.0
    t2, s2 = params.tau ** 2, params.sigma ** 2
    out = {}
    for f in teams:
        prior = center + params.proj_weight * (proj[f] - pbar) if f in proj else center
        xs = scores.get(f) or []
        prec = 1 / t2 + len(xs) / s2
        mean = (prior / t2 + sum(xs) / s2) / prec
        out[f] = (mean, prec ** -0.5)
    return out


def _bracket_season(season, teams, reg, year):
    """A minimal season shell six_team_playoff accepts; matchups filled per sim."""
    return {"season": max(year, 2025), "weeks_in_regular_season": reg,
            "final_standings": list(teams), "playoff_teams": list(teams[:6]),
            "matchups": []}


def simulate(season, strength, params, n=10000, seed=0):
    """Run `n` simulated seasons from the current state. Returns
    {fid: {outcome: probability, 'wins': mean final wins, 'seed': mean seed}}."""
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
    tally = {f: dict.fromkeys(OUTCOMES, 0) for f in teams}
    wins = dict.fromkeys(teams, 0)
    seeds = dict.fromkeys(teams, 0)
    sigma = params.sigma
    for _ in range(n):
        level = {f: rng.gauss(*strength[f]) for f in teams}
        sim = list(base)
        for m in remaining:
            h, a = m["home"], m["away"]
            sim.append({"week": m["week"], "home": h, "away": a,
                        "home_score": rng.gauss(level[h], sigma),
                        "away_score": rng.gauss(level[a], sigma)})
        # Playoff weeks: every team plays (scores only matter per team).
        for w in pweeks:
            for i in range(0, len(teams), 2):
                h, a = teams[i], teams[i + 1]
                sim.append({"week": w, "home": h, "away": a,
                            "home_score": rng.gauss(level[h], sigma),
                            "away_score": rng.gauss(level[a], sigma)})
        shell["matchups"] = sim
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
        tally[order[0]]["shiva"] += 1
        for f in order[:3]:
            tally[f]["top3"] += 1
        tally[order[-1]]["sacko"] += 1
        for m in sim:
            if m["week"] <= reg and m["home_score"] != m["away_score"]:
                wins[m["home"] if m["home_score"] > m["away_score"] else m["away"]] += 1
    return {f: dict({k: v / n for k, v in tally[f].items()},
                    wins=wins[f] / n, seed=seeds[f] / n) for f in teams}


def forecast(season, params, proj=None, n=10000, seed=0):
    """Strength estimate + simulation from the season's completed weeks."""
    teams = sorted(season.get("teams") or {})
    st = strengths(teams, team_scores(played_games(season)), params, proj)
    return st, simulate(season, st, params, n=n, seed=seed)


def pct_label(p):
    """Display a probability: '<1%' / '>99%' at the extremes (a simulation can't
    prove a clinch or an elimination), otherwise a whole percent."""
    if p < 0.005:
        return "<1%"
    if p > 0.995:
        return ">99%"
    return f"{round(p * 100)}%"


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


def forecast_rows(season, franchises, strength, result, prev=None):
    """Display rows for the season-page forecast table, best playoff odds first
    (ties broken by bye, then Shiva odds).
    Each: {fid, team, owner, logo, record, pf, rating, proj_wins, cells},
    where `cells` is {outcome: {text, color}} — the colour on the same warm heat
    ramp as every other table, scaled to the probability itself (0% cream .. 100%
    red-orange). `pf` is points scored so far — the 6th seed is a points
    wildcard, so it matters to the odds — with `pf_color` shaded across the league
    exactly as the season standings table shades it. `prev` is last week's (strength, result);
    when given, the playoff cell carries a trend ({dir, text}) for meaningful moves."""
    prev_res = (prev or ({}, {}))[1]
    teams = season.get("teams") or {}
    logos = season.get("team_logos") or {}
    rec, pf = {}, {}
    for m in played_games(season):
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
            "cells": {o: {"text": pct_label(res[o]), "color": warm_heat(res[o])}
                      for o in TABLE_OUTCOMES},
            "_key": (-res["playoffs"], -res["bye"], -res["shiva"], res["sacko"]),
        })
    for r in rows:
        before = prev_res.get(r["fid"], {}).get("playoffs")
        r["cells"]["playoffs"]["trend"] = trend(
            result[r["fid"]]["playoffs"], before, PLAYOFF_MOVE_MIN, scale=100)
    rows.sort(key=lambda r: r.pop("_key"))
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
