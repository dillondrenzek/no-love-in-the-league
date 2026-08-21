"""Scoring & roster-construction settings: labels, extraction, and history.

Pure functions over plain dicts (no filesystem, no network) so they're easy to
test. `scripts/import_settings.py` fetches ESPN settings into `data/settings.yml`
as raw stat/slot ids; `compute_rules` labels them here and diffs consecutive
seasons into a change log for the rulebook page.

ESPN's read API returns numeric ids, not names. The maps below cover the common
football stats and lineup slots; anything unmapped is shown as `stat #N` /
`slot #N` so no change is ever hidden — just occasionally unlabeled. When a `#N`
shows up on the site, name it here and rebuild (no re-import needed).
"""

# ESPN scoring stat ids -> labels. Authoritative full map from ESPN's own
# scoring-stat list (ids 0-210); unmapped ids still fall back to 'stat #N'.
STAT_LABELS = {
    0: "Each Pass Attempted",  # PA
    1: "Each Pass Completed",  # PC
    2: "Each Incomplete Pass",  # INC
    3: "Passing Yards",  # PY
    4: "TD Pass",  # PTD
    5: "Every 5 passing yards",  # PY5
    6: "Every 10 passing yards",  # PY10
    7: "Every 20 passing yards",  # PY20
    8: "Every 25 passing yards",  # PY25
    9: "Every 50 passing yards",  # PY50
    10: "Every 100 passing yards",  # PY100
    11: "Every 5 pass completions",  # PC5
    12: "Every 10 pass completions",  # PC10
    13: "Every 5 pass incompletions",  # IP5
    14: "Every 10 pass incompletions",  # IP10
    15: "40+ yard TD pass bonus",  # PTD40
    16: "50+ yard TD pass bonus",  # PTD50
    17: "300-399 yard passing game",  # P300
    18: "400+ yard passing game",  # P400
    19: "2pt Passing Conversion",  # 2PC
    20: "Interceptions Thrown",  # INTT
    21: "Passing Completion Pct",  # CPCT
    22: "Passing Yards Per Game",  # PYPG
    23: "Rushing Attempts",  # RA
    24: "Rushing Yards",  # RY
    25: "TD Rush",  # RTD
    26: "2pt Rushing Conversion",  # 2PR
    27: "Every 5 rushing yards",  # RY5
    28: "Every 10 rushing yards",  # RY10
    29: "Every 20 rushing yards",  # RY20
    30: "Every 25 rushing yards",  # RY25
    31: "Every 50 rushing yards",  # RY50
    32: "Every 100 rushing yards",  # R100
    33: "Every 5 rush attempts",  # RA5
    34: "Every 10 rush attempts",  # RA10
    35: "40+ yard TD rush bonus",  # RTD40
    36: "50+ yard TD rush bonus",  # RTD50
    37: "100-199 yard rushing game",  # RY100
    38: "200+ yard rushing game",  # RY200
    39: "Rushing Yards Per Attempt",  # RYPA
    40: "Rushing Yards Per Game",  # RYPG
    41: "Receptions",  # RECS
    42: "Receiving Yards",  # REY
    43: "TD Reception",  # RETD
    44: "2pt Receiving Conversion",  # 2PRE
    45: "40+ yard TD rec bonus",  # RETD40
    46: "50+ yard TD rec bonus",  # RETD50
    47: "Every 5 receiving yards",  # REY5
    48: "Every 10 receiving yards",  # REY10
    49: "Every 20 receiving yards",  # REY20
    50: "Every 25 receiving yards",  # REY25
    51: "Every 50 receiving yards",  # REY50
    52: "Every 100 receiving yards",  # RE100
    53: "Each reception",  # REC
    54: "Every 5 receptions",  # REC5
    55: "Every 10 receptions",  # REC10
    56: "100-199 yard receiving game",  # REY100
    57: "200+ yard receiving game",  # REY200
    58: "Receiving Target",  # RET
    59: "Receiving Yards After Catch",  # YAC
    60: "Receiving Yards Per Catch",  # YPC
    61: "Receiving Yards Per Game",  # REYPG
    62: "Total 2pt Conversions",  # PTL
    63: "Fumble Recovered for TD",  # FTD
    64: "Sacked",  # SKD
    65: "Passing Fumbles",  # PFUM
    66: "Rushing Fumbles",  # RFUM
    67: "Receiving Fumbles",  # REFUM
    68: "Total Fumbles",  # FUM
    69: "Passing Fumbles Lost",  # PFUML
    70: "Rushing Fumbles Lost",  # RFUML
    71: "Receiving Fumbles Lost",  # REFUML
    72: "Total Fumbles Lost",  # FUML
    73: "Total Turnovers",  # TT
    74: "FG Made (50+ yards)",  # FG50P
    75: "FG Attempted (50+ yards)",  # FGA50P
    76: "FG Missed (50+ yards)",  # FGM50P
    77: "FG Made (40-49 yards)",  # FG40
    78: "FG Attempted (40-49 yards)",  # FGA40
    79: "FG Missed (40-49 yards)",  # FGM40
    80: "FG Made (0-39 yards)",  # FG0
    81: "FG Attempted (0-39 yards)",  # FGA0
    82: "FG Missed (0-39 yards)",  # FGM0
    83: "Total FG Made",  # FG
    84: "Total FG Attempted",  # FGA
    85: "Total FG Missed",  # FGM
    86: "Each PAT Made",  # PAT
    87: "Each PAT Attempted",  # PATA
    88: "Each PAT Missed",  # PATM
    89: "0 points allowed",  # PA0
    90: "1-6 points allowed",  # PA1
    91: "7-13 points allowed",  # PA7
    92: "14-17 points allowed",  # PA14
    93: "Blocked Punt or FG return for TD",  # BLKKRTD
    94: "Fumble or INT Return for TD",  # DEFRETTD
    95: "Each Interception",  # INT
    96: "Each Fumble Recovered",  # FR
    97: "Blocked Punt, PAT or FG",  # BLKK
    98: "Each Safety",  # SF
    99: "Each Sack",  # SK
    100: "1/2 Sack",  # HALFSK
    101: "Kickoff Return TD",  # KRTD
    102: "Punt Return TD",  # PRTD
    103: "Interception Return TD",  # INTTD
    104: "Fumble Return TD",  # FRTD
    105: "Total Return TD",  # TRTD
    106: "Each Fumble Forced",  # FF
    107: "Assisted Tackles",  # TKA
    108: "Solo Tackles",  # TKS
    109: "Total Tackles",  # TK
    110: "Every 3 Total Tackles",  # TK3
    111: "Every 5 Total Tackles",  # TK5
    112: "Stuffs",  # STF
    113: "Passes Defensed",  # PD
    114: "Kickoff Return Yards",  # KR
    115: "Punt Return Yards",  # PR
    116: "Every 10 kickoff return yards",  # KR10
    117: "Every 25 kickoff return yards",  # KR25
    118: "Every 10 punt return yards",  # PR10
    119: "Every 25 punt return yards",  # PR25
    120: "Points Allowed",  # PTSA
    121: "18-21 points allowed",  # PA18
    122: "22-27 points allowed",  # PA22
    123: "28-34 points allowed",  # PA28
    124: "35-45 points allowed",  # PA35
    125: "46+ points allowed",  # PA46
    126: "Points Allowed Per Game",  # PAPG
    127: "Yards Allowed",  # YA
    128: "Less than 100 total yards allowed",  # YA100
    129: "100-199 total yards allowed",  # YA199
    130: "200-299 total yards allowed",  # YA299
    131: "300-349 total yards allowed",  # YA349
    132: "350-399 total yards allowed",  # YA399
    133: "400-449 total yards allowed",  # YA449
    134: "450-499 total yards allowed",  # YA499
    135: "500-549 total yards allowed",  # YA549
    136: "550+ total yards allowed",  # YA550
    137: "Yards Allowed Per Game",  # YAPG
    138: "Net Punts",  # PT
    139: "Punt Yards",  # PTY
    140: "Punts Inside the 10",  # PT10
    141: "Punts Inside the 20",  # PT20
    142: "Blocked Punts",  # PTB
    143: "Punts Returned",  # PTR
    144: "Punt Return Yards",  # PTRY
    145: "Touchbacks",  # PTTB
    146: "Fair Catches",  # PTFC
    147: "Punt Average",  # PTAVG
    148: "Punt Average 44.0+",  # PTA44
    149: "Punt Average 42.0-43.9",  # PTA42
    150: "Punt Average 40.0-41.9",  # PTA40
    151: "Punt Average 38.0-39.9",  # PTA38
    152: "Punt Average 36.0-37.9",  # PTA36
    153: "Punt Average 34.0-35.9",  # PTA34
    154: "Punt Average 33.9 or less",  # PTA33
    155: "Team Win",  # TW
    156: "Team Loss",  # TL
    157: "Team Tie",  # TIE
    158: "Points Scored",  # PTS
    159: "Points Scored Per Game",  # PPG
    160: "Margin of Victory",  # MGN
    161: "25+ point Win Margin",  # WM25
    162: "20-24 point Win Margin",  # WM20
    163: "15-19 point Win Margin",  # WM15
    164: "10-14 point Win Margin",  # WM10
    165: "5-9 point Win Margin",  # WM5
    166: "1-4 point Win Margin",  # WM1
    167: "1-4 point Loss Margin",  # LM1
    168: "5-9 point Loss Margin",  # LM5
    169: "10-14 point Loss Margin",  # LM10
    170: "15-19 point Loss Margin",  # LM15
    171: "20-24 point Loss Margin",  # LM20
    172: "25+ point Loss Margin",  # LM25
    173: "Margin of Victory Per Game",  # MGNPG
    174: "Winning Pct",  # WINPCT
    175: "0-9 yd TD pass bonus",  # PTD0
    176: "10-19 yd TD pass bonus",  # PTD10
    177: "20-29 yd TD pass bonus",  # PTD20
    178: "30-39 yd TD pass bonus",  # PTD30
    179: "0-9 yd TD rush bonus",  # RTD0
    180: "10-19 yd TD rush bonus",  # RTD10
    181: "20-29 yd TD rush bonus",  # RTD20
    182: "30-39 yd TD rush bonus",  # RTD30
    183: "0-9 yd TD rec bonus",  # RETD0
    184: "10-19 yd TD rec bonus",  # RETD10
    185: "20-29 yd TD rec bonus",  # RETD20
    186: "30-39 yd TD rec bonus",  # RETD30
    187: "D/ST Points Allowed",  # DPTSA
    188: "D/ST 0 points allowed",  # DPA0
    189: "D/ST 1-6 points allowed",  # DPA1
    190: "D/ST 7-13 points allowed",  # DPA7
    191: "D/ST 14-17 points allowed",  # DPA14
    192: "D/ST 18-21 points allowed",  # DPA18
    193: "D/ST 22-27 points allowed",  # DPA22
    194: "D/ST 28-34 points allowed",  # DPA28
    195: "D/ST 35-45 points allowed",  # DPA35
    196: "D/ST 46+ points allowed",  # DPA46
    197: "D/ST Points Allowed Per Game",  # DPAPG
    198: "FG Made (50-59 yards)",  # FG50
    199: "FG Attempted (50-59 yards)",  # FGA50
    200: "FG Missed (50-59 yards)",  # FGM50
    201: "FG Made (60+ yards)",  # FG60
    202: "FG Attempted (60+ yards)",  # FGA60
    203: "FG Missed (60+ yards)",  # FGM60
    204: "Offensive 2pt Return",  # O2PRET
    205: "Defensive 2pt Return",  # D2PRET
    206: "2pt Return",  # 2PRET
    207: "Offensive 1pt Safety",  # O1PSF
    208: "Defensive 1pt Safety",  # D1PSF
    209: "1pt Safety",  # 1PSF
    210: "Games Played",  # GP
}

