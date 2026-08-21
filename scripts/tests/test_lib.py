#!/usr/bin/env python3
"""Tests for the compute functions in scripts/lib.

Plain asserts, no test framework needed (keeps dependencies to just PyYAML).
Run from the repo root:

    .venv/bin/python scripts/tests/test_lib.py

Uses small in-memory fixtures so it never touches the real data files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.standings import get_standings, record_string, parse_record, has_points
from lib.records import compute_records
from lib.teams import compute_profiles, rec_str, fmt_titles
from lib.rulings import meaningless_keys, co_champions


# --- Explicit-standings season (the ESPN-import shape, no scores) ------------

def explicit_season(year=2025):
    return {
        "season": year,
        "standings": [
            {"finish": 1, "team": "Alpha", "record": "12-2-0"},
            {"finish": 2, "team": "Bravo", "record": "9-5-0"},
            {"finish": 3, "team": "Charlie", "record": "7-6-1"},
            {"finish": 4, "team": "Delta", "record": "1-13-0"},
        ],
    }


# --- Matchup season (scores present) ----------------------------------------

def matchup_season(year=2025):
    return {
        "season": year,
        "weeks_in_regular_season": 2,
        "teams": {"a": "Alpha Cats", "b": "Bravo Dogs", "c": "Charlie Birds", "d": "Delta Fish"},
        "matchups": [
            {"week": 1, "home": "a", "away": "b", "home_score": 100.0, "away_score": 90.0},
            {"week": 1, "home": "c", "away": "d", "home_score": 80.0, "away_score": 120.0},
            {"week": 2, "home": "a", "away": "c", "home_score": 110.0, "away_score": 70.0},
            {"week": 2, "home": "b", "away": "d", "home_score": 95.0, "away_score": 95.0},
            {"week": 3, "home": "d", "away": "a", "home_score": 200.0, "away_score": 60.0,
             "playoff": True},
        ],
    }


def test_trade_counts_and_most_trades_record():
    from lib.teams import compute_profiles
    s = matchup_season(2025)
    # Trades with no `complete: false` flag are treated as fully detailed; every
    # listed participant gets credit.
    s["trades"] = [
        {"week": 3, "teams": ["a", "b"], "assets": []},
        {"week": 5, "teams": ["a", "c"], "assets": []},
    ]
    profiles = compute_profiles([s], {})
    assert profiles["a"]["trades"] == 2          # participated in two trades
    assert profiles["a"]["trades_known"] is True # all their seasons fully detailed
    assert len(profiles["a"]["trade_log"]) == 2  # ...with a detail entry each
    assert profiles["b"]["trades"] == 1
    assert profiles["c"]["trades"] == 1
    assert profiles["d"]["trades"] == 0

    recs = {r["category"]: r for r in compute_records([s], {})}
    assert recs["Most Trades"]["value"] == "2"


def test_incomplete_trades_credit_and_log_accepted():
    from lib.teams import compute_profiles
    s = matchup_season(2025)
    s["trades_complete"] = False        # importer couldn't detail every trade
    s["trades"] = [
        {"week": 3, "teams": ["a", "b"],
         "assets": [{"from": "a", "to": "b", "label": "RB X"}]},        # complete
        {"week": 6, "teams": ["c"], "assets": [], "complete": False},   # c accepted; hidden proposer
    ]
    profiles = compute_profiles([s], {})
    # No cookie tied to a franchise -> everyone who played is a floor.
    for fid in ("a", "b", "c", "d"):
        assert profiles[fid]["trades_known"] is False
    # Counts credit every listed participant, including the accepting team.
    assert profiles["a"]["trades"] == 1
    assert profiles["c"]["trades"] == 1
    # The accepted-but-undetailed trade still shows in c's history as a bare
    # "Trade Accepted" entry (no parties, no flow).
    assert len(profiles["c"]["trade_log"]) == 1
    acc = profiles["c"]["trade_log"][0]
    assert acc["accepted"] is True and acc["with"] == [] and acc["got"] == []
    # The detailed trade logs a full entry, not an accepted stub.
    assert len(profiles["a"]["trade_log"]) == 1
    assert profiles["a"]["trade_log"][0].get("accepted") is not True
    # "Most Trades" is withheld while any season is incomplete.
    recs = {r["category"]: r for r in compute_records([s], {})}
    assert "Most Trades" not in recs


def test_cookie_holder_count_is_exact_in_incomplete_season():
    from lib.teams import compute_profiles
    s = matchup_season(2025)
    s["trades_complete"] = False
    s["trades_known_for"] = ["a"]       # a's manager cookie was merged
    s["trades"] = [
        {"week": 3, "teams": ["a", "b"],
         "assets": [{"from": "a", "to": "b", "label": "RB X"}]},
        {"week": 6, "teams": ["c"], "assets": [], "complete": False},
    ]
    profiles = compute_profiles([s], {})
    # a supplied a cookie, so an undetailed trade can't be theirs -> exact count.
    assert profiles["a"]["trades_known"] is True
    # Everyone else who played is still a floor.
    for fid in ("b", "c", "d"):
        assert profiles[fid]["trades_known"] is False


def test_season_trades_complete_inference():
    from lib.data import season_trades_complete
    assert season_trades_complete({"trades": [{"teams": ["a", "b"]}]}) is True
    assert season_trades_complete({"trades": [{"teams": ["a"], "complete": False}]}) is False
    assert season_trades_complete({"trades_complete": False, "trades": []}) is False
    assert season_trades_complete({"trades_complete": True}) is True


# --- Rules: scoring & roster history (lib/rules.py) --------------------------

def _rules_entry(year, passtd, ppr, flex, bench, fmt="H2H_POINTS"):
    scoring = {3: 0.04, 4: passtd, 24: 0.1, 43: 6}
    if ppr:
        scoring[53] = ppr
    roster = {0: 1, 2: 2, 4: 2, 6: 1, 16: 1, 17: 1, 20: bench, 21: 1}
    if flex:
        roster[23] = flex
    return {"season": year, "format": fmt, "scoring": scoring, "roster": roster}


def test_compute_rules_current_and_change_log():
    from lib.rules import compute_rules
    entries = [
        _rules_entry(2013, 4, 0, 0, 7),      # baseline: 4-pt pass TD, no FLEX
        _rules_entry(2014, 6, 0, 1, 6),      # pass TD 4->6, +FLEX, bench 7->6
        _rules_entry(2015, 6, 0.5, 1, 6),    # +half PPR
        _rules_entry(2016, 6, 0.5, 1, 6),    # no change this year
    ]
    r = compute_rules(entries)

    # current = the latest season, labeled (ESPN's official stat names).
    assert r["current"]["season"] == 2016
    pts = {s["label"]: s["points"] for s in r["current"]["scoring"]}
    assert pts["TD Pass"] == "6" and pts["Each reception"] == "0.5"
    rv = r["current"]["roster"]
    assert (rv["starters"], rv["bench"], rv["ir"], rv["total"]) == (9, 6, 1, 16)

    # Each current scoring row is flagged whether the league ever changed it, so
    # the rulebook can show just the house tweaks and route the rest to ESPN.
    changed = {s["label"]: s["changed"] for s in r["current"]["scoring"]}
    assert changed["TD Pass"] is True and changed["Each reception"] is True
    assert changed["Passing Yards"] is False and changed["Rushing Yards"] is False
    assert r["current"]["scoring_changed_count"] == 2

    # change log is newest-first and only lists years that actually moved.
    assert [c["season"] for c in r["changes"]] == [2015, 2014]
    y2014 = {i["label"]: i for i in r["changes"][1]["items"]}
    assert y2014["TD Pass"]["text"] == "TD Pass: 4 → 6"
    assert y2014["FLEX"]["op"] == "added" and y2014["FLEX"]["kind"] == "roster"
    assert y2014["Bench"]["text"] == "Bench: 7 → 6"
    y2015 = r["changes"][0]["items"]
    assert any(i["label"] == "Each reception" and i["op"] == "added" for i in y2015)


def test_compute_rules_format_change_and_empty():
    from lib.rules import compute_rules
    assert compute_rules([]) == {"current": None, "changes": []}
    assert compute_rules(None) == {"current": None, "changes": []}
    e = [_rules_entry(2013, 6, 0.5, 1, 6, "H2H_POINTS"),
         _rules_entry(2014, 6, 0.5, 1, 6, "H2H_CATEGORY")]
    item = compute_rules(e)["changes"][0]["items"][0]
    assert item["kind"] == "format"
    assert "H2H_POINTS → H2H_CATEGORY" in item["text"]


def test_scoring_map_reads_points_overrides():
    # ESPN's post-2023 format stores some items' value in pointsOverrides with a
    # base points of 0. Those must still count, or a scored stat looks "removed".
    from lib.rules import scoring_map_from_settings
    settings = {"scoringSettings": {"scoringItems": [
        {"statId": 4, "points": 5, "pointsOverrides": {"16": 5}},     # normal base
        {"statId": 98, "points": 0, "pointsOverrides": {"16": 2}},    # value only in override
        {"statId": 99, "points": 0.0, "pointsOverrides": {"16": 0}},  # genuinely unscored
        {"statId": 20, "points": -2, "pointsOverrides": {"16": -2}},  # negative base kept
    ]}}
    m = scoring_map_from_settings(settings)
    assert m[4] == 5
    assert m[98] == 2          # picked up from the override despite points: 0
    assert 99 not in m         # both zero -> not scored
    assert m[20] == -2


def test_compute_rules_unknown_id_falls_back():
    from lib.rules import compute_rules
    r = compute_rules([{"season": 2020, "format": "x",
                        "scoring": {999: 3}, "roster": {0: 1, 20: 6}}])
    assert any(s["label"] == "stat #999" for s in r["current"]["scoring"])


def test_parse_record():
    assert parse_record("9-5-0") == (9, 5, 0)
    assert parse_record("7-6-1") == (7, 6, 1)


def test_record_string_drops_zero_ties():
    assert record_string({"wins": 11, "losses": 2, "ties": 0}) == "11-2"
    assert record_string({"wins": 7, "losses": 6, "ties": 1}) == "7-6-1"


def test_explicit_standings_order_and_no_points():
    rows = get_standings(explicit_season())
    assert [r["finish"] for r in rows] == [1, 2, 3, 4]
    assert rows[0]["name"] == "Alpha" and rows[0]["record"] == "12-2"
    assert rows[2]["record"] == "7-6-1"
    assert not has_points(rows)


def test_matchup_standings_and_points():
    rows = get_standings(matchup_season(), {})
    by = {r["id"]: r for r in rows}
    assert by["a"]["wins"] == 2 and by["a"]["points_for"] == 210.0  # playoff excluded
    assert by["d"]["ties"] == 1
    assert has_points(rows)


def test_matchup_standings_show_season_team_name():
    rows = get_standings(matchup_season(), {})
    by = {r["id"]: r for r in rows}
    assert by["a"]["name"] == "Alpha Cats"   # season team name, not the franchise id


def test_score_record_holder_uses_team_name():
    recs = {r["category"]: r for r in compute_records([matchup_season()], {})}
    assert recs["Most Points in a Week"]["holder"] == "Delta Fish"


def test_most_championships_counts_by_franchise_id_across_renames():
    # Same franchise "a" wins both seasons under different team names.
    s1 = matchup_season(2024)
    s2 = matchup_season(2025)
    s2["teams"] = dict(s2["teams"], a="Alpha Reborn")
    recs = {r["category"]: r for r in compute_records([s1, s2], {})}
    assert recs["Most Championships"]["value"] == "2", recs.get("Most Championships")


def test_records_standings_based():
    seasons = [explicit_season(2024), explicit_season(2025)]
    recs = {r["category"]: r for r in compute_records(seasons)}
    assert recs["Best Regular-Season Record"]["value"] == "12-2", recs["Best Regular-Season Record"]
    assert recs["Worst Regular-Season Record"]["value"] == "1-13", recs["Worst Regular-Season Record"]
    # Alpha wins both seasons' titles.
    assert recs["Most Championships"]["holder"] == "Alpha"
    assert recs["Most Championships"]["value"] == "2"


def test_records_score_based_appear_with_matchups():
    recs = {r["category"]: r for r in compute_records([matchup_season()], {})}
    assert recs["Most Points in a Week"]["value"] == "200.00"
    assert recs["Biggest Blowout"]["holder"] == "Delta Fish"
    assert "Most Points in a Season" in recs
    assert recs["Most Points in a Season"]["week"] is None


def test_owner_profiles_totals_and_h2h():
    # Same franchises across two seasons; 'a' wins both.
    seasons = [matchup_season(2024), matchup_season(2025)]
    profiles = compute_profiles(seasons, {}, {})

    a = profiles["a"]
    assert a["seasons_count"] == 2
    assert a["titles"] == 2 and sorted(y for y, _ in a["champ_years"]) == [2024, 2025]
    # Reg season 2-0 each year -> 4-0 all time.
    assert (a["reg"]["w"], a["reg"]["l"]) == (4, 0), a["reg"]
    # No playoff_teams list -> fallback counts the post-season game 'a' played
    # each season, so 2 appearances.
    assert a["berths"] == 2, a["berths"]

    # Head-to-head is symmetric: a beat b twice (weeks 1), b lost to a twice.
    assert a["h2h"]["b"]["w"] == 2 and profiles["b"]["h2h"]["a"]["l"] == 2


def test_rec_str():
    assert rec_str(4, 0, 0) == "4-0"
    assert rec_str(7, 6, 1) == "7-6-1"


def test_berths_use_winners_bracket_seeds():
    s = matchup_season(2025)
    s["playoff_teams"] = ["a", "c"]      # only these two made the winners bracket
    profiles = compute_profiles([s], {}, {})
    assert profiles["a"]["berths"] == 1 and profiles["c"]["berths"] == 1
    assert profiles["b"]["berths"] == 0 and profiles["d"]["berths"] == 0


def test_berths_fallback_without_seed_list():
    s = matchup_season(2025)              # no playoff_teams -> fallback counts the
    profiles = compute_profiles([s], {}, {})  # one post-season game's participants
    assert profiles["a"]["berths"] == 1 and profiles["d"]["berths"] == 1


def test_sacko_counts_last_place():
    # 4-team season; whoever finishes last (finish == team_count) gets a Sacko.
    profiles = compute_profiles([matchup_season(2025)], {}, {})
    last = max(profiles.values(), key=lambda p: p["seasons"][0]["finish"])
    assert last["seasons"][0]["team_count"] == 4
    assert last["sackos"] == 1 and last["sacko_years"] == [2025]
    # Exactly one Sacko handed out.
    assert sum(p["sackos"] for p in profiles.values()) == 1


def test_fmt_titles_half():
    assert fmt_titles(0.5) == "½"
    assert fmt_titles(2) == "2"
    assert fmt_titles(2.5) == "2½"


def test_co_champions_split_half_titles():
    # Two seasons; in 2024 the title is a co-championship shared by a and b.
    seasons = [matchup_season(2024), matchup_season(2025)]
    overrides = {"co_champions": {2024: ["a", "b"]}}
    profiles = compute_profiles(seasons, {}, overrides)
    # a: outright champ 2025 (1.0) + co-champ 2024 (0.5) = 1.5
    assert profiles["a"]["titles"] == 1.5, profiles["a"]["titles"]
    # b: only the 2024 co-championship = 0.5
    assert profiles["b"]["titles"] == 0.5, profiles["b"]["titles"]
    co_years = [y for y, is_co in profiles["a"]["champ_years"] if is_co]
    assert co_years == [2024]


def test_meaningless_games_excluded_from_records_and_h2h():
    # Build a double-elim season where the week-5 game between two 5th-8th
    # finishers is meaningless and carries an absurd score that must be ignored.
    season = {
        "season": 2025,
        "weeks_in_regular_season": 2,
        "final_standings": ["a", "b", "c", "d", "e", "f", "g", "h"],  # e..h are 5th-8th
        "teams": {},
        "matchups": [
            {"week": 1, "home": "a", "away": "b", "home_score": 100.0, "away_score": 90.0},
            {"week": 1, "home": "e", "away": "f", "home_score": 80.0, "away_score": 70.0},   # real
            {"week": 5, "home": "e", "away": "f", "home_score": 999.0, "away_score": 5.0, "playoff": True},  # meaningless
        ],
    }
    overrides = {"double_elim_6": [2025]}
    keys = meaningless_keys(season, overrides)
    assert (5, frozenset(("e", "f"))) in keys

    recs = {r["category"]: r for r in compute_records([season], {}, overrides)}
    # The 999 must NOT be the record — it came from a meaningless game.
    assert recs["Most Points in a Week"]["value"] != "999.00", recs["Most Points in a Week"]

    profiles = compute_profiles([season], {}, overrides)
    # The meaningless playoff game adds nothing: the e-vs-f head-to-head reflects
    # only the real regular-season game (1-0, not 1-1).
    assert (profiles["e"]["h2h"]["f"]["w"], profiles["e"]["h2h"]["f"]["l"]) == (1, 0)


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    run()
