---
layout: page
title: Owners
permalink: /teams/
---

<!-- This page is hand-maintained: it renders scripts-generated data
     (docs/_data/owners.yml) through _includes/owners_table.html. Unlike the
     other pages, it is NOT overwritten by the build. -->

Every manager in league history. Click a name for their full profile.

{% include owners_table.html rows=site.data.owners.active %}

## Inactive Owners

{% include owners_table.html rows=site.data.owners.inactive %}
