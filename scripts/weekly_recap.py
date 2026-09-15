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
                      load_projections, short_name_of)
from lib.weeks import week_summary
from lib.context import (standings_snapshot, recent_moves, league_bests,
                         week_roster_context, team_form)

ROOT = Path(__file__).resolve().parent.parent
SEASON_PAGE_DIR = ROOT / "docs" / "seasons"
AGENT_SPEC = ROOT / "agents" / "weekly-recap.md"
RECORDS_PATH = ROOT / "docs" / "_data" / "records.yml"
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
{% include week_detail.html wk=wk %}

{% if wk.state != "complete" %}
<h2>The Preview</h2>

<!-- Paste the preview below. Prep the facts with:
     python scripts/weekly_preview.py %%YEAR%% %%WEEK%%
     then have your agent (agents/weekly-preview.md) write it.
     Shows until the week is complete, then the recap takes over. -->

_Preview coming soon._
{% endif %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Prep the facts with:
     python scripts/weekly_recap.py %%YEAR%% %%WEEK%%
     then have your agent (agents/weekly-recap.md) write it.
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete. -->

_Recap coming soon._
{% endif %}
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
    """Pull the prose pasted under `<h2>{heading}</h2>` on a week page, up to the
    `{% endif %}` that closes its block. Strips the paste-instructions comment.
    Returns the markdown, or None if it's missing or still the placeholder."""
    if not page_path or not Path(page_path).exists():
        return None
    text = Path(page_path).read_text(encoding="utf-8")
    m = re.search(rf"<h2>\s*{re.escape(heading)}\s*</h2>(.*?)\{{%\s*endif\s*%\}}",
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
    return "; ".join(bits) if bits else None


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

    lines += ["", "Highlights:"]
    for h in summary["highlights"]:
        who = f" — {h['team']} ({h['owner_name']})" if h["owner_name"] else ""
        sub = f" [{h['sub']}]" if h["sub"] else ""
        lines.append(f"- {h['label']}: {h['value']}{who}{sub}")

    moves = ctx.get("moves") or {}
    if moves.get("trades") or moves.get("adds"):
        lines += ["", "Recent moves:"]
        for t in moves.get("trades", []):
            lines.append(f"- Trade (Wk {t['week']}): {t['detail']}")
        for ad in moves.get("adds", []):
            lines.append(f"- {ad['owner']} added {ad['player']} ({ad['kind']}, Wk {ad['week']})")

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


def main():
    ap = argparse.ArgumentParser(description="Prep a weekly recap (scaffold page + facts file).")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season file for {args.year} (data/seasons/{args.year}.yml).")

    summary = week_summary(season, args.week, franchises)
    if summary["state"] != "complete":
        sys.exit(f"{args.year} week {args.week} is {summary['state']}, not complete — "
                 f"recaps are only written for a complete week. Import the finished "
                 f"week first, then re-run.")

    path, created = scaffold_page(args.year, args.week)

    records = (yaml.safe_load(RECORDS_PATH.read_text()) or {}).get("records", []) if RECORDS_PATH.exists() else []
    # Per-player actuals from the roster snapshot the importer persisted for this
    # week (data/rosters/<year>-week-<nn>.yml). Read from disk — no live fetch.
    week_rosters = load_week_rosters(args.year, args.week, franchises)
    rosters = week_roster_context(week_rosters, want_actual=True) if week_rosters else None
    # Streaks (W2+/L2+) carried INTO this week, so the recap can say whether each
    # heater or skid held or snapped — a natural narrative thread as the season runs.
    form = team_form(season, franchises, args.week, load_projections(args.year, franchises))
    streaks = sorted(
        ({"owner": short_name_of(fid, franchises), "streak": e["streak"]}
         for fid, e in form.items()
         if e.get("streak") and int(e["streak"][1:]) >= 2),
        key=lambda s: s["owner"])
    ctx = {
        "rosters": rosters,
        "standings": standings_snapshot(season, franchises),
        "moves": recent_moves(season, franchises, max(0, args.week - 1), args.week),
        "bests": league_bests(records),
        "streaks": streaks,
    }
    if not read_preview(path):
        print("NOTE: no preview found on the week page — the recap can't grade "
              "predictions. (Write the preview first for a continuous column.)",
              file=sys.stderr)
    if not rosters:
        print("NOTE: no roster snapshot for this week (data/rosters/"
              f"{args.year}-week-{args.week:02d}.yml missing) — facts omit per-player "
              "boom/bust lines. Re-run the importer for this week.", file=sys.stderr)

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
