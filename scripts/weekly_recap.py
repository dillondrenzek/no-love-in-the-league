#!/usr/bin/env python3
"""Prep a week's recap: scaffold the page and write the computed facts file.

Weekly workflow for the live season (agentic):

    1. Import the week's games:   ./scripts/import_manager.sh   (or import_espn.py)
    2. Prep the recap facts:      python scripts/weekly_recap.py 2026 1
    3. Point your agent at agents/weekly-recap.md and ask it to write the Week 1
       recap. The agent reads the facts file this script wrote plus the season's
       prior editions straight from docs/seasons/, then you paste its reply into
       docs/seasons/2026/week-1.md (below "The Recap").
    4. Rebuild:                   python scripts/build.py

Running early (right after the last game, before ESPN flips the week to complete):
add `--finalize`. ESPN can lag hours in stamping the winners after the final
whistle, which would otherwise block the recap and under-count records. `--finalize`
marks the week's now-over games final locally (only if every game has a score), so
the recap can be written and shown immediately. It's safe: a later import never
un-finishes a game (import_espn.preserve_final_matchups), so ESPN catching up just
confirms it. One caveat — a stat correction in the day(s) after can nudge a score;
the daily rebuild refreshes the scoreboard numbers, but the hand-written prose is a
snapshot, so eyeball a very close game before it's locked in.

This script owns only the part that must be *computed and correct*: it reads the
already-imported matchups (the "hit the API" part is the importer), isolates this
week's scoreboard + highlights + league context (standings, moves, form/streaks,
records), scaffolds the week page if it doesn't exist, and writes a lean, bounded
facts file. The narrative — prior previews/recaps, this week's preview to grade —
is left in the repo for the agent to read on demand, so the prompt stays small and
the season's story is never re-pasted wholesale. It never calls an LLM itself.
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, load_week_rosters,
                      load_projections, load_nfl_schedule, short_name_of)
from lib.weeks import week_summary
from lib.context import (standings_snapshot, recent_moves, league_bests,
                         week_roster_context, team_form, week_superlatives,
                         bye_watch, bye_watch_lines, pregame_line, renamed_teams,
                         h2h_record, swing_players, decisive_bench_swap)
from lib.power import week_power_rankings
from lib.nfl_schedule import (week_windows, lineup_by_window, matchup_flow,
                              flow_lines, spotlight, spotlight_lines)

ROOT = Path(__file__).resolve().parent.parent
SEASONS_DIR = ROOT / "data" / "seasons"
SEASON_PAGE_DIR = ROOT / "docs" / "seasons"
AGENT_SPEC = ROOT / "agents" / "weekly-recap.md"
RECORDS_PATH = ROOT / "docs" / "_data" / "records.yml"
PROFILES_PATH = ROOT / "docs" / "_data" / "owner_profiles.yml"
ODDS_PATH = ROOT / "docs" / "_data" / "odds.yml"
PROMPT_DIR = ROOT / "recaps"
FIRST_SEASON = 2014

PAGE_TEMPLATE = """---
layout: page
title: Week %%WEEK%% · %%YEAR%%
permalink: /seasons/%%YEAR%%/week-%%WEEK%%/
season_year: %%YEAR%%
season_no: %%NO%%
week: %%WEEK%%
---
{% assign wk = site.data.weeks["%%YEAR%%-%%WEEK%%"] %}
{% include sections/week_detail.html wk=wk %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Prep the facts with:
     python scripts/weekly_recap.py %%YEAR%% %%WEEK%%
     then have your agent (agents/weekly-recap.md) write it.
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete, and sits above the preview. -->

_Recap coming soon._
{% endif %}

<h2>The Preview</h2>

<!-- Paste the preview below. Prep the facts with:
     python scripts/weekly_preview.py %%YEAR%% %%WEEK%%
     then have your agent (agents/weekly-preview.md) write it.
     The preview stays at the bottom of the page all season, below the recap. -->

_Preview coming soon._

{% include sections/week_power.html wk=wk %}
"""


def _fill(template, year, week, no):
    return (template.replace("%%YEAR%%", str(year))
                    .replace("%%WEEK%%", str(week))
                    .replace("%%NO%%", str(no)))


def scaffold_page(year, week):
    """Create docs/seasons/<year>/week-<n>.md if missing. Returns (path, created)."""
    no = year - FIRST_SEASON + 1
    out_dir = SEASON_PAGE_DIR / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"week-{week}.md"
    if path.exists():
        return path, False
    path.write_text(_fill(PAGE_TEMPLATE, year, week, no), encoding="utf-8")
    return path, True


_PLACEHOLDERS = {"_Preview coming soon._", "_Recap coming soon._"}


def _read_page_section(page_path, heading):
    """Pull the prose pasted under `<h2>{heading}</h2>` on a week page. A section
    runs until the next `<h2>`, a closing `{% endif %}`, or end of file — so it
    works whether the block is Liquid-gated (the recap) or ungated at the bottom of
    the page (the preview). Strips the paste-instructions comment. Returns the
    markdown, or None if it's missing or still the placeholder."""
    if not page_path or not Path(page_path).exists():
        return None
    text = Path(page_path).read_text(encoding="utf-8")
    m = re.search(rf"<h2>\s*{re.escape(heading)}\s*</h2>(.*?)(?=<h2|\{{%\s*endif\s*%\}}|\Z)",
                  text, re.DOTALL)
    if not m:
        return None
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.DOTALL).strip()
    if not body or body in _PLACEHOLDERS:
        return None
    return body


