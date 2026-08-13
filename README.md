# no-love-in-the-league

Website for The League — where there is no love.

A static site built with [Jekyll](https://jekyllrb.com/) and hosted on
GitHub Pages. League data (pulled manually from ESPN) lives in hand-edited
YAML files and is compiled into Markdown pages by small Python scripts.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and conventions. The short
version: each season is one YAML file. At minimum it holds the final standings
(finish, team, record) pasted from ESPN; later you can add game scores and the
build scripts compute points and richer records from those.

## What you edit vs. what's generated

**Edit these** (source of truth):

- `data/seasons/*.yml` — season results (usually written by the importer).
- `data/franchises.yml` — owners; edit the `name` field freely.
- `data/overrides.yml` — league rulings (co-champions, double-elim years).
- `data/season_notes.yml` — the per-year event bullets shown on the History page.
- `data/seasons/<year>.yml` `draft_order:` — an optional, hand-edited draft order
  (franchise ids, first pick first). The importer preserves it across re-imports;
  seasons without one just don't show a draft table.
- `docs/_layouts/`, `docs/_includes/`, `docs/*.md` templates (incl. the
  hand-written `docs/rulebook/index.md`), `docs/assets/main.scss` — the site's
  presentation (HTML/Liquid/CSS).

**Never hand-edit these** (rewritten by `scripts/build.py`):

- `docs/_data/*.yml` — pre-computed data the templates render.
- Generated pages under `docs/history/`, `docs/teams/*.md`, and
  `docs/seasons/*.md` (the per-season pages).

The pipeline is always: edit `data/` → `python scripts/build.py` → the generated
files are rewritten → Jekyll renders. Computation lives in Python; presentation
lives in the Liquid templates + includes.

## How it works

```
data/                    <- hand-edited YAML, the only thing you edit
  seasons/
    2014.yml ... 2025.yml   one file per season (final standings; scores optional)
  franchises.yml            owner mapping for future team pages (empty for now)

scripts/
  lib/                      shared pure functions (standings, records, teams) — tested
  generate_records.py       record book
  generate_standings.py     standings per season (History page)
  generate_teams.py         owner index + per-owner profile pages
  generate_seasons.py       per-season pages (/seasons/<year>/)
  import_espn.py            pull a season from ESPN
  update_season.sh          weekly: import one season + rebuild
  build.py                  runs every generator
  tests/test_lib.py         plain-python tests for lib

docs/                    <- Jekyll site (the GitHub Pages source); no theme gem
  _layouts/                 default / page / home layouts (our own)
  _includes/                head, header (nav), footer
  assets/main.scss          the single self-contained stylesheet
  standings/index.md        generated — do not edit by hand
  history/index.md          generated — do not edit by hand
  index.md
```

## Updating the site with new data

1. Download the relevant ESPN page(s) and edit the matching `data/seasons/<year>.yml`.
   For a new season, paste its final standings; to enrich an existing one, add game scores.
2. Rebuild every page:
   ```
   .venv/bin/python scripts/build.py
   ```
3. Commit both the `data/` changes and the regenerated `docs/` files, then push.
   GitHub Pages rebuilds the site automatically.

## Importing a season's scores from ESPN

`scripts/import_espn.py` pulls a full season (scores + final standings) from ESPN
and writes `data/seasons/<year>.yml` plus the owner mapping in
`data/franchises.yml`. It's a local dev tool — its dependency isn't needed to
build the site.

```
.venv/bin/pip install -r requirements-dev.txt   # one-time: installs espn-api
cp .espn-cookies.example .espn-cookies           # then paste your cookie values in
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

## Keeping the site current during the season

Run the weekly updater — it imports the one season and rebuilds:

```
scripts/update_season.sh              # the current calendar year
scripts/update_season.sh 2026         # a specific season
```

Then review with `git diff` and push; GitHub Pages redeploys automatically.
About once a week during the season is plenty.

**In-progress vs. final.** Mid-season, ESPN hasn't assigned final placements, so
the importer orders teams by their current standing and writes `status:
in_progress` into `data/seasons/<year>.yml`. An in-progress season:

- shows **current standings** on its own page at `/seasons/<year>/`, but
- is deliberately **left out** of all-time standings, records, owner profiles,
  and the homepage's reigning-champ/Sacko hero — so a half-season never skews
  the record book.

When the season ends, re-run the updater once more. ESPN now reports final
placements, the importer drops the `in_progress` flag, and the season flows into
the all-time numbers automatically.

**Before games are played** (e.g. right after the draft), the season imports with
no matchups; its page just shows the draft order (if you've filled one in) until
results start coming in.

## Season pages

Every season has a page at `/seasons/<year>/`, generated by
`scripts/generate_seasons.py`. Season numbers count from 2014 (so 2026 is Season
13). The current season is linked from the nav and the homepage.

To show a draft order on a season's page, add an optional `draft_order:` list of
franchise ids (first pick first) to that `data/seasons/<year>.yml`. It's the one
field in a season file you hand-edit — the importer preserves it on every
re-import. Leave it out and no draft table appears.

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
