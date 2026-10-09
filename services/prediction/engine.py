"""Prediction engine core (docs/ai/prediction-engine.md §2–§7). Pure Python — no Django/ORM imports.

Faithful port of the reference implementation in sample_data/scripts/generate_sample_data.py
(weighted_rate, stage_rates, project, project_pre, predict_all). The answer key is the test
(tests/test_engine_matches_answer_key.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from services.calendar import is_working_day, nth_wd, wd_between
from services.prediction.params import EngineParams

ONE = timedelta(days=1)
ALL_STAGES = ["knitting", "linking", "trimming_mending", "washing", "ironing", "packing"]
STAGE_LABEL = {
    "knitting": "Knitting",
    "linking": "Linking",
    "trimming_mending": "Trimming & Mending",
    "washing": "Washing",
    "ironing": "Ironing",
    "packing": "Packing",
}


def weighted_rate(values: list[float]) -> float:
    if not values:
        return 0.0
    w = range(1, len(values) + 1)
    return sum(a * b for a, b in zip(w, values, strict=False)) / sum(w)


@dataclass
class Milestone:
    planned: date | None = None
    revised: date | None = None
    actual: date | None = None


@dataclass
class POContext:
    po_no: str
    order_qty: int
    planned_exfactory: date
    weight_kg_pc: float
    fob_usd_pc: float
    wash_required: bool
    # reported daily production up to the factory's last report:
    day_pcs: dict[str, dict[date, int]]  # stage -> {date: day pcs}
    cum: dict[str, int]  # stage -> latest cumulative
    last_report: date
    # T&A milestones by name:
    milestones: dict[str, Milestone]
    # factory stats:
    factory_otd_12m: float
    factory_aql_pass_90d: float
    slip_distribution: list[int]
    factory_last_report: date
    latest_expected_report: date
    latest_inspection_result: str | None = None  # "Pass"/"Fail"/None
    link_machines_current: int | None = None

    def stages(self) -> list[str]:
        return [s for s in ALL_STAGES if s != "washing" or self.wash_required]


@dataclass
class Projection:
    state: str
    finish: float | None
    n: int | None
    available_wd: int
    slack_wd: float | None
    projected_exfactory: date
    slip_days: int
    bottleneck: str | None
    bottleneck_rate: float | None
    required_rate: float | None
    stages: dict[str, dict] = field(default_factory=dict)
    proj_knit: date | None = None


def stage_rates(ctx: POContext, params: EngineParams, holidays: frozenset[date]) -> dict[str, float]:
    # Window: the last RATE_WINDOW working days ending at the factory's last report (base calendar).
    window: list[date] = []
    d = ctx.last_report
    while len(window) < params.rate_window_wd:
        if is_working_day(d, holidays):
            window.append(d)
        d -= ONE
    window.reverse()
    rates: dict[str, float] = {}
    for s in ctx.stages():
        series = ctx.day_pcs.get(s, {})
        firsts = sorted(dt for dt, v in series.items() if v > 0)
        if not firsts:
            rates[s] = 0.0
            continue
        first = firsts[0]
        days = [dt for dt in window if dt >= first]
        rates[s] = weighted_rate([series.get(dt, 0) for dt in days])
    return rates


def project_in_production(
    ctx: POContext,
    params: EngineParams,
    today: date,
    holidays: frozenset[date] = frozenset(),
    overtime: frozenset[date] = frozenset(),
    link_mult: float = 1.0,
) -> Projection:
    stages = ctx.stages()
    cum = dict(ctx.cum)
    meas = stage_rates(ctx, params, holidays)
    meas["linking"] = meas.get("linking", 0.0) * link_mult

    info: dict[str, dict] = {}
    prev = None
    f_prev = 0.0
    rem_prev = 0
    eff_prev = None
    for s in stages:
        rem = ctx.order_qty - cum.get(s, 0)
        m = meas.get(s, 0.0)
        limited = prev is not None and (cum.get(s, 0) == 0 or cum.get(prev, 0) - cum.get(s, 0) <= params.flow_limit_days * m)
        follows = limited and rem_prev > 0
        eff = max(m, eff_prev) if (limited and eff_prev is not None) else m
        lag = params.stage_lag.get(s, 0.0)
        lower = f_prev + lag if (prev is not None and rem_prev > 0) else 0.0
        if rem <= 0:
            fin, binding = 0.0, "done"
        elif follows:
            fin, binding = lower, "flow"
        else:
            own = rem / eff if eff > 0 else math.inf
            fin, binding = (own, "own") if own >= lower else (lower, "flow")
        info[s] = {"cum": cum.get(s, 0), "rem": rem, "rate": m, "eff": eff, "finish": fin, "binding": binding}
        prev, f_prev, rem_prev, eff_prev = s, fin, rem, eff

    finish = f_prev
    n = 0 if finish <= 0 else math.ceil(finish - 1e-9)
    avail = wd_between(today, ctx.planned_exfactory, holidays, overtime)
    if n == 0:
        proj_exf = max(today, ctx.planned_exfactory) if ctx.planned_exfactory >= today else today
    else:
        proj_exf = _next_wd(nth_wd(today, n, holidays, overtime), holidays, overtime)

    bott = None
    for s in stages:
        if info[s]["binding"] == "own":
            bott = s
    req = None
    if bott:
        later = stages[stages.index(bott) + 1:]
        denom = avail - sum(params.stage_lag.get(s, 0.0) for s in later)
        req = info[bott]["rem"] / denom if denom > 0 else None

    return Projection(
        state="In production",
        finish=finish,
        n=n,
        available_wd=avail,
        slack_wd=avail - n,
        projected_exfactory=proj_exf,
        slip_days=(proj_exf - ctx.planned_exfactory).days,
        bottleneck=bott,
        bottleneck_rate=info[bott]["eff"] if bott else None,
        required_rate=req,
        stages=info,
    )


def _next_wd(d: date, holidays: frozenset[date], overtime: frozenset[date]) -> date:
    d += ONE
    while not is_working_day(d, holidays, overtime):
        d += ONE
    return d


def project_pre(ctx: POContext, params: EngineParams, today: date, holidays: frozenset[date] = frozenset()) -> Projection:
    yarn = ctx.milestones.get("Yarn in-house", Milestone())
    knit = ctx.milestones.get("Knitting start", Milestone())
    yarn_date = yarn.actual or max(yarn.revised or yarn.planned or today, today)
    knit_planned = knit.planned or today
    if knit.actual:
        proj_knit = knit.actual
    else:
        proj_knit = max(knit_planned, yarn_date + timedelta(days=params.yarn_to_knit_days))
        if knit_planned < today:
            proj_knit = max(proj_knit, today)
    delay = max(0, (proj_knit - knit_planned).days)
    proj_exf = ctx.planned_exfactory + timedelta(days=delay)
    return Projection(
        state="Pre-production",
        finish=None,
        n=None,
        available_wd=wd_between(today, ctx.planned_exfactory, holidays),
        slack_wd=None,
        projected_exfactory=proj_exf,
        slip_days=delay,
        bottleneck=None,
        bottleneck_rate=None,
        required_rate=None,
        proj_knit=proj_knit,
    )


def has_started_knitting(ctx: POContext) -> bool:
    return ctx.cum.get("knitting", 0) > 0


def project(
    ctx: POContext,
    params: EngineParams,
    today: date,
    holidays: frozenset[date] = frozenset(),
    overtime: frozenset[date] = frozenset(),
    link_mult: float = 1.0,
) -> Projection:
    if has_started_knitting(ctx):
        return project_in_production(ctx, params, today, holidays, overtime, link_mult)
    return project_pre(ctx, params, today, holidays)
