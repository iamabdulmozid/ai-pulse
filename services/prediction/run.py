"""ORM adapter for the prediction engine (docs/ai/prediction-engine.md §9).

This is the ONLY prediction module that touches the Django ORM. It loads rows into the plain record
shapes the pure engine expects, runs the engine, and writes PredictionRun / PredictionSnapshot /
FactoryStat. Pages and assistant tools read the resulting snapshots; they never recompute.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from services.prediction.aggregate import (
    build_contexts,
    compute_factory_stats,
    latest_inspection_by_po,
)
from services.prediction.params import EngineParams
from services.prediction.score import predict

HISTORY_DAYS = 365


def _load_params():
    from apps.masterdata.models import EngineParameter

    return EngineParams.from_mapping({p.key: p.value for p in EngineParameter.objects.all()})


def _params_hash(params: EngineParams) -> str:
    return hashlib.sha256(repr(params).encode()).hexdigest()[:64]


def _records():
    from apps.masterdata.models import Factory
    from apps.orders.models import PurchaseOrder, TAMilestone
    from apps.production.models import DailyProduction, Inspection, Shipment

    pos = [
        {
            "po_no": p.po_no,
            "factory_code": p.factory.code,
            "order_qty": p.order_qty,
            "planned_exfactory": p.planned_exfactory,
            "weight_kg_pc": float(p.style.weight_kg_pc),
            "fob_usd_pc": float(p.fob_usd_pc),
            "wash_required": p.style.wash_required,
            "is_open": p.is_open,
        }
        for p in PurchaseOrder.objects.select_related("factory", "style").all()
    ]
    daily = [
        {
            "po_no": d.purchase_order.po_no,
            "factory_code": d.factory.code,
            "report_date": d.report_date,
            "stage": d.stage,
            "day_pcs": d.day_pcs,
            "cum_pcs": d.cum_pcs,
            "machines": d.machines,
        }
        for d in DailyProduction.objects.select_related("purchase_order", "factory").all()
    ]
    milestones = [
        {
            "po_no": m.purchase_order.po_no,
            "milestone": m.milestone,
            "planned": m.planned_date,
            "revised": m.revised_date,
            "actual": m.actual_date,
        }
        for m in TAMilestone.objects.select_related("purchase_order").all()
    ]
    shipments = [
        {
            "factory_code": s.factory.code,
            "planned_exfactory": s.planned_exfactory,
            "actual_exfactory": s.actual_exfactory,
        }
        for s in Shipment.objects.select_related("factory").all()
    ]
    inspections = [
        {
            "po_no": i.purchase_order.po_no,
            "factory_code": i.factory.code,
            "inspection_date": i.inspection_date,
            "result": i.result,
        }
        for i in Inspection.objects.select_related("purchase_order", "factory").all()
    ]
    factory_codes = list(Factory.objects.values_list("code", flat=True))
    return pos, daily, milestones, shipments, inspections, factory_codes


@transaction.atomic
def run_predictions(
    trigger: str = "manual",
    today: date | None = None,
    upload_batch=None,
    latest_expected_report: date | None = None,
):
    from django.conf import settings

    from apps.masterdata.models import Factory, HolidayCalendar
    from apps.orders.models import PurchaseOrder
    from apps.predictions.models import FactoryStat, PredictionRun, PredictionSnapshot

    today = today or settings.DEMO_TODAY
    latest_expected_report = latest_expected_report or _latest_expected(today)
    history_start = date(today.year - 1, today.month, today.day)
    holidays = frozenset(HolidayCalendar.objects.values_list("date", flat=True))
    params = _load_params()

    pos, daily, milestones, shipments, inspections, factory_codes = _records()
    fstats = compute_factory_stats(
        factory_codes, daily, shipments, inspections, today, history_start, latest_expected_report, holidays
    )
    last_insp = latest_inspection_by_po(inspections)
    contexts = build_contexts(pos, daily, milestones, fstats, last_insp, latest_expected_report, open_only=True)

    as_of = _as_of(today)
    run = PredictionRun.objects.create(
        as_of=as_of, trigger=trigger, upload_batch=upload_batch, pos_scored=len(contexts),
        params_hash=_params_hash(params),
    )

    po_by_no = {p.po_no: p for p in PurchaseOrder.objects.filter(po_no__in=[c.po_no for c in contexts])}
    fac_by_code = {f.code: f for f in Factory.objects.all()}

    snapshots = []
    var_by_factory: dict[str, float] = {c: 0.0 for c in factory_codes}
    fob_by_factory: dict[str, float] = {c: 0.0 for c in factory_codes}
    pcs_by_factory: dict[str, int] = {c: 0 for c in factory_codes}
    pos_by_factory: dict[str, int] = {c: 0 for c in factory_codes}
    po_factory = {p["po_no"]: p["factory_code"] for p in pos}
    po_qty = {p["po_no"]: p["order_qty"] for p in pos}
    po_fob = {p["po_no"]: round(p["order_qty"] * p["fob_usd_pc"], 2) for p in pos}

    for ctx in contexts:
        r = predict(ctx, params, today, holidays)
        fc = po_factory[r.po_no]
        var_by_factory[fc] += r.value_at_risk_usd
        fob_by_factory[fc] += po_fob[r.po_no]
        pcs_by_factory[fc] += po_qty[r.po_no]
        pos_by_factory[fc] += 1
        snapshots.append(
            PredictionSnapshot(
                purchase_order=po_by_no[r.po_no], run=run, as_of=as_of, state=r.state,
                bottleneck_stage=r.bottleneck_stage, bottleneck_rate=r.bottleneck_rate,
                required_rate=r.required_rate, projected_finish_wd=r.projected_finish_wd,
                completion_day_n=r.completion_day_n, available_wd=r.available_wd, slack_wd=r.slack_wd,
                projected_exfactory=r.projected_exfactory, slip_days=r.slip_days,
                score_schedule=r.score_schedule, score_ta=r.score_ta, score_otd=r.score_otd,
                score_quality=r.score_quality, score_freshness=r.score_freshness, risk_score=r.risk_score,
                band=r.band, on_time_probability=r.on_time_probability,
                value_at_risk_usd=r.value_at_risk_usd, air_freight_exposure_usd=r.air_freight_exposure_usd,
                drivers=r.drivers,
            )
        )
    PredictionSnapshot.objects.bulk_create(snapshots, batch_size=500)

    stats = []
    for code in factory_codes:
        fs = fstats[code]
        stats.append(
            FactoryStat(
                run=run, factory=fac_by_code[code], otd_12m=round(fs.otd_12m, 3),
                aql_pass_90d=round(fs.aql_pass_90d, 3), slip_distribution=fs.slip_distribution,
                last_report_date=fs.last_report_date, reported_today=fs.reported_today, missed_wd=fs.missed_wd,
                knit_load_pct=0, open_pos=pos_by_factory[code], open_pcs=pcs_by_factory[code],
                exposure_usd=round(fob_by_factory[code], 2), value_at_risk_usd=round(var_by_factory[code], 2),
            )
        )
    FactoryStat.objects.bulk_create(stats, batch_size=200)
    return run


def build_po_context(po_no: str, today: date | None = None, latest_expected_report: date | None = None):
    """Build a single PO's engine context from the ORM (for PO detail + what-if). Pure engine downstream."""
    from django.conf import settings

    from apps.orders.models import PurchaseOrder, TAMilestone
    from apps.production.models import DailyProduction, Inspection, Shipment
    from services.prediction.aggregate import build_contexts, compute_factory_stats, latest_inspection_by_po

    today = today or settings.DEMO_TODAY
    latest_expected_report = latest_expected_report or _latest_expected(today)
    history_start = date(today.year - 1, today.month, today.day)

    po = PurchaseOrder.objects.select_related("factory", "style").get(po_no=po_no)
    fc = po.factory.code
    pos = [{
        "po_no": po.po_no, "factory_code": fc, "order_qty": po.order_qty,
        "planned_exfactory": po.planned_exfactory, "weight_kg_pc": float(po.style.weight_kg_pc),
        "fob_usd_pc": float(po.fob_usd_pc), "wash_required": po.style.wash_required, "is_open": po.is_open,
    }]
    daily = [
        {"po_no": d.purchase_order.po_no, "factory_code": fc, "report_date": d.report_date, "stage": d.stage,
         "day_pcs": d.day_pcs, "cum_pcs": d.cum_pcs, "machines": d.machines}
        for d in DailyProduction.objects.filter(factory=po.factory).select_related("purchase_order")
    ]
    milestones = [
        {"po_no": po.po_no, "milestone": m.milestone, "planned": m.planned_date,
         "revised": m.revised_date, "actual": m.actual_date}
        for m in TAMilestone.objects.filter(purchase_order=po)
    ]
    shipments = [
        {"factory_code": fc, "planned_exfactory": s.planned_exfactory, "actual_exfactory": s.actual_exfactory}
        for s in Shipment.objects.filter(factory=po.factory)
    ]
    inspections = [
        {"po_no": i.purchase_order.po_no, "factory_code": fc, "inspection_date": i.inspection_date,
         "result": i.result}
        for i in Inspection.objects.filter(factory=po.factory).select_related("purchase_order")
    ]
    fstats = compute_factory_stats([fc], daily, shipments, inspections, today, history_start, latest_expected_report)
    last_insp = latest_inspection_by_po(inspections)
    # Only keep this PO's daily rows for context building (factory daily was loaded for stats/rates).
    daily_po = [d for d in daily if d["po_no"] == po.po_no]
    ctxs = build_contexts(pos, daily_po, milestones, fstats, last_insp, latest_expected_report, open_only=False)
    return ctxs[0] if ctxs else None


def _latest_expected(today: date) -> date:
    """Factories report the previous working day; for the demo this is 14 Oct for today 15 Oct."""
    from services.calendar import prev_wd

    return prev_wd(today)


def _as_of(today: date) -> datetime:
    return timezone.make_aware(datetime(today.year, today.month, today.day, 9, 40))
