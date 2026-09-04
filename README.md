# no-love-in-the-league

Website for The League — where there is no love.

A static site built with [Jekyll](https://jekyllrb.com/) and hosted on
GitHub Pages. League data (pulled manually from ESPN) lives in hand-edited
YAML files and is compiled into Markdown pages by small Python scripts.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and conventions. The short
version: each season is one YAML file of matchups (imported from ESPN), and the
build scripts compute standings, records, and owner stats from those.

## What you edit vs. what's generated

**Edit these** (source of truth):

- `data/seasons/*.yml` — season results (usually written by the importer).
- `data/franchises.yml` — owners; edit the `name` field freely.
- `data/overrides.yml` — league rulings (co-champions, double-elim years).
- `data/season_notes.yml` — the per-year event bullets shown on the History page.
- `data/seasons/<year>.yml` `draft_order:` — the draft board (franchise ids, 1.01
  first). Locked, hand-maintained data: the importer preserves it verbatim across
  re-imports (remove the block to hide the draft table). It drives the season-page
  draft table, the Draft Order History heatmap, and the "Most Times Drafting 1.01"
  record.
- `docs/_layouts/`, `docs/_includes/`, `docs/*.md` templates (incl. the
  hand-written `docs/rulebook/index.md`), `docs/assets/main.scss` — the site's
  presentation (HTML/Liquid/CSS).

**Never hand-edit these** (rewritten by `scripts/build.py`):

- `docs/_data/*.yml` — pre-computed data the templates render.

**Scaffolded once, then yours to edit:**

- `docs/teams/*.md` and `docs/seasons/*.md` — the per-owner and per-season pages.
  The build only creates one when it's missing; it never overwrites an existing
  page. Edit them freely. To regenerate a fresh stub, delete the file and run
  `scripts/build.py`. (They render the generated `docs/_data/*.yml` through
  includes, so their tables still update on rebuild — unless you replace the
  include with your own hand-written content.)

The pipeline is always: edit `data/` → `python scripts/build.py` → the generated
files are rewritten → Jekyll renders. Computation lives in Python; presentation
lives in the Liquid templates + includes.

## How it works

```
data/                    <- hand-edited YAML (or importer-written); source of truth
  seasons/2014.yml … 2026.yml   one file per season (matchups + metadata)
  franchises.yml                owner ↔ franchise mapping
  overrides.yml                 league rulings (co-champions, double-elim years)
  season_notes.yml              per-year event bullets (History)

scripts/
  lib/                      shared, tested pure functions (standings, records, teams, …)
  generate_records.py       record book
  generate_standings.py     per-season standings (History page)
  generate_teams.py         owner index + per-owner pages
  generate_seasons.py       per-season pages (/seasons/<year>/)
  import_espn.py            pull a season from ESPN
  update_season.sh          weekly: import one season + rebuild
  build.py                  runs every generator
  tests/test_lib.py         plain-python tests for lib

docs/                    <- themeless Jekyll site (GitHub Pages source)
  _layouts/                 default · home · page · owner · season
  _includes/                components + compositions + chrome (head/header/footer)
  _data/*.yml               generated — never hand-edit
  assets/main.scss          one stylesheet (:root color tokens, .num numeric cells)
  index.md · history/ · records/ · teams/ · rulebook/ · feedback/   pages
  teams/<id>.md · seasons/<year>.md   generated once, then hand-editable
```

To get new data in, import it (below) rather than editing season files by hand.

## Importing a season's scores from ESPN

`scripts/import_espn.py` pulls a full season (scores + final standings) from ESPN
and writes `data/seasons/<year>.yml` plus the owner mapping in
`data/franchises.yml`. It's a local dev tool — its dependency isn't needed to
build the site.

The data comes through [the-league-espn-api](https://github.com/dillondrenzek/espn-fantasy-cli),
The League's own ESPN client.

```
.venv/bin/pip install -r requirements-dev.txt          # installs the-league-espn-api
cp .espn-cookies.example .espn-cookies                 # then paste your cookie values in
```

The importer reads your two cookie values straight from `.espn-cookies` (which
is git-ignored), so nothing is exported into your shell or saved in shell
history. Then import everything and rebuild:

```
scripts/import_all.sh                 # all seasons, then rebuild
scripts/import_all.sh 2025            # or just one/some seasons
```

To preview a single season without writing anything:

```
.venv/bin/python scripts/import_espn.py 2025 --stdout
```

The importer prints the regular-season records it computed — eyeball them against
ESPN's final standings. Supplying cookies is what populates owner names and lets
the same owner keep one franchise id across seasons.

It also captures each season's **completed trades** (used for the record book,
owner profiles, History notes, and a per-season trades section) and **keepers**
(the player each team kept and the round it cost, shown on owner profiles and at
the bottom of season pages). Fetching trades makes one request per week, so imports
are a little slower. Trades and keepers only exist in a season file once it's
imported under this version — re-run the importer once per past season (or
`scripts/import_all.sh`) to backfill them. (Keepers began in 2023.)

### Filling in trade detail, one manager at a time

ESPN reveals a trade's *contents* (the players and picks) only to the accounts
that were in it. With just your cookie, trades you weren't part of show up as
"Trade Accepted" with no detail. As other managers hand over their cookie, import
each one and it **merges in** — additively, by ESPN trade id, so a new manager's
detail never clobbers what an earlier import recorded:

```
scripts/import_manager.sh ~/zach-cookies            # trade-era seasons, then build
scripts/import_manager.sh ~/zach-cookies 2023 2024  # just these seasons
```

You don't have to keep anyone's cookie afterward — the detail is already written to
the season files. Each season tracks `trades_known_for` (whose count is exact) and
`trades_complete` (every trade detailed). One-time note: season files imported
*before* trades carried an `id` are re-established with ids on the next full
import, so run `scripts/import_all.sh` once (with whatever cookies you have) before
relying on the one-at-a-time merge.

## Keeping the site current during the season

Run the weekly updater — it imports the one season and rebuilds:

```
scripts/update_season.sh              # the current calendar year
scripts/update_season.sh 2026         # a specific season
```

Then review with `git diff` and push; GitHub Pages redeploys automatically.
About once a week during the season is plenty.

**Lifecycle state.** Every season carries a `state:` (`preseason → pre_draft →
drafting → season → playoffs → complete`) that the whole site renders off — see
[design/season-state.md](design/season-state.md). The importer detects the state
from ESPN each run and advances it **forward only**; a season that isn't yet
`complete` is deliberately **left out** of all-time standings, records, owner
profiles, and the homepage hero, so a half-season never skews the record book. It
flows into the all-time numbers once it reaches `complete`.

Two states are hand-controlled: set `state: drafting` yourself in the ~day between
keepers locking and the draft (ESPN can't tell us that), and add `state_locked:
true` to pin a state against auto-advance. **Complete seasons are frozen** — a
routine `update_season.sh` skips them so history isn't rewritten; pass `--patch`
to `import_espn.py` to re-import one on purpose.

## Season pages

Every season has a page at `/seasons/<year>/`, generated by
`scripts/generate_seasons.py`. Season numbers count from 2014 (so 2026 is Season
13). The current season is linked from the nav and the homepage.

To show a draft order on a season's page, add an optional `draft_order:` list of
franchise ids (first pick first) to that `data/seasons/<year>.yml`. It's the one
field in a season file you hand-edit — the importer preserves it on every
re-import. Leave it out and no draft table appears.

## Weekly pages (previews & recaps)

For a live season (2026+), every regular-season week gets its own page at
`/seasons/<year>/week-<n>/`, scaffolded automatically by the build. Each week has
a **state** derived from its games:

- **future** — no game has a score yet; the scoreboard lists the matchups (no
  scores) and the page shows a **Preview**.
- **in_progress** — some games have live scores but not all are final; the
  scoreboard shows live scores. Still a **Preview**; season stats don't move yet.
- **complete** — every game is final; the scoreboard shows finals + a winner and
  a highlights strip (top/low score, biggest blowout, closest call), and the page
  shows a **Recap** instead of the preview. Season stats fold in now.

So each page carries two hand-written, AI-generated pieces that swap on state: a
**Preview** while the week is upcoming/live, then a **Recap** once it's done. Both
are repo-stored, reusable agent specs anyone can run:

- `agents/weekly-preview.md` — a forward-looking hype/oddsmaker voice (column +
  Game of the Week / Lock / Upset / Bold Prediction).
- `agents/weekly-recap.md` — a backward-looking trash-talk voice (column + awards).

**Writing a preview** (week is future or in progress):

1. `python scripts/weekly_preview.py <year> <week>` — writes a ready-to-paste
   prompt to `recaps/<year>-week-<nn>.preview.prompt.md` (git-ignored): the
   preview spec + each matchup's context (both owners' all-time record, titles,
   best finish, and the all-time head-to-head).
2. Paste it into Claude (or any model) → paste the reply into the week page under
   **The Preview**.
3. `python scripts/build.py`.

**Writing a recap** (week is complete):

1. **Import the finished week** — `scripts/update_season.sh <year>` so its final
   scores land in `data/seasons/<year>.yml` and the week flips to complete.
2. `python scripts/weekly_recap.py <year> <week>` — writes
   `recaps/<year>-week-<nn>.prompt.md`: the recap spec + the week's scoreboard and
   highlights. (Refuses to run until the week is complete.)
3. Paste it into Claude → paste the reply into the week page under **The Recap**.
4. `python scripts/build.py`.

The scoreboard/highlights and each week's state are always regenerated from the
imported matchups (`scripts/generate_weeks.py` → `docs/_data/weeks.yml`); only the
preview/recap prose is hand-pasted, and each shows only in the right state, so a
re-import that corrects a score or flips a week to complete just needs a rebuild.
Playoff weeks are handled separately (not yet built).

## Running the tests

```
.venv/bin/python scripts/tests/test_lib.py
```

## Local setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Previewing the Jekyll site locally (optional)

Requires Ruby (v3+) + Bundler.

```
cd docs
bundle install
bundle exec jekyll serve
```

Then open http://localhost:4000.

## GitHub Pages setup

In the repo's Settings → Pages, set the source to the `main` branch,
`/docs` folder.
