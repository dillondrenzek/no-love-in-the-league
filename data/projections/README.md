# Weekly projection snapshots

One file per week: `<year>-week-<nn>.yml`, written by
`scripts/snapshot_projections.py` (run automatically by the
**Weekly projection snapshot** GitHub Action on Thursday afternoons, before any
game is played).

Each file is the **pre-game "line"** — every team's projected total (sum of its
starters' ESPN projections) at capture time — kept so results can be compared
against expectations later. Write-once: a week's file is never overwritten, so
the first pre-game capture stands.

```yaml
season: 2026
week: 3
captured_at: "2026-09-24T20:00:00+00:00"   # UTC
projections:
  - team_id: 12
    manager_id: "{ABC-123}"        # owner SWID — joinable to a franchise
    team_name: "The ChoSimba Ones"
    projected: 118.4
```

Nothing consumes these yet — they're captured now so the data accumulates for a
future "vs. projections" stat. They are independent of `data/seasons/*.yml`; the
importer never touches them.
