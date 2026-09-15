#!/usr/bin/env python3
"""Prep a weekly *preview*: write the computed facts file for the upcoming week.

Companion to weekly_recap.py. Where the recap looks back at a complete week, the
preview looks forward at a week that hasn't finished. It reads the week's fixtures
plus each owner's résumé + last-season standing, the all-time head-to-head,
projected lineups, form and projected strength, and writes a lean facts file.

    python scripts/weekly_preview.py 2026 1

Then point your agent at agents/weekly-preview.md and ask it to write the week's
preview: it reads this facts file plus the season's prior editions from
docs/seasons/, and you paste its reply into the week page under "The Preview"
(which shows until the week is complete). Only works while the week is future or in
progress — a complete week gets a recap, not a preview.
"""

import argparse
import sys
from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, short_name_of,
                      load_week_rosters, load_projections)
from lib.weeks import week_state, _games_in_week
from lib.context import (standings_snapshot, recent_moves, league_bests,
                         week_roster_context, perceived_strength, team_form)
from weekly_recap import scaffold_page

ROOT = Path(__file__).resolve().parent.parent
AGENT_SPEC = ROOT / "agents" / "weekly-preview.md"
PROFILES_PATH = ROOT / "docs" / "_data" / "owner_profiles.yml"
RECORDS_PATH = ROOT / "docs" / "_data" / "records.yml"
PROMPT_DIR = ROOT / "recaps"


def _fmt_best(bf):
    if not bf:
        return "—"
    if bf.get("type") == "shiva":
        return f"Shiva ({', '.join(map(str, bf.get('years') or []))})"
    if bf.get("type") == "cochamp":
        return f"Co-champ ({', '.join(map(str, bf.get('years') or []))})"
    return bf.get("ordinal") or "—"


def _last_season_bit(prof):
    """Most-recent-season framing for stakes and story: 'reigning champ', 'reigning
    sacko', last year's finish, or a rookie flag for a first-timer (like a new
    league member). Returns None when there's nothing to say."""
    completed = [s for s in (prof.get("seasons") or []) if not s.get("in_progress")]
    if not completed:
        return "rookie — first season in the league"
    last = max(completed, key=lambda s: s.get("year", 0))
    tag, fin, yr = last.get("tag"), last.get("finish"), last.get("year")
    special = {"shiva": "REIGNING CHAMP", "sacko": "reigning sacko"}.get(tag)
    if special:
        return f"last year ({yr}): {fin} — {special}"
    return f"last year ({yr}): {fin}" if fin else None


def _owner_line(name, prof):
    if not prof:
        return f"{name}: no league history yet"
    r = prof["resume"]
    titles = r.get("titles", "0")
    base = (f"{name}: all-time {r['all_time']} ({r['win_pct']}), "
            f"{titles} title(s), best finish {_fmt_best(r.get('best_finish'))}")
    bit = _last_season_bit(prof)
    return f"{base}; {bit}" if bit else base


def _h2h_line(home_name, home_prof, away_fid, away_name):
    for h in (home_prof or {}).get("h2h", []):
        if h.get("opp_id") == away_fid:
            parts = (h["record"].split("-") + ["0", "0"])[:2]
            w, l = int(parts[0]), int(parts[1])
            verb = "leads" if w > l else "trails" if l > w else "is even with"
            return f"Head-to-head: {home_name} {verb} {away_name} {h['record']} all-time"
    return "Head-to-head: first meeting"


def _lineup_line(entry):
    """Projected starters, best first: 'Josh Allen (QB) 22.1, CMC (RB) 18.4, …'."""
    if not entry or not entry.get("starters"):
        return None
    starters = sorted(entry["starters"], key=lambda s: (s.get("proj") or 0), reverse=True)
    bits = [f"{s['player']} ({s['pos']}) {s['proj']:.1f}" for s in starters
            if s.get("proj") is not None]
    return ", ".join(bits) if bits else None


def _form_line(entry):
    """'W3, last week 148.2 (league high, +12.4 vs proj)' — the momentum hook."""
    if not entry:
        return None
    bits = [f"on a {entry['streak']} run" if entry.get("streak") else None]
    lp = entry.get("last_points")
    if lp is not None:
        extra = []
        if entry.get("last_high"):
            extra.append("league high")
        if entry.get("last_low"):
            extra.append("league low")
        vp = entry.get("last_vs_proj")
        if vp is not None:
            extra.append(f"{'+' if vp >= 0 else ''}{vp} vs proj")
        tail = f" ({', '.join(extra)})" if extra else ""
        bits.append(f"last week {lp:.1f}{tail}")
    bits = [b for b in bits if b]
    return "; ".join(bits) if bits else None


