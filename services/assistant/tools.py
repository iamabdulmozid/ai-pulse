"""Assistant tool catalogue (docs/ai/assistant.md).

Every tool calls the SAME services.* functions the screens use, so chat and screens never disagree. Each
tool returns {data, as_of, source}. No free-form SQL; numbers never come from the model.
"""
from __future__ import annotations

from datetime import date

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


def get_po_prediction(run, po_no: str) -> dict:
    try:
        return _env(run, metrics.po_snapshot(run, po_no))
    except Exception:
        return _env(run, None)


def get_po_whatif(po_no: str, link_machines: int | None = None, overtime_days: list[str] | None = None) -> dict:
    from django.conf import settings

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
    "get_po_whatif": get_po_whatif,
    "get_po_recommendation": get_po_recommendation,
    "get_factory_scorecard": get_factory_scorecard,
    "list_factory_scorecards": list_factory_scorecards,
    "list_at_risk_pos": list_at_risk_pos,
    "get_shipment_outlook": get_shipment_outlook,
}