def read_preview(page_path):
    """The preview prose pasted into this week's page. None if none was written yet.
    Used only to warn when the recap is prepped before its preview exists — the
    agent itself reads the preview straight from the page for continuity."""
    return _read_page_section(page_path, "The Preview")


def _team_actual_line(entry):
    """'top CMC 31.2; bust Josh Allen (24.0 proj → 9.1); 38.4 left on bench'."""
    if not entry:
        return None
    bits = []
    if entry.get("top"):
        bits.append(f"top scorer {entry['top']['player']} {entry['top']['actual']:.1f}")
    if entry.get("bust"):
        b = entry["bust"]
        bits.append(f"bust {b['player']} ({b['proj']:.1f} proj → {b['actual']:.1f})")
    if entry.get("bench_points"):
        bits.append(f"{entry['bench_points']:.1f} left on the bench")
    if entry.get("injured"):
        inj = ", ".join(
            f"{p['player']} {p['status']}" + (f" ({p['actual']:.1f})"
                                              if p.get("actual") is not None else "")
            for p in entry["injured"])
        bits.append(f"injuries: {inj}")
    started_on_bye = [p["player"] for p in entry.get("on_bye") or [] if p.get("starter")]
    if started_on_bye:
        bits.append(f"STARTED on bye (zero): {', '.join(started_on_bye)}")
    # Benched bye players are schedule, not strategy — listed so the agent doesn't
    # read "X sat on the bench" as a lineup call.
    benched_on_bye = [p["player"] for p in entry.get("on_bye") or [] if not p.get("starter")]
    if benched_on_bye:
        bits.append(f"on bye (benched, no game): {', '.join(benched_on_bye)}")
    return "; ".join(bits) if bits else None


def _fmt_swing(rows):
    return ", ".join(f"{r['player']} {r['actual']:.1f} on {r['proj']:.1f} proj "
                     f"({r['diff']:+.1f})" for r in rows)


def _matchup_context_lines(g, ctx):
    """Per-matchup context beyond the box score: the pre-game line (and upset
    flag), how each side did against it, rank coming in, the all-time series after
    this game, each side's outlier games, and a bench call only if it flipped it."""
    out = []
    h, a = g["home_id"], g["away_id"]
    ho, ao = g["home_owner"], g["away_owner"]
    proj = ctx.get("pregame") or {}
    ln = pregame_line(proj.get(h), proj.get(a), g["home_score"], g["away_score"])
    if ln:
        if ln["favorite"]:
            fav = ho if ln["favorite"] == "a" else ao
            head = f"Pre-game line: {fav} favored by {ln['spread']:.1f} ({ho} {proj[h]:.1f}, {ao} {proj[a]:.1f})"
        else:
            head = f"Pre-game line: dead even ({proj[h]:.1f} each)"
        if ln["upset"]:
            head += " — UPSET"
        out.append(f"{head}; vs projection: {ho} {ln['vs_proj_a']:+.1f}, {ao} {ln['vs_proj_b']:+.1f}")
    rank = ctx.get("power_rank") or {}
    if h in rank and a in rank:
        out.append(f"Power rank coming in: {ho} #{rank[h]}, {ao} #{rank[a]}")
    rec = h2h_record(ctx.get("profiles"), h, a)
    if rec:
        out.append(f"All-time series after this game: {ho} {rec} vs {ao}")
    rosters = ctx.get("rosters") or {}
    for fid, who in ((h, ho), (a, ao)):
        sw = swing_players(rosters.get(fid))
        bits = []
        if sw["booms"]:
            bits.append("booms " + _fmt_swing(sw["booms"]))
        if sw["busts"]:
            bits.append("busts " + _fmt_swing(sw["busts"]))
        if bits:
            out.append(f"{who} outliers (10+ off projection): " + "; ".join(bits))
    if not g["tie"]:
        loser, lname = (a, ao) if g["winner_id"] == h else (h, ho)
        margin = abs(g["home_score"] - g["away_score"])
        swap = decisive_bench_swap(rosters.get(loser), margin)
        if swap:
            out.append(f"DECISIVE BENCH CALL — {lname}: {swap['bench']} ({swap['pos']}) scored "
                       f"{swap['bench_pts']:.1f} on the bench while {swap['starter']} started for "
                       f"{swap['starter_pts']:.1f}; that one swap (+{swap['gain']:.1f}) wins a game "
                       f"lost by {margin:.1f}")
    return out


