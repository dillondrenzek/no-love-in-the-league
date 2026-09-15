---
layout: page
title: Week 4 · 2026
permalink: /seasons/2026/week-4/
season_year: 2026
season_no: 13
week: 4
---
{% assign wk = site.data.weeks["2026-4"] %}
{% include sections/week_detail.html wk=wk %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Prep the facts with:
     python scripts/weekly_recap.py 2026 4
     then have your agent (agents/weekly-recap.md) write it.
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete, and sits above the preview. -->

_Recap coming soon._
{% endif %}

<h2>The Preview</h2>

<!-- Paste the preview below. Prep the facts with:
     python scripts/weekly_preview.py 2026 4
     then have your agent (agents/weekly-preview.md) write it.
     The preview stays at the bottom of the page all season, below the recap. -->

_Preview coming soon._
