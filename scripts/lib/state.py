"""Season lifecycle state — the deterministic source of truth for how a season
should display and how much of it counts toward all-time stats.

States, in order:

    preseason → pre_draft → drafting → season → playoffs → complete

`complete` is terminal and absorbs what issue #31 called "postseason" (all games
played, final standings, Shiva/Sacko awarded). See design/season-state.md.

A season file carries `state:`. During the migration, older files may still only
carry the legacy `status: in_progress` flag (→ `season`) or nothing (→ `complete`);
`state_of` normalizes all three so callers only ever deal with a real state.
"""

STATE_ORDER = ["preseason", "pre_draft", "drafting", "season", "playoffs", "complete"]
_INDEX = {s: i for i, s in enumerate(STATE_ORDER)}


def state_of(season):
    """The normalized lifecycle state for a season dict.

    Prefers an explicit `state:`; falls back to the legacy `status: in_progress`
    flag (→ 'season'); defaults to 'complete' for finished seasons with neither.
    """
    s = (season.get("state") or "").strip()
    if s in _INDEX:
        return s
    if season.get("status") == "in_progress":
        return "season"
    return "complete"


def state_index(state):
    """Position in STATE_ORDER; unknown states sort last (treated as newest)."""
    return _INDEX.get(state, len(STATE_ORDER))


def state_at_least(season, threshold):
    """True when a season's state is `threshold` or later in the lifecycle."""
    return state_index(state_of(season)) >= _INDEX[threshold]


def detect_state(*, draft_order_set, draft_run, reg_season_done, playoffs_scheduled,
                 all_games_complete):
    """The state implied by the ESPN signals, most-advanced first.

    Keys only off things ESPN sets when they actually happen (draft run, games
    decided) — never off pre-filled seeds/ranks. Note it never returns `drafting`:
    that transition (keepers locked, ~day before the draft) isn't exposed by the
    API and is set by hand; `advance_state` preserves it."""
    if all_games_complete:
        return "complete"
    if reg_season_done and playoffs_scheduled:
        return "playoffs"
    if draft_run:
        return "season"
    if draft_order_set:
        return "pre_draft"
    return "preseason"


def advance_state(existing, detected, locked=False):
    """The state to store: forward-only (never regress), unless `locked`, in which
    case the hand-set `existing` is kept. Forward-only is what preserves a manual
    `drafting` until the draft actually runs (then detection advances it)."""
    if locked:
        return existing
    return existing if state_index(existing) >= state_index(detected) else detected


def is_in_progress(season):
    """A season whose data is still arriving — anything not yet `complete`.

    This is the state-aware replacement for the old `status == 'in_progress'`
    check: a pre-draft, drafting, live, or playoff season all count as in
    progress and stay out of all-time stats until they reach `complete`.
    """
    return state_of(season) != "complete"
