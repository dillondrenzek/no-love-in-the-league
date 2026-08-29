"""Generate a fair, reshuffled regular-season schedule.

The league's format (12 teams, 14 weeks) is a full single round-robin — everyone
plays everyone once, 11 weeks — plus 3 weeks of rematches, so every team ends up
playing exactly 3 opponents twice and the other 8 once (14 games). That's already
balanced by construction: the only yearly freedom is *which* matchups fall in
which week and which opponents get the rematches. This module reshuffles those
each year while keeping the balance exact.

Pure functions over plain lists (no I/O, no network) so the properties are easy
to test. See scripts/generate_schedule.py for the CLI that feeds ESPN.
"""

import random


def round_robin(teams):
    """Circle method: for n teams, n-1 rounds each a list of (a, b) pairs. Every
    pair meets exactly once across the rounds. Adds a bye if n is odd."""
    ts = list(teams)
    if len(ts) % 2:
        ts.append(None)                      # odd -> one bye per round
    n = len(ts)
    arr = ts[:]
    rounds = []
    for _ in range(n - 1):
        pairs = [(arr[i], arr[n - 1 - i]) for i in range(n // 2)
                 if arr[i] is not None and arr[n - 1 - i] is not None]
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]   # rotate, first fixed
    return rounds


def generate_schedule(teams, weeks=14, seed=None):
    """A `weeks`-long schedule for `teams`: a full round-robin plus enough
    repeated rounds to reach `weeks`, week order and home/away randomized.

    Returns a list of weeks; each week is a list of (home, away) tuples. Balanced
    by construction: every team plays `weeks` games and exactly (weeks-(n-1))
    opponents twice. Deterministic for a given seed so a year is reproducible.
    """
    ts = list(teams)
    n = len(ts)
    if n < 2:
        raise ValueError("need at least two teams")
    if n % 2:
        raise ValueError("odd team counts would need byes; league runs even")
    rr_rounds = n - 1                        # weeks in a single round-robin
    extra = weeks - rr_rounds
    if extra < 0:
        raise ValueError(f"{weeks} weeks < {rr_rounds}-week single round-robin")
    if extra > rr_rounds:
        raise ValueError(f"{weeks} weeks needs more than a double round-robin")

    rng = random.Random(seed)
    ts_base = list(ts)
    rng.shuffle(ts_base)
    base = round_robin(ts_base)              # a full round-robin: every pair once

    # The rematch weeks come from a *separate* round-robin rotation, so each is a
    # genuine perfect matching but not a carbon copy of a base week. Every rematch
    # pair already appears once in `base`, so it becomes a "twice" — exactly `extra`
    # rematches per team, no pair more than twice. Re-roll if a whole week repeats.
    schedule = None
    for _ in range(200):
        ts_alt = list(ts)
        rng.shuffle(ts_alt)
        alt = round_robin(ts_alt)
        extra_rounds = rng.sample(alt, extra)
        weeks_rounds = [list(r) for r in base] + [list(r) for r in extra_rounds]
        keys = [frozenset(frozenset(p) for p in wk) for wk in weeks_rounds]
        if len(set(keys)) == len(keys):      # no two weeks are the same slate
            schedule = weeks_rounds
            break
    if schedule is None:                     # astronomically unlikely fallback
        schedule = [list(r) for r in base] + [list(base[i])
                                              for i in rng.sample(range(rr_rounds), extra)]
    rng.shuffle(schedule)                    # shuffle the week order

    weeks_out = []
    for pairs in schedule:
        games = []
        for a, b in pairs:
            if rng.random() < 0.5:           # home/away is cosmetic in fantasy
                a, b = b, a
            games.append((a, b))
        weeks_out.append(games)
    return weeks_out


# --- inspection ------------------------------------------------------------- #

def pair_counts(schedule):
    """{frozenset({a, b}): times they meet} across the whole schedule."""
    from collections import Counter
    return Counter(frozenset(g) for wk in schedule for g in wk)


def per_team(schedule):
    """{team: {'games': int, 'twice': [opponents played twice]}}."""
    from collections import Counter, defaultdict
    opp = defaultdict(Counter)
    for wk in schedule:
        for a, b in wk:
            opp[a][b] += 1
            opp[b][a] += 1
    return {t: {"games": sum(c.values()),
                "twice": sorted(o for o, n in c.items() if n >= 2)}
            for t, c in opp.items()}


def validate(schedule, teams, weeks):
    """Raise AssertionError unless the schedule is balanced and complete."""
    n = len(teams)
    stats = per_team(schedule)
    assert set(stats) == set(teams), "every team must appear"
    for t, s in stats.items():
        assert s["games"] == weeks, f"{t} has {s['games']} games, expected {weeks}"
    expected_twice = weeks - (n - 1)
    for t, s in stats.items():
        assert len(s["twice"]) == expected_twice, \
            f"{t} plays {len(s['twice'])} opponents twice, expected {expected_twice}"
    counts = pair_counts(schedule)
    assert all(v in (1, 2) for v in counts.values()), "pairs meet once or twice"
    assert len(counts) == n * (n - 1) // 2, "every pair must meet at least once"
    for wk in schedule:
        seats = [x for g in wk for x in g]
        assert len(seats) == len(set(seats)) == n, "each team plays once per week"
    return True
