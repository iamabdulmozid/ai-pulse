"""Assistant answer router.

In fallback mode (no OPENAI_API_KEY, or ASSISTANT_FALLBACK_MODE) a deterministic intent router maps the
question to tools and composes the answer — so the 3 demo questions always work offline. When a key is
present, services.assistant.llm drives the same tools via OpenAI tool-calling (numbers still only from
tools). Every answer carries sources with an "as of" time; unknown questions say "I don't have that".
"""
from __future__ import annotations

import re
from datetime import date

from django.conf import settings

from services import charts, metrics
from services.assistant import tools


def _src(run):
    return [{"name": "Prediction snapshot", "as_of": run.as_of.isoformat()}]


# Industry terms the assistant can explain without data (fallback mode has no LLM to do it).
GLOSSARY = {
    "aql": ("AQL (Acceptable Quality Level, ISO 2859-1) is the sampling standard used in garment "
            "inspections: an inspector checks a random sample from the lot and the lot passes if the "
            "defects found are within the accept number for the agreed level (e.g. AQL 2.5 for majors, "
            "4.0 for minors). A factory's **AQL pass rate** is the share of its inspections that passed."),
    "otd": ("OTD (on-time delivery) is the share of a factory's POs that left the factory on or before the "
            "planned ex-factory date. Pulse shows the trailing 12-month OTD per factory."),
    "ex-factory": ("Ex-factory is the date goods leave the factory for the port; it is the date Pulse "
                   "predicts and measures on-time against."),
    "fob": ("FOB (Free On Board) is the price/value of the goods loaded on the vessel at origin; Pulse uses "
            "FOB value to size order book exposure and value at risk."),
}
_TERM_ALIASES = {"acceptable quality": "aql", "on-time delivery": "otd", "ex factory": "ex-factory",
                 "exfactory": "ex-factory", "free on board": "fob"}


def _term(q: str) -> str | None:
    for alias, term in _TERM_ALIASES.items():
        if alias in q:
            return term
    return next((t for t in GLOSSARY if re.search(rf"\b{re.escape(t)}\b", q)), None)


def _factory_in(q: str, cards: list[dict]) -> dict | None:
    for c in cards:
        if re.search(rf"\b{c['code'].lower()}\b", q) or c["name"].lower() in q:
            return c
    return None


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december"]


def _shipped_month(q: str) -> str | None:
    """'YYYY-MM' when the question is about actual shipments of a past (or the current) month."""
    today = settings.DEMO_TODAY
    if "last month" in q or "previous month" in q or "past month" in q:
        return metrics.last_month(today)
    for i, name in enumerate(_MONTHS, 1):
        abbr = f"{name}|{name[:3]}|sept" if i == 9 else f"{name}|{name[:3]}"
        if re.search(rf"\b({abbr})\b", q):
            if i == today.month:  # current month is predictions territory unless asking what shipped
                return f"{today:%Y-%m}" if "shipped" in q else None
            return f"{today.year if i < today.month else today.year - 1}-{i:02d}"
    if "shipped" in q:
        return metrics.last_month(today) if "this month" not in q else f"{today:%Y-%m}"
    return None


def answer(run, question: str) -> dict:
    """Return {steps, text, table, chart, sources, followups}."""
    q = (question or "").lower().strip()

    # --- Any question that names a PO -> the PO explainer (why/risk/status/what-if) ---
    m = re.search(r"\b(7\d{7})\b", q)
    if m:
        rate = re.search(r"(\d+(?:\.\d+)?)\s*%", q)
        if rate and re.search(r"\b(fine|penalt\w*|charge|deduct\w*|claim)\b", q):
            per = "week" if re.search(r"\b(week|weekly)\b", q) else (
                "once" if re.search(r"\b(flat|once|one[- ]off)\b", q) else "day")
            return _po_penalty(run, m.group(1), float(rate.group(1)), per)
        return _po_why(run, m.group(1))

    # --- Last month / a past month / "what shipped" -> shipment actuals ---
    month = _shipped_month(q)
    if month:
        return _shipped(run, month, late_only=bool(re.search(r"\b(late|delay|delayed|behind)\b", q)))

    # --- Quality / AQL, factory scorecards, and short follow-ups naming a factory ---
    cards = tools.list_factory_scorecards(run)["data"]
    factory = _factory_in(q, cards)
    term = _term(q)
    if "aql" in q or "quality" in q or "inspection" in q:
        return _factory_quality(run, cards, factory)
    if factory and (len(q.split()) <= 3 or "scorecard" in q or "how is" in q or "how's" in q):
        return _factory_quality(run, cards, factory)
    if term and re.search(r"\b(what|meaning|mean|explain|define)\b", q):
        return {"steps": [], "text": GLOSSARY[term], "table": None, "chart": None, "sources": [],
                "followups": ["What is the AQL pass rate by factory?", "What's our October on-time %?"]}

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
            "specific PO (e.g. 71010305), a factory's AQL pass rate, or which factories haven't reported.",
            "table": None, "chart": None, "sources": _src(run), "followups": []}


