"""Read-side metrics (docs/tech/architecture.md §1).

Every number shown on a screen or returned by an assistant tool comes from here, computed from the latest
PredictionSnapshot / FactoryStat. Pages never recompute the engine. Each function returns plain data with
an `as_of`, so chat and screens cannot disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Q, Sum

BAND_LEVEL = {"On track": 1, "Watch": 2, "At risk": 3, "Critical": 4, "Late": 4}
AT_RISK_BANDS = ("At risk", "Critical", "Late")
OUTLOOK_WEEKS = 8


def outlook_start(today: date | None = None) -> date:
    """Saturday that starts the current Bangladesh work week (Sat-Thu): week 1 of the 8-week outlook.
    For the 15 Oct demo clock this is 10 Oct, matching the answer-key Weekly Outlook."""
    from django.conf import settings

    today = today or settings.DEMO_TODAY
    return today - timedelta(days=(today.weekday() - 5) % 7)


def latest_run():
    from apps.predictions.models import PredictionRun

    return PredictionRun.objects.order_by("-as_of").first()


def _snapshots(run):
    from apps.predictions.models import PredictionSnapshot

    return (
        PredictionSnapshot.objects.filter(run=run)
        .select_related("purchase_order", "purchase_order__factory", "purchase_order__style",
                        "purchase_order__style__department", "purchase_order__season",
                        "purchase_order__merchandiser")
    )


def reports_today(run) -> dict:
    from apps.predictions.models import FactoryStat

    stats = FactoryStat.objects.filter(run=run)
    expected = stats.count()
    received = stats.filter(reported_today=True).count()
    missing = list(
        FactoryStat.objects.filter(run=run, reported_today=False)
        .select_related("factory").values_list("factory__code", "factory__name", "last_report_date")
    )
    return {
        "received": received,
        "expected": expected,
        "missing": [{"code": c, "name": n, "last_report": lr} for c, n, lr in missing],
    }


def portfolio_kpis(run) -> dict:
    snaps = _snapshots(run)
    open_pos = snaps.count()
    agg = snaps.aggregate(
        pcs=Sum("purchase_order__order_qty"),
        fob=Sum("purchase_order__fob_value_usd"),
        var=Sum("value_at_risk_usd"),
        air=Sum("air_freight_exposure_usd"),
    )
    oct_pct = october_on_time(run)
    rt = reports_today(run)
    return {
        "as_of": run.as_of,
        "open_pos": open_pos,
        "open_pcs": agg["pcs"] or 0,
        "open_fob_usd": agg["fob"] or 0,
        "october_on_time_pct": oct_pct,
        "value_at_risk_usd": agg["var"] or 0,
        "air_freight_exposure_usd": agg["air"] or 0,
        "at_risk_pos": snaps.filter(band__in=AT_RISK_BANDS).count(),
        "reports_today": rt,
    }


def october_on_time(run) -> float:
    from apps.production.models import Shipment

    snaps = _snapshots(run)
    oct_lo, oct_hi = date(2026, 10, 1), date(2026, 10, 31)
    octo = snaps.filter(purchase_order__planned_exfactory__range=(oct_lo, oct_hi))
    oct_open_on = octo.filter(slip_days__lte=0).exclude(band="Late").count()
    oct_open_total = octo.count()
    from django.db.models import F

    # Only shipments known when this run was made, so an older run keeps the figure it reported.
    ship = Shipment.objects.filter(planned_exfactory__range=(oct_lo, oct_hi), actual_exfactory__lt=run.as_of.date())
    oct_ship_total = ship.count()
    oct_ship_on = ship.filter(actual_exfactory__lte=F("planned_exfactory")).count()
    total = oct_open_total + oct_ship_total
    return round((oct_ship_on + oct_open_on) / total, 4) if total else 0.0


def last_month(today: date) -> str:
    """'YYYY-MM' of the calendar month before `today` (the demo clock, settings.DEMO_TODAY)."""
    prev = today.replace(day=1) - timedelta(days=1)
    return f"{prev:%Y-%m}"


def shipped_in_month(month: str) -> dict:
    """What actually left the factories in a calendar month ('YYYY-MM'), by actual ex-factory date."""
    y, m = (int(x) for x in month.split("-"))
    lo = date(y, m, 1)
    hi = (lo + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return {"month": month, **shipped_between(lo, hi)}


def shipped_between(lo: date, hi: date) -> dict:
    """What actually left the factories between two dates (inclusive), by actual ex-factory date.

    On time = actual ex-factory on or before the planned ex-factory date. Values are invoice USD.
    """
    from django.db.models import F

    from apps.production.models import Shipment

    ship = Shipment.objects.filter(actual_exfactory__range=(lo, hi)).select_related("factory", "purchase_order")
    total = ship.count()
    on_time = ship.filter(actual_exfactory__lte=F("planned_exfactory")).count()
    agg = ship.aggregate(pcs=Sum("shipped_qty"), value=Sum("invoice_value_usd"), air=Sum("air_freight_cost_usd"))

    by_factory: dict[str, dict] = {}
    late = []
    for s in ship.order_by("actual_exfactory"):
        g = by_factory.setdefault(s.factory.code, {"code": s.factory.code, "name": s.factory.name,
                                                   "shipments": 0, "pcs": 0, "value_usd": 0.0, "on_time": 0})
        g["shipments"] += 1
        g["pcs"] += s.shipped_qty
        g["value_usd"] += float(s.invoice_value_usd)
        delay = (s.actual_exfactory - s.planned_exfactory).days
        if delay <= 0:
            g["on_time"] += 1
        else:
            late.append({"po_no": s.purchase_order.po_no, "factory_code": s.factory.code,
                         "planned_exfactory": s.planned_exfactory, "actual_exfactory": s.actual_exfactory,
                         "days_late": delay, "ship_mode": s.ship_mode, "shipped_qty": s.shipped_qty})
    factories = sorted(by_factory.values(), key=lambda g: g["value_usd"], reverse=True)
    for g in factories:
        g["value_usd"] = round(g["value_usd"], 2)
        g["on_time_pct"] = round(g["on_time"] / g["shipments"] * 100, 1)

    return {
        "from": lo, "to": hi,
        "shipments": total,
        "pos": ship.values("purchase_order").distinct().count(),
        "pcs": agg["pcs"] or 0,
        "value_usd": float(agg["value"] or 0),
        "on_time": on_time,
        "on_time_pct": round(on_time / total * 100, 1) if total else 0.0,
        "late_count": len(late),
        "air_freight_cost_usd": float(agg["air"] or 0),
        "by_ship_mode": dict(ship.values_list("ship_mode").annotate(n=Count("id"))),
        "by_status": dict(ship.values_list("shipment_status").annotate(n=Count("id"))),
        "by_factory": factories,
        "late_shipments": sorted(late, key=lambda r: r["days_late"], reverse=True),
    }


def top_at_risk(run, n=10) -> list[dict]:
    snaps = _snapshots(run).filter(band__in=AT_RISK_BANDS).order_by("-risk_score")[:n]
    return [_po_row(s) for s in snaps]


def _po_row(s) -> dict:
    po = s.purchase_order
    return {
        "po_no": po.po_no,
        "style_no": po.style.style_no,
        "style_name": po.style.style_name,
        "department": po.style.department.name,
        "season": po.season.code,
        "gauge": po.style.gauge,
        "yarn": po.style.yarn_short,
        "factory_code": po.factory.code,
        "factory_name": po.factory.name,
        "qty_pcs": po.order_qty,
        "fob_usd_pc": float(po.fob_usd_pc),
        "fob_value_usd": float(po.fob_value_usd),
        "exf_date": po.planned_exfactory,
        "band": s.band,
        "risk_score": s.risk_score,
        "slip_days": s.slip_days,
        "on_time_prob": float(s.on_time_probability),
        "merchandiser": po.merchandiser.get_full_name() if po.merchandiser else "",
        "top_driver": s.drivers[0] if s.drivers else "",
    }


def status_counts(run) -> dict:
    snaps = _snapshots(run)
    by_band = dict(snaps.values_list("band").annotate(n=Count("id")))
    return {
        "all": snaps.count(),
        "critical": by_band.get("Critical", 0),
        "risk": by_band.get("At risk", 0),
        "late": by_band.get("Late", 0),
        "watch": by_band.get("Watch", 0),
        "ok": by_band.get("On track", 0),
    }


def outlook(run) -> list[dict]:
    """8-week shipment outlook by band (FOB USD), matching the answer-key Weekly Outlook."""
    snaps = _snapshots(run)
    weeks = []
    for i in range(OUTLOOK_WEEKS):
        a = outlook_start() + timedelta(days=7 * i)
        b = a + timedelta(days=6)
        wk = snaps.filter(purchase_order__planned_exfactory__range=(a, b))
        row = {"week_start": a, "label": a.strftime("%d %b"),
               "pos": wk.count(),
               "pcs": wk.aggregate(s=Sum("purchase_order__order_qty"))["s"] or 0,
               "fob_usd": float(wk.aggregate(s=Sum("purchase_order__fob_value_usd"))["s"] or 0)}
        for band in ("On track", "Watch", "At risk", "Critical", "Late"):
            v = wk.filter(band=band).aggregate(s=Sum("purchase_order__fob_value_usd"))["s"] or 0
            row[band] = float(v)
        weeks.append(row)
    return weeks


def heatmap(run, limit=10) -> list[dict]:
    """Factory × 8-week risk cells (0 none … 4 critical; -1 = factory not reporting)."""
    from apps.predictions.models import FactoryStat

    snaps = _snapshots(run)
    stats = {fs.factory.code: fs for fs in FactoryStat.objects.filter(run=run).select_related("factory")}
    # Rank factories by exposure, show the top `limit`.
    ranked = sorted(stats.values(), key=lambda fs: fs.value_at_risk_usd, reverse=True)[:limit]
    rows = []
    for fs in ranked:
        cells = []
        for i in range(OUTLOOK_WEEKS):
            a = outlook_start() + timedelta(days=7 * i)
            b = a + timedelta(days=6)
            if not fs.reported_today:
                cells.append(-1)
                continue
            wk = snaps.filter(purchase_order__factory=fs.factory,
                              purchase_order__planned_exfactory__range=(a, b))
            level = 0
            for band in wk.values_list("band", flat=True):
                level = max(level, BAND_LEVEL.get(band, 0))
            cells.append(level)
        rows.append({"code": fs.factory.code, "name": fs.factory.name, "cells": cells,
                     "reported": fs.reported_today})
    return rows


def leaderboard(run) -> list[dict]:
    from apps.predictions.models import FactoryStat

    out = []
    for fs in FactoryStat.objects.filter(run=run).select_related("factory").order_by("-value_at_risk_usd"):
        out.append({
            "code": fs.factory.code, "name": fs.factory.name, "district": fs.factory.district,
            "otd_pct": float(fs.otd_12m) * 100, "knit_load_pct": float(fs.knit_load_pct),
            "reported_today": fs.reported_today, "open_pos": fs.open_pos,
            "exposure_usd": float(fs.exposure_usd), "value_at_risk_usd": float(fs.value_at_risk_usd),
            "aql_pass_pct": float(fs.aql_pass_90d) * 100, "last_report": fs.last_report_date,
        })
    return out


def dept_gauge_split(run) -> dict:
    snaps = _snapshots(run)

    def split(field):
        rows = []
        groups = snaps.values(field).annotate(
            value=Sum("purchase_order__fob_value_usd"),
            at_risk=Sum("purchase_order__fob_value_usd", filter=Q(band__in=AT_RISK_BANDS)),
            n=Count("id"),
        ).order_by("-value")
        total = sum(g["value"] or 0 for g in groups) or 1
        for g in groups:
            val = float(g["value"] or 0)
            rows.append({"name": str(g[field]), "open_value_usd": val, "pos": g["n"],
                         "share_pct": round(val / float(total) * 100, 1),
                         "at_risk_pct": round(float(g["at_risk"] or 0) / val * 100, 1) if val else 0})
        return rows

    return {
        "department": split("purchase_order__style__department__name"),
        "gauge": split("purchase_order__style__gauge"),
    }


# --------------------------------------------------------------- PO list ---
@dataclass
class POFilters:
    dept: list[str] = None
    season: list[str] = None
    factory: list[str] = None
    gauge: list[int] = None
    band: list[str] = None
    exf_month: list[str] = None  # "YYYY-MM"
    exf_from: date = None  # planned ex-factory window (inclusive)
    exf_to: date = None
    merchandiser: list[str] = None
    q: str = None
    sort: str = "risk"  # risk|slip|exf|fob


def po_list(run, filters: POFilters | None = None) -> list[dict]:
    filters = filters or POFilters()
    snaps = _snapshots(run)
    f = filters
    if f.dept:
        snaps = snaps.filter(purchase_order__style__department__name__in=f.dept)
    if f.season:
        snaps = snaps.filter(purchase_order__season__code__in=f.season)
    if f.factory:
        snaps = snaps.filter(purchase_order__factory__code__in=f.factory)
    if f.gauge:
        snaps = snaps.filter(purchase_order__style__gauge__in=f.gauge)
    if f.band:
        snaps = snaps.filter(band__in=f.band)
    if f.merchandiser:
        snaps = snaps.filter(purchase_order__merchandiser__username__in=f.merchandiser)
    if f.q:
        snaps = snaps.filter(
            Q(purchase_order__po_no__icontains=f.q)
            | Q(purchase_order__style__style_no__icontains=f.q)
            | Q(purchase_order__style__style_name__icontains=f.q)
        )
    if f.exf_month:
        from functools import reduce
        from operator import or_

        q = reduce(or_, (Q(purchase_order__planned_exfactory__year=int(m.split("-")[0]),
                           purchase_order__planned_exfactory__month=int(m.split("-")[1])) for m in f.exf_month))
        snaps = snaps.filter(q)
    if f.exf_from:
        snaps = snaps.filter(purchase_order__planned_exfactory__gte=f.exf_from)
    if f.exf_to:
        snaps = snaps.filter(purchase_order__planned_exfactory__lte=f.exf_to)
    order = {"risk": "-risk_score", "slip": "-slip_days", "exf": "purchase_order__planned_exfactory",
             "fob": "-purchase_order__fob_value_usd"}.get(f.sort, "-risk_score")
    snaps = snaps.order_by(order)
    return [_po_row(s) for s in snaps]


def inspections_between(lo: date, hi: date, factory: str | None = None, result: str | None = None,
                        kind: str | None = None) -> dict:
    """QA inspections in a date window: counts by type/result and the rows (newest first)."""
    from apps.production.models import Inspection

    qs = Inspection.objects.filter(inspection_date__range=(lo, hi)).select_related("purchase_order", "factory")
    if factory:
        qs = qs.filter(factory__code=factory.upper())
    if result:
        qs = qs.filter(result__iexact=result)
    if kind:
        qs = qs.filter(inspection_type__icontains=kind)
    rows = [{"date": i.inspection_date, "po_no": i.purchase_order.po_no, "factory_code": i.factory.code,
             "type": i.inspection_type, "result": i.result, "major_found": i.major_found,
             "major_accept": i.major_accept, "main_defect": i.main_defect, "inspector": i.inspector}
            for i in qs.order_by("-inspection_date", "-id")]
    passed = sum(1 for r in rows if r["result"] == "Pass")
    return {"from": lo, "to": hi, "total": len(rows), "passed": passed, "failed": len(rows) - passed,
            "pass_pct": round(passed / len(rows) * 100, 1) if rows else None,
            "by_type": dict(qs.values_list("inspection_type").annotate(n=Count("id"))), "inspections": rows}


def overdue_milestones(today: date, factory: str | None = None) -> list[dict]:
    """Open POs' T&A milestones past their (revised) due date with no actual date."""
    from apps.orders.models import TAMilestone

    qs = (TAMilestone.objects.filter(purchase_order__is_open=True, actual_date__isnull=True)
          .select_related("purchase_order", "factory"))
    if factory:
        qs = qs.filter(factory__code=factory.upper())
    out = []
    for m in qs:
        due = m.revised_date or m.planned_date
        if due < today:
            out.append({"po_no": m.purchase_order.po_no, "factory_code": m.factory.code, "milestone": m.milestone,
                        "responsible": m.responsible, "due": due, "days_overdue": (today - due).days})
    return sorted(out, key=lambda r: r["days_overdue"], reverse=True)


