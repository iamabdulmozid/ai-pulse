"""Assistant answer router.

In fallback mode (no OPENAI_API_KEY, or ASSISTANT_FALLBACK_MODE) a deterministic intent router maps the
question to tools and composes the answer — so the 3 demo questions always work offline. When a key is
present, services.assistant.llm drives the same tools via OpenAI tool-calling (numbers still only from
tools). Every answer carries sources with an "as of" time; unknown questions say "I don't have that".
"""
from __future__ import annotations

import re

from services import charts, metrics
from services.assistant import tools


def _src(run):
    return [{"name": "Prediction snapshot", "as_of": run.as_of.isoformat()}]


def answer(run, question: str) -> dict:
    """Return {steps, text, table, chart, sources, followups}."""
    q = (question or "").lower().strip()

    # --- Any question that names a PO -> the PO explainer (why/risk/status/what-if) ---
    m = re.search(r"\b(7\d{7})\b", q)
    if m:
        return _po_why(run, m.group(1))

    # --- Demo Q1: which factories miss October ex-factory and by how much ---
    if ("miss" in q or "late" in q or "slip" in q) and ("october" in q or "oct" in q) and "factor" in q:
        return _october_misses(run)

    # --- Demo Q3: October on-time % + where the value at risk concentrates ---
    if ("october" in q or "on-time" in q or "on time" in q) and ("at risk" in q or "concentrat" in q or "risk" in q):
        return _october_and_risk(run)
    if "on-time" in q or "on time" in q:
        return _october_and_risk(run)

    # --- which factories have not reported / are quiet ---
    if ("not report" in q or "missing" in q or "quiet" in q or "no update" in q) and "factor" in q:
        return _missing(run)

    # --- value at risk / exposure / top factories ---
    if ("at risk" in q or "value at risk" in q or "exposure" in q or "risk" in q
            or ("top" in q and "factor" in q) or "carries the most" in q):
        return _october_and_risk(run)

    # --- portfolio snapshot ---
    if ("open po" in q or "order book" in q or "piece" in q or "pcs" in q
            or ("how many" in q and ("po" in q or "order" in q))):
        k = tools.get_portfolio_kpis(run)["data"]
        txt = (f"There are {k['open_pos']} open POs — {k['open_pcs']:,} pcs, "
               f"${float(k['open_fob_usd'])/1e6:.1f}M FOB (as of {run.as_of:%d %b %H:%M}).")
        return {"steps": ["Reading portfolio snapshot"], "text": txt, "table": None, "chart": None,
                "sources": _src(run), "followups": ["What's our October on-time %?"]}

    return {"steps": [], "text": "I don't have that. Try asking about October on-time, value at risk, a "
            "specific PO (e.g. 71010305), or which factories haven't reported.",
            "table": None, "chart": None, "sources": _src(run), "followups": []}


def _po_why(run, po_no: str) -> dict:
    pred = tools.get_po_prediction(run, po_no)["data"]
    if not pred:
        return {"steps": [], "text": f"I don't have PO {po_no}.", "table": None, "chart": None,
                "sources": _src(run), "followups": []}
    recs = tools.get_po_recommendation(run, po_no)["data"]
    drivers = "; ".join(pred["drivers"]) if pred["drivers"] else "no specific drivers"
    fix = recs[0] if recs else None
    text = (f"PO {po_no} ({pred['style_name']}, {pred['factory_code']}) is **{pred['band']}** — predicted "
            f"ex-factory {pred['projected_exfactory']:%d %b} vs planned {pred['exf_date']:%d %b} "
            f"({'+' if pred['slip_days'] > 0 else ''}{pred['slip_days']} days), on-time probability "
            f"{pred['on_time_prob']*100:.0f}%. Drivers: {drivers}.")
    if fix:
        text += f" Fastest fix: {fix['body']} — {fix['cost_note']}, making it on time."
    table = {
        "columns": ["Metric", "Value"],
        "rows": [
            ["Predicted ex-factory", f"{pred['projected_exfactory']:%d %b %Y}"],
            ["Slip (days)", pred["slip_days"]],
            ["Band", pred["band"]],
            ["Risk score", pred["risk_score"]],
            ["On-time probability", f"{pred['on_time_prob']*100:.0f}%"],
            ["Bottleneck", f"{pred['bottleneck_stage']} {pred['bottleneck_rate']:.0f}/day vs {pred['required_rate']:.0f} needed"
             if pred.get("bottleneck_rate") else "—"],
        ],
    }
    return {"steps": [f"Loading PO {po_no} prediction", "Reading risk drivers", "Computing the cheapest recovery"],
            "text": text, "table": table, "chart": None, "sources": _src(run),
            "followups": [f"Show the what-if for {po_no}", f"Who is the merchandiser for {po_no}?"]}