# ESPN lineup slot ids -> labels.
SLOT_LABELS = {
    0: "QB", 1: "TQB", 2: "RB", 3: "RB/WR", 4: "WR", 5: "WR/TE", 6: "TE",
    7: "OP", 8: "DT", 9: "DE", 10: "LB", 11: "DL", 12: "CB", 13: "S",
    14: "DB", 15: "DP", 16: "D/ST", 17: "K", 18: "P", 19: "HC",
    20: "Bench", 21: "IR", 22: "Unknown", 23: "FLEX", 24: "ER", 25: "Rookie",
}

# Bench (20) and IR (21) hold players but aren't starting slots.
BENCH_SLOT, IR_SLOT = 20, 21
STARTER_SLOTS = set(SLOT_LABELS) - {BENCH_SLOT, IR_SLOT}

# Natural football order for displaying lineup slots; unknown slots sort last.
SLOT_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 23, 8, 9, 10, 11, 12, 13, 14, 15, 16,
              17, 18, 19]


def stat_name(sid):
    return STAT_LABELS.get(sid, f"stat #{sid}")


def slot_name(sid):
    return SLOT_LABELS.get(sid, f"slot #{sid}")


def fmt(n):
    """Trim trailing zeros: 4.0 -> '4', 0.50 -> '0.5', 0.04 -> '0.04'."""
    if n is None:
        return "?"
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return f"{n:g}"


