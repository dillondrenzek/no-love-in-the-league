"""Shared context for the weekly preview/recap prompt builders.

Pure, network-free functions over already-stored season data: the current
standings, recent trades / waiver adds, and the league record book — the
"what's actually going on in the league right now" material that makes a preview
or recap specific rather than generic. The prompt builders layer live per-player
data (from the ESPN client) on top of these.
"""

from .standings import get_standings
from .data import short_name_of, complete_weeks
from .state import is_in_progress


def standings_snapshot(season, franchises):
    """Standings through the latest complete week, best finish first:
    [{rank, owner, team, record, pf}]. Empty until a game is complete.

    For an in-progress season we re-sort by live record (wins, then points-for):
    `get_standings` orders a season by its `final_standings`, which is the
    authoritative end-of-year ranking once complete but only the *preseason/seeded*
    order mid-season — so without this the weekly preview/recap would show stale
    standings. A complete season keeps `get_standings`' order (real final finish)."""
    rows = get_standings(season, franchises)
    if is_in_progress(season):
        rows = sorted(rows, key=lambda r: (r.get("wins", 0), r.get("points_for") or 0),
                      reverse=True)
    teams = season.get("teams", {})
    out = []
    for i, r in enumerate(rows, 1):
        out.append({
            "rank": i,
            "owner": short_name_of(r["id"], franchises),
            "team": teams.get(r["id"]) or r["name"],
            "record": r["record"],
            "pf": r["points_for"],
        })
    return out


def recent_moves(season, franchises, lo_week, hi_week):
    """Trades and waiver/FA adds with a week in [lo_week, hi_week] inclusive:
    {trades: [{week, parties, detail}], adds: [{week, owner, player, kind}]}.

    Adds come from the season's `rosters:` block (present once re-imported under
    the roster feature); trades from `trades`. A trade at week 0 is a draft-day
    deal and only shows when the window includes 0."""
    def nm(fid):
        return short_name_of(fid, franchises)

    trades = []
    for t in season.get("trades") or []:
        wk = t.get("week") or 0
        if lo_week <= wk <= hi_week and t.get("assets"):
            legs = []
            for f in t.get("teams") or []:
                got = [a["label"] for a in t["assets"] if a.get("to") == f]
                if got:
                    legs.append(f"{nm(f)} got " + ", ".join(got))
            trades.append({"week": wk, "parties": " / ".join(nm(f) for f in (t.get("teams") or [])),
                           "detail": "; ".join(legs)})

    adds = []
    for fid, entries in (season.get("rosters") or {}).items():
        for e in entries or []:
            wk = e.get("week") or 0
            if e.get("via") == "add" and lo_week <= wk <= hi_week:
                adds.append({"week": wk, "owner": nm(fid), "player": e.get("player"),
                             "kind": "waiver" if e.get("waiver") else "FA"})

    trades.sort(key=lambda x: x["week"])
    adds.sort(key=lambda x: (x["week"], x["owner"]))
    return {"trades": trades, "adds": adds}


def perceived_strength(rosters_ctx, franchises):
    """A 'who's strongest on paper this week' ranking from the projected starter
    totals, best first: [{rank, owner, fid, proj_total}].

    This is the only strength signal available before games are played (ESPN's own
    projected ranks come back zeroed for this league), so it stands in for the
    barbershop 'that's the team to beat' take — the preview uses it to crown a paper
    favorite and needle everyone below. Empty when no projections are loaded."""
    rows = [(fid, e.get("proj_total")) for fid, e in (rosters_ctx or {}).items()
            if e.get("proj_total") is not None]
    rows.sort(key=lambda r: r[1], reverse=True)
    return [{"rank": i, "owner": short_name_of(fid, franchises), "fid": fid,
             "proj_total": pt} for i, (fid, pt) in enumerate(rows, 1)]


def _reg_results_through(season, upto_week):
    """{fid: [(week, 'W'|'L'|'T', points)]} for every complete regular-season week
    strictly before `upto_week`, plus that latest completed week number (or None).
    The raw material for streaks and last-week form."""
    complete = {w for w in complete_weeks(season) if w and w < upto_week}
    res = {}
    for m in season.get("matchups") or []:
        wk = m.get("week")
        if wk not in complete or m.get("playoff"):
            continue
        hs, as_ = m.get("home_score"), m.get("away_score")
        if hs is None or as_ is None:
            continue
        for fid, pf, pa in ((m["home"], hs, as_), (m["away"], as_, hs)):
            r = "T" if pf == pa else ("W" if pf > pa else "L")
            res.setdefault(fid, []).append((wk, r, round(float(pf), 1)))
    for fid in res:
        res[fid].sort()
    return res, (max(complete) if complete else None)


