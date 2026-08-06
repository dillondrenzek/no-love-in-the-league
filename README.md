# no-love-in-the-league

Website for The League — where there is no love.

A static site built with [Jekyll](https://jekyllrb.com/) and hosted on
GitHub Pages. League data (pulled manually from ESPN) lives in hand-edited
YAML files and is compiled into Markdown pages by a small Python script.

## How it works

```
data/               <- hand-edited YAML, source of truth
  history/
    champions.yml
    records.yml

scripts/
  generate_history.py   <- reads data/history/*.yml, writes docs/history/index.md

docs/                <- Jekyll site (this is the GitHub Pages source)
  history/index.md      <- generated, do not edit by hand
  index.md
  assets/css/style.scss <- custom styling / branding
```

## Updating the site with new data

1. Pull the latest info from ESPN and edit the relevant file(s) under `data/`.
2. Regenerate the Markdown pages:
   ```
   .venv/bin/python scripts/generate_history.py
   ```
3. Commit both the `data/` changes and the regenerated `docs/` files, then push.
   GitHub Pages rebuilds the site automatically.

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
