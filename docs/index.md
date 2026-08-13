---
layout: home
title: Home
---

{% assign latest = site.data.standings.seasons[0] %}
{% assign champ = latest.rows[0] %}
{% assign sacko = latest.rows | last %}

<section class="hero">
  <h1 class="hero__title">The League</h1>
  <a class="hero__subtitle hero__subtitle--link" href="{{ '/seasons/2026/' | relative_url }}">Season 13</a>

  <div class="hero__highlights">
    <div class="hero__stat hero__stat--shiva">
      <span class="hero__stat-label">🏆 Reigning Shiva · {{ latest.year }}</span>
      <a class="hero__stat-value" href="{{ '/teams/' | append: champ.owner_id | append: '/' | relative_url }}">{{ champ.owner_name }}</a>
      <span class="hero__stat-owner">{{ champ.team }}</span>
    </div>
    <div class="hero__stat hero__stat--sacko">
      <span class="hero__stat-label">💩 Current Sacko · {{ latest.year }}</span>
      <a class="hero__stat-value" href="{{ '/teams/' | append: sacko.owner_id | append: '/' | relative_url }}">{{ sacko.owner_name }}</a>
      <span class="hero__stat-owner">{{ sacko.team }}</span>
    </div>
  </div>

  <nav class="hero__links">
    <a href="{{ '/history/' | relative_url }}">History</a>
    <a href="{{ '/records/' | relative_url }}">Records</a>
    <a href="{{ '/teams/' | relative_url }}">Owners</a>
    <a href="{{ '/rulebook/' | relative_url }}">Rulebook</a>
  </nav>

  <h3>Comments or concerns? <a href="{{ '/feedback/' | relative_url }}">Submit feedback</a></h3>
</section>
