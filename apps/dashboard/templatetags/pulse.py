from django import template

register = template.Library()

_BAND_CLASS = {
    "On track": "b-ok",
    "Watch": "b-watch",
    "At risk": "b-risk",
    "Critical": "b-crit",
    "Late": "b-late",
    "Shipped": "b-ship",
    "No update": "b-noupd",
}


@register.filter
def band_class(band):
    return _BAND_CLASS.get(band, "b-ok")


@register.filter
def usd(value, decimals=0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"${v:,.{int(decimals)}f}"


@register.filter
def usd_m(value):
    """Compact USD in millions/thousands for KPI cards."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


@register.filter
def pcs(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct(value, decimals=1):
    try:
        return f"{float(value):.{int(decimals)}f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def pct_from_fraction(value, decimals=2):
    try:
        return f"{float(value) * 100:.{int(decimals)}f}%"
    except (TypeError, ValueError):
        return "—"


@register.filter
def get(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None