def data_block(year, week, summary, ctx):
    """Human-readable scoreboard + player detail + league context the recap agent
    writes from."""
    rosters = ctx.get("rosters") or {}
    lines = [f"## This week: {year}, Week {week}", "", "Scoreboard:"]
    for g in summary["scoreboard"]:
        home = f"{g['home_team']} ({g['home_owner']}) {g['home_score']:.1f}"
        away = f"{g['away_team']} ({g['away_owner']}) {g['away_score']:.1f}"
        verb = "tie" if g["tie"] else ("def." if g["winner_id"] == g["home_id"] else "lost to")
        tag = " [playoff]" if g["playoff"] else ""
        lines.append(f"- {home} {verb} {away}{tag}")
        for fid, who in ((g["home_id"], g["home_owner"]), (g["away_id"], g["away_owner"])):
            dl = _team_actual_line(rosters.get(fid))
            if dl:
                lines.append(f"    {who}: {dl}")
        lines += ["    " + l for l in _matchup_context_lines(g, ctx)]
        by_win = ctx.get("by_window") or {}
        if g["home_id"] in by_win and g["away_id"] in by_win:
            side = {g["home_id"]: "home", g["away_id"]: "away"}.get(g["winner_id"])
            flow = matchup_flow(by_win[g["home_id"]], by_win[g["away_id"]],
                                ctx["windows"], None if g["tie"] else side)
            lines += ["    " + l for l in flow_lines(flow, g["home_owner"], g["away_owner"],
                                                    by_win[g["home_id"]], by_win[g["away_id"]])]

    lines += ["", "Highlights:"]
    for h in summary["highlights"]:
        who = f" — {h['team']} ({h['owner_name']})" if h["owner_name"] else ""
        sub = f" [{h['sub']}]" if h["sub"] else ""
        lines.append(f"- {h['label']}: {h['value']}{who}{sub}")

    spot = spotlight_lines(ctx.get("spotlight"))
    if spot:
        lines += ["", "Standalone windows — every fantasy starter in the week's opener, "
                  "closer, and other non-Sunday-afternoon games, best first (a big "
                  "Thursday or Monday night is a story):"] + spot

    sup = ctx.get("superlatives") or {}
    if sup.get("best_player") or sup.get("bench_leader"):
        lines += ["", "Week superlatives (these — plus Top/Low Score above — are the "
                  "ONLY true league-highs; do NOT call any other number 'league-high', "
                  "'the most', or 'biggest'):"]
        bp = sup.get("best_player")
        if bp:
            lines.append(f"- Best individual game (whole league): {bp['player']} "
                         f"{bp['actual']:.1f} — {bp['owner']}")
        bl = sup.get("bench_leader")
        if bl:
            lines.append(f"- Most points left on the bench (whole league): "
                         f"{bl['points']:.1f} — {bl['owner']}")

    moves = ctx.get("moves") or {}
    if moves.get("trades") or moves.get("adds"):
        lines += ["", "Recent moves:"]
        for t in moves.get("trades", []):
            lines.append(f"- Trade (Wk {t['week']}): {t['detail']}")
        for ad in moves.get("adds", []):
            lines.append(f"- {ad['owner']} added {ad['player']} ({ad['kind']}, Wk {ad['week']})")

    if ctx.get("renames"):
        lines += ["", "Renamed this week (team name changed since the pre-game snapshot):"]
        for r in ctx["renames"]:
            lines.append(f"- {r['owner']}: \"{r['old']}\" → \"{r['new']}\"")

    odds = ctx.get("odds") or []
    if odds:
        lines += ["", "Playoff odds after this week (10,000 sims; ▲/▼ = change from last "
                  "week — a big swing is a story):"]
        for r in odds:
            c = r.get("cells") or {}
            def cell(k):
                v = c.get(k) or {}
                t = v.get("trend") or {}
                return v.get("text", "?") + (f" ({t['text']})" if t.get("text") else "")
            lines.append(f"- {r['owner']} ({r['record']}): playoffs {cell('playoffs')}, "
                         f"Shiva {cell('shiva')}, Sacko {cell('sacko')}")

    byes = bye_watch_lines(ctx.get("byes"), week, this_week=False)
    if byes:
        lines += ["", "Byes (lineup blunders this week; next week's crunch to tease):"] + byes

    standings = ctx.get("standings") or []
    if standings:
        lines += ["", "Standings (after this week):"]
        for r in standings:
            pf = f", {r['pf']:.1f} PF" if r.get("pf") is not None else ""
            lines.append(f"- {r['rank']}. {r['owner']} ({r['team']}) {r['record']}{pf}")

    bests = ctx.get("bests") or []
    if bests:
        lines += ["", "League bests (all-time, for reference — note if this week neared one):"]
        for b in bests:
            yr = f", {b['season']}" if b.get("season") else ""
            lines.append(f"- {b['category']}: {b['value']} — {b['holder']}{yr}")

    streaks = ctx.get("streaks") or []
    if streaks:
        lines += ["", "Streaks on the line coming in (say whether each HELD or "
                  "SNAPPED this week — that's the story):"]
        for s in streaks:
            lines.append(f"- {s['owner']} entered on a {s['streak']}")

    return "\n".join(lines) + "\n"


