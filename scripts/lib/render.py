"""Small presentation helpers shared by the generators.

Heat-shaded table cells are the signature of the look: one warm magnitude ramp
(cream -> gold -> red-orange) drives every colored value — points, win
percentages, all of it. These functions return hex colors; the templates render
them as chips inside the cell (see _includes/chip.html). All the color logic
lives here so every table shades consistently.
"""


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def warm_heat(t):
    """t in [0,1] -> cream to golden yellow to red-orange (FiveThirtyEight's
    YlOrRd sequential ramp). Cream low end, an amber/gold midrange, deep
    red-orange at the top."""
    t = 0.0 if t is None else max(0.0, min(1.0, t))
    pale, mid, hot = (253, 243, 224), (249, 182, 77), (238, 107, 59)
    rgb = _lerp(pale, mid, t / 0.5) if t <= 0.5 else _lerp(mid, hot, (t - 0.5) / 0.5)
    return _hex(rgb)


def heat_color(value, lo, hi):
    """Warm-heat hex for `value` normalized against a column's lo..hi range."""
    t = 0.0 if hi == lo else (value - lo) / (hi - lo)
    return warm_heat(t)


def finish_tag(finish, team_count, is_co=False):
    """A small inline tag for a notable finish: Shiva (title), Co-champ, or Sacko
    (dead last). Empty string for everything in between."""
    if is_co:
        return ' <span class="tag tag--shiva">Co-champ</span>'
    if finish == 1:
        return ' <span class="tag tag--shiva">Shiva</span>'
    if team_count and finish == team_count:
        return ' <span class="tag tag--sacko">Sacko</span>'
    return ""
