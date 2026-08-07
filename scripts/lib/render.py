"""Small presentation helpers shared by the generators.

Colored value "chips" are the signature of the look: a magnitude scale (warm,
pale -> orange) for raw numbers like points, and a diverging scale (red <-> green,
neutral at .500) for win percentages. All logic lives here so every table colors
consistently.
"""


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def warm_heat(t):
    """t in [0,1] -> pale cream to hot orange."""
    t = 0.0 if t is None else max(0.0, min(1.0, t))
    pale, mid, hot = (250, 241, 233), (240, 153, 123), (214, 90, 48)
    rgb = _lerp(pale, mid, t / 0.5) if t <= 0.5 else _lerp(mid, hot, (t - 0.5) / 0.5)
    return _hex(rgb)


def winpct_color(p):
    """Win% in [0,1] -> red (losing) through neutral (.500) to green (winning)."""
    neutral, green, red = (244, 243, 240), (46, 158, 106), (208, 67, 63)
    t = (p - 0.5) * 2
    if t >= 0:
        return _hex(_lerp(neutral, green, min(1.0, t) ** 0.85))
    return _hex(_lerp(neutral, red, min(1.0, -t) ** 0.85))


def chip(text, bg):
    return f'<span class="chip" style="background:{bg}">{text}</span>'


def heat_chip(value, lo, hi, text=None):
    """A warm-heat chip for `value` normalized against a column's lo..hi range."""
    t = 0.0 if hi == lo else (value - lo) / (hi - lo)
    return chip(text if text is not None else value, warm_heat(t))


def winpct_chip(p, text=None):
    return chip(text if text is not None else f"{p:.3f}".lstrip("0"), winpct_color(p))
