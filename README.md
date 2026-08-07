# no-love-in-the-league

Website for The League — where there is no love.

A static site built with [Jekyll](https://jekyllrb.com/) and hosted on
GitHub Pages. League data (pulled manually from ESPN) lives in hand-edited
YAML files and is compiled into Markdown pages by small Python scripts.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design and conventions. The short
version: each season is one YAML file. At minimum it holds the final standings
(finish, team, record) pasted from ESPN; later you can add game scores and the
build scripts compute points and richer records from those.

## How it works

```
data/                    <- hand-edited YAML, the only thing you edit
  seasons/
    2014.yml ... 2025.yml   one file per season (final standings; scores optional)
  franchises.yml            owner mapping for future team pages (empty for now)

scripts/
  lib/                      shared pure functions (standings, records) — tested
  generate_history.py       champions + record book
  generate_standings.py     standings per season
  build.py                  runs every generator
  tests/test_lib.py         plain-python tests for lib

docs/                    <- Jekyll site (the GitHub Pages source)
  standings/index.md        generated — do not edit by hand
  history/index.md          generated — do not edit by hand
  index.md
  assets/css/style.scss     custom styling / branding
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

`.espn-cookies` is git-ignored, so your credentials never hit the repo or your
shell history. Then import everything and rebuild:

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

Requires Ruby + Bundler.

```
cd docs
bundle install
bundle exec jekyll serve
```

Then open http://localhost:4000.

## GitHub Pages setup

In the repo's Settings → Pages, set the source to the `main` branch,
`/docs` folder.
