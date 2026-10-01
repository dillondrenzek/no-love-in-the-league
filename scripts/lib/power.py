"""Weekly power rankings — the computed half of a hybrid feature.

The order and week-over-week movement are computed here from the season's results
(deterministic, reproducible); the one-line blurb per team is written by an agent
and joined in at build time (see scripts/weekly_power.py and generate_weeks.py).

A team's power score, as of a given week, blends three normalized signals over its
completed regular-season games *before* that week: scoring average (how good the
team is), recent form (its last three weeks), and win rate. Scoring leads because
points are the truest talent signal in fantasy; form and record adjust around it.
The score itself is intentionally not published — only the rank and the movement.
"""

import statistics

from .data import (DATA_DIR, game_final, short_name_of, load_power_blurbs,
                   load_power_order)
from .weeks import week_state

def prep_window_problem(season, week):
    """Why `week`'s power rankings shouldn't be generated right now, or None when
    it's the right time. Rankings are a start-of-week snapshot, so they're
    generated in the window between the prior week going final and this week's
    first kickoff (Thursday night) — late enough to reflect the latest results,
    early enough to be a true preview. Week 1 has no prior week to wait on."""
    if week > 1 and week_state(season, week - 1) != "complete":
        return f"Week {week - 1} isn't final yet — rank Week {week} once it is."
    if week_state(season, week) != "future":
        return f"Week {week} has already kicked off — its rankings would be stale."
    return None


# Weight the three signals. Scoring average dominates; recent form and win rate
# nudge it.
_W_AVG, _W_FORM, _W_WIN = 0.5, 0.3, 0.2


def _metrics_before(season, week):
    """{fid: (avg_pf, last3_avg, win_pct)} over completed regular-season games in
    the weeks before `week`. Empty when no games have been played yet."""
    per = {}
    for m in season.get("matchups") or []:
        w = m.get("week")
        if not w or w >= week or m.get("playoff") or not game_final(m):
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None:
            continue
        for fid, pf, pa in ((m["home"], hs, as_), (m["away"], as_, hs)):
            d = per.setdefault(fid, {"pf": [], "w": 0, "t": 0})
            d["pf"].append((w, pf))
            if pf > pa:
                d["w"] += 1
            elif pf == pa:
                d["t"] += 1
    out = {}
    for fid, d in per.items():
        pfs = [p for _, p in sorted(d["pf"])]
        g = len(pfs)
        out[fid] = (sum(pfs) / g, sum(pfs[-3:]) / len(pfs[-3:]),
                    (d["w"] + 0.5 * d["t"]) / g)
    return out


def _z(values):
    """{key: z-score} for a {key: value} map (population stdev; 0 when flat)."""
    vals = list(values.values())
    mean = statistics.mean(vals)
    sd = statistics.pstdev(vals) or 1.0
    return {k: (v - mean) / sd for k, v in values.items()}


def _order_at(season, week):
    """The fids ranked best-to-worst by power score as of `week` (data from the
    weeks before it), or None when there's nothing to rank on yet."""
    m = _metrics_before(season, week)
    if not m:
        return None
    z_avg = _z({f: v[0] for f, v in m.items()})
    z_form = _z({f: v[1] for f, v in m.items()})
    z_win = _z({f: v[2] for f, v in m.items()})
    score = {f: _W_AVG * z_avg[f] + _W_FORM * z_form[f] + _W_WIN * z_win[f]
             for f in m}
    return sorted(score, key=lambda f: score[f], reverse=True)


def power_rankings(season, week, franchises, blurbs=None,
                   order=None, prev_order=None, records=None):
    """Ranked list of dicts for `week`, reflecting the state going *into* that week
    (data from the weeks before it): {rank, fid, team, owner, logo, record,
    movement, is_new, blurb}. `movement` is last week's rank minus this week's
    (positive = climbed); `is_new` marks a team with no prior ranking.

    Order is normally computed from prior results, but an explicit `order`/
    `prev_order` (a list of fids, e.g. an editorial preseason ranking loaded from
    the data file) takes precedence — that's how week 1, with no games to compute
    from, gets ranked. `records` is an optional {fid: "W-L[-T]"} shown inline.
    Returns [] when the week can't be ranked and no explicit order is given."""
    if order is None:
        order = _order_at(season, week)
    if not order:
        return []
    if prev_order is None:
        prev_order = _order_at(season, week - 1)
    prev_rank = {f: i + 1 for i, f in enumerate(prev_order)} if prev_order else {}
    teams = season.get("teams", {})
    logos = season.get("team_logos") or {}
    blurbs = blurbs or {}
    records = records or {}
    rows = []
    for i, fid in enumerate(order):
        rank = i + 1
        was = prev_rank.get(fid)
        rows.append({
            "rank": rank,
            "fid": fid,
            "team": teams.get(fid) or short_name_of(fid, franchises),
            "owner": short_name_of(fid, franchises),
            "logo": logos.get(fid, ""),
            "record": records.get(fid, ""),
            "movement": (was - rank) if was else 0,
            "is_new": was is None,
            "blurb": blurbs.get(fid, ""),
        })
    return rows


def week_power_rankings(season, week, franchises, records=None, data_dir=DATA_DIR):
    """power_rankings for `week` wired to its data/power files: that week's blurbs
    and any editorial `order:`, with the *prior* week's editorial order (when it set
    one) as the baseline for movement. The site build and scripts/weekly_power.py
    both go through here, so the movement the agent writes about is the movement
    the page renders."""
    year = season["season"]
    return power_rankings(
        season, week, franchises, load_power_blurbs(year, week, data_dir),
        order=load_power_order(year, week, data_dir),
        prev_order=load_power_order(year, week - 1, data_dir), records=records)