def open_alerts(severity: str | None = None) -> list[dict]:
    from apps.alerts.models import Alert

    qs = Alert.objects.filter(state="open").select_related("purchase_order", "factory")
    if severity:
        qs = qs.filter(severity=severity)
    return [{"created": a.created_at, "kind": a.kind, "severity": a.severity, "text": a.text,
             "po_no": a.purchase_order.po_no if a.purchase_order else None,
             "factory_code": a.factory.code if a.factory else None} for a in qs[:100]]


def run_changes(run) -> dict | None:
    """What changed between the previous prediction run and this one: headline KPIs, band moves per PO,
    POs that shipped in between, and the biggest slip changes."""
    from apps.predictions.models import PredictionRun, PredictionSnapshot

    prev = PredictionRun.objects.filter(as_of__lt=run.as_of).order_by("-as_of").first()
    if prev is None:
        return None
    k_now, k_prev = portfolio_kpis(run), portfolio_kpis(prev)
    keys = ("open_pos", "open_fob_usd", "october_on_time_pct", "value_at_risk_usd", "air_freight_exposure_usd",
            "at_risk_pos")
    now = {s.purchase_order.po_no: s for s in _snapshots(run)}
    before = {s.purchase_order.po_no: s
              for s in PredictionSnapshot.objects.filter(run=prev).select_related("purchase_order")}
    shipped = sorted(set(before) - set(now))
    worse, better = [], []
    for po_no, s in now.items():
        b = before.get(po_no)
        if b is None:
            continue
        d = s.slip_days - b.slip_days
        row = {"po_no": po_no, "factory_code": s.purchase_order.factory.code, "band_before": b.band,
               "band_now": s.band, "slip_before": b.slip_days, "slip_now": s.slip_days, "change_days": d}
        if BAND_LEVEL[s.band] > BAND_LEVEL[b.band] or d > 0:
            worse.append(row)
        elif BAND_LEVEL[s.band] < BAND_LEVEL[b.band] or d < 0:
            better.append(row)
    worse.sort(key=lambda r: (BAND_LEVEL[r["band_now"]] - BAND_LEVEL[r["band_before"]], r["change_days"]),
               reverse=True)
    better.sort(key=lambda r: (BAND_LEVEL[r["band_before"]] - BAND_LEVEL[r["band_now"]], -r["change_days"]),
                reverse=True)
    return {
        "previous_as_of": prev.as_of, "current_as_of": run.as_of,
        "kpis": {k: {"before": float(k_prev[k]), "now": float(k_now[k])} for k in keys},
        "shipped_since": len(shipped), "shipped_po_nos": shipped[:30],
        "worsened": len(worse), "improved": len(better), "top_worsened": worse[:10], "top_improved": better[:10],
    }