# --- pulling the two maps out of a raw ESPN settings blob ------------------- #

def _effective_points(item):
    """The configured points for one scoring item.

    ESPN usually holds the value in `points`, but its post-2023 scoring-settings
    format moved many items' value into `pointsOverrides` and left `points: 0`.
    So prefer a non-zero `points`, then a non-zero override, then fall back to
    whatever `points` was (0 or None) — otherwise a still-scored stat looks
    unscored and reads as "removed" the year the format changed. See
    scripts/inspect_scoring.py --raw to inspect the raw items."""
    base = item.get("points")
    if base:
        return base
    for v in (item.get("pointsOverrides") or {}).values():
        if v:
            return v
    return base


def scoring_map_from_settings(settings):
    """statId -> effective points, for stats that are actually scored (non-zero)."""
    items = settings.get("scoringSettings", {}).get("scoringItems", [])
    out = {}
    for it in items:
        pts = _effective_points(it)
        if pts:
            out[int(it["statId"])] = pts
    return out


def roster_map_from_settings(settings):
    """slotId -> count, for lineup slots that hold at least one player."""
    counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {}) or {}
    return {int(k): v for k, v in counts.items() if v}


def format_from_settings(settings):
    return settings.get("scoringSettings", {}).get("scoringType") or "?"