def _shipped(run, month: str, late_only: bool = False) -> dict:
    d = tools.get_shipped_summary(run, month, late_limit=None)["data"]
    label = f"{date.fromisoformat(month + '-01'):%B %Y}"
    src = [{"name": "Shipment log", "as_of": run.as_of.isoformat()}]
    if not d["shipments"]:
        return {"steps": [f"Reading {label} shipments"], "text": f"Nothing shipped in {label}.",
                "table": None, "chart": None, "sources": src, "followups": []}
    late = d["late_shipments"]
    weak = [f for f in d["by_factory"] if f["on_time_pct"] < 80]
    text = (f"In **{label}** we shipped **{d['shipments']}** shipments ({d['pos']} POs) — "
            f"**{d['pcs']:,} pcs** worth **${d['value_usd'] / 1e6:.2f}M** (invoice). "
            f"**{d['on_time_pct']:.1f}%** left the factory on or before the planned ex-factory date "
            f"({d['on_time']} of {d['shipments']}).")
    if late:
        worst = late[0]
        text += (f" {d['late_count']} shipped late; the worst was PO {worst['po_no']} ({worst['factory_code']}), "
                 f"{worst['days_late']} days late.")
    if weak:
        text += " Factories below 80% on time: " + ", ".join(
            f"{f['code']} ({f['on_time_pct']:.0f}%)" for f in sorted(weak, key=lambda f: f["on_time_pct"])) + "."
    if d["air_freight_cost_usd"]:
        text += f" Air freight cost: ${d['air_freight_cost_usd']:,.0f}."
    if late_only:
        text = (f"**{d['late_count']}** of {d['shipments']} {label} shipments left the factory after the planned "
                f"ex-factory date ({d['on_time_pct']:.1f}% on time)." if late else f"Every {label} shipment was on time.")
        table = {"columns": ["PO", "Factory", "Planned ex-factory", "Actual ex-factory", "Days late", "Mode"],
                 "rows": [[r["po_no"], r["factory_code"], r["planned_exfactory"], r["actual_exfactory"],
                           r["days_late"], r["ship_mode"]] for r in late]}
        return {"steps": [f"Reading {label} shipment log", "Keeping shipments past planned ex-factory"],
                "text": text, "table": table if late else None, "chart": None, "sources": src,
                "followups": [f"How did {label.split()[0]} go overall?"]}
    table = {"columns": ["Factory", "Shipments", "Pcs", "Value (USD)", "On time"],
             "rows": [[f"{f['code']} {f['name']}", f["shipments"], f"{f['pcs']:,}", f"${f['value_usd']:,.0f}",
                       f"{f['on_time_pct']:.0f}%"] for f in d["by_factory"]]}
    chart = charts.bar_option([f["code"] for f in d["by_factory"]], [round(f["value_usd"]) for f in d["by_factory"]],
                              name="USD shipped", color="#3aa676")
    return {"steps": [f"Reading {label} shipment log", "Comparing actual vs planned ex-factory",
                      "Grouping by factory"],
            "text": text, "table": table, "chart": chart, "sources": src,
            "followups": [f"Which {label.split()[0]} shipments were late?", "What's our October on-time %?"]}


def _factory_quality(run, cards: list[dict], factory: dict | None) -> dict:
    """AQL pass rate for one factory, or every factory ranked weakest-first when none is named."""
    if factory:
        f = factory
        text = (f"**{f['code']} {f['name']}** passed **{f['aql_pass_pct']:.1f}%** of AQL inspections in the "
                f"last 90 days; 12-month on-time delivery is **{f['otd_pct']:.1f}%**, knit load "
                f"{f['knit_load_pct']:.0f}%, {f['open_pos']} open POs with ${f['value_at_risk_usd']:,.0f} at risk.")
        if f["aql_pass_pct"] < 85:
            text += " That is below the 85% quality threshold, so its POs carry a quality risk penalty."
        table = {"columns": ["Metric", "Value"], "rows": [
            ["AQL pass (90 days)", f"{f['aql_pass_pct']:.1f}%"], ["OTD (12 months)", f"{f['otd_pct']:.1f}%"],
            ["Knit load", f"{f['knit_load_pct']:.0f}%"], ["Open POs", f["open_pos"]],
            ["Value at risk (USD)", f"${f['value_at_risk_usd']:,.0f}"],
            ["Reported today", "Yes" if f["reported_today"] else "No"]]}
        return {"steps": [f"Loading {f['code']} scorecard"], "text": text, "table": table, "chart": None,
                "sources": _src(run), "followups": [f"Which {f['code']} POs are at risk?",
                                                     "What is the AQL pass rate by factory?"]}

    ranked = sorted(cards, key=lambda c: c["aql_pass_pct"])
    below = [c for c in ranked if c["aql_pass_pct"] < 85]
    avg = sum(c["aql_pass_pct"] for c in cards) / len(cards) if cards else 0
    text = (GLOSSARY["aql"] + f"\n\nAcross {len(cards)} factories the 90-day AQL pass rate averages "
            f"**{avg:.1f}%**. ")
    if below:
        text += (f"{len(below)} are below the 85% threshold: "
                 + ", ".join(f"{c['code']} ({c['aql_pass_pct']:.1f}%)" for c in below) + ". ")
    text += "Which factory would you like to look at?"
    table = {"columns": ["Factory", "AQL pass (90d)", "OTD (12m)", "Open POs"],
             "rows": [[f"{c['code']} {c['name']}", f"{c['aql_pass_pct']:.1f}%", f"{c['otd_pct']:.1f}%",
                       c["open_pos"]] for c in ranked]}
    chart = charts.bar_option([c["code"] for c in ranked], [c["aql_pass_pct"] for c in ranked],
                              name="AQL pass %", color="#4c8bf5")
    return {"steps": ["Reading factory inspection results", "Ranking by AQL pass rate"], "text": text,
            "table": table, "chart": chart, "sources": _src(run),
            "followups": [f"{c['code']} scorecard" for c in ranked[:3]]}