# --------------------------------------------------------------- PO detail -
def po_snapshot(run, po_no: str):
    """The latest snapshot + PO row for a single PO (detail header, prediction, drivers)."""

    s = _snapshots(run).get(purchase_order__po_no=po_no)
    row = _po_row(s)
    po = s.purchase_order
    row.update({
        "state": s.state,
        "projected_exfactory": s.projected_exfactory,
        "bottleneck_stage": s.bottleneck_stage,
        "bottleneck_rate": float(s.bottleneck_rate) if s.bottleneck_rate else None,
        "required_rate": float(s.required_rate) if s.required_rate else None,
        "available_wd": s.available_wd,
        "slack_wd": float(s.slack_wd) if s.slack_wd is not None else None,
        "model_version": s.model_version,
        "as_of": s.as_of,
        "drivers": s.drivers,
        "ship_mode": po.planned_ship_mode,
        "port": po.port_of_loading,
        "destination": po.destination,
        "colours": po.lines.count(),
        "wash_required": po.style.wash_required,
        "score": {"schedule": float(s.score_schedule), "ta": float(s.score_ta), "otd": float(s.score_otd),
                  "quality": float(s.score_quality), "freshness": float(s.score_freshness)},
    })
    return row


def po_details(run, po_no: str) -> dict | None:
    """Commercial + delivery record for ANY PO, open or shipped: order value, shipments, days late,
    latest inspection, and the prediction when the PO is still open. None if the PO does not exist."""
    from apps.orders.models import PurchaseOrder

    po = (PurchaseOrder.objects.select_related("factory", "style", "style__department", "season", "merchandiser")
          .filter(po_no=po_no).first())
    if po is None:
        return None
    shipments = []
    for s in po.shipments.order_by("actual_exfactory"):
        shipments.append({
            "shipment_id": s.shipment_id, "planned_exfactory": s.planned_exfactory,
            "actual_exfactory": s.actual_exfactory, "days_late": (s.actual_exfactory - s.planned_exfactory).days,
            "shipped_qty": s.shipped_qty, "invoice_no": s.invoice_no, "invoice_value_usd": float(s.invoice_value_usd),
            "ship_mode": s.ship_mode, "air_freight_cost_usd": float(s.air_freight_cost_usd or 0),
            "status": s.shipment_status,
        })
    insp = po.inspections.order_by("-inspection_date", "-id").first()
    snap = po.snapshots.filter(run=run).first() if run else None
    return {
        "po_no": po.po_no, "status": "Open" if po.is_open else "Shipped",
        "po_date": po.po_date, "season": po.season.code,
        "factory_code": po.factory.code, "factory_name": po.factory.name,
        "style_no": po.style.style_no, "style_name": po.style.style_name, "department": po.style.department.name,
        "merchandiser": po.merchandiser.get_full_name() if po.merchandiser else "",
        "order_qty": po.order_qty, "fob_usd_pc": float(po.fob_usd_pc), "order_value_usd": float(po.fob_value_usd),
        "planned_exfactory": po.planned_exfactory, "planned_ship_mode": po.planned_ship_mode,
        "destination": po.destination, "delivery_terms": po.delivery_terms,
        "shipments": shipments,
        "shipped_qty": sum(s["shipped_qty"] for s in shipments),
        "invoice_value_usd": round(sum(s["invoice_value_usd"] for s in shipments), 2),
        "days_late": max((s["days_late"] for s in shipments), default=None),
        "latest_inspection": ({"date": insp.inspection_date, "type": insp.inspection_type, "result": insp.result,
                               "main_defect": insp.main_defect} if insp else None),
        "prediction": ({"band": snap.band, "projected_exfactory": snap.projected_exfactory,
                        "slip_days": snap.slip_days} if snap else None),
    }


