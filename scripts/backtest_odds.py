#!/usr/bin/env python3
"""Fit and grade the season-forecast model (lib/odds) against past seasons.

Two passes:

  fit   — score level, every season with roster snapshots (2018+): for each
          cutoff week, how far off is each team's predicted scoring level from its
          actual rest-of-season average? Grid-searches `tau` and `proj_weight`.
  grade — outcome level, seasons in today's format (12 teams, 6-team playoff,
          14-week regular season): simulate from each cutoff and score the
          predicted Shiva / top-3 / playoffs / Sacko-bracket / Sacko odds against
          what happened (Brier score; lower is better), next to a coin-flip
          baseline that treats every team as equal.

    python scripts/backtest_odds.py fit
    python scripts/backtest_odds.py grade [--tau 8 --proj-weight 0.5 --sims 2000]

Not part of the build — run it when tuning lib/odds.Params.
"""

import argparse
import functools
import statistics

from lib.data import load_seasons, load_franchises, load_week_rosters
from lib.odds import (Params, OUTCOMES, rest_of_season_errors, starter_projection,
                      truncate, forecast, actual_outcomes, brier)
from lib.playoff_order import corrected_standings

FIT_YEARS = range(2018, 2026)
GRADE_YEARS = (2023, 2024, 2025)
_FR = None


@functools.lru_cache(maxsize=None)
def _starters(year, week):
    return starter_projection(load_week_rosters(year, week, _FR))


@functools.lru_cache(maxsize=None)
def _proj_cached(year, week, mode):
    weeks = [week] if mode == "next" else range(1, week + 1)
    per = [p for p in (_starters(year, w) for w in weeks) if p]
    if not per:
        return None
    return {f: statistics.mean(p[f] for p in per if f in p) for f in per[-1]}


def _proj(year, week, franchises, mode):
    return _proj_cached(year, week, mode)


def _proj_uncached(year, week, franchises, mode):
    """Starter projections entering `week`: that week's snapshot ('next'), or the
    average over weeks 1..week ('avg', smooths bye-week dips)."""
    weeks = [week] if mode == "next" else range(1, week + 1)
    per = [starter_projection(load_week_rosters(year, w, franchises)) for w in weeks]
    per = [p for p in per if p]
    if not per:
        return None
    return {f: statistics.mean(p[f] for p in per if f in p) for f in per[-1]}


def fit(seasons, franchises):
    rows = []
    cuts = (1, 2, 3, 4, 6, 8, 10)
    for mode in ("next", "avg"):
        for tau in (2, 3, 4, 5, 6, 8):
            for pw in (0.0, 0.25, 0.5, 0.625, 0.75, 1.0):
                p = Params(tau=tau, proj_weight=pw)
                err = {k: [] for k in cuts}
                for s in seasons:
                    for k in cuts:
                        proj = _proj(s["season"], k + 1, franchises, mode) if pw else None
                        err[k] += rest_of_season_errors(s, k, p, proj)
                rmse = {k: statistics.mean(e * e for e in v) ** .5 for k, v in err.items()}
                rows.append((statistics.mean(rmse.values()), mode, tau, pw, rmse))
    rows.sort(key=lambda r: r[0])
    print("Rest-of-season scoring error (RMSE, pts/wk) by cutoff week — best first")
    print(f"{'proj':5} {'tau':>4} {'pw':>5} | " + " ".join(f"wk{k:>2}" for k in cuts) + " |  avg")
    for avg, mode, tau, pw, rmse in rows[:12]:
        print(f"{mode:5} {tau:4} {pw:5.2f} | " + " ".join(f"{rmse[k]:5.1f}" for k in cuts) + f" | {avg:5.2f}")
    naive = Params(tau=1000)
    err = [e for s in seasons for k in cuts for e in rest_of_season_errors(s, k, naive)]
    print(f"\nFor reference — face-value averages (no shrinkage): {statistics.mean(e*e for e in err)**.5:.2f}")


def grade(seasons, franchises, params, mode, sims):
    cuts = (0, 2, 4, 6, 8, 10, 12)
    coin = Params(tau=0.001, proj_weight=0.0)
    print(f"Brier score by outcome (lower is better); model {params}, proj={mode}\n")
    print(f"{'cutoff':>6} | " + " ".join(f"{o:>13}" for o in OUTCOMES) + " |   model   coin")
    tot = {"m": [], "c": []}
    for k in cuts:
        bm = {o: [] for o in OUTCOMES}
        bc = {o: [] for o in OUTCOMES}
        for s in seasons:
            actual = actual_outcomes(s, corrected_standings(s))
            t = truncate(s, k)
            proj = _proj(s["season"], k + 1, franchises, mode) if params.proj_weight else None
            _, pm = forecast(t, params, proj, n=sims, seed=k)
            _, pc = forecast(t, coin, None, n=sims, seed=k)
            for o in OUTCOMES:
                bm[o].append(brier(pm, actual, o))
                bc[o].append(brier(pc, actual, o))
        m = {o: statistics.mean(v) for o, v in bm.items()}
        c = {o: statistics.mean(v) for o, v in bc.items()}
        tot["m"].append(statistics.mean(m.values()))
        tot["c"].append(statistics.mean(c.values()))
        print(f"{'wk ' + str(k):>6} | " + " ".join(f"{m[o]:.3f} ({c[o]:.3f})" for o in OUTCOMES)
              + f" |  {tot['m'][-1]:.4f} {tot['c'][-1]:.4f}")
    print(f"{'all':>6} | {'(coin-flip baseline in parentheses)':>69} |  "
          f"{statistics.mean(tot['m']):.4f} {statistics.mean(tot['c']):.4f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=("fit", "grade"))
    ap.add_argument("--tau", type=float, default=Params.tau)
    ap.add_argument("--proj-weight", type=float, default=Params.proj_weight)
    ap.add_argument("--proj", choices=("next", "avg"), default="avg")
    ap.add_argument("--sims", type=int, default=2000)
    args = ap.parse_args()
    global _FR
    franchises = _FR = load_franchises()
    seasons = {s["season"]: s for s in load_seasons()}
    if args.mode == "fit":
        fit([seasons[y] for y in FIT_YEARS], franchises)
    else:
        params = Params(tau=args.tau, proj_weight=args.proj_weight)
        grade([seasons[y] for y in GRADE_YEARS], franchises, params, args.proj, args.sims)


if __name__ == "__main__":
    main()