def _po_penalty(run, po_no: str, rate_pct: float, per: str) -> dict:
    res = tools.calculate_late_penalty(run, po_no, rate_pct, per=per)
    p = res["data"]
    src = [{"name": res["source"], "as_of": run.as_of.isoformat()}]
    if p is None:
        return {"steps": [], "text": res["note"], "table": None, "chart": None, "sources": src, "followups": []}
    if not p["days_late"]:
        return {"steps": [f"Loading PO {po_no} delivery dates"], "text": f"PO {po_no} was not late, so no late "
                "penalty applies.", "table": None, "chart": None, "sources": src, "followups": []}
    text = (f"PO {po_no} ({p['factory_code']}) was **{p['days_late']} days late** ({p['days_late_source']}). "
            f"At {p['rate_pct']}% per {p['per']} on the {p['base']}: {p['formula']}, so the penalty is "
            f"**${p['penalty_usd']:,.2f}**.")
    if p["total_pct"] > 10:
        text += " Penalty clauses are often capped (e.g. 5-10% of value); tell me the cap if your policy has one."
    table = {"columns": ["Item", "Value"], "rows": [
        ["Planned ex-factory", p["planned_exfactory"]], ["Actual ex-factory", p["actual_exfactory"] or "-"],
        ["Days late", p["days_late"]], ["Base", f"${p['base_amount_usd']:,.2f}"],
        ["Total %", f"{p['total_pct']}%"], ["Penalty (USD)", f"${p['penalty_usd']:,.2f}"]]}
    return {"steps": [f"Loading PO {po_no} order value", "Measuring days late", "Applying the penalty rate"],
            "text": text, "table": table, "chart": None, "sources": src, "followups": []}


def _po_shipped(run, po_no: str) -> dict:
    """A PO with no prediction: shipped (show its order + shipment record) or unknown."""
    res = tools.get_po_details(run, po_no)
    d = res["data"]
    src = [{"name": res["source"], "as_of": run.as_of.isoformat()}]
    if d is None:
        return {"steps": [], "text": f"I don't have PO {po_no}.", "table": None, "chart": None,
                "sources": src, "followups": []}
    late = d["days_late"] or 0
    actual = d["shipments"][-1]["actual_exfactory"] if d["shipments"] else "-"
    text = (f"PO {po_no} ({d['style_name']}, {d['factory_code']}) has **shipped**: {d['shipped_qty']:,} of "
            f"{d['order_qty']:,} pcs. Order value **${d['order_value_usd']:,.2f}** ({d['order_qty']:,} x "
            f"${d['fob_usd_pc']:.2f} FOB). Planned ex-factory {d['planned_exfactory']}, actual {actual}, "
            + (f"**{late} days late**." if late > 0 else "on time."))
    table = {"columns": ["Metric", "Value"], "rows": [
        ["Order qty", f"{d['order_qty']:,}"], ["FOB / pc", f"${d['fob_usd_pc']:.2f}"],
        ["Order value", f"${d['order_value_usd']:,.2f}"], ["Invoice value", f"${d['invoice_value_usd']:,.2f}"],
        ["Planned ex-factory", d["planned_exfactory"]], ["Actual ex-factory", actual], ["Days late", late]]}
    return {"steps": [f"Loading PO {po_no} order and shipment record"], "text": text, "table": table,
            "chart": None, "sources": src,
            "followups": [f"Calculate a 4% per day late fine for PO {po_no}"] if late > 0 else []}


def _po_why(run, po_no: str) -> dict:
    pred = tools.get_po_prediction(run, po_no)["data"]
    if not pred:
        return _po_shipped(run, po_no)
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