def _october_misses(run) -> dict:
    f = metrics.POFilters(exf_month=["2026-10"])
    rows = [r for r in metrics.po_list(run, f) if r["slip_days"] > 0]
    by_factory: dict[str, dict] = {}
    for r in rows:
        g = by_factory.setdefault(r["factory_code"], {"name": r["factory_name"], "n": 0, "worst": 0, "pcs": 0})
        g["n"] += 1
        g["worst"] = max(g["worst"], r["slip_days"])
        g["pcs"] += r["qty_pcs"]
    ordered = sorted(by_factory.items(), key=lambda kv: kv[1]["worst"], reverse=True)
    table = {"columns": ["Factory", "POs late", "Worst slip (days)", "Pcs at risk"],
             "rows": [[f"{c} {g['name']}", g["n"], g["worst"], f"{g['pcs']:,}"] for c, g in ordered]}
    chart = charts.bar_option([c for c, _ in ordered], [g["worst"] for _, g in ordered],
                              name="days late", color="#ec8140")
    total_pos = sum(g["n"] for _, g in ordered)
    text = (f"{len(ordered)} factories have October POs predicted to miss ex-factory ({total_pos} POs). "
            f"Worst: {ordered[0][0]} at {ordered[0][1]['worst']} days late." if ordered else
            "No October POs are predicted late.")
    return {"steps": [f"Scanning {metrics.portfolio_kpis(run)['open_pos']} open POs", "Filtering October ex-factory",
                      "Keeping predicted-late", "Grouping by factory"],
            "text": text, "table": table, "chart": chart, "sources": _src(run),
            "followups": ["Why is PO 71010305 late?", "What's our October on-time %?"]}


def _october_and_risk(run) -> dict:
    k = tools.get_portfolio_kpis(run)["data"]
    var = tools.get_value_at_risk(run)["data"]
    top = var["by_factory"][:3]
    top_share = sum(t["share_pct"] for t in top)
    text = (f"October is tracking **{k['october_on_time_pct']*100:.2f}%** on time. "
            f"**${float(var['total_usd'])/1e6:.1f}M** is at risk across {k['at_risk_pos']} POs, and "
            f"{', '.join(t['code'] for t in top)} carry {top_share:.0f}% of it.")
    table = {"columns": ["Factory", "Value at risk (USD)", "Share"],
             "rows": [[f"{t['code']} {t['name']}", f"${t['value_at_risk_usd']:,.0f}", f"{t['share_pct']:.0f}%"] for t in var["by_factory"]]}
    chart = charts.bar_option([t["code"] for t in var["by_factory"]],
                              [round(t["value_at_risk_usd"]) for t in var["by_factory"]],
                              name="USD at risk", color="#e9564d")
    return {"steps": ["Reading October on-time", "Summing value at risk", "Ranking factories by exposure"],
            "text": text, "table": table, "chart": chart, "sources": _src(run),
            "followups": ["Which factories will miss October ex-factory?", "Why is PO 71010305 late?"]}


def _missing(run) -> dict:
    d = tools.list_factories_missing_report(run)["data"]
    miss = d["missing"]
    text = (f"{len(miss)} of {d['expected']} factories have not reported today: "
            + ", ".join(f"{m['code']} (last {m['last_report']:%d %b})" if m['last_report'] else m['code'] for m in miss)
            + ".")
    table = {"columns": ["Factory", "Code", "Last report"],
             "rows": [[m["name"], m["code"], f"{m['last_report']:%d %b}" if m["last_report"] else "—"] for m in miss]}
    return {"steps": ["Checking factory reporting state"], "text": text, "table": table, "chart": None,
            "sources": _src(run), "followups": ["Which factories will miss October ex-factory?"]}
