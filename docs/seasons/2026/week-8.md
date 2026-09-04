---
layout: page
title: Week 8 · 2026
permalink: /seasons/2026/week-8/
season_year: 2026
season_no: 13
week: 8
---
{% assign wk = site.data.weeks["2026-8"] %}
{% include week_detail.html wk=wk %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Build the prompt with:
     python scripts/weekly_recap.py 2026 8
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete. -->

_Recap coming soon._
{% endif %}
