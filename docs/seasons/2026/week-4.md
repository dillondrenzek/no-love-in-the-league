---
layout: page
title: Week 4 · 2026
permalink: /seasons/2026/week-4/
season_year: 2026
season_no: 13
week: 4
---
{% assign wk = site.data.weeks["2026-4"] %}
{% include week_detail.html wk=wk %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Build the prompt with:
     python scripts/weekly_recap.py 2026 4
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete. -->

_Recap coming soon._
{% endif %}
