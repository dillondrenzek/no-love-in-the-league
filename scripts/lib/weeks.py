"""Per-week matchup summaries for the weekly recap pages.

A single week's games become a scoreboard (each matchup with scores and the
winner) plus a few computed highlights (top/low score, biggest blowout, closest
call). This is the factual layer under /seasons/<year>/week-<n>/ — the AI recap
is written on top of it by a human running the agent spec (see agents/).
"""

from .data import short_name_of


def week_matchups(season, week):
    """All of a season's games in `week` (regular season + any playoff)."""
    return [m for m in (season.get("matchups") or []) if m.get("week") == week]


def _side(season, franchises, fid, score, opp_fid, opp_score):
    teams = season.get("teams", {})
    return {
        "owner_id": fid if fid in franchises else None,
        "owner_name": short_name_of(fid, franchises),
        "team": teams.get(fid) or short_name_of(fid, franchises),
        "score": round(float(score), 2),
        "opp_owner_id": opp_fid if opp_fid in franchises else None,
        "opp_owner_name": short_name_of(opp_fid, franchises),
        "opp_team": (season.get("teams", {}).get(opp_fid)
                     or short_name_of(opp_fid, franchises)),
        "opp_score": round(float(opp_score), 2),
    }


def week_summary(season, week, franchises):
    """{'week', 'played', 'scoreboard', 'highlights'} for one week.

    scoreboard: one row per game with both teams, scores and the winner id
    (None on a tie). highlights: computed superlatives, each a small card
    ({key, label, value, sub, owner_id, owner_name, team}). Empty when no games
    were played that week.
    """
    games = week_matchups(season, week)
    scoreboard, sides = [], []
    for m in games:
        h, a = m["home"], m["away"]
        hs, as_ = m["home_score"], m["away_score"]
        winner = h if hs > as_ else a if as_ > hs else None
        teams = season.get("teams", {})
        scoreboard.append({
            "home_id": h if h in franchises else None,
            "home_team": teams.get(h) or short_name_of(h, franchises),
            "home_owner": short_name_of(h, franchises),
            "home_score": round(float(hs), 2),
            "away_id": a if a in franchises else None,
            "away_team": teams.get(a) or short_name_of(a, franchises),
            "away_owner": short_name_of(a, franchises),
            "away_score": round(float(as_), 2),
            "winner_id": winner if winner in franchises else None,
            "tie": winner is None,
            "playoff": bool(m.get("playoff")),
            "margin": round(abs(hs - as_), 2),
        })
        sides.append(_side(season, franchises, h, hs, a, as_))
        sides.append(_side(season, franchises, a, as_, h, hs))

    if not sides:
        return {"week": week, "played": False, "scoreboard": [], "highlights": []}

    top = max(sides, key=lambda s: s["score"])
    low = min(sides, key=lambda s: s["score"])
    blowout = max(scoreboard, key=lambda g: g["margin"])
    closest = min(scoreboard, key=lambda g: g["margin"])

    def score_pair(g):
        hi, lo = sorted((g["home_score"], g["away_score"]), reverse=True)
        return f"{hi:.1f}–{lo:.1f}"

    def game_side(g, which):
        return {"owner_id": g[f"{which}_id"], "owner_name": g[f"{which}_owner"],
                "team": g[f"{which}_team"]}

    win_side = "home" if blowout["winner_id"] == blowout["home_id"] else "away"
    lose_side = "away" if win_side == "home" else "home"

    highlights = [
        {"key": "top", "label": "Top Score", "value": f"{top['score']:.2f}",
         "sub": f"vs {top['opp_team']}", "owner_id": top["owner_id"],
         "owner_name": top["owner_name"], "team": top["team"]},
        {"key": "low", "label": "Low Score", "value": f"{low['score']:.2f}",
         "sub": f"vs {low['opp_team']}", "owner_id": low["owner_id"],
         "owner_name": low["owner_name"], "team": low["team"]},
        {"key": "blowout", "label": "Biggest Blowout", "value": f"+{blowout['margin']:.2f}",
         "sub": f"{score_pair(blowout)} over {game_side(blowout, lose_side)['team']}",
         "owner_id": game_side(blowout, win_side)["owner_id"],
         "owner_name": game_side(blowout, win_side)["owner_name"],
         "team": game_side(blowout, win_side)["team"]},
        {"key": "closest", "label": "Closest Call", "value": f"{closest['margin']:.2f}",
         "sub": score_pair(closest) if not closest["tie"] else "tie",
         "owner_id": None, "owner_name": None, "team": None},
    ]
    return {"week": week, "played": True, "scoreboard": scoreboard, "highlights": highlights}


def played_weeks(season):
    """Sorted list of week numbers that have at least one game."""
    weeks = {m.get("week") for m in (season.get("matchups") or []) if m.get("week")}
    return sorted(weeks)
