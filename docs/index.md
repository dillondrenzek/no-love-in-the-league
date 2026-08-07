---
layout: home
title: Home
---

{% assign latest = site.data.standings.seasons[0] %}
{% assign champ = latest.rows[0] %}
{% assign sacko = latest.rows | last %}

<section class="hero">
  <h1 class="hero__title">The League</h1>
  <p class="hero__subtitle">Season 13</p>

  <div class="hero__highlights">
    <div class="hero__stat">
      <span class="hero__stat-label">🏆 Reigning Shiva · {{ latest.year }}</span>
      <a class="hero__stat-value" href="{{ '/teams/' | append: champ.owner_id | append: '/' | relative_url }}">{{ champ.team }}</a>
      <span class="hero__stat-owner">{{ champ.owner_name }}</span>
    </div>
    <div class="hero__stat">
      <span class="hero__stat-label">💩 Current Sacko · {{ latest.year }}</span>
      <a class="hero__stat-value" href="{{ '/teams/' | append: sacko.owner_id | append: '/' | relative_url }}">{{ sacko.team }}</a>
      <span class="hero__stat-owner">{{ sacko.owner_name }}</span>
    </div>
  </div>

  <nav class="hero__links">
    <a href="{{ '/history/' | relative_url }}">History</a>
    <a href="{{ '/records/' | relative_url }}">Records</a>
    <a href="{{ '/teams/' | relative_url }}">Owners</a>
    <a href="{{ '/rulebook/' | relative_url }}">Rulebook</a>
  </nav>
</section>