def po_ta(po_no: str) -> list[dict]:
    from apps.orders.models import TAMilestone

    out = []
    for m in TAMilestone.objects.filter(purchase_order__po_no=po_no).order_by("seq"):
        out.append({"seq": m.seq, "milestone": m.milestone, "responsible": m.responsible,
                    "planned": m.planned_date, "revised": m.revised_date, "actual": m.actual_date,
                    "status": m.status, "remarks": m.remarks})
    return out


def po_curves(po_no: str) -> dict:
    from apps.production.models import DailyProduction

    series: dict[str, list[dict]] = {}
    qs = DailyProduction.objects.filter(purchase_order__po_no=po_no).order_by("report_date")
    for d in qs:
        series.setdefault(d.stage, []).append({"date": d.report_date.isoformat(), "cum": d.cum_pcs})
    return series


# --------------------------------------------------------------- factories -
def _machines_by_gauge(factory):
    return {m.gauge: m.count for m in factory.machines.all()}


def factory_scorecards(run) -> list[dict]:
    from apps.masterdata.models import Factory
    from apps.predictions.models import FactoryStat

    stats = {fs.factory_id: fs for fs in FactoryStat.objects.filter(run=run)}
    out = []
    for f in Factory.objects.prefetch_related("machines").all():
        fs = stats.get(f.id)
        if not fs:
            continue
        mbg = _machines_by_gauge(f)
        out.append({
            "code": f.code, "name": f.name, "location": f"{f.area}, {f.district}",
            "machines_by_gauge": mbg, "machines_total": sum(mbg.values()),
            "linking_machines": f.linking_machines,
            "knit_load_pct": float(fs.knit_load_pct), "otd_pct": float(fs.otd_12m) * 100,
            "aql_pass_pct": float(fs.aql_pass_90d) * 100, "reported_today": fs.reported_today,
            "last_report": fs.last_report_date, "open_pos": fs.open_pos, "open_pcs": fs.open_pcs,
            "exposure_usd": float(fs.exposure_usd), "value_at_risk_usd": float(fs.value_at_risk_usd),
            "certifications": f.certifications, "bsci_rating": f.bsci_rating,
        })
    return sorted(out, key=lambda r: r["value_at_risk_usd"], reverse=True)


