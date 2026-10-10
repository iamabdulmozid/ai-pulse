"""Assistant tool catalogue (docs/ai/assistant.md).

Every tool calls the SAME services.* functions the screens use, so chat and screens never disagree. Each
tool returns {data, as_of, source}. No free-form SQL; numbers never come from the model.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from services import metrics
from services.prediction.recommend import recommend

SOURCE = "Prediction snapshot"


def _env(run, data, source=SOURCE):
    return {"data": data, "as_of": run.as_of.isoformat(), "source": source}


def get_portfolio_kpis(run) -> dict:
    return _env(run, metrics.portfolio_kpis(run))


def get_october_ontime(run) -> dict:
    k = metrics.portfolio_kpis(run)
    return _env(run, {"october_on_time_pct": k["october_on_time_pct"]})


def get_value_at_risk(run) -> dict:
    lb = metrics.leaderboard(run)
    total = sum(f["value_at_risk_usd"] for f in lb)
    top = [f for f in lb if f["value_at_risk_usd"] > 0][:5]
    return _env(run, {
        "total_usd": total,
        "by_factory": [{"code": f["code"], "name": f["name"], "value_at_risk_usd": f["value_at_risk_usd"],
                        "share_pct": round(f["value_at_risk_usd"] / total * 100, 1) if total else 0} for f in top],
    })


def list_factories_missing_report(run) -> dict:
    rt = metrics.reports_today(run)
    return _env(run, {"missing": rt["missing"], "received": rt["received"], "expected": rt["expected"]})


def _closed_note(po_no: str) -> str | None:
    """Why a PO has no prediction: shipped/closed, or unknown. None when the PO is open."""
    from apps.orders.models import PurchaseOrder

    po = PurchaseOrder.objects.filter(po_no=po_no).only("is_open").first()
    if po is None:
        return f"PO {po_no} does not exist."
    if not po.is_open:
        return f"PO {po_no} has already shipped (closed) — predictions only cover open POs. Use get_po_details."
    return None


def get_po_prediction(run, po_no: str) -> dict:
    try:
        return _env(run, metrics.po_snapshot(run, po_no))
    except Exception:
        return {**_env(run, None), "note": _closed_note(po_no) or f"No prediction for PO {po_no}."}


def _iso(v):
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _iso(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_iso(x) for x in v]
    return v


def get_po_details(run, po_no: str) -> dict:
    """Order + delivery record for any PO (open or shipped): qty, FOB/pc, order value, shipments, days late."""
    d = metrics.po_details(run, po_no)
    return {**_env(run, _iso(d), source="Order book + shipment log"),
            **({} if d else {"note": f"PO {po_no} does not exist."})}


def calculate_late_penalty(run, po_no: str, rate_pct: float, per: str = "day", base: str = "order_value",
                           days_late: int | None = None, cap_pct: float | None = None) -> dict:
    """Late-delivery penalty for a PO, computed exactly (the model never does the arithmetic).

    per: "day" | "week" (started weeks) | "once" (flat). base: "order_value" (qty x FOB) | "invoice_value"
    (what was actually invoiced). Days late default to the shipment's actual vs planned ex-factory, or the
    predicted slip for an open PO. cap_pct caps the total penalty as a % of the base.
    """
    src = "Order book + shipment log"
    d = metrics.po_details(run, po_no)
    if d is None:
        return {**_env(run, None, source=src), "note": f"PO {po_no} does not exist."}
    days_source = "given"
    if days_late is None:
        if d["days_late"] is not None:
            days_late, days_source = d["days_late"], "actual vs planned ex-factory"
        elif d["prediction"]:
            days_late, days_source = d["prediction"]["slip_days"], "PROJECTED slip (PO not shipped yet)"
        else:
            days_late, days_source = 0, "no shipment or prediction"
    days = max(int(days_late), 0)

    if base == "invoice_value" and d["invoice_value_usd"]:
        base_label, base_amount = "invoice value", Decimal(str(d["invoice_value_usd"]))
    else:
        base_label, base_amount = "order value (qty x FOB)", Decimal(str(d["order_value_usd"]))
    units = {"day": days, "week": math.ceil(days / 7), "once": 1 if days > 0 else 0}.get(per, days)
    raw_pct = pct = Decimal(str(rate_pct)) * units
    capped = cap_pct is not None and pct > Decimal(str(cap_pct))
    if capped:
        pct = Decimal(str(cap_pct))
    penalty = (base_amount * pct / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    unit_word = {"day": "day", "week": "week", "once": "flat"}.get(per, "day")
    formula = (f"{rate_pct}% x {units} {unit_word}{'s' if units != 1 and per != 'once' else ''} = {raw_pct}%"
               + (f", capped at {pct}%" if capped else "") + f" of ${base_amount:,.2f} = ${penalty:,.2f}")
    return _env(run, {
        "po_no": po_no, "status": d["status"], "factory_code": d["factory_code"],
        "planned_exfactory": _iso(d["planned_exfactory"]),
        "actual_exfactory": _iso(d["shipments"][-1]["actual_exfactory"]) if d["shipments"] else None,
        "days_late": days, "days_late_source": days_source,
        "rate_pct": rate_pct, "per": per, "units": units, "total_pct": float(pct), "capped": capped,
        "base": base_label, "base_amount_usd": float(base_amount),
        "penalty_usd": float(penalty), "formula": formula,
    }, source=src)


def get_po_whatif(po_no: str, link_machines: int | None = None, overtime_days: list[str] | None = None) -> dict:
    from django.conf import settings

    note = _closed_note(po_no)
    if note:
        return {"data": None, "as_of": None, "source": "What-if engine", "note": note}

    from services.prediction.run import _load_params, build_po_context
    from services.prediction.whatif import simulate

    ctx = build_po_context(po_no)
    if ctx is None:
        return {"data": None, "as_of": None, "source": "What-if engine"}
    ot = frozenset(date.fromisoformat(d) for d in (overtime_days or []))
    sim = simulate(ctx, _load_params(), settings.DEMO_TODAY, link_machines=link_machines, overtime_days=ot)
    sim = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in sim.items()}
    return {"data": sim, "as_of": settings.DEMO_TODAY.isoformat(), "source": "What-if engine"}


def get_po_recommendation(run, po_no: str) -> dict:
    note = _closed_note(po_no)
    if note:
        return {**_env(run, [], source="Recommendation engine"), "note": note}
    opts = recommend(po_no, run)
    out = []
    for o in opts:
        o = dict(o)
        if o.get("projected_exfactory") and isinstance(o["projected_exfactory"], date):
            o["projected_exfactory"] = o["projected_exfactory"].isoformat()
        out.append(o)
    return _env(run, out, source="Recommendation engine")


def get_factory_scorecard(run, code: str) -> dict:
    """One factory's scorecard, matched by code (GRL) or by name (case-insensitive substring)."""
    key = (code or "").strip().lower()
    cards = metrics.factory_scorecards(run)
    card = next((c for c in cards if c["code"].lower() == key), None)
    if card is None and key:
        card = next((c for c in cards if key in c["name"].lower()), None)
    return _env(run, card)


