---
layout: page
title: Palette
permalink: /palette/
---

<!-- A standalone living style guide: every color token and UI component the site
     uses, rendered with its real classes. Not linked in the nav — reach it at
     /palette/. Handy for eyeballing a theme change in one place. -->

A living reference of the site's colors, type, and components — rendered with the
same classes the real pages use, so a theme tweak shows up here first.

<style>
  .pal-swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin: 1em 0 2em; }
  .pal-swatch { border: 1px solid var(--rule); border-radius: 8px; overflow: hidden; }
  .pal-swatch__fill { height: 54px; border-bottom: 1px solid var(--rule); }
  .pal-swatch__name { padding: 7px 9px 0; font-family: var(--mono); font-size: 0.72rem; color: var(--ink); }
  .pal-swatch__hex { padding: 0 9px 7px; font-family: var(--mono); font-size: 0.66rem; color: var(--muted); text-transform: uppercase; }
  .pal-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 0.6em 0 2em; }
  .pal-note { color: var(--muted); font-size: 0.9rem; margin: -0.4em 0 1.4em; }
</style>

## Colors

<p class="pal-note">Named CSS custom properties from <code>:root</code> in <code>assets/main.scss</code>. Table heat chips are computed from a warm ramp in <code>lib/render.py</code>, not tokens (see Chips below).</p>

<div class="pal-swatches">
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--ink)"></div><div class="pal-swatch__name">--ink</div><div class="pal-swatch__hex">#1a1a1a</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--muted)"></div><div class="pal-swatch__name">--muted</div><div class="pal-swatch__hex">#6b6b6b</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--faint)"></div><div class="pal-swatch__name">--faint</div><div class="pal-swatch__hex">#9a9a9a</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--rule)"></div><div class="pal-swatch__name">--rule</div><div class="pal-swatch__hex">#e7e4de</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--brand)"></div><div class="pal-swatch__name">--brand</div><div class="pal-swatch__hex">#d94f30</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--row-hover)"></div><div class="pal-swatch__name">--row-hover</div><div class="pal-swatch__hex">#faf7f3</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--bg)"></div><div class="pal-swatch__name">--bg</div><div class="pal-swatch__hex">#ffffff</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--code-bg)"></div><div class="pal-swatch__name">--code-bg</div><div class="pal-swatch__hex">#f4f2ec</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--chip-ink)"></div><div class="pal-swatch__name">--chip-ink</div><div class="pal-swatch__hex">#33251c</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--gold-bg)"></div><div class="pal-swatch__name">--gold-bg</div><div class="pal-swatch__hex">#fdf3e0</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--gold-border)"></div><div class="pal-swatch__name">--gold-border</div><div class="pal-swatch__hex">#f7e0b6</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-shiva-bg)"></div><div class="pal-swatch__name">--tag-shiva-bg</div><div class="pal-swatch__hex">#fbe6d6</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-shiva-ink)"></div><div class="pal-swatch__name">--tag-shiva-ink</div><div class="pal-swatch__hex">#a4530f</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-sacko-bg)"></div><div class="pal-swatch__name">--tag-sacko-bg</div><div class="pal-swatch__hex">#ece3da</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-sacko-ink)"></div><div class="pal-swatch__name">--tag-sacko-ink</div><div class="pal-swatch__hex">#6d4a2c</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-added-bg)"></div><div class="pal-swatch__name">--tag-added-bg</div><div class="pal-swatch__hex">#e2f0e0</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-added-ink)"></div><div class="pal-swatch__name">--tag-added-ink</div><div class="pal-swatch__hex">#2f6b34</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-removed-bg)"></div><div class="pal-swatch__name">--tag-removed-bg</div><div class="pal-swatch__hex">#fbe4e2</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--tag-removed-ink)"></div><div class="pal-swatch__name">--tag-removed-ink</div><div class="pal-swatch__hex">#a83029</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--danger)"></div><div class="pal-swatch__name">--danger</div><div class="pal-swatch__hex">#d0433f</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--danger-bg)"></div><div class="pal-swatch__name">--danger-bg</div><div class="pal-swatch__hex">#fcebeb</div></div>
  <div class="pal-swatch"><div class="pal-swatch__fill" style="background: var(--danger-ink)"></div><div class="pal-swatch__name">--danger-ink</div><div class="pal-swatch__hex">#a32d2d</div></div>
</div>

## Typography

<p class="pal-note">Sans is Inter (<code>--sans</code>); numerics and labels use JetBrains Mono (<code>--mono</code>). This section header shows the <code>h2</code> style.</p>

<h1 class="post-title">The League — h1 / post-title</h1>
<h3>Section heading — h3</h3>
<h4>Sub-heading — h4</h4>