def factory_detail(run, code: str) -> dict:
    from datetime import timedelta

    from apps.masterdata.models import Factory
    from apps.production.models import DailyProduction, Inspection

    f = Factory.objects.prefetch_related("machines").get(code=code)
    card = next((c for c in factory_scorecards(run) if c["code"] == code), None)
    order_book = [r for r in po_list(run) if r["factory_code"] == code]
    # 14-day stage output
    cutoff = run.as_of.date() - timedelta(days=15)
    output: dict[str, list] = {}
    for d in DailyProduction.objects.filter(factory=f, report_date__gte=cutoff).order_by("report_date"):
        output.setdefault(d.stage, {})
        day = output[d.stage].setdefault(d.report_date.isoformat(), 0)
        output[d.stage][d.report_date.isoformat()] = day + d.day_pcs
    output_series = {st: [{"date": k, "pcs": v} for k, v in sorted(days.items())] for st, days in output.items()}
    inspections = [
        {"po_no": i.purchase_order.po_no, "date": i.inspection_date, "type": i.inspection_type,
         "result": i.result, "main_defect": i.main_defect}
        for i in Inspection.objects.filter(factory=f).select_related("purchase_order").order_by("-inspection_date")[:20]
    ]
    certs = [{"name": c.strip(), "status": "Valid"} for c in (f.certifications or "").split(",") if c.strip()]
    return {"card": card, "factory": {"code": f.code, "name": f.name, "area": f.area, "district": f.district,
                                      "contact": f.contact_name, "bsci": f.bsci_rating,
                                      "last_audit": f.last_social_audit},
            "order_book": order_book, "output": output_series, "inspections": inspections, "certificates": certs}


def factory_performance(run) -> list[dict]:
    return factory_scorecards(run)


def shipment_forecast(run) -> list[dict]:
    rows = outlook(run)
    snaps = _snapshots(run)
    for i, row in enumerate(rows):
        from datetime import timedelta
        a = outlook_start() + timedelta(days=7 * i)
        b = a + timedelta(days=6)
        wk = snaps.filter(purchase_order__planned_exfactory__range=(a, b))
        total = wk.count()
        on = wk.filter(slip_days__lte=0).exclude(band="Late").count()
        row["on_time_pct"] = round(on / total * 100, 1) if total else 0.0
        row["at_risk_usd"] = sum(row[b] for b in ("At risk", "Critical", "Late"))
    return rows