def team_form(season, franchises, upto_week, projections=None):
    """Momentum hooks for each team entering `upto_week`, from completed weeks:

        {fid: {record, streak, last_week, last_points, last_result,
               last_high, last_low, last_vs_proj}}

    streak is like 'W3' / 'L2'; last_high/last_low flag the prior week's league
    top/bottom score; last_vs_proj is that week's points minus the pre-game
    projection (needs `projections` = lib.data.load_projections output). Empty
    until at least one week is complete — so week 1 previews simply skip it. This
    is the 'can the heater continue / will they bounce back' fuel."""
    results, last_wk = _reg_results_through(season, upto_week)
    if last_wk is None:
        return {}
    last_scores = {fid: pts for fid, seq in results.items()
                   for (wk, _, pts) in seq if wk == last_wk}
    hi = max(last_scores.values()) if last_scores else None
    lo = min(last_scores.values()) if last_scores else None
    wk_proj = ((projections or {}).get(last_wk) or {}).get("proj") or {}

    out = {}
    for fid, seq in results.items():
        last_r = seq[-1][1]
        n = 0
        for (_, r, _) in reversed(seq):
            if r == last_r:
                n += 1
            else:
                break
        wins = sum(1 for _, r, _ in seq if r == "W")
        losses = sum(1 for _, r, _ in seq if r == "L")
        ties = sum(1 for _, r, _ in seq if r == "T")
        lp = last_scores.get(fid)
        proj = wk_proj.get(fid)
        out[fid] = {
            "record": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
            "streak": f"{last_r}{n}",
            "last_week": last_wk,
            "last_points": lp,
            "last_result": last_r,
            "last_high": lp is not None and lp == hi,
            "last_low": lp is not None and lp == lo,
            "last_vs_proj": round(lp - proj, 1) if (lp is not None and proj is not None) else None,
        }
    return out


def week_roster_context(week_rosters, *, want_actual=False):
    """Turn persisted per-player rosters into the per-team shape the preview/recap
    data blocks consume:

        {fid: {starters:[{player,pos,proj,actual}], proj_total, actual_total,
               bench_points, top?, bust?}}

    `week_rosters` is {fid: [{player,pos,starter,proj,actual}, ...]} from
    data.load_week_rosters. `want_actual` (recap) adds each team's top scorer and
    biggest bust (projected minus actual) plus bench points, once games are
    played. Pure — no network; empty in, empty out."""
    def num(v):
        return float(v) if isinstance(v, (int, float)) else None

    out = {}
    for fid, players in (week_rosters or {}).items():
        starters, bench_points = [], 0.0
        for p in players or []:
            proj, act = num(p.get("proj")), num(p.get("actual"))
            if p.get("starter"):
                starters.append({"player": p.get("player"), "pos": p.get("pos"),
                                 "proj": proj, "actual": act})
            elif act is not None:
                bench_points += act

        acts = [s["actual"] for s in starters if s["actual"] is not None]
        entry = {
            "starters": starters,
            "proj_total": round(sum(s["proj"] or 0.0 for s in starters), 1),
            "actual_total": round(sum(acts), 1) if acts else None,
            "bench_points": round(bench_points, 1),
        }
        if want_actual and acts:
            scored = [s for s in starters if s["actual"] is not None]
            top = max(scored, key=lambda s: s["actual"], default=None)
            busts = [s for s in scored if s["proj"] is not None and s["proj"] > s["actual"]]
            bust = max(busts, key=lambda s: s["proj"] - s["actual"], default=None)
            entry["top"] = {"player": top["player"], "actual": round(top["actual"], 1)} if top else None
            entry["bust"] = ({"player": bust["player"], "proj": round(bust["proj"], 1),
                              "actual": round(bust["actual"], 1)} if bust else None)
        out[fid] = entry
    return out


def league_bests(records):
    """Score-based record book values for reference, from records.yml's `records`
    list: [{category, value, holder, season}]. Lets the agent note when a game is
    at or near an all-time mark."""
    keep = ("Most Points in a Week", "Fewest Points in a Week", "Biggest Blowout",
            "Highest Combined Score", "Most Points in a Season")
    out = []
    for r in records or []:
        if r.get("category") in keep:
            out.append({"category": r["category"], "value": r["value"],
                        "holder": r.get("holder") or r.get("owner_name"),
                        "season": r.get("season")})
    return out