Body copy is Inter at a comfortable reading size. Here's a [link in the brand
color](#), some inline `code`, and a run of text to show line spacing and how a
paragraph settles on the page.

> Blockquotes double as callout boxes — brand-color left rule, warm fill, italic.
> Links inside [still work](#).

## Tables

<p class="pal-note">Right-aligned numeric cells use <code>.num</code> (mono, tabular). The gray secondary name uses <code>.owner-name</code>; the heat pill is a <code>.chip</code>.</p>

<div class="table-scroll">
<table>
  <thead>
    <tr><th>Finish</th><th>Team</th><th class="num">Record</th><th class="num">PF</th><th class="num">PA</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td><a href="#">Pukkake</a> <span class="owner-name">Jack</span> <span class="tag tag--shiva">Shiva</span></td><td class="num">11-3</td><td class="num"><span class="chip" style="background:#ee6b3b">1742.4</span></td><td class="num">1520.1</td></tr>
    <tr><td>2</td><td><a href="#">2x Runner Up</a> <span class="owner-name">Luke</span></td><td class="num">10-4</td><td class="num"><span class="chip" style="background:#f7a749">1690.8</span></td><td class="num">1544.9</td></tr>
    <tr><td>12</td><td><a href="#">I am dead inside</a> <span class="owner-name">Trevor</span> <span class="tag tag--sacko">Sacko</span></td><td class="num">3-11</td><td class="num"><span class="chip" style="background:#fdf3e0">1201.7</span></td><td class="num">1633.2</td></tr>
  </tbody>
</table>
</div>

## Chips &amp; tags

<p class="pal-note">Heat chips fill cream → gold → red-orange with the value's magnitude (computed in <code>lib/render.py</code>). Finish tags flag notable placements.</p>

<div class="pal-row">
  <span class="chip" style="background:#fdf3e0">80.1</span>
  <span class="chip" style="background:#fbd496">110.4</span>
  <span class="chip" style="background:#f9b64d">128.7</span>
  <span class="chip" style="background:#f49044">150.2</span>
  <span class="chip" style="background:#ee6b3b">184.9</span>
</div>

<div class="pal-row">
  <span class="tag tag--shiva">Shiva</span>
  <span class="tag tag--shiva">Co-champ</span>
  <span class="tag tag--sacko">Sacko</span>
  <span class="shiva">Shiva (inline label)</span>
</div>

<div class="rule-changes">
  <section class="rule-change">
    <h3 class="rule-change__year">Rule-change chips</h3>
    <ul class="rule-change__items">
      <li class="rule-change__item rule-change__item--added"><span class="rule-change__kind">Roster</span> Added a second IR slot</li>
      <li class="rule-change__item rule-change__item--removed"><span class="rule-change__kind">Scoring</span> Removed the third WR flex</li>
    </ul>
  </section>
</div>

## Cards

<p class="pal-note">Résumé card, record card, homepage hero stat cards, and a trade card.</p>

<div class="resume">
  <div class="resume__honors">🏆 <b>1× Shiva (2019)</b> · 🥈 2× Runner-Up · 💩 <b>1× Sacko (2016)</b></div>
  <div class="resume__grid">
    <div class="tile"><div class="tile__label">All-Time</div><div class="tile__val">95-49 <span class="muted">(.660)</span></div></div>
    <div class="tile"><div class="tile__label">Titles</div><div class="tile__val">1</div></div>
    <div class="tile"><div class="tile__label">Sackos</div><div class="tile__val">1</div></div>
    <div class="tile"><div class="tile__label">Trades</div><div class="tile__val">12</div></div>
    <div class="tile"><div class="tile__label">Seasons</div><div class="tile__val">10</div></div>
    <div class="tile"><div class="tile__label">Best Finish</div><div class="tile__val"><span class="shiva">Shiva</span> 2019</div></div>
  </div>
</div>

<div class="records-list">
  <section class="record-row">
    <h3 class="record-row__name">Most Points in a Week</h3>
    <article class="record-card">
      <div class="record-card__value">184.90</div>
      <div class="record-card__owner"><a href="#">Kevin</a></div>
      <div class="record-card__team">Tom Bradys Only Fans</div>
      <div class="record-card__meta"><a href="#">2024 · Week 17</a></div>
    </article>
  </section>
</div>

<div class="hero">
  <div class="hero__highlights">
    <div class="hero__stat hero__stat--shiva">
      <span class="hero__stat-label">🏆 Reigning Shiva · 2025</span>
      <a class="hero__stat-value" href="#">Jack</a>
      <span class="hero__stat-owner">Pukkake</span>
    </div>
    <div class="hero__stat">
      <span class="hero__stat-label">💩 Current Sacko · 2025</span>
      <a class="hero__stat-value" href="#">Shawnee</a>
      <span class="hero__stat-owner">D***er my Sufficient Tight End</span>
    </div>
  </div>
</div>

<div class="trades">
  <article class="trade">
    <div class="trade__head">
      <span class="trade__when"><a href="#">2024</a> · Preseason</span>
      <span class="trade__parties">with <a href="#">Jack</a></span>
    </div>
    <ul class="trade__flow">
      <li><span class="trade__giver">Got</span> 1.10 pick, Sam LaPorta</li>
      <li><span class="trade__giver">Sent</span> 1.11 pick, Puka Nacua</li>
    </ul>
  </article>
</div>

## Notices &amp; states

<p class="pal-note">In-progress note, empty state, the prank alert, and the back-link.</p>

<p class="season-status">Season in progress — through week 8.</p>

<p class="empty-state">No trades on record — never made a deal.</p>

<div class="form-alert">Oops! Try again. Your feedback is very important to us.</div>

<p class="back-link" style="margin-top:1.4em"><a href="#">← All owners</a></p>

## Forms

<p class="pal-note">Inputs and the submit button, from the feedback page.</p>

<form class="feedback-form" onsubmit="return false">
  <label for="pal-name">Name</label>
  <input id="pal-name" type="text" placeholder="Your name" autocomplete="off">
  <label for="pal-msg">Feedback</label>
  <textarea id="pal-msg" rows="3" placeholder="Tell us all your complaints…"></textarea>
  <button type="submit">Submit feedback</button>
</form>
