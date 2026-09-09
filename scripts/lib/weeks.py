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

import datetime

try:
    from zoneinfo import ZoneInfo
    _PACIFIC = ZoneInfo("America/Los_Angeles")   # auto PST/PDT by date
except Exception:                                # pragma: no cover - missing tzdata
    _PACIFIC = None

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
        if m.get("home_proj") is not None:
            entry["home_proj"] = round(float(m["home_proj"]), 1)
        if m.get("away_proj") is not None:
            entry["away_proj"] = round(float(m["away_proj"]), 1)
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


def _projection_report(season, week, franchises, week_proj):
    """One row per regular-season matchup that has a pre-game projection for both
    teams: the projected line (favorite + spread) and, once the game is final,
    whether the projection called the winner ('hit'/'miss'/'push').

    `week_proj` is {fid: projected} from that week's snapshot (see
    lib.data.load_projections). Empty/absent -> no rows. Built so a parallel
    prediction source (e.g. Claude's picks) can render the same way later.
    """
    if not week_proj:
        return []
    teams = season.get("teams", {})
    rows = []
    for m in _games_in_week(season, week):
        if m.get("playoff"):
            continue
        h, a = m["home"], m["away"]
        hp, ap = week_proj.get(h), week_proj.get(a)
        if hp is None or ap is None:
            continue
        if hp == ap:
            fav = dog = None
            fav_p, dog_p = hp, ap
        elif hp > ap:
            fav, dog, fav_p, dog_p = h, a, hp, ap
        else:
            fav, dog, fav_p, dog_p = a, h, ap, hp

        def name(fid):
            return teams.get(fid) or short_name_of(fid, franchises)

        row = {
            "home_id": h if h in franchises else None,
            "away_id": a if a in franchises else None,
            "home_team": name(h), "away_team": name(a),
            "home_proj": hp, "away_proj": ap,
            "pickem": fav is None,
            "fav_id": fav if (fav in franchises) else None,
            "fav_team": name(fav) if fav else None,
            "dog_team": name(dog) if dog else None,
            "fav_proj": fav_p, "dog_proj": dog_p,
            "spread": round(abs(hp - ap), 1),
            "decided": False, "result": None,
        }
        if game_final(m) and game_has_score(m):
            hs, as_ = m.get("home_score"), m.get("away_score")
            winner = h if hs > as_ else a if as_ > hs else None
            row["decided"] = True
            row["winner_id"] = winner if winner in franchises else None
            if winner is None:
                row["result"] = "push"          # actual tie — no call to grade
            elif fav is None:
                row["result"] = None            # projected pick'em — no favorite
            else:
                row["result"] = "hit" if winner == fav else "miss"
        rows.append(row)
    return rows


def _fmt_captured(iso):
    """A short, platform-safe 'Sep 9, 2026 · 12:14 AM PDT' from an ISO timestamp.

    The snapshot time is UTC; it's shown in Pacific, with PST/PDT resolved
    automatically from the date (so it switches correctly across the season).
    Falls back to UTC only if the tz database isn't available."""
    if not iso:
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    tz_abbr = "UTC"
    if _PACIFIC is not None:
        dt = dt.astimezone(_PACIFIC)
        tz_abbr = dt.strftime("%Z") or "PT"          # PST / PDT
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} · {hour}:{dt.minute:02d} {ampm} {tz_abbr}"


def week_summary(season, week, franchises, week_proj=None):
    """{'week', 'state', 'scoreboard', 'highlights', 'projections', 'projected_at'}
    for one week. Highlights are populated only for a complete week; projections
    come from the week's snapshot (see _projection_report) and are empty when none
    was taken. `week_proj` is that week's load_projections entry
    ({'captured_at', 'proj'}) or None."""
    games = _games_in_week(season, week)
    state = week_state(season, week)
    highlights = _highlights(season, franchises, games) if state == "complete" else []
    proj_map = (week_proj or {}).get("proj")
    rows = _projection_report(season, week, franchises, proj_map)
    return {"week": week, "state": state,
            "scoreboard": _scoreboard(season, franchises, games),
            "highlights": highlights,
            "projections": rows,
            "projected_at": _fmt_captured((week_proj or {}).get("captured_at")) if rows else None}


def played_weeks(season):
    """Sorted week numbers that are complete (every game final)."""
    return sorted(w for w in complete_weeks(season) if w)
