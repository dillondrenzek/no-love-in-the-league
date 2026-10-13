"""NFL game windows: when each player's points landed during a fantasy week.

A fantasy week isn't one event — it's Thursday night, (sometimes) an
international morning game, the Sunday early and late slates, Sunday night, and
Monday night. The order matters to the story: a stud who went off Thursday to
put a manager up early, or a Monday-night player who flipped the matchup at the
last minute. This module groups a week's NFL games into those windows from their
kickoff times, then splits each fantasy team's starters across them.

Kickoffs come from data/nfl_schedule/<year>.yml (written by the importer from
ESPN's public pro schedule). Pure functions over plain dicts/lists — no I/O, no
network — so the bucketing and lead-tracking are easy to test.
"""

import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Sunday's two afternoon slates are crowded; every other window is a standalone
# (or near-standalone) game whose players are worth naming one by one.
CROWDED = {"Sunday early", "Sunday late"}


def parse_kickoff(value):
    """An ISO-8601 kickoff ('2026-10-09T00:15:00Z') -> aware UTC datetime."""
    if isinstance(value, datetime.datetime):
        dt = value
    else:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def window_label(kickoff):
    """Name the window a kickoff falls in, judged on the US Eastern clock:
    'Thursday night', 'Sunday morning (international)', 'Sunday early', 'Sunday
    late', 'Sunday night', 'Monday night', or the weekday for anything else
    (Thanksgiving afternoon, Black Friday, a late-season Saturday, Christmas)."""
    t = parse_kickoff(kickoff).astimezone(ET)
    day, hour = t.strftime("%A"), t.hour
    if day == "Sunday":
        if hour < 12:
            return "Sunday morning (international)"
        if hour < 15:
            return "Sunday early"
        if hour < 19:
            return "Sunday late"
        return "Sunday night"
    if day in ("Thursday", "Monday"):
        return f"{day} night" if hour >= 19 else f"{day} afternoon"
    return day


def fmt_kickoff(kickoff):
    """'Thu 8:15 PM ET' — a kickoff on the Eastern clock, for the facts file."""
    t = parse_kickoff(kickoff).astimezone(ET)
    return f"{t.strftime('%a')} {t.strftime('%I:%M %p').lstrip('0')} ET"


def week_windows(games, week):
    """The week's NFL windows in kickoff order:

        [{"label", "start" (first kickoff, aware datetime),
          "games": [{away, home, kickoff}], "teams": {abbrev, ...}}]

    `games` is the schedule file's list ({week, kickoff, away, home}). Teams on
    bye simply don't appear. [] when the week has no games on file."""
    by_label = {}
    for g in games or []:
        if g.get("week") != week or not g.get("kickoff"):
            continue
        ko = parse_kickoff(g["kickoff"])
        w = by_label.setdefault(window_label(ko), {"label": window_label(ko),
                                                   "start": ko, "games": [],
                                                   "teams": set()})
        w["start"] = min(w["start"], ko)
        w["games"].append({"away": g.get("away"), "home": g.get("home"), "kickoff": ko})
        w["teams"].update(t for t in (g.get("away"), g.get("home")) if t)
    out = sorted(by_label.values(), key=lambda w: w["start"])
    for w in out:
        w["games"].sort(key=lambda g: g["kickoff"])
    return out


def team_windows(windows):
    """{NFL abbrev: window label} for the week."""
    return {t: w["label"] for w in windows for t in w["teams"]}


def lineup_by_window(starters, windows, *, value="actual"):
    """Split one fantasy team's starters across the week's windows, in order:

        [{"window", "points", "players": [{player, pos, points}]}]

    `value` is "actual" (recap: what they scored) or "proj" (preview: what
    they're expected to). Players best-first within a window. Only windows where
    this team had a starter appear. A starter with no NFL team on file, or whose
    team isn't playing (a bye), lands in no window — his zero is the schedule."""
    where = team_windows(windows)
    buckets = {w["label"]: [] for w in windows}
    for s in starters or []:
        label = where.get((s.get("pro_team") or "").upper())
        if label is None:
            continue
        pts = s.get(value)
        buckets[label].append({"player": s.get("player"), "pos": s.get("pos"),
                               "points": float(pts) if isinstance(pts, (int, float)) else 0.0})
    out = []
    for w in windows:
        players = sorted(buckets[w["label"]], key=lambda p: -p["points"])
        if players:
            out.append({"window": w["label"],
                        "points": round(sum(p["points"] for p in players), 1),
                        "players": players})
    return out


