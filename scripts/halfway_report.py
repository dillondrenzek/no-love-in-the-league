#!/usr/bin/env python3
"""Prep the season's Halfway report: write the computed facts file the agent
writes the page's prose from, and scaffold the page + prose file if needed.

    python scripts/halfway_report.py 2026

Best run once the first half is final; before that it uses the weeks that are
final so far and says so.

Then point your agent at agents/halfway-report.md. It reads the facts file
(recaps/<year>-halfway.data.md) plus the season's weekly editions from
docs/seasons/<year>/, and writes the intro, the season outlook, and one paragraph
per team into data/halfway/<year>.yml. Rebuild (scripts/build.py) to publish.

Like the weekly prep scripts, this only computes; it never calls an LLM. Every
number is as of the halfway week (lib/halfway), so the facts match the frozen
standings and odds on the page.
"""

import argparse
import sys
from pathlib import Path

import yaml

from lib.data import (load_franchises, load_seasons, load_projections,
                      load_season_notes, load_halfway_prose, load_halfway_snapshot,
                      load_week_rosters,
                      short_name_of, trade_asset_label)
from lib.context import recent_moves, league_bests, h2h_record
from lib.halfway import (halfway_week, snapshot, first_half_complete, team_halves,
                         schedule_ranks, starter_points, best_moves, second_half_slate,
                         bye_load)
from lib.overrides import load_overrides
from lib.power import week_power_rankings
from generate_halfway import halfway_entry, scaffold_page, scaffold_prose
from weekly_preview import _owner_line

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "docs" / "_data" / "owner_profiles.yml"
RECORDS_PATH = ROOT / "docs" / "_data" / "records.yml"
PROMPT_DIR = ROOT / "recaps"
HEAVY_BYE = 4            # players off in one week that makes it a heavy bye
AGENT_SPEC = ROOT / "agents" / "halfway-report.md"


def _read_yaml(path):
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def _game(g, franchises, label):
    if not g:
        return None
    verb = {"W": "beat", "L": "lost to", "T": "tied"}[g["res"]]
    return (f"{label}: Wk {g['week']} {g['pf']:.1f}–{g['pa']:.1f}, "
            f"{verb} {short_name_of(g['opp'], franchises)}")


def _bye_weeks(weeks, pts):
    """'Wk 8 — 5 off, HEAVY (A, B, …)' per week with 2+ players off, the
    team's best players (by starter points) named first."""
    out = []
    for w, players in weeks.items():
        if len(players) < 2:
            continue
        names = sorted(players, key=lambda pl: -pts.get(pl, 0.0))
        heavy = ", HEAVY" if len(players) >= HEAVY_BYE else ""
        out.append(f"Wk {w} — {len(players)} off{heavy} ({', '.join(names)})")
    return "; ".join(out)


