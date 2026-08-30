# Season State — design note

Design for a deterministic per-season lifecycle state, per
[issue #31](https://github.com/dillondrenzek/no-love-in-the-league/issues/31).

## Decisions (resolved)

1. **State names:** snake_case, as originally named — `preseason`, `pre_draft`,
   `drafting`, `season`, `playoffs`, `complete`.
2. **Entering `drafting`:** by hand-editing `state:` in the YAML (no CLI flag).
3. **`postseason` folded into `complete`** for now — one terminal state that owns
   final standings + Shiva/Sacko. Can split later if needed.
4. **Keeper-cost pre-draft view: deferred** — not implemented yet, tracked
   separately (the keeper-cost rule isn't encoded anywhere yet).
5. **Backfill:** 2014–2025 → `complete`, 2026 → `season`. **Complete seasons are
   never re-edited by a normal import** — the importer skips writing a `complete`
   season unless a future `--patch` flag says otherwise (optional, not built now).

## Goal

Give every season an explicit **state** so the site can decide *deterministically*
how to display it, and so the importer knows *exactly which data to pull*. Today a
single boolean (`status: in_progress`) drives everything; it can't distinguish a
pre-draft season from a live one from a finished-but-not-final one, and it lets
ESPN's habit of pre-filling fields (playoff seeds, final ranks) leak wrong
conclusions into the page.

## Core principle: render off stored state, detect at import time

- **Rendering is always deterministic.** Each `data/seasons/<year>.yml` carries a
  `state:` field. The generators/templates switch on that value and never infer
  state from the presence of matchups, seeds, or ranks at build time.
- **Detection happens only when you pull data** — inside `import_espn.py`, invoked
  by `scripts/update_season.sh` (the entry point stays exactly as it is). The
  importer computes a *detected* state from robust API signals and advances the
  stored value **forward only**.
- **Manual override wins.** You can hand-set `state:` (and the importer won't
  regress it). Exactly one transition is routinely manual — entering `drafting` —
  because ESPN doesn't expose pre-draft keeper locks.

This keeps the live site fully deterministic while still automating ~5 of the 6
transitions.

## The state field

```yaml
# data/seasons/<year>.yml
state: season          # one of the six below (replaces `status: in_progress`)
state_locked: false    # optional; true = importer must not change `state`
```

Ordered lifecycle (forward-only under automation):

```
preseason → pre_draft → drafting → season → playoffs → complete
```

`state_order = [preseason, pre_draft, drafting, season, playoffs, complete]`
gives us a comparable index for "advance forward only" and for gating rules like
"≥ season". (`complete` is terminal and absorbs what the issue called
"postseason": all games played, final standings, titles awarded.)

## Transitions & detection signals

All signals come from the `the-league-espn-api` client. The rule of thumb:
**key off things ESPN sets when they actually happen (draft run, game decided),
never off things ESPN pre-fills (`playoffSeed`, `rankCalculatedFinal`).**

| → State | Trigger | Client signal | Detect? | Set by |
|---|---|---|---|---|
| **preseason** | League activated for the new year | `League(year).teams()` returns teams (no 404); `draftSettings.pickOrder` empty | ✅ | auto |
| **pre_draft** | Draft order set | `mSettings.settings.draftSettings.pickOrder` non-empty | ✅ | auto |
| **drafting** | Keepers locked (~day before draft) | *none — not exposed pre-draft* | ❌ | **manual** |
| **season** | Draft has run | `draft()` returns picks with real `player_id` (≠ -1) | ✅ | auto |
| **playoffs** | Final regular-season week complete | every `season().matchups` game with `week ≤ matchupPeriodCount` has `winner ≠ UNDECIDED`, and a playoff-week game exists | ✅ | auto |
| **complete** | All games (incl. playoffs) played | `season()["complete"] == true` (last week's games all decided) | ✅ | auto |

Notes:

- **preseason vs pre_draft** hinges only on `pickOrder`. Both are "no games";
  the difference is whether we can show the draft slot order yet.
- **drafting** is the one blind spot. It exists so that in the ~24h between
  "keepers locked" and "draft run" the page hides rosters/matchups. The importer
  cannot detect entry into `drafting`; it *can* detect the exit (draft ran →
  `season`). So: you set `drafting` by hand; the next import that sees a completed
  draft advances it to `season`.
- **playoffs**: trust *week completion*, not `playoffSeed`. ESPN populates seeds
  early; a decided final regular week is the real trigger. The winners-bracket
  seed list is still read for the bracket, just not used to decide the state.
- **complete** flips when the season's last games are all decided
  (`season()["complete"]`). The issue's separate "archived when next year is
  generated" nuance is dropped for now (postseason + complete are one state); the
  season-page banner can still vary on "is there a newer season?" without a
  distinct state.

## Importer behavior (inside `import_espn.py`, run by `update_season.sh`)

`update_season.sh <year>` is unchanged as the entry point: it calls
`import_espn.py <year>` then `build.py`. The new logic lives in the importer:

1. Read the current stored `state` (and `state_locked`) from the season file.
2. Compute `detected_state` from the signals above.
3. Decide the written state:
   - If `state_locked: true` → keep the stored state untouched (still print the
     detected one as a hint).
   - Else advance **forward only**: `new = max(stored, detected)` by
     `state_order`. Never regress (guards against an API blip reporting an earlier
     phase).
   - Special case `drafting`: it's never *detected*, so if the stored state is
     `drafting` and nothing newer is detected yet, it stays `drafting`.
4. If `detected_state` is *behind* the stored state, print a warning (something
   looks off — e.g. you're marked `season` but ESPN shows no completed draft).
5. Write `state:` into the season YAML (preserved/emitted like the other fields).

**Complete seasons are left alone.** If the stored state is `complete`, a normal
import is a no-op on that file (print "skipping complete season 2019") — history
doesn't get rewritten by routine pulls. A future optional `--patch <year>` flag
would allow re-pulling a complete season on purpose (e.g. when a new feature needs
a field backfilled). Not built now.

The importer also uses the state to **pull only what's relevant** (and skip calls
that will 404 or return placeholders):

| State | Pulls | Skips |
|---|---|---|
| preseason | teams, settings | draft, matchups, trades |
| pre_draft | teams, settings, `draft()` (for pick order only) | matchups |
| drafting | teams, settings, draft order, keepers (hand-entered) | matchups |
| season | teams, settings, matchups, trades, keepers | — |
| playoffs | matchups (incl. playoff bracket), trades | — |
| postseason | final matchups, final standings, trades, keepers | — |
| complete | (archival re-pull only if asked) | — |

Entering `drafting` (the one undetectable transition) is done by **hand-editing
`state: drafting`** in the season file — no CLI flag. The importer treats a
hand-set state as authoritative and won't regress it.

## Display rules per state

What the **season page** shows, and what the season contributes to **site-wide
aggregates**. This replaces the current binary `in_progress` gate with a
state-indexed one.

| State | Season page | Owner profiles | Records / berths / titles |
|---|---|---|---|
| preseason | "New season" active page; no rosters/matchups | season **not** shown | nothing |
| pre_draft | Draft order + previous rosters w/ keeper costs | not shown | nothing |
| drafting | Locked-down: draft order only, no rosters/matchups | not shown | nothing |
| season | **Full standings table** (History-style, header **"Rank"** not "Finish"); weekly pages (2026+); trades/keepers | season **shown**, updates as data arrives | records update; **no** berths/titles yet |
| playoffs | Standings + bracket/seeding | shown | **playoff berths** incremented |
| complete | Final standings + bracket results (archival) | shown | **Shiva/Sacko** titles + counts awarded; fully counted |

Aggregation gating (concrete predicates, keyed off `state_order` index):

- **In profiles / owner tables:** `state ≥ season`. *(Slice 4 — done, in
  `lib/teams.compute_profiles`.)*
- **Playoff berths:** `state ≥ playoffs`. *(Slice 4 — done; fixes ESPN's
  pre-filled `playoff_teams` phantom-counting berths on a live season.)*
- **Titles (Shiva) & Sacko:** `state == complete`. *(Slice 4 — done.)*
- **Record book (best/worst record, most points, championships):** stays
  **complete-only** for now. Counting a live 2-0 season as the "best record" is
  misleading, so season-aggregate records wait for `complete`; trades and the 1.01
  record already include the live season. A future refinement can split per-week
  score records (safe to show live) from season-aggregate records.

This makes the earlier ad-hoc rules explicit: a live season counts its record the
moment it's `season`, earns berths at `playoffs`, and only crowns a champ/Sacko at
`postseason`.

## Week state (coming later — design hook only)

Not built now, but the season state is designed so it can slot in without rework.
When we add it, a **week** in a `season`/`playoffs` state carries its own status:

- `completed` — every game that week has `winner ≠ UNDECIDED`.
- `current` — the earliest week that still has `UNDECIDED` games (ESPN's active
  scoring period).
- `future` — beyond current.

This is a pure function of `season().matchups` (the `winner` field) plus the
current scoring period, so it's always auto-derived — no manual input, no new
source of truth. The weekly recap pages (already built) will consume it to label
Week N and to decide "generate a recap page" (only for `completed`/`current`
weeks, 2026+). Season state stays independent of week state: adding week state
later is additive.

## Data model change & migration

- Replace `status: in_progress` with `state:` in the season schema. (`status`
  can be kept as a deprecated alias for one release if convenient, but the intent
  is to retire it.)
- `load_seasons()` gains state awareness: instead of `include_in_progress`, callers
  ask for a threshold, e.g. `load_seasons(min_state="season")` or filter on the
  returned `state`. The current `include_in_progress=True/False` maps to
  `state ≥ season` vs `state == complete`/postseason.
- **Backfill:** 2014–2025 → `state: complete`. 2026 → its true current state
  (today: `season`, since the draft is done). One-time script or hand-edit.

## Rollout (vertical slices)

1. **Field + migration.** Add `state:` to every season file; add `state_order`
   and helpers to `lib/`. No behavior change yet (map `complete`≈old-final,
   `season`≈old-in_progress).
2. **Render switch.** Season page + `lib` gating read `state` instead of
   `status`. Ship the `season` view first: full standings table with the **Rank**
   header. Verify each state renders the right blocks.
3. **Importer detection.** `import_espn.py` computes + writes state (forward-only,
   lock-aware); add `--set-state`/`--lock-state`. `update_season.sh` unchanged.
4. **Aggregation gating.** Move profiles/records/berths/titles onto the
   state predicates above; delete the old `in_progress` special-cases.
5. **(Later) Week state.** Derive per-week status; wire weekly pages to it.

## Deferred / follow-up

- **Keeper-cost pre-draft view** — the `pre_draft` state should show previous
  rosters with keeper costs "according to the keeper cost rule." That rule isn't
  encoded anywhere yet; this is tracked as its own piece of work and is not part
  of the state rollout.
- **`--patch <year>` flag** — to deliberately re-pull a `complete` season when a
  new feature needs a backfill. Optional; the default is that complete seasons are
  never touched by a routine import.
- **Splitting `complete` back into `postseason` + `complete`** — only if we later
  need distinct behavior for "games done" vs "archived."
