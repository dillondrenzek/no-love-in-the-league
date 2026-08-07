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


def test_owner_profiles_totals_and_h2h():
    # Same franchises across two seasons; 'a' wins both.
    seasons = [matchup_season(2024), matchup_season(2025)]
    profiles = compute_profiles(seasons, {}, {})

    a = profiles["a"]
    assert a["seasons_count"] == 2
    assert a["titles"] == 2 and sorted(y for y, _ in a["champ_years"]) == [2024, 2025]
    # Reg season 2-0 each year -> 4-0 all time.
    assert (a["reg"]["w"], a["reg"]["l"]) == (4, 0), a["reg"]
    # 'a' has a playoff loss to 'd' each season (200-60), so playoff record 0-2.
    assert (a["playoff"]["w"], a["playoff"]["l"]) == (0, 2), a["playoff"]

    # Head-to-head is symmetric: a beat b twice (weeks 1), b lost to a twice.
    assert a["h2h"]["b"]["w"] == 2 and profiles["b"]["h2h"]["a"]["l"] == 2


def test_rec_str():
    assert rec_str(4, 0, 0) == "4-0"
    assert rec_str(7, 6, 1) == "7-6-1"


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
    # The meaningless playoff game adds nothing: no playoff win, and the e-vs-f
    # head-to-head reflects only the real regular-season game (1-0, not 1-1).
    assert profiles["e"]["playoff"]["w"] == 0
    assert (profiles["e"]["h2h"]["f"]["w"], profiles["e"]["h2h"]["f"]["l"]) == (1, 0)


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    run()
