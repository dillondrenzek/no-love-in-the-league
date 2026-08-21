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
- `data/seasons/<year>.yml` `draft_order:` — an optional, hand-edited draft order
  (franchise ids, first pick first). The importer preserves it across re-imports;
  seasons without one just don't show a draft table.
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
The League's own dependency-free ESPN client. It's a private repo installed over
HTTPS, so pip reuses the GitHub credentials you already push/pull with — no token
in the repo. Only your machine needs it — GitHub Pages builds the site from
`requirements.txt` alone and never touches it.

```
git -C ~/Codebase/espn-fantasy-cli push origin v0.1.1  # once: publish the pinned tag
.venv/bin/pip install -r requirements-dev.txt          # installs the-league-espn-api
cp .espn-cookies.example .espn-cookies                 # then paste your cookie values in
```

Actively hacking on the client too? Install it editable instead —
`pip install -e ~/Codebase/espn-fantasy-cli` — no network or auth at all.

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
owner profiles, History notes, and a per-season trades section). Fetching trades
makes one request per week, so imports are a little slower. Trades only exist in a
season file once it's imported under this version — re-run the importer once per
past season (or `scripts/import_all.sh`) to backfill them.

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
