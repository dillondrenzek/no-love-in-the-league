#!/usr/bin/env python3
"""Prep a week's recap: isolate highlights, scaffold the page, build the prompt.

Weekly workflow for the live season:

    1. Import the week's games:   ./scripts/import_manager.sh   (or import_espn.py)
    2. Prep the recap:            python scripts/weekly_recap.py 2026 1
    3. Paste recaps/2026-week-01.prompt.md into Claude (uses agents/weekly-recap.md),
       then paste the reply into docs/seasons/2026/week-1.md (below "The Recap").
    4. Rebuild:                   python scripts/build.py

This script does steps 2's grunt work: it reads the already-imported matchups
(the "hit the API" part is the importer), isolates this week's scoreboard +
highlights, scaffolds the week page if it doesn't exist, and writes a ready-to-
paste prompt (the recap agent spec + this week's data). It never calls an LLM
itself — generation stays in your hands (or anyone's, via the spec).
"""

import argparse
import sys
from pathlib import Path

from lib.data import load_franchises, load_seasons
from lib.weeks import week_summary

ROOT = Path(__file__).resolve().parent.parent
SEASON_PAGE_DIR = ROOT / "docs" / "seasons"
AGENT_SPEC = ROOT / "agents" / "weekly-recap.md"
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
<p class="back-link"><a href="{{ '/seasons/%%YEAR%%/' | relative_url }}">← Season %%NO%% · %%YEAR%%</a></p>

{% assign wk = site.data.weeks["%%YEAR%%-%%WEEK%%"] %}
{% include week_detail.html wk=wk %}

<h2>The Recap</h2>

<!-- Paste the agent's recap below. Regenerate the prompt any time with:
     python scripts/weekly_recap.py %%YEAR%% %%WEEK%%
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. -->

_Recap coming soon._
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


def data_block(year, week, summary):
    """Human-readable scoreboard + highlights the recap agent writes from."""
    lines = [f"## This week: {year}, Week {week}", "", "Scoreboard:"]
    for g in summary["scoreboard"]:
        home = f"{g['home_team']} ({g['home_owner']}) {g['home_score']:.1f}"
        away = f"{g['away_team']} ({g['away_owner']}) {g['away_score']:.1f}"
        verb = "tie" if g["tie"] else ("def." if g["winner_id"] == g["home_id"] else "lost to")
        tag = " [playoff]" if g["playoff"] else ""
        lines.append(f"- {home} {verb} {away}{tag}")
    lines += ["", "Highlights:"]
    for h in summary["highlights"]:
        who = f" — {h['team']} ({h['owner_name']})" if h["owner_name"] else ""
        sub = f" [{h['sub']}]" if h["sub"] else ""
        lines.append(f"- {h['label']}: {h['value']}{who}{sub}")
    return "\n".join(lines) + "\n"


def build_prompt(year, week, summary):
    spec = AGENT_SPEC.read_text(encoding="utf-8")
    block = data_block(year, week, summary)
    return f"{spec}\n\n---\n\n{block}"


def main():
    ap = argparse.ArgumentParser(description="Prep a weekly recap (scaffold page + prompt).")
    ap.add_argument("year", type=int)
    ap.add_argument("week", type=int)
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season file for {args.year} (data/seasons/{args.year}.yml).")

    summary = week_summary(season, args.week, franchises)
    if not summary["played"]:
        sys.exit(f"No games found for {args.year} week {args.week}. "
                 f"Import the week first (see scripts/import_manager.sh), then re-run.")

    path, created = scaffold_page(args.year, args.week)

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.prompt.md"
    prompt_path.write_text(build_prompt(args.year, args.week, summary), encoding="utf-8")

    n_games = len(summary["scoreboard"])
    print(f"Week {args.week}, {args.year}: {n_games} game(s) summarized.", file=sys.stderr)
    print(f"  page:   {path.relative_to(ROOT)}  ({'created' if created else 'already exists — kept'})",
          file=sys.stderr)
    print(f"  prompt: {prompt_path.relative_to(ROOT)}", file=sys.stderr)
    print("\nNext: paste the prompt into Claude, then paste its reply into the page "
          "below \"The Recap\", and run: python scripts/build.py", file=sys.stderr)


if __name__ == "__main__":
    main()
