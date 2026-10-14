"""Keeper-cost rules and the owner page's Current Roster table.

The rule (docs/rulebook): a player costs **two rounds earlier than the round he
was drafted** that season. Trades and drops don't change it — the cost follows
the player's draft round, whoever drafted him. Undrafted players cost a 13th;
1st- and 2nd-round picks are ineligible. A kept player is "drafted" at his
keeper round, so keeping him again costs two more rounds.
"""

KEEPER_DISCOUNT = 2           # rounds earlier than the draft round
UNDRAFTED_COST = 13           # round an undrafted player costs
LAST_INELIGIBLE_ROUND = 2     # rounds 1..this can't be kept

# Display order for positions on the roster table; unknown positions sort last.
POS_ORDER = ["QB", "RB", "WR", "TE", "K", "D/ST"]


def draft_rounds(season):
    """{player: round} for every player drafted in a season, from the season
    YAML's `rosters:` block (via: draft entries), across all franchises."""
    out = {}
    for entries in (season.get("rosters") or {}).values():
        for e in entries or []:
            if e.get("via") == "draft" and e.get("round") and e.get("player"):
                out[e["player"]] = e["round"]
    return out


def keeper_cost(draft_round):
    """The round it costs to keep a player drafted in `draft_round` (None =
    undrafted). Returns None when the player is ineligible to be kept."""
    if draft_round is None:
        return UNDRAFTED_COST
    if draft_round <= LAST_INELIGIBLE_ROUND:
        return None
    return draft_round - KEEPER_DISCOUNT


def current_roster_rows(players, rounds):
    """Shape one team's roster snapshot into Current Roster rows:
    [{player, pos, cost, basis, ineligible}], ordered by position, then by
    draft round within a position (earliest picks first, undrafted last).
    `players` are snapshot rows ({player, pos, ...});
    `rounds` is draft_rounds() for the snapshot's season."""
    rows = []
    for p in players or []:
        name = p.get("player")
        if not name:
            continue
        rnd = rounds.get(name)
        cost = keeper_cost(rnd)
        rows.append({
            "player": name,
            "pos": p.get("pos") or "",
            "cost": f"R{cost}" if cost is not None else "Ineligible",
            "basis": f"Drafted R{rnd}" if rnd else "Undrafted",
            "ineligible": cost is None,
            "_round": rnd,
        })

    def key(r):
        pos = POS_ORDER.index(r["pos"]) if r["pos"] in POS_ORDER else len(POS_ORDER)
        return (pos, r["_round"] is None, r["_round"] or 0, r["player"].lower())

    rows.sort(key=key)
    for r in rows:
        del r["_round"]
    return rows
