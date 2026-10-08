"""Shared context for the weekly preview/recap prompt builders.

Pure, network-free functions over already-stored season data: the current
standings, recent trades / waiver adds, and the league record book — the
"what's actually going on in the league right now" material that makes a preview
or recap specific rather than generic. The prompt builders layer live per-player
data (from the ESPN client) on top of these.
"""

from .standings import get_standings
from .data import short_name_of, complete_weeks, trade_asset_label
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
        # Win% (a tie = half a win), then points-for — so a 0-0-1 outranks a 0-1.
        rows = sorted(rows, key=lambda r: (r.get("wins", 0) + 0.5 * r.get("ties", 0),
                                           r.get("points_for") or 0), reverse=True)
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


def week_superlatives(rosters_ctx):
    """League-wide bests from a week's per-player data, so a recap only claims a
    superlative that's actually true: the single best individual game and the most
    points left on a bench. `rosters_ctx` is week_roster_context output. Returns
    {best_player: {fid, player, actual} | None, bench_leader: {fid, points} | None};
    both None when there's no per-player data (no roster snapshot)."""
    rc = rosters_ctx or {}
    best = None
    for fid, e in rc.items():
        t = e.get("top")
        if t and t.get("actual") is not None and (best is None or t["actual"] > best["actual"]):
            best = {"fid": fid, "player": t["player"], "actual": t["actual"]}
    bench = None
    for fid, e in rc.items():
        bp = e.get("bench_points")
        if bp is not None and (bench is None or bp > bench["points"]):
            bench = {"fid": fid, "points": bp}
    return {"best_player": best, "bench_leader": bench}


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
                got = [trade_asset_label(a) for a in t["assets"] if a.get("to") == f]
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


# ESPN injury designations that mean a player did not (or will not) suit up.
_UNAVAILABLE = {"OUT", "DOUBTFUL", "INJURY_RESERVE", "IR", "SUSPENSION",
                "SUSPENDED", "PUP", "NFI"}
_PRETTY = {"INJURY_RESERVE": "IR", "IR": "IR", "SUSPENSION": "Susp",
           "SUSPENDED": "Susp"}


def _injury_note(injury, starter, proj, actual):
    """A status label ('Out', 'IR', 'Doubtful', 'Questionable', …) when a player was
    unavailable this week, else None — so previews/recaps credit players by what they
    actually did. Out/IR/Doubtful always count as unavailable. A soft tag
    (Questionable) is ignored when the player was projected or actually scored — the
    league rule of thumb: if a questionable player made the active lineup, he played.
    Works off whatever status was captured; empty when ESPN gave none."""
    raw = (injury or "").strip().upper()
    if not raw or raw == "ACTIVE":
        return None
    label = _PRETTY.get(raw) or raw.replace("_", " ").title()
    if raw in _UNAVAILABLE:
        return label
    # Soft designation: treat as played (not flagged) if there's any sign he suited up.
    if (actual or 0) > 0 or (proj or 0) > 0:
        return None
    return label


def _bye_week(p):
    """A player's NFL bye week as an int, or None when the snapshot predates byes."""
    b = p.get("bye_week")
    return b if isinstance(b, int) and b > 0 else None


