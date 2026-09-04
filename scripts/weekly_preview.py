#!/usr/bin/env python3
"""Prep a weekly *preview*: gather the upcoming matchups + history, build the prompt.

Companion to weekly_recap.py. Where the recap looks back at a complete week, the
preview looks forward at a week that hasn't finished. It reads the week's fixtures
plus each owner's all-time record / titles / best finish and the all-time
head-to-head, and writes a paste-ready prompt (the agents/weekly-preview.md spec +
that context).

    python scripts/weekly_preview.py 2026 1

Paste the output into Claude, then paste its reply into the week page under
"The Preview" (which shows until the week is complete). Only works while the week
is future or in progress — a complete week gets a recap, not a preview.
"""

import argparse
import sys
from pathlib import Path

import yaml

from lib.data import load_franchises, load_seasons, short_name_of
from lib.weeks import week_state, _games_in_week
from weekly_recap import scaffold_page

ROOT = Path(__file__).resolve().parent.parent
AGENT_SPEC = ROOT / "agents" / "weekly-preview.md"
PROFILES_PATH = ROOT / "docs" / "_data" / "owner_profiles.yml"
PROMPT_DIR = ROOT / "recaps"


def _fmt_best(bf):
    if not bf:
        return "—"
    if bf.get("type") == "shiva":
        return f"Shiva ({', '.join(map(str, bf.get('years') or []))})"
    if bf.get("type") == "cochamp":
        return f"Co-champ ({', '.join(map(str, bf.get('years') or []))})"
    return bf.get("ordinal") or "—"


def _owner_line(name, prof):
    if not prof:
        return f"{name}: no league history yet"
    r = prof["resume"]
    titles = r.get("titles", "0")
    return (f"{name}: all-time {r['all_time']} ({r['win_pct']}), "
            f"{titles} title(s), best finish {_fmt_best(r.get('best_finish'))}")


def _h2h_line(home_name, home_prof, away_fid, away_name):
    for h in (home_prof or {}).get("h2h", []):
        if h.get("opp_id") == away_fid:
            parts = (h["record"].split("-") + ["0", "0"])[:2]
            w, l = int(parts[0]), int(parts[1])
            verb = "leads" if w > l else "trails" if l > w else "is even with"
            return f"Head-to-head: {home_name} {verb} {away_name} {h['record']} all-time"
    return "Head-to-head: first meeting"


def data_block(year, week, games, season, franchises, profiles):
    teams = season.get("teams", {})

    def team_name(fid):
        return teams.get(fid) or short_name_of(fid, franchises)

    lines = [f"## Preview: {year}, Week {week}", "", "Upcoming matchups:"]
    for m in games:
        h, a = m["home"], m["away"]
        hn, an = short_name_of(h, franchises), short_name_of(a, franchises)
        lines.append(f"- {team_name(h)} ({hn}) vs {team_name(a)} ({an})")
        lines.append(f"    {_owner_line(hn, profiles.get(h))}")
        lines.append(f"    {_owner_line(an, profiles.get(a))}")
        lines.append(f"    {_h2h_line(hn, profiles.get(h), a, an)}")
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
    scaffold_page(args.year, args.week)   # ensure the page exists

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    prompt_path = PROMPT_DIR / f"{args.year}-week-{args.week:02d}.preview.prompt.md"
    prompt = (AGENT_SPEC.read_text(encoding="utf-8") + "\n\n---\n\n"
              + data_block(args.year, args.week, games, season, franchises, profiles))
    prompt_path.write_text(prompt, encoding="utf-8")

    print(f"Week {args.week}, {args.year} ({state}): {len(games)} matchup(s).", file=sys.stderr)
    print(f"  prompt: {prompt_path.relative_to(ROOT)}", file=sys.stderr)
    print("\nPaste it into Claude, then paste the reply into the week page under "
          "\"The Preview\", and run: python scripts/build.py", file=sys.stderr)


if __name__ == "__main__":
    main()
