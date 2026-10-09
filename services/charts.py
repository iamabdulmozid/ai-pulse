"""ECharts option builders (pure dicts). Reused by screens and by assistant `chart` SSE events,
so a chart in chat and the same chart on a page are identical.
"""
from __future__ import annotations

BAND_COLORS = {
    "On track": "#3fbd85",
    "Watch": "#d9a63c",
    "At risk": "#ec8140",
    "Critical": "#e9564d",
    "Late": "#b3303a",
}
STAGE_COLORS = {
    "knitting": "#7a97ea",
    "linking": "#e8a24f",
    "trimming_mending": "#b98ad9",
    "washing": "#62d2c6",
    "ironing": "#5cbccb",
    "packing": "#95c76f",
}
AXIS = {"axisLine": {"lineStyle": {"color": "#8b8579"}}, "axisLabel": {"color": "#9a9388"}, "splitLine": {"show": False}}


def outlook_option(weeks: list[dict]) -> dict:
    labels = [w["label"] for w in weeks]
    bands = ["On track", "Watch", "At risk", "Critical", "Late"]
    series = [
        {
            "name": b, "type": "bar", "stack": "total",
            "itemStyle": {"color": BAND_COLORS[b]},
            "data": [round(w[b] / 1000) for w in weeks],  # USD thousands
        }
        for b in bands
    ]
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"},
                    "valueFormatter": "__USD_K__"},
        "legend": {"textStyle": {"color": "#9a9388"}, "top": 0},
        "grid": {"left": 48, "right": 16, "top": 32, "bottom": 24},
        "xAxis": {"type": "category", "data": labels, **AXIS},
        "yAxis": {"type": "value", "name": "USD (000)", "nameTextStyle": {"color": "#9a9388"}, **AXIS},
        "series": series,
    }


def curves_option(series_by_stage: dict[str, list[dict]], markers: dict, required: float | None) -> dict:
    """Stage cumulative curves + today/exf/predicted markers (PO detail)."""
    series = []
    for stage, pts in series_by_stage.items():
        series.append({
            "name": stage.replace("_", " ").title(), "type": "line", "smooth": True, "showSymbol": False,
            "itemStyle": {"color": STAGE_COLORS.get(stage, "#888")},
            "data": [[p["date"], p["cum"]] for p in pts],
        })
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"textStyle": {"color": "#9a9388"}, "top": 0, "type": "scroll"},
        "grid": {"left": 56, "right": 16, "top": 32, "bottom": 28},
        "xAxis": {"type": "time", **AXIS},
        "yAxis": {"type": "value", "name": "pcs", "nameTextStyle": {"color": "#9a9388"}, **AXIS},
        "series": series,
    }


def bar_option(labels: list[str], values: list[float], name: str = "", color: str = "#5f90f0") -> dict:
    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 60, "right": 16, "top": 20, "bottom": 60},
        "xAxis": {"type": "category", "data": labels, "axisLabel": {"color": "#9a9388", "rotate": 30}, **{k: v for k, v in AXIS.items() if k != "axisLabel"}},
        "yAxis": {"type": "value", "name": name, "nameTextStyle": {"color": "#9a9388"}, **AXIS},
        "series": [{"type": "bar", "data": values, "itemStyle": {"color": color}}],
    }
