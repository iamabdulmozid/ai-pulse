"""Risk score, bands, probability, cost and drivers (docs/ai/prediction-engine.md §5–§7).

Pure Python. Faithful port of generate_sample_data.py::predict_all. Produces a PredictionResult that
maps 1:1 to the answer key's `Open PO Predictions` columns and to PredictionSnapshot fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from services.calendar import next_wd, wd_between
from services.prediction.engine import STAGE_LABEL, Milestone, POContext, Projection, project
from services.prediction.params import EngineParams


@dataclass
class PredictionResult:
    po_no: str
    state: str
    bottleneck_stage: str
    bottleneck_rate: float | None
    required_rate: float | None
    projected_finish_wd: float | None
    completion_day_n: int | None
    available_wd: int
    slack_wd: float | None
    projected_exfactory: date
    slip_days: int
    score_schedule: float
    score_ta: float
    score_otd: float
    score_quality: float
    score_freshness: float
    risk_score: int
    band: str
    on_time_probability: float
    value_at_risk_usd: float
    air_freight_exposure_usd: float
    drivers: list[str] = field(default_factory=list)


def _days(a: date, b: date) -> int:
    return (a - b).days


def predict(
    ctx: POContext,
    params: EngineParams,
    today: date,
    holidays: frozenset[date] = frozenset(),
) -> PredictionResult:
    pr: Projection = project(ctx, params, today, holidays)
    slip = pr.slip_days

    # --- schedule (max 50) ---
    if pr.n == 0:
        sched = 0.0
    elif slip > 0:
        sched = 35 + min(15, 1.5 * slip)
    elif pr.state == "In production" and pr.slack_wd is not None and pr.slack_wd <= 2:
        sched = 25.0
    elif pr.state == "In production" and pr.slack_wd is not None and pr.slack_wd <= 5:
        sched = 12.0
    else:
        sched = 0.0

    # --- T&A (max 20) ---
    y = ctx.milestones.get("Yarn in-house", Milestone())
    y_planned = y.planned or today
    y_eff = y.actual or max(y.revised or y_planned, today)
    y_late = _days(y_eff, y_planned)
    ppa = ctx.milestones.get("PP sample approval", Milestone())
    pp_planned = ppa.planned or today
    pp_late = _days(ppa.actual or today, pp_planned) if (ppa.actual or pp_planned < today) else 0
    tna = (12 if y_late >= 8 else 8 if y_late >= 4 else 4 if y_late >= 1 else 0) + (8 if pp_late >= 3 else 0)
    tna = min(20, tna)

    # --- factory OTD (max 15) ---
    rel = min(15.0, (1 - ctx.factory_otd_12m) * 50)

    # --- quality (max 10) ---
    if ctx.latest_inspection_result == "Fail":
        qual = 10
    elif ctx.factory_aql_pass_90d < 0.85:
        qual = 5
    else:
        qual = 0

    # --- freshness (max 5) — in-production only ---
    if pr.state == "In production":
        stale = wd_between(next_wd(ctx.factory_last_report, holidays), next_wd(ctx.latest_expected_report, holidays), holidays)
    else:
        stale = 0
    fresh = 0 if stale == 0 else (3 if stale == 1 else 5)

    score = round(min(100, sched + tna + rel + qual + fresh))

    # --- band ---
    if score < params.band_on_track_max:
        band = "On track"
    elif score < params.band_watch_max:
        band = "Watch"
    elif score < params.band_at_risk_max:
        band = "At risk"
    else:
        band = "Critical"
    if slip > 0 and band in ("On track", "Watch"):
        band = "At risk"
    if slip >= params.slip_forces_critical:
        band = "Critical"
    if ctx.planned_exfactory < today:
        band = "Late"

    # --- probability ---
    s_cal = -slip
    hs = ctx.slip_distribution
    if hs:
        prob = min(params.prob_ceiling, max(params.prob_floor, sum(1 for v in hs if v <= s_cal) / len(hs)))
    else:
        prob = 0.5

    at_risk = band in ("At risk", "Critical", "Late")
    late_flag = slip > 0 or ctx.planned_exfactory < today
    var = round(ctx.order_qty * ctx.fob_usd_pc, 2) if at_risk else 0.0
    air = round(ctx.order_qty * ctx.weight_kg_pc * (params.air_usd_per_kg - params.sea_usd_per_kg), 2) if late_flag else 0.0

    # --- drivers (order matters; matches answer key) ---
    drivers: list[str] = []
    if pr.bottleneck and pr.required_rate and pr.bottleneck_rate is not None and pr.bottleneck_rate < pr.required_rate:
        drivers.append(f"{STAGE_LABEL[pr.bottleneck]} {pr.bottleneck_rate:,.0f} pcs/day vs {pr.required_rate:,.0f} needed")
    if y.revised and not y.actual:
        drivers.append(f"Yarn in-house revised to {y.revised:%d %b} ({y_late} days late)")
    elif y_late >= 4:
        drivers.append(f"Yarn in-house {y_late} days late")
    if pp_late >= 3:
        drivers.append(f"PP sample approval {pp_late} days late")
    if ctx.factory_otd_12m < 0.8:
        drivers.append(f"Factory OTD {ctx.factory_otd_12m:.0%} (12 months)")
    if qual == 10:
        drivers.append("Last inspection failed")
    if fresh:
        drivers.append(f"No report since {ctx.factory_last_report:%d %b}")

    return PredictionResult(
        po_no=ctx.po_no,
        state=pr.state,
        bottleneck_stage=STAGE_LABEL.get(pr.bottleneck, "") if pr.bottleneck else "",
        bottleneck_rate=round(pr.bottleneck_rate, 1) if pr.bottleneck_rate else None,
        required_rate=round(pr.required_rate, 1) if pr.required_rate else None,
        projected_finish_wd=round(pr.finish, 2) if pr.finish is not None else None,
        completion_day_n=pr.n,
        available_wd=pr.available_wd,
        slack_wd=pr.slack_wd,
        projected_exfactory=pr.projected_exfactory,
        slip_days=slip,
        score_schedule=round(sched, 1),
        score_ta=tna,
        score_otd=round(rel, 1),
        score_quality=qual,
        score_freshness=fresh,
        risk_score=score,
        band=band,
        on_time_probability=round(prob, 2),
        value_at_risk_usd=var,
        air_freight_exposure_usd=air,
        drivers=drivers,
    )
