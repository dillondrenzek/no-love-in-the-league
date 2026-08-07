"""Shared logic for the site generators.

Generators stay thin: they load data, call one of these functions, and render a
table. All the real thinking (what counts as a win, how standings sort, what the
records are) lives here so it's written and tested once.
"""