# --- ordering + display helpers --------------------------------------------- #

def _scoring_group(sid):
    """Rank stats into passing / rushing / receiving / kicking / defense groups
    so the current-settings list reads in a sensible order."""
    label = stat_name(sid).lower()
    for rank, key in enumerate(("pass", "interception", "rush",
                                "receiv", "reception", "fumble",
                                "fg ", "pat", "points allowed", "yards allowed",
                                "defensiv", "sack", "safety", "return")):
        if key in label:
            return rank
    return 99


def _slot_rank(sid):
    return SLOT_ORDER.index(sid) if sid in SLOT_ORDER else 100 + sid


def scoring_rows(smap):
    """Sorted [{id, label, points}] for a scoring map."""
    return [{"id": sid, "label": stat_name(sid), "points": fmt(smap[sid])}
            for sid in sorted(smap, key=lambda s: (_scoring_group(s), stat_name(s)))]


def roster_view(rmap):
    """A rendered roster: ordered starter/bench/IR slots + counts + a summary."""
    slots = [{"id": sid, "label": slot_name(sid), "count": rmap[sid]}
             for sid in sorted(rmap, key=_slot_rank)]
    starters = sum(v for k, v in rmap.items() if k in STARTER_SLOTS)
    bench = rmap.get(BENCH_SLOT, 0)
    ir = rmap.get(IR_SLOT, 0)
    starter_bits = [f"{slot_name(k)}×{rmap[k]}"
                    for k in sorted(rmap, key=_slot_rank) if k in STARTER_SLOTS]
    tail = [f"Bench×{bench}"] + ([f"IR×{ir}"] if ir else [])
    return {
        "slots": slots,
        "starters": starters, "bench": bench, "ir": ir,
        "total": starters + bench + ir,
        "summary": ", ".join(starter_bits + tail),
    }