def week_roster_context(week_rosters, *, want_actual=False, week=None):
    """Turn persisted per-player rosters into the per-team shape the preview/recap
    data blocks consume:

        {fid: {starters:[{player,pos,proj,actual}], proj_total, actual_total,
               bench_points, injured, on_bye, bye_next, top?, bust?}}

    `week_rosters` is {fid: [{player,pos,starter,proj,actual,pro_team,bye_week},
    ...]} from data.load_week_rosters. `want_actual` (recap) adds each team's top
    scorer and biggest bust (projected minus actual) plus bench points, once games
    are played. `week` (the week being written about) fills `on_bye` — every
    rostered player whose NFL team is off that week, starter flag included, since
    starting one is a guaranteed zero — and `bye_next`, who's off the week after.
    A player on bye is listed there, not under `injured`: his zero is the
    schedule, not his health. Pure — no network; empty in, empty out."""
    def num(v):
        return float(v) if isinstance(v, (int, float)) else None

    out = {}
    for fid, players in (week_rosters or {}).items():
        starters, bench_points, injured = [], 0.0, []
        on_bye, bye_next = [], []
        for p in players or []:
            proj, act = num(p.get("proj")), num(p.get("actual"))
            inj = (p.get("injury") or "").strip()
            starting = bool(p.get("starter"))
            if starting:
                starters.append({"player": p.get("player"), "pos": p.get("pos"),
                                 "proj": proj, "actual": act, "injury": inj})
            elif act is not None:
                bench_points += act
            bye = _bye_week(p)
            if week is not None and bye is not None:
                who = {"player": p.get("player"), "pos": p.get("pos"),
                       "pro_team": p.get("pro_team") or ""}
                if bye == week:
                    on_bye.append(dict(who, starter=starting))
                    continue
                if bye == week + 1:
                    bye_next.append(who)
            # Injury/inactive detection spans the whole roster, not just starters —
            # an IR or Out player is usually on the bench, and that's the context a
            # manager's blurb needs. `status` is None for anyone deemed to have played.
            status = _injury_note(inj, starting, proj, act)
            if status:
                injured.append({"player": p.get("player"), "pos": p.get("pos"),
                                "status": status, "proj": proj, "actual": act,
                                "starter": starting})

        acts = [s["actual"] for s in starters if s["actual"] is not None]
        entry = {
            "starters": starters,
            "proj_total": round(sum(s["proj"] or 0.0 for s in starters), 1),
            "actual_total": round(sum(acts), 1) if acts else None,
            "bench_points": round(bench_points, 1),
            "injured": injured,
            "on_bye": on_bye,
            "bye_next": bye_next,
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


def bye_watch(rosters_ctx, franchises):
    """League-wide bye picture from week_roster_context(..., week=W) output:

        {"teams": ["CAR", "KC"],            # NFL teams off this week (rostered)
         "next_teams": [...],               # ... and next week
         "starting": [{owner, player, pos, pro_team}],   # started while on bye
         "hardest_hit": [{owner, count, players}],       # this week, most first
         "next_hardest_hit": [{owner, count, players}]}  # next week, most first

    Only NFL teams with a rostered player show up — that's every bye that matters
    here. The hit lists include every team with a bye player, most first (ties by
    owner name), so the agent can verify a "most byes" claim instead of eyeballing
    it. Empty lists when the snapshot carries no bye data."""
    teams, next_teams, starting, hit, next_hit = set(), set(), [], [], []
    for fid, e in (rosters_ctx or {}).items():
        owner = short_name_of(fid, franchises)
        byes, nxt = e.get("on_bye") or [], e.get("bye_next") or []
        teams.update(p["pro_team"] for p in byes if p.get("pro_team"))
        next_teams.update(p["pro_team"] for p in nxt if p.get("pro_team"))
        starting += [{"owner": owner, "player": p["player"], "pos": p["pos"],
                      "pro_team": p["pro_team"]} for p in byes if p.get("starter")]
        if byes:
            hit.append({"owner": owner, "count": len(byes), "players": byes})
        if nxt:
            next_hit.append({"owner": owner, "count": len(nxt), "players": nxt})

    def order(rows):
        return sorted(rows, key=lambda r: (-r["count"], r["owner"]))
    return {"teams": sorted(teams), "next_teams": sorted(next_teams),
            "starting": sorted(starting, key=lambda r: (r["owner"], r["player"])),
            "hardest_hit": order(hit), "next_hardest_hit": order(next_hit)}


def _bye_player(p):
    return f"{p['player']} ({p['pos']}, {p['pro_team']})" if p.get("pro_team") \
        else f"{p['player']} ({p['pos']})"


def bye_note(entry):
    """One team's bye line for a facts file — 'McMillan (WR, CAR), Kelce (TE, KC);
    STARTING (a zero unless swapped out): Rice (WR, KC)' — or None when nobody's off."""
    byes = (entry or {}).get("on_bye") or []
    if not byes:
        return None
    bench = [_bye_player(p) for p in byes if not p.get("starter")]
    start = [_bye_player(p) for p in byes if p.get("starter")]
    bits = [", ".join(bench)] if bench else []
    if start:
        bits.append("STARTING (a zero unless swapped out): " + ", ".join(start))
    return "; ".join(bits)


def bye_watch_lines(watch, week, *, this_week=True):
    """The facts-file 'Bye watch' section for bye_watch() output. `this_week=False`
    (recap: the week is over) skips the who's-off-now block and keeps only any
    starters who sat on bye plus next week's crunch. [] when there's no bye data."""
    w = watch or {}
    lines = []
    if this_week and w.get("teams"):
        lines.append(f"Bye watch — Week {week} (NFL teams off: {', '.join(w['teams'])}):")
        for r in w["hardest_hit"]:
            lines.append(f"- {r['owner']} ({r['count']}): "
                         + ", ".join(_bye_player(p) for p in r["players"]))
    if w.get("starting"):
        lines.append("- STARTING a player on bye (a zero unless swapped out): "
                     + "; ".join(f"{r['owner']} — {_bye_player(r)}" for r in w["starting"]))
    if w.get("next_teams"):
        if lines:
            lines.append("")
        lines.append(f"Next week's byes — Week {week + 1} "
                     f"(NFL teams off: {', '.join(w['next_teams'])}), most hit first:")
        for r in w["next_hardest_hit"]:
            lines.append(f"- {r['owner']} ({r['count']}): "
                         + ", ".join(_bye_player(p) for p in r["players"]))
    return lines


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