def team_block(fid, h, ctx, franchises):
    """The facts for one team — résumé, moves, road ahead."""
    who = short_name_of(fid, franchises)
    team = ctx["teams"].get(fid) or who
    lines = [f"### {ctx['rank'][fid]}. {team} ({who}) [fid: {fid}]"]
    names = []
    for snap in ctx["name_seq"]:
        nm = snap.get(fid)
        if nm and (not names or names[-1] != nm):
            names.append(nm)
    if team and (not names or names[-1] != team):
        names.append(team)
    if len(names) > 1:
        lines.append("- Team names this season, in order: " + " → ".join(f'"{n}"' for n in names))
    lines.append(f"- History: {_owner_line(who, ctx['profiles'].get(fid))}")
    lines.append(f"- First half: {h['record']}, {h['pf']:.1f} PF ({h['avg']:.1f}/wk, "
                 f"#{h['pf_rank']} in points), {h['pa']:.1f} PA; all-play {h['all_play']} "
                 f"(record vs every team every week — far better than the real record means "
                 f"unlucky, far worse means lucky)")
    lines.append(f"- Close games (decided by under 10): {h['close']}; "
                 f"longest win streak {h['longest_win']}, longest skid {h['longest_loss']}; "
                 f"on a {h['streak']} at the break" if h.get("streak") else
                 f"- Close games (decided by under 10): {h['close']}")
    for g, label in ((h["best"], "Best week"), (h["worst"], "Worst week"),
                     (h["big_win"], "Biggest win"), (h["bad_loss"], "Worst loss")):
        s = _game(g, franchises, label)
        if s:
            lines.append(f"- {s}")
    pts = ctx["starter_pts"].get(fid) or {}
    for t in ctx["trades"]:
        if fid not in (t.get("teams") or []):
            continue
        got = [trade_asset_label(a) for a in t.get("assets") or [] if a.get("to") == fid]
        gave = [trade_asset_label(a) for a in t.get("assets") or [] if a.get("from") == fid]
        got, gave = [x for x in got if x], [x for x in gave if x]
        others = [short_name_of(f, franchises) for f in t.get("teams") or [] if f != fid]
        paid = best_moves(got, pts, limit=len(got))
        line = (f"- Trade (Wk {t.get('week') or 0}) with {', '.join(others)}: got "
                f"{', '.join(got) or 'nothing listed'}; gave {', '.join(gave) or 'nothing listed'}")
        line += (f" — what they've given {who} as starters: "
                 + ", ".join(f"{p} {v:.1f}" for p, v in paid)) if paid else \
                " — nothing scored for them as a starter yet"
        lines.append(line)
    adds = [a for a in ctx["moves"]["adds"] if a["owner"] == who]
    if adds:
        top = best_moves([a["player"] for a in adds], pts)
        line = f"- Pickups: {len(adds)} adds"
        if top:
            line += "; best by points as a starter: " + ", ".join(f"{p} {v:.1f}" for p, v in top)
        lines.append(line)
    drafted = [e for e in (ctx["rosters"].get(fid) or [])
               if e.get("via") == "draft" and (e.get("round") or 99) <= 2]
    if drafted:
        lines.append("- Top draft picks: " + ", ".join(
            f"R{e['round']} {e['player']}" for e in sorted(drafted, key=lambda e: e["round"])))
    odds = ctx["odds"].get(fid)
    if odds:
        c = odds["cells"]
        lines.append(f"- Odds at the break: playoffs {c['playoffs']['text']}, bye {c['bye']['text']}, "
                     f"Shiva {c['shiva']['text']}, Sacko {c['sacko']['text']}; "
                     f"projected {odds['proj_wins']} wins; model rating {odds['rating']} pts/wk")
    if fid in ctx["power"]:
        lines.append(f"- Power rank going into the second half: #{ctx['power'][fid]}")
    byes = ctx["byes"].get(fid) or {}
    past, ahead = _bye_weeks(byes.get("past") or {}, pts), _bye_weeks(byes.get("ahead") or {}, pts)
    lines.append(f"- Bye weeks already behind them (2+ rostered players off): {past or 'none that heavy'}")
    lines.append(f"- Bye weeks ahead (current roster, 2+ off): {ahead or 'none that heavy'}")
    slate = second_half_slate(ctx["halves"], fid)
    if slate:
        lines.append("- Second half, game by game (opponent's record and standing; "
                     "RACE = same record or a tie apart, a six-pointer):")
        for r in slate:
            opp = r["opp"]
            bits = [f"{r['opp_record']}, #{ctx['rank'].get(opp, '?')}"]
            po = ((ctx["odds"].get(opp) or {}).get("cells") or {}).get("playoffs", {}).get("text")
            if po:
                bits.append(f"{po} playoffs")
            if r["race"]:
                bits.append("RACE")
            if r["twice"]:
                bits.append("they meet twice in the second half")
            m = r["rematch"]
            if m:
                verb = {"W": "won", "L": "lost", "T": "tied"}[m["res"]]
                bits.append(f"rematch — {verb} {m['pf']:.1f}–{m['pa']:.1f} in Wk {m['week']}")
            series = h2h_record(ctx["profiles"], fid, opp)
            if series:
                bits.append(f"all-time {series}")
            lines.append(f"  - Wk {r['week']} vs {short_name_of(opp, franchises)} "
                         f"({'; '.join(bits)})")
        top6 = sum(ctx["rank"].get(r["opp"], 99) <= 6 for r in slate)
        races = sum(r["race"] for r in slate)
        sos = ctx["sos"].get(fid)
        line = (f"- Remaining schedule: {top6} of {len(slate)} games vs the current top six, "
                f"{races} race game{'' if races == 1 else 's'}")
        if sos:
            line += (f"; opponents averaged {h['remaining_opp_avg']:.1f} in the first half "
                     f"— #{sos} of {len(ctx['sos'])} toughest")
        lines.append(line)
    return lines