def data_block(year, week, games, season, franchises, profiles, ctx):
    teams = season.get("teams", {})
    rosters = ctx.get("rosters") or {}
    form = ctx.get("form") or {}

    def team_name(fid):
        return teams.get(fid) or short_name_of(fid, franchises)

    lines = [f"## Preview: {year}, Week {week}", "", "Upcoming matchups:"]
    for m in games:
        h, a = m["home"], m["away"]
        hn, an = short_name_of(h, franchises), short_name_of(a, franchises)
        lines.append(f"- {team_name(h)} ({hn}) vs {team_name(a)} ({an})")
        if m.get("home_proj") is not None and m.get("away_proj") is not None:
            lines.append(f"    ESPN projection: {team_name(h)} {m['home_proj']:.1f} "
                         f"– {team_name(a)} {m['away_proj']:.1f}")
        lines.append(f"    {_owner_line(hn, profiles.get(h))}")
        lines.append(f"    {_owner_line(an, profiles.get(a))}")
        lines.append(f"    {_h2h_line(hn, profiles.get(h), a, an)}")
        for fid, who in ((h, hn), (a, an)):
            lu = _lineup_line(rosters.get(fid))
            if lu:
                lines.append(f"    {who}'s projected starters: {lu}")
        for fid, who in ((h, hn), (a, an)):
            fl = _form_line(form.get(fid))
            if fl:
                lines.append(f"    {who}'s form: {fl}")

    strength = ctx.get("strength") or []
    if strength:
        lines += ["", "Projected strength this week (starter projections, best "
                  "first — the 'team to beat' on paper):"]
        for s in strength:
            lines.append(f"- {s['rank']}. {s['owner']} — {s['proj_total']:.1f} projected")

    standings = ctx.get("standings") or []
    if standings:
        lines += ["", "Standings (entering this week):"]
        for r in standings:
            pf = f", {r['pf']:.1f} PF" if r.get("pf") is not None else ""
            lines.append(f"- {r['rank']}. {r['owner']} ({r['team']}) {r['record']}{pf}")

    moves = ctx.get("moves") or {}
    if moves.get("trades") or moves.get("adds"):
        lines += ["", "Recent moves:"]
        for t in moves.get("trades", []):
            lines.append(f"- Trade (Wk {t['week']}): {t['detail']}")
        for ad in moves.get("adds", []):
            lines.append(f"- {ad['owner']} added {ad['player']} ({ad['kind']}, Wk {ad['week']})")

    bests = ctx.get("bests") or []
    if bests:
        lines += ["", "League bests (all-time, for reference):"]
        for b in bests:
            yr = f", {b['season']}" if b.get("season") else ""
            lines.append(f"- {b['category']}: {b['value']} — {b['holder']}{yr}")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Prep a weekly preview (prompt for upcoming matchups).")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season file for {args.year}.")

    state = week_state(season, args.week)
    if state == "complete":
        sys.exit(f"{args.year} week {args.week} is complete — write a recap "
                 f"(weekly_recap.py), not a preview.")
    games = _games_in_week(season, args.week)
    if not games:
        sys.exit(f"No matchups known for {args.year} week {args.week} yet — "
                 f"import the schedule first.")

    profiles = yaml.safe_load(PROFILES_PATH.read_text()) if PROFILES_PATH.exists() else {}
    records = (yaml.safe_load(RECORDS_PATH.read_text()) or {}).get("records", []) if RECORDS_PATH.exists() else []
    scaffold_page(args.year, args.week)   # ensure the page exists

    # Per-player projections from the roster snapshot the importer persisted for
    # this week (data/rosters/<year>-week-<nn>.yml). Read from disk — no live fetch.
    week_rosters = load_week_rosters(args.year, args.week, franchises)
    rosters = week_roster_context(week_rosters, want_actual=False) if week_rosters else None
    projections = load_projections(args.year, franchises)
    ctx = {
        "rosters": rosters,
        "strength": perceived_strength(rosters, franchises) if rosters else [],
        "form": team_form(season, franchises, args.week, projections),
        "standings": standings_snapshot(season, franchises),
        "moves": recent_moves(season, franchises, max(0, args.week - 2), args.week - 1),
        "bests": league_bests(records),
    }
    if not rosters:
        print("NOTE: no roster snapshot for this week (data/rosters/"
              f"{args.year}-week-{args.week:02d}.yml missing) — facts omit projected "
              "lineups. Re-run the importer for this week.", file=sys.stderr)

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    facts_path = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.preview.data.md"
    facts_path.write_text(
        data_block(args.year, args.week, games, season, franchises, profiles, ctx),
        encoding="utf-8")

    spec_rel = AGENT_SPEC.relative_to(ROOT)
    print(f"Week {args.week}, {args.year} ({state}): {len(games)} matchup(s).", file=sys.stderr)
    print(f"  facts: {facts_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"\nNext: point your agent at {spec_rel} and ask it to write the Week "
          f"{args.week} preview. It reads the facts file above plus the season's prior "
          "editions from docs/seasons/. Paste its reply under \"The Preview\" on the "
          "page, then run: python scripts/build.py", file=sys.stderr)


if __name__ == "__main__":
    main()
