---
layout: page
title: Week 1 · 2026
permalink: /seasons/2026/week-1/
season_year: 2026
season_no: 13
week: 1
---
{% assign wk = site.data.weeks["2026-1"] %}
{% include week_detail.html wk=wk %}

{% if wk.state != "complete" %}
<h2>The Preview</h2>

<!-- Paste the preview below. Build the prompt with:
     python scripts/weekly_preview.py 2026 1
     Shows until the week is complete, then the recap takes over. -->

Football's back, and so is your worst decision-making. Let's set the table.

The marquee is **The People's Commissioner** vs **Tuten Your Mom** — Wade and Zach have played *twenty-three* times and Wade leads by a nervous 13-10, which is fantasy-speak for "these two hate each other and it's Week 1." Winner talks trash for a month; loser pretends the season is long. Meanwhile the reigning Shiva **Gibbed for your pleasure** opens against **Return of the IDP**, and Jack owns Jono 13-9 — Jono's still starting defensive players like it's a lifestyle, and Jack will happily punish the sentiment.

Grudge alert in **One Big Beautiful Dill** vs **Swift kick in the Dak**: on paper Shawnee's the grown-up here with two Shivas, but somehow Grant is *3-1* against her all-time. Records don't care about your trophy case. Elsewhere **The ChoSimba Ones** should feast — Dillon's a .619 machine who's beaten Kevin eight of eleven, and **Josh Jacobs Alibi** is a great team name for a squad that's going to need one. **2x Runner Up** over **I am dead inside** feels academic (Luke's up 5-2 and owns a ring), which is exactly the kind of game Luke autodrafts his way into losing.

And then there's the debut: **Cornstar** (welcome, Lexi) draws **Trick or Trick It's Mike Vick**, a first meeting against a man whose career high-water mark is *fourth place*. Nate, respectfully, this is the softest landing a rookie will ever get. Don't blow it.

Twelve teams, one Week 1, eleven future excuses. Let's ride.

### 🔮 Picks

- **Game of the Week** — People's Commissioner vs Tuten Your Mom — 23 meetings, one point of separation, zero chill.
- **Lock of the Week** — The ChoSimba Ones — Dillon's 8-3 on Kevin and it hasn't been close; book it.
- **Upset Alert** — One Big Beautiful Dill — Grant's 3-1 on the two-time champ, and history is history.
- **Bold Prediction** — Lexi drops 130 in her debut and Nate spends Week 2 explaining variance.
{% endif %}

{% if wk.state == "complete" %}
<h2>The Recap</h2>

<!-- Paste the agent's recap below. Build the prompt with:
     python scripts/weekly_recap.py 2026 1
     It's Markdown: a chaotic column, then a "### 🏆 Awards" list. The recap only
     renders once the week is complete. -->

_Recap coming soon._
{% endif %}