def facts(season, franchises, through, entry):
    year = season["season"]
    # Everything is as of the last final week: the halfway week once it's done,
    # earlier while it's still being played (so a live week's partial scores and
    # its games stay out, and its matchup counts as still to come).
    as_of = entry.get("as_of_week", through)
    halves = team_halves(season, as_of)
    odds = {r["fid"]: r for r in (entry.get("odds") or {}).get("rows") or []}
    rank = {t["fid"]: t["rank"] for t in entry.get("teams") or []}
    power = {r["fid"]: r["rank"]
             for r in week_power_rankings(snapshot(season, as_of), as_of + 1, franchises)}
    projections = load_projections(year, franchises)
    # Rosters through the week after the break, so "byes ahead" uses the newest roster.
    rosters_by_week = {w: load_week_rosters(year, w, franchises) for w in range(1, as_of + 2)}
    rosters_by_week = {w: r for w, r in rosters_by_week.items() if r}
    ctx = {
        "teams": season.get("teams") or {},
        "rank": rank,
        "halves": halves,
        "odds": odds,
        "power": power,
        "sos": schedule_ranks(halves),
        "profiles": _read_yaml(PROFILES_PATH),
        "moves": recent_moves(season, franchises, 0, through + 1),
        "trades": [t for t in season.get("trades") or []
                   if (t.get("week") or 0) <= through + 1 and t.get("assets")],
        "starter_pts": starter_points({w: r for w, r in rosters_by_week.items() if w <= as_of}),
        "byes": bye_load(rosters_by_week, as_of),
        "rosters": season.get("rosters") or {},
        "name_seq": [(projections[w].get("names") or {})
                     for w in sorted(w for w in projections if w <= through + 1)],
    }
    reg = season.get("weeks_in_regular_season") or 14
    out = [f"## Halfway report: {year}, through Week {as_of} of {reg}", "",
           "Format: 12 teams, 6 make the playoffs (top 2 seeds get a bye; the 6th seed "
           "is a points wildcard: the top scorer outside the top five). Every number "
           "below is as of the end of Week " + str(as_of) + "."
           + ("" if as_of == through else f" Week {through} (the last of the first half) "
              "isn't final yet, so it isn't counted."), "",
           "Standings at the break (rank, record, PF, all-play, playoff odds):"]
    for t in entry.get("teams") or []:
        h = halves.get(t["fid"]) or {}
        po = (odds.get(t["fid"]) or {}).get("cells", {}).get("playoffs", {})
        trend = (po.get("trend") or {}).get("text")
        out.append(f"- {t['rank']}. {t['owner']} ({t['team']}) {t['record']}, "
                   f"{h.get('pf', 0):.1f} PF, all-play {h.get('all_play')}, "
                   f"playoffs {po.get('text', '?')}" + (f" ({trend} last week)" if trend else ""))
    out += ["", "League bests (all-time, for reference):"]
    for b in league_bests((_read_yaml(RECORDS_PATH) or {}).get("records", [])):
        yr = f", {b['season']}" if b.get("season") else ""
        out.append(f"- {b['category']}: {b['value']} — {b['holder']}{yr}")
    heavy = sorted(((len(pl), w, fid) for fid, b in ctx["byes"].items()
                    for w, pl in (b.get("ahead") or {}).items()), reverse=True)[:6]
    if heavy:
        out += ["", "Heaviest bye weeks still ahead, league-wide (players off, current rosters):"]
        out += [f"- {short_name_of(fid, franchises)}: Wk {w}, {n} off" for n, w, fid in heavy]
    out += ["", "## Team by team (in standings order)", ""]
    for t in entry.get("teams") or []:
        out += team_block(t["fid"], halves[t["fid"]], ctx, franchises) + [""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Prep the season's Halfway report facts.")
    ap.add_argument("year", type=int)
    args = ap.parse_args()

    franchises = load_franchises()
    seasons = {s["season"]: s for s in load_seasons(include_in_progress=True)}
    season = seasons.get(args.year)
    if not season:
        sys.exit(f"No season file for {args.year}.")
    through = halfway_week(season)
    if not first_half_complete(season, through):
        print(f"NOTE: Week {through} isn't final yet — the facts cover the weeks that "
              f"are. Re-run once it is for the real halfway numbers.", file=sys.stderr)

    entry, rows = halfway_entry(season, franchises, load_overrides(), load_season_notes(),
                                load_halfway_prose(args.year), load_halfway_snapshot(args.year))
    scaffold_page(args.year, through)
    created = scaffold_prose(args.year, rows)

    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    path = PROMPT_DIR / f"{args.year}-halfway.data.md"
    path.write_text(facts(season, franchises, through, entry), encoding="utf-8")
    print(f"Halfway {args.year} (through Week {through}): facts -> {path.relative_to(ROOT)}",
          file=sys.stderr)
    print(f"  prose: data/halfway/{args.year}.yml ({'created' if created else 'kept'})",
          file=sys.stderr)
    print(f"\nNext: point your agent at {AGENT_SPEC.relative_to(ROOT)} to write the intro, "
          "outlook and team paragraphs into the prose file, then run: python scripts/build.py",
          file=sys.stderr)


if __name__ == "__main__":
    main()