def list_factory_scorecards(run) -> dict:
    """Quality + delivery headline for every factory (AQL pass % over 90 days, 12-month OTD, load, risk)."""
    rows = [{"code": c["code"], "name": c["name"], "aql_pass_pct": round(c["aql_pass_pct"], 1),
             "otd_pct": round(c["otd_pct"], 1), "knit_load_pct": round(c["knit_load_pct"], 1),
             "open_pos": c["open_pos"], "value_at_risk_usd": round(c["value_at_risk_usd"]),
             "reported_today": c["reported_today"]}
            for c in metrics.factory_scorecards(run)]
    return _env(run, sorted(rows, key=lambda r: r["aql_pass_pct"]))  # weakest quality first


def list_at_risk_pos(run, factory: str | None = None, dept: str | None = None, band: list | None = None,
                     exf_month: list | None = None, limit: int = 50) -> dict:
    f = metrics.POFilters(
        factory=[factory] if factory else None,
        dept=[dept] if dept else None,
        band=band or ["At risk", "Critical", "Late"],
        exf_month=exf_month,
    )
    rows = metrics.po_list(run, f)[:limit]
    rows = [{**r, "exf_date": r["exf_date"].isoformat()} for r in rows]
    return _env(run, rows)


def get_shipped_summary(run, month: str | None = None, late_limit: int | None = 50) -> dict:
    """What actually shipped in a month ('YYYY-MM'); defaults to last month relative to the demo clock."""
    from django.conf import settings

    month = month or metrics.last_month(settings.DEMO_TODAY)
    d = metrics.shipped_in_month(month)
    d["late_shipments"] = [{**r, "planned_exfactory": r["planned_exfactory"].isoformat(),
                            "actual_exfactory": r["actual_exfactory"].isoformat()} for r in d["late_shipments"][:late_limit]]
    return _env(run, d, source="Shipment log")


def get_shipment_outlook(run) -> dict:
    rows = metrics.shipment_forecast(run)
    rows = [{**r, "week_start": r["week_start"].isoformat()} for r in rows]
    return _env(run, rows)


# Catalogue (name -> callable) for the OpenAI tool-calling loop and the fallback router.
CATALOGUE = {
    "get_portfolio_kpis": get_portfolio_kpis,
    "get_october_ontime": get_october_ontime,
    "get_value_at_risk": get_value_at_risk,
    "list_factories_missing_report": list_factories_missing_report,
    "get_po_prediction": get_po_prediction,
    "get_po_details": get_po_details,
    "calculate_late_penalty": calculate_late_penalty,
    "get_po_whatif": get_po_whatif,
    "get_po_recommendation": get_po_recommendation,
    "get_factory_scorecard": get_factory_scorecard,
    "list_factory_scorecards": list_factory_scorecards,
    "list_at_risk_pos": list_at_risk_pos,
    "get_shipment_outlook": get_shipment_outlook,
    "get_shipped_summary": get_shipped_summary,
}
