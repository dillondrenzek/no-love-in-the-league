---
layout: page
title: Week 13 · 2026
permalink: /seasons/2026/week-13/
season_year: 2026
season_no: 13
week: 13
---
{% assign wk = site.data.weeks["2026-13"] %}
{% include week_detail.html wk=wk %}

{% if wk.state != "complete" %}
<h2>The Preview</h2>

<!-- Paste the preview below. Build the prompt with:
     python scripts/weekly_preview.py 2026 13
     Shows until the week is complete, then the recap takes over. -->

_Preview coming soon._
{% endif %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Build the prompt with:
     python scripts/weekly_recap.py 2026 13
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete. -->

_Recap coming soon._
{% endif %}