def _all_games_scored(season, week):
    """True when every game in `week` has a score — i.e. the week is physically over,
    even if ESPN hasn't stamped the winners yet (no `future` games left)."""
    games = [m for m in (season.get("matchups") or []) if m.get("week") == week]
    return bool(games) and all(m.get("home_score") is not None for m in games)


def _read_yaml_file(path):
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def _odds_rows(year, week):
    """This season's playoff-odds rows from the built docs/_data/odds.yml — only
    when they're as of this week (run build.py first), else []."""
    doc = (_read_yaml_file(ODDS_PATH) or {}).get(year) or {}
    return doc.get("rows") or [] if doc.get("as_of_week") == week else []


def finalize_week(year, week):
    """Promote a week's live games to final in data/seasons/<year>.yml by dropping
    their `final: false` flag — what ESPN will do once it stamps the winners, done
    early because the games are physically over. Surgical text edit (only this
    week's matchup lines), so the file's comments and formatting are untouched. A
    later import keeps it final (see import_espn.preserve_final_matchups). No-op if
    the week still has unplayed games. Returns the number of games finalized."""
    path = SEASONS_DIR / f"{year}.yml"
    text = path.read_text(encoding="utf-8")
    line_re = re.compile(rf"^(\s*- \{{ week:\s*{week},.*?), final: false(.*\}})$",
                         re.MULTILINE)
    new, n = line_re.subn(r"\1\2", text)
    if n:
        path.write_text(new, encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser(description="Prep a weekly recap (scaffold page + facts file).")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    ap.add_argument("--finalize", action="store_true",
                    help="Mark the week final now (all its games are over) so the "
                         "recap can be written and shown before ESPN flips the week "
                         "to complete. Safe: a later import won't undo it.")
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season file for {args.year} (data/seasons/{args.year}.yml).")

    summary = week_summary(season, args.week, franchises)
    if summary["state"] != "complete" and args.finalize:
        if not _all_games_scored(season, args.week):
            sys.exit(f"Can't finalize {args.year} week {args.week}: it still has games "
                     f"with no score. Wait until every game is over.")
        n = finalize_week(args.year, args.week)
        print(f"Finalized {n} game(s) for week {args.week} (marked final locally).",
              file=sys.stderr)
        # Reload so the state, records and highlights reflect the now-final week.
        seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
        season = seasons[args.year]
        summary = week_summary(season, args.week, franchises)
    if summary["state"] != "complete":
        sys.exit(f"{args.year} week {args.week} is {summary['state']}, not complete — "
                 f"recaps are only written for a complete week. If the week's games "
                 f"are all over but ESPN hasn't caught up, re-run with --finalize.")

    path, created = scaffold_page(args.year, args.week)

    records = (yaml.safe_load(RECORDS_PATH.read_text()) or {}).get("records", []) if RECORDS_PATH.exists() else []
    # Per-player actuals from the roster snapshot the importer persisted for this
    # week (data/rosters/<year>-week-<nn>.yml). Read from disk — no live fetch.
    week_rosters = load_week_rosters(args.year, args.week, franchises)
    rosters = (week_roster_context(week_rosters, want_actual=True, week=args.week)
               if week_rosters else None)
    # Streaks (W2+/L2+) carried INTO this week, so the recap can say whether each
    # heater or skid held or snapped — a natural narrative thread as the season runs.
    projections = load_projections(args.year, franchises)
    pregame = projections.get(args.week) or {}
    form = team_form(season, franchises, args.week, projections)
    streaks = sorted(
        ({"owner": short_name_of(fid, franchises), "streak": e["streak"]}
         for fid, e in form.items()
         if e.get("streak") and int(e["streak"][1:]) >= 2),
        key=lambda s: s["owner"])
    # League-wide superlatives (best individual game, biggest bench) resolved to
    # owner names — so the recap only labels the *real* league-highs.
    sup = week_superlatives(rosters)
    for key in ("best_player", "bench_leader"):
        if sup.get(key):
            sup[key]["owner"] = short_name_of(sup[key]["fid"], franchises)
    # NFL kickoff windows (data/nfl_schedule/<year>.yml), so the facts can tell
    # the week in order: who scored Thursday, who swung it Monday night.
    windows = week_windows(load_nfl_schedule(args.year), args.week)
    by_window = ({fid: lineup_by_window(e["starters"], windows) for fid, e in rosters.items()}
                 if windows and rosters else {})
    ctx = {
        "rosters": rosters,
        "windows": windows,
        "by_window": by_window,
        "spotlight": spotlight(by_window, windows, lambda f: short_name_of(f, franchises)),
        "standings": standings_snapshot(season, franchises),
        "moves": recent_moves(season, franchises, max(0, args.week - 1), args.week),
        "bests": league_bests(records),
        "streaks": streaks,
        "superlatives": sup,
        "byes": bye_watch(rosters, franchises),
        "pregame": pregame.get("proj") or {},
        "renames": [dict(r, owner=short_name_of(r["fid"], franchises))
                    for r in renamed_teams(pregame.get("names"), season.get("teams"))],
        "profiles": _read_yaml_file(PROFILES_PATH),
        "power_rank": {r["fid"]: r["rank"]
                       for r in week_power_rankings(season, args.week, franchises)},
        "odds": _odds_rows(args.year, args.week),
    }
    if not read_preview(path):
        print("NOTE: no preview found on the week page — the recap can't grade "
              "predictions. (Write the preview first for a continuous column.)",
              file=sys.stderr)
    if not rosters:
        print("NOTE: no roster snapshot for this week (data/rosters/"
              f"{args.year}-week-{args.week:02d}.yml missing) — facts omit per-player "
              "boom/bust lines. Re-run the importer for this week.", file=sys.stderr)
    elif not windows:
        print(f"NOTE: no NFL schedule on file (data/nfl_schedule/{args.year}.yml) — "
              "facts omit the scoring order. Re-run the importer.", file=sys.stderr)

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    facts_path = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.recap.data.md"
    facts_path.write_text(data_block(args.year, args.week, summary, ctx), encoding="utf-8")

    n_games = len(summary["scoreboard"])
    spec_rel = AGENT_SPEC.relative_to(ROOT)
    print(f"Week {args.week}, {args.year}: {n_games} game(s) summarized.", file=sys.stderr)
    print(f"  page:  {path.relative_to(ROOT)}  ({'created' if created else 'already exists — kept'})",
          file=sys.stderr)
    print(f"  facts: {facts_path.relative_to(ROOT)}", file=sys.stderr)
    print(f"\nNext: point your agent at {spec_rel} and ask it to write the Week "
          f"{args.week} recap. It reads the facts file above plus the season's prior "
          "editions from docs/seasons/. Paste its reply below \"The Recap\" on the "
          "page, then run: python scripts/build.py", file=sys.stderr)


if __name__ == "__main__":
    main()
