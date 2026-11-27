"""Playoff-path checklists: a team's list of results it needs to make the
playoffs (hand-written in data/playoff_paths.yml), checked against the scores.

Each condition is one of:

    {"label", "win": fid, "week": n}                  that team wins that week
    {"label", "team": fid, "weeks": [..], "max_wins": n}
                                                      that team wins no more than
                                                      n of those games (tie = half)

and comes back with a `status`: "done" (decided in our favor), "dead" (decided
against), or "open" (still to be played). An open condition also gets a
`lean` while one of its games is in progress: "ahead" if the current scores
would check the box, "behind" if they'd kill it, None otherwise.
"""

from .data import game_final


def _games(season, fid, weeks):
    """{week: matchup} for the team's regular-season games in those weeks."""
    reg = season.get("weeks_in_regular_season") or 14
    out = {}
    for m in season.get("matchups") or []:
        w = m.get("week") or 0
        if w in weeks and w <= reg and not m.get("playoff") and fid in (m["home"], m["away"]):
            out[w] = m
    return out


def _result(m, fid):
    """(state, wins) for one game from the team's side: state is "final", "live"
    or "future"; wins is 1 / 0.5 / 0 from the current scores (None if unplayed)."""
    hs, as_ = m.get("home_score"), m.get("away_score")
    if hs is None or as_ is None:
        return "future", None
    mine, theirs = (hs, as_) if m["home"] == fid else (as_, hs)
    wins = 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0
    return ("final" if game_final(m) else "live"), wins


def _max_wins_status(results, cap):
    """Status + lean for "wins no more than `cap` of these games"."""
    final = sum(w for s, w in results if s == "final")
    undecided = sum(1 for s, _ in results if s != "final")
    if final > cap:
        return "dead", None
    if final + undecided <= cap:
        return "done", None
    if not any(s == "live" for s, _ in results):
        return "open", None
    # If the live games ended as they stand now:
    now = final + sum(w for s, w in results if s == "live")
    left = sum(1 for s, _ in results if s == "future")
    if now > cap:
        return "open", "behind"
    if now + left <= cap:
        return "open", "ahead"
    return "open", None


def check_condition(season, c):
    """The condition with its status and lean filled in."""
    out = {"label": c.get("label") or "", "status": "open", "lean": None}
    if c.get("win"):
        g = _games(season, c["win"], [c["week"]]).get(c["week"])
        if g is None:
            return out
        state, wins = _result(g, c["win"])
        if state == "final":
            out["status"] = "done" if wins == 1.0 else "dead"
        elif state == "live":
            out["lean"] = "ahead" if wins == 1.0 else "behind"
        return out
    weeks = list(c.get("weeks") or [])
    results = [_result(m, c["team"]) for m in _games(season, c["team"], weeks).values()]
    out["status"], out["lean"] = _max_wins_status(results, c.get("max_wins", 0))
    return out


def playoff_path(season, path):
    """One checklist, checked: {fid, title, nav, intro, footnote, status, done,
    total, conditions}. Overall `status` is "in" when every box is checked, "dead" as soon
    as any box is dead, otherwise "alive"."""
    conds = [check_condition(season, c) for c in path.get("conditions") or []]
    done = sum(1 for c in conds if c["status"] == "done")
    if any(c["status"] == "dead" for c in conds):
        status = "dead"
    elif conds and done == len(conds):
        status = "in"
    else:
        status = "alive"
    return {"fid": path.get("fid"), "title": path.get("title") or "",
            "nav": path.get("nav") or path.get("title") or "",
            "intro": path.get("intro") or "", "footnote": path.get("footnote") or "",
            "status": status, "done": done, "total": len(conds), "conditions": conds}


def season_paths(season, paths_by_year):
    """The season's checklists (data/playoff_paths.yml), checked. [] when none."""
    return [playoff_path(season, p) for p in (paths_by_year or {}).get(season["season"]) or []]
