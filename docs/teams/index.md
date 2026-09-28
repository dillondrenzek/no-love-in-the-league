---
layout: page
title: Owners
permalink: /teams/
---

<!-- This page is hand-maintained: it renders scripts-generated data
     (docs/_data/owners.yml) through _includes/tables/owners_table.html. Unlike the
     other pages, it is NOT overwritten by the build. -->

Every manager in league history. Click a name for their full profile.

{% include tables/owners_table.html rows=site.data.owners.active %}

## Inactive Owners

{% include tables/owners_table.html rows=site.data.owners.inactive %}

## Finish History

_Where each manager placed each year — hotter is better. Sorted by average finish._

{% include tables/finish_heatmap.html data=site.data.owners.finish_heatmap %}

## Draft Order History

{% include tables/draft_heatmap.html data=site.data.owners.draft_heatmap %}

## Transaction History

_Transaction history is only available for 2018 and beyond_

{% include tables/tx_heatmap.html data=site.data.owners.tx_heatmap %}
