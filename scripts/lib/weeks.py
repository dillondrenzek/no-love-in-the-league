"""Per-week matchup summaries for the weekly pages at /seasons/<year>/week-<n>/.

A week has a state derived from its games:
  - future       — no game has a score yet (or the fixtures aren't known); the
                   scoreboard lists the matchups without scores.
  - in_progress  — some games have live scores but not every game is final; the
                   scoreboard shows live scores. No highlights yet.
  - complete     — every game is final; the scoreboard shows finals + a winner,
                   and the computed highlights (top/low/blowout/closest) appear.

Highlights are a Complete-week artifact; the AI recap (written by a human on the
page) is too. Season stats only fold in a complete week — see lib.data.
"""

from .data import short_name_of, game_final, game_has_score, complete_weeks


def _games_in_week(season, week):
    return [m for m in (season.get("matchups") or []) if m.get("week") == week]


def week_state(season, week):
    """'future' | 'in_progress' | 'complete' for one week."""
    games = _games_in_week(season, week)
    if games and all(game_final(g) for g in games):
        return "complete"
    if any(game_has_score(g) for g in games):
        return "in_progress"
    return "future"


def _scoreboard(season, franchises, games):
    teams = season.get("teams", {})
    board = []
    for m in games:
        h, a = m["home"], m["away"]
        scored = game_has_score(m)
        final = game_final(m)
        hs, as_ = m.get("home_score"), m.get("away_score")
        entry = {
            "home_id": h if h in franchises else None,
            "home_team": teams.get(h) or short_name_of(h, franchises),
            "home_owner": short_name_of(h, franchises),
            "away_id": a if a in franchises else None,
            "away_team": teams.get(a) or short_name_of(a, franchises),
            "away_owner": short_name_of(a, franchises),
            "scored": scored,
            "final": final,
            "live": scored and not final,
            "playoff": bool(m.get("playoff")),
        }
        if scored:
            entry["home_score"] = round(float(hs), 2)
            entry["away_score"] = round(float(as_), 2)
            winner = None
            if final:
                winner = h if hs > as_ else a if as_ > hs else None
            entry["winner_id"] = winner if winner in franchises else None
            entry["tie"] = final and winner is None
            entry["margin"] = round(abs(hs - as_), 2)
        board.append(entry)
    return board


def _side(season, franchises, fid, score, opp_fid):
    teams = season.get("teams", {})
    return {
        "owner_id": fid if fid in franchises else None,
        "owner_name": short_name_of(fid, franchises),
        "team": teams.get(fid) or short_name_of(fid, franchises),
        "score": round(float(score), 2),
        "opp_team": teams.get(opp_fid) or short_name_of(opp_fid, franchises),
    }


def _highlights(season, franchises, games):
    """Top/low score, biggest blowout, closest call — computed over a complete
    week's final games."""
    sides, board = [], []
    for m in games:
        h, a = m["home"], m["away"]
        hs, as_ = m["home_score"], m["away_score"]
        winner = h if hs > as_ else a if as_ > hs else None
        board.append({"home": h, "away": a, "home_score": hs, "away_score": as_,
                      "home_team": season.get("teams", {}).get(h) or short_name_of(h, franchises),
                      "away_team": season.get("teams", {}).get(a) or short_name_of(a, franchises),
                      "winner": winner, "margin": round(abs(hs - as_), 2)})
        sides.append(_side(season, franchises, h, hs, a))
        sides.append(_side(season, franchises, a, as_, h))
    if not sides:
        return []
    top = max(sides, key=lambda s: s["score"])
    low = min(sides, key=lambda s: s["score"])
    blowout = max(board, key=lambda g: g["margin"])
    closest = min(board, key=lambda g: g["margin"])

    def score_pair(g):
        hi, lo = sorted((g["home_score"], g["away_score"]), reverse=True)
        return f"{hi:.1f}–{lo:.1f}"

    win_team = blowout["home_team"] if blowout["winner"] == blowout["home"] else blowout["away_team"]
    lose_team = blowout["away_team"] if blowout["winner"] == blowout["home"] else blowout["home_team"]
    win_fid = blowout["winner"]
    return [
        {"key": "top", "label": "Top Score", "value": f"{top['score']:.2f}",
         "sub": f"vs {top['opp_team']}", "owner_id": top["owner_id"],
         "owner_name": top["owner_name"], "team": top["team"]},
        {"key": "low", "label": "Low Score", "value": f"{low['score']:.2f}",
         "sub": f"vs {low['opp_team']}", "owner_id": low["owner_id"],
         "owner_name": low["owner_name"], "team": low["team"]},
        {"key": "blowout", "label": "Biggest Blowout", "value": f"+{blowout['margin']:.2f}",
         "sub": f"{score_pair(blowout)} over {lose_team}",
         "owner_id": win_fid if win_fid in franchises else None,
         "owner_name": short_name_of(win_fid, franchises) if win_fid else None, "team": win_team},
        {"key": "closest", "label": "Closest Call", "value": f"{closest['margin']:.2f}",
         "sub": score_pair(closest), "owner_id": None, "owner_name": None, "team": None},
    ]


def week_summary(season, week, franchises):
    """{'week', 'state', 'scoreboard', 'highlights'} for one week. Highlights are
    populated only for a complete week."""
    games = _games_in_week(season, week)
    state = week_state(season, week)
    highlights = _highlights(season, franchises, games) if state == "complete" else []
    return {"week": week, "state": state,
            "scoreboard": _scoreboard(season, franchises, games),
            "highlights": highlights}


def played_weeks(season):
    """Sorted week numbers that are complete (every game final)."""
    return sorted(w for w in complete_weeks(season) if w)
