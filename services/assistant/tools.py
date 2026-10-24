"""Assistant tool catalogue (docs/ai/assistant.md).

Every tool calls the SAME services.* functions the screens use, so chat and screens never disagree. Each
tool returns {data, as_of, source}. No free-form SQL; numbers never come from the model.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
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


def get_shipped_summary(run, month: str | None = None, date_from: str | None = None, date_to: str | None = None,
                        late_limit: int | None = 50) -> dict:
    """What actually shipped in a month ('YYYY-MM') or a date window; defaults to last month (demo clock)."""
    from django.conf import settings

    if date_from or date_to:
        lo = date.fromisoformat(date_from) if date_from else date.fromisoformat(date_to).replace(day=1)
        d = metrics.shipped_between(lo, date.fromisoformat(date_to) if date_to else settings.DEMO_TODAY)
    else:
        d = metrics.shipped_in_month(month or metrics.last_month(settings.DEMO_TODAY))
    d["late_shipments"] = _iso(d["late_shipments"][:late_limit])
    return _env(run, _iso(d), source="Shipment log")


def _merch_usernames(name: str) -> list[str]:
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    users = get_user_model().objects.filter(
        Q(username__icontains=name) | Q(first_name__icontains=name) | Q(last_name__icontains=name))
    return list(users.values_list("username", flat=True))


def search_pos(run, factory: str | None = None, dept: str | None = None, merchandiser: str | None = None,
               band: list | None = None, exf_from: str | None = None, exf_to: str | None = None,
               exf_month: str | None = None, text: str | None = None, sort: str = "risk", limit: int = 30) -> dict:
    """Open POs matching any filters (all bands unless given), with totals. Covers upcoming ex-factories,
    a merchandiser's or department's book, a factory's orders, style search."""
    f = metrics.POFilters(
        factory=[factory.upper()] if factory else None, dept=[dept] if dept else None,
        merchandiser=_merch_usernames(merchandiser) or ["__none__"] if merchandiser else None,
        band=band or None, exf_month=[exf_month] if exf_month else None,
        exf_from=date.fromisoformat(exf_from) if exf_from else None,
        exf_to=date.fromisoformat(exf_to) if exf_to else None, q=text or None, sort=sort)
    rows = metrics.po_list(run, f)
    bands: dict[str, int] = {}
    for r in rows:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
    return _env(run, {
        "count": len(rows), "pcs": sum(r["qty_pcs"] for r in rows),
        "fob_value_usd": round(sum(r["fob_value_usd"] for r in rows), 2), "by_band": bands,
        "pos": _iso([{k: r[k] for k in ("po_no", "factory_code", "style_name", "department", "merchandiser",
                                         "qty_pcs", "fob_value_usd", "exf_date", "band", "slip_days")}
                     for r in rows[:limit]]),
    })


def list_inspections(run, date_from: str | None = None, date_to: str | None = None, factory: str | None = None,
                     result: str | None = None, inspection_type: str | None = None) -> dict:
    """QA inspections in a window (default: the last 7 days)."""
    from django.conf import settings

    hi = date.fromisoformat(date_to) if date_to else settings.DEMO_TODAY
    lo = date.fromisoformat(date_from) if date_from else hi - timedelta(days=7)
    d = metrics.inspections_between(lo, hi, factory, result, inspection_type)
    d["inspections"] = d["inspections"][:40]
    return _env(run, _iso(d), source="Inspection log")


def list_overdue_milestones(run, factory: str | None = None) -> dict:
    from django.conf import settings

    rows = metrics.overdue_milestones(settings.DEMO_TODAY, factory)
    by_ms: dict[str, int] = {}
    for r in rows:
        by_ms[r["milestone"]] = by_ms.get(r["milestone"], 0) + 1
    return _env(run, {"count": len(rows), "by_milestone": by_ms, "milestones": _iso(rows[:40])},
                source="T&A calendar")


def list_open_alerts(run, severity: str | None = None) -> dict:
    rows = metrics.open_alerts(severity)
    return _env(run, {"count": len(rows), "alerts": _iso(rows[:40])}, source="Alerts")


def get_changes_since_last_run(run) -> dict:
    d = metrics.run_changes(run)
    return {**_env(run, _iso(d) if d else None), **({} if d else {"note": "There is no earlier run to compare."})}


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
    "search_pos": search_pos,
    "list_inspections": list_inspections,
    "list_overdue_milestones": list_overdue_milestones,
    "list_open_alerts": list_open_alerts,
    "get_changes_since_last_run": get_changes_since_last_run,
}