# --- diffing consecutive seasons -------------------------------------------- #

def _diff(old, new, namer, kind):
    """Structured change items between two id->value maps."""
    items = []
    for k in sorted(set(old) | set(new)):
        o, n = old.get(k), new.get(k)
        if o is None:
            items.append({"kind": kind, "id": k, "op": "added", "label": namer(k),
                          "from": None, "to": fmt(n),
                          "text": f"Added {namer(k)} ({fmt(n)})"})
        elif n is None:
            items.append({"kind": kind, "id": k, "op": "removed", "label": namer(k),
                          "from": fmt(o), "to": None,
                          "text": f"Removed {namer(k)} (was {fmt(o)})"})
        elif o != n:
            items.append({"kind": kind, "id": k, "op": "changed", "label": namer(k),
                          "from": fmt(o), "to": fmt(n),
                          "text": f"{namer(k)}: {fmt(o)} → {fmt(n)}"})
    return items


def _season_maps(entry):
    return (scoring_from_entry(entry), roster_from_entry(entry),
            entry.get("format") or "?")


def scoring_from_entry(entry):
    """A settings.yml entry already holds a raw {statId: points} scoring map."""
    return {int(k): v for k, v in (entry.get("scoring") or {}).items()}


def roster_from_entry(entry):
    return {int(k): v for k, v in (entry.get("roster") or {}).items()}


def compute_rules(entries):
    """Given settings.yml season entries (each {season, format, scoring, roster}),
    return {current, changes} for the rulebook page.

    `current` is the most recent season's labeled scoring + roster. `changes` is
    a newest-first log of the seasons where scoring or roster construction moved,
    each with a list of structured change items.
    """
    seasons = sorted((e for e in (entries or []) if e.get("season") is not None),
                     key=lambda e: e["season"])
    if not seasons:
        return {"current": None, "changes": []}

    changes = []
    for prev, cur in zip(seasons, seasons[1:]):
        po, pr, pf = _season_maps(prev)
        co, cr, cf = _season_maps(cur)
        items = []
        if pf != cf:
            items.append({"kind": "format", "op": "changed", "label": "Scoring format",
                          "from": pf, "to": cf, "text": f"Scoring format: {pf} → {cf}"})
        items += _diff(po, co, stat_name, "scoring")
        items += _diff(pr, cr, slot_name, "roster")
        if items:
            changes.append({"season": cur["season"], "prev": prev["season"],
                            "items": items})
    changes.reverse()   # newest first

    # Stat ids the league has ever added/removed/changed — the "house tweaks"
    # worth surfacing on the rulebook (the rest live on ESPN, the source of truth).
    changed_stat_ids = {it["id"] for yr in changes for it in yr["items"]
                        if it["kind"] == "scoring" and "id" in it}

    latest = seasons[-1]
    lo, lr, lf = _season_maps(latest)
    scoring = scoring_rows(lo)
    for row in scoring:
        row["changed"] = row["id"] in changed_stat_ids
    current = {
        "season": latest["season"],
        "format": lf,
        "scoring": scoring,
        "scoring_changed_count": sum(1 for r in scoring if r["changed"]),
        "scoring_total_count": len(scoring),
        "roster": roster_view(lr),
    }
    return {"current": current, "changes": changes}