def matchup_flow(home_by_window, away_by_window, windows, winner=None):
    """How a matchup's score built up across the week, from each side's
    lineup_by_window output:

        {"checkpoints": [{window, home_pts, away_pts, home_run, away_run}],
         "winner": "home" | "away" | None,   # as passed in
         "lead_changes": int,        # times the leader flipped between checkpoints
         "took_lead_for_good": label or None,  # window the winner went ahead to stay
         "wire_to_wire": bool,       # winner led after every checkpoint
         "comeback": bool,           # winner trailed going into the last window
         "max_deficit": {window, points} or None,  # winner's deepest hole, overcome
         "entering_last": {window, home_run, away_run} or None}

    A checkpoint is a window where either side had a starter playing. `winner`
    is "home", "away" or None (tie / unknown) and comes from the scoreboard, so a
    rounding wobble in the summed player points can't flip the result."""
    hmap = {r["window"]: r["points"] for r in home_by_window or []}
    amap = {r["window"]: r["points"] for r in away_by_window or []}
    checkpoints, hr, ar = [], 0.0, 0.0
    for w in windows:
        label = w["label"]
        if label not in hmap and label not in amap:
            continue
        hp, ap = hmap.get(label, 0.0), amap.get(label, 0.0)
        hr, ar = round(hr + hp, 1), round(ar + ap, 1)
        checkpoints.append({"window": label, "home_pts": hp, "away_pts": ap,
                            "home_run": hr, "away_run": ar})

    def leader(c):
        if c["home_run"] > c["away_run"]:
            return "home"
        if c["away_run"] > c["home_run"]:
            return "away"
        return None

    leaders = [leader(c) for c in checkpoints]
    seen = [x for x in leaders if x]
    lead_changes = sum(1 for a, b in zip(seen, seen[1:]) if a != b)

    took, wire, comeback, max_deficit = None, False, False, None
    if winner in ("home", "away") and checkpoints:
        # Walk back from the end to the first checkpoint of the winner's final run.
        i = len(leaders)
        while i > 0 and leaders[i - 1] == winner:
            i -= 1
        if i < len(leaders):
            took = checkpoints[i]["window"]
            wire = i == 0
        comeback = len(leaders) >= 2 and leaders[-2] != winner
        sign = 1 if winner == "home" else -1
        worst = min(checkpoints, key=lambda c: sign * (c["home_run"] - c["away_run"]))
        gap = round(-sign * (worst["home_run"] - worst["away_run"]), 1)
        if gap > 0:
            max_deficit = {"window": worst["window"], "points": gap}
    entering_last = None
    if len(checkpoints) >= 2:
        c = checkpoints[-2]
        entering_last = {"window": checkpoints[-1]["window"],
                         "home_run": c["home_run"], "away_run": c["away_run"]}
    return {"checkpoints": checkpoints, "winner": winner, "lead_changes": lead_changes,
            "took_lead_for_good": took, "wire_to_wire": wire, "comeback": comeback,
            "max_deficit": max_deficit, "entering_last": entering_last}


def spotlight(rosters_by_window, windows, owner_of):
    """League-wide view of the standalone windows (everything but the crowded
    Sunday afternoon slates): every fantasy starter who played in each, best first.

        [{"window", "games": [...], "players": [{owner, player, pos, points}]}]

    `rosters_by_window` is {fid: lineup_by_window(...)}; `owner_of(fid)` names the
    manager. This is where the Thursday-night opener and the Monday-night closer
    live. Windows with no rostered starter are dropped."""
    out = []
    for w in windows:
        if w["label"] in CROWDED:
            continue
        players = []
        for fid, rows in (rosters_by_window or {}).items():
            for r in rows:
                if r["window"] == w["label"]:
                    players += [dict(p, owner=owner_of(fid)) for p in r["players"]]
        if players:
            players.sort(key=lambda p: (-p["points"], p["owner"], p["player"]))
            out.append({"window": w["label"], "games": w["games"], "players": players})
    return out


