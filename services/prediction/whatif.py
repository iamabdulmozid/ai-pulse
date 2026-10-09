"""What-if simulation (docs/ai/prediction-engine.md §10). Pure Python.

Re-runs the SAME project() with overridden inputs (linking machines, Friday overtime days). Never a
separate formula, so the what-if partial and the recommendation cards always agree with the engine.
"""
from __future__ import annotations

from datetime import date

from services.prediction.engine import POContext, project
from services.prediction.params import EngineParams


def simulate(
    ctx: POContext,
    params: EngineParams,
    today: date,
    link_machines: int | None = None,
    overtime_days: frozenset[date] = frozenset(),
    holidays: frozenset[date] = frozenset(),
) -> dict:
    """Return the projection under the given overrides, as the UI/answer-key shape."""
    current = ctx.link_machines_current or link_machines or 1
    link_mult = (link_machines / current) if (link_machines and current) else 1.0
    pr = project(ctx, params, today, holidays=holidays, overtime=overtime_days, link_mult=link_mult)
    on_time = pr.slip_days <= 0
    air_avoided = (
        round(ctx.order_qty * ctx.weight_kg_pc * (params.air_usd_per_kg - params.sea_usd_per_kg), 2)
        if on_time
        else 0.0
    )
    linking = pr.stages.get("linking", {}) if pr.stages else {}
    return {
        "linking_pcs_day": round(linking.get("eff", 0.0), 1) if linking else None,
        "required_pcs_day": round(pr.required_rate, 1) if pr.required_rate else None,
        "available_wd": pr.available_wd,
        "completion_day_n": pr.n,
        "projected_exfactory": pr.projected_exfactory,
        "slip_days": pr.slip_days,
        "on_time": on_time,
        "air_freight_avoided_usd": air_avoided,
    }