def _game_str(g):
    return f"{g['away']} @ {g['home']} ({fmt_kickoff(g['kickoff'])})"


def _players_str(players, limit=None):
    shown = players if limit is None else players[:limit]
    return ", ".join(f"{p['player']} {p['points']:.1f}" for p in shown)


def flow_lines(flow, home_who, away_who, home_rows, away_rows):
    """Facts-file lines for one matchup's scoring order (recap). Each checkpoint
    shows the running score and who scored in that window — every player in a
    standalone window, the top two per side in a crowded Sunday slate — then a
    line on when the winner pulled ahead for good."""
    if not flow or not flow["checkpoints"]:
        return []
    hp = {r["window"]: r["players"] for r in home_rows or []}
    ap = {r["window"]: r["players"] for r in away_rows or []}
    lines = [f"Scoring order (running score {home_who}–{away_who} after each window):"]
    for c in flow["checkpoints"]:
        label, limit = c["window"], (2 if c["window"] in CROWDED else None)
        who = []
        for name, rows, pts in ((home_who, hp, c["home_pts"]), (away_who, ap, c["away_pts"])):
            if rows.get(label):
                top = "top " if limit else ""
                who.append(f"{name} +{pts:.1f} ({top}{_players_str(rows[label], limit)})")
        lines.append(f"  {label}: {c['home_run']:.1f}–{c['away_run']:.1f} — "
                     + "; ".join(who))
    winner_side = flow.get("winner")
    winner = {"home": home_who, "away": away_who}.get(winner_side)
    if flow["took_lead_for_good"] and winner:
        bits = []
        if flow["wire_to_wire"]:
            bits.append(f"{winner} led after every window (wire to wire)")
        else:
            bits.append(f"{winner} took the lead for good in the {flow['took_lead_for_good']} window")
        if flow["comeback"] and flow["entering_last"]:
            e = flow["entering_last"]
            run = (e["home_run"], e["away_run"]) if winner_side == "home" else (e["away_run"], e["home_run"])
            bits.append(f"COMEBACK — trailed {run[0]:.1f}–{run[1]:.1f} going into "
                        f"{e['window']} and won it there")
        if flow["max_deficit"]:
            d = flow["max_deficit"]
            bits.append(f"{winner} was down {d['points']:.1f} after {d['window']} at worst")
        if flow["lead_changes"]:
            bits.append(f"{flow['lead_changes']} lead change(s)")
        lines.append("  " + "; ".join(bits) + ".")
    elif flow["entering_last"]:
        e = flow["entering_last"]
        lines.append(f"  Going into {e['window']}: {e['home_run']:.1f}–{e['away_run']:.1f}.")
    return lines


def spotlight_lines(spot):
    """Facts-file bullets listing every starter in each standalone window, with
    the game(s) and kickoff. The caller supplies the section heading."""
    lines = []
    for s in spot or []:
        games = "; ".join(_game_str(g) for g in s["games"])
        lines.append(f"- {s['window']} — {games}:")
        lines.append("    " + ", ".join(f"{p['player']} ({p['owner']}) {p['points']:.1f}"
                                        for p in s["players"]))
    return lines


def plan_line(rows):
    """Preview: one team's lineup split by window, e.g. 'Thursday night: Bucky
    Irving 14.0 · Sunday early 5 starters (61.2 proj) · Monday night: Puka Nacua
    18.1'. Standalone windows name their players; crowded slates give a count."""
    bits = []
    for r in rows or []:
        if r["window"] in CROWDED:
            n = len(r["players"])
            bits.append(f"{r['window']} {n} starter{'s' if n != 1 else ''} ({r['points']:.1f} proj)")
        else:
            bits.append(f"{r['window']}: {_players_str(r['players'])}")
    return " · ".join(bits) if bits else None
