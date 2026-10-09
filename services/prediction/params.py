"""Engine parameter set (docs/ai/prediction-engine.md §8). Pure; no Django imports.

The ORM adapter builds EngineParams from the EngineParameter table; tests and the reference engine build
it from the defaults. Decimal in, float out only where the generator uses float arithmetic internally
(rates/finishes); money is rounded at output by the adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class EngineParams:
    air_usd_per_kg: float = 6.0
    sea_usd_per_kg: float = 0.5
    rate_window_wd: int = 7
    flow_limit_days: float = 1.5
    yarn_to_knit_days: int = 2
    knit_mc_minutes_per_day: int = 1020
    stage_lag: dict[str, float] = field(
        default_factory=lambda: {"linking": 1.0, "trimming_mending": 0.5, "washing": 0.5, "ironing": 0.5, "packing": 0.5}
    )
    score_schedule_cap: float = 50.0
    score_ta_cap: float = 20.0
    score_otd_cap: float = 15.0
    score_quality_cap: float = 10.0
    score_freshness_cap: float = 5.0
    band_on_track_max: float = 25.0
    band_watch_max: float = 50.0
    band_at_risk_max: float = 75.0
    slip_forces_critical: int = 7
    freshness_missed1: float = 3.0
    freshness_missed2plus: float = 5.0
    prob_floor: float = 0.02
    prob_ceiling: float = 0.98

    @classmethod
    def from_mapping(cls, m: dict[str, Decimal | float | int | str]) -> EngineParams:
        return cls(
            air_usd_per_kg=float(m.get("air_usd_per_kg", 6.0)),
            sea_usd_per_kg=float(m.get("sea_usd_per_kg", 0.5)),
            rate_window_wd=int(float(m.get("rate_window_wd", 7))),
            flow_limit_days=float(m.get("flow_limit_days", 1.5)),
            yarn_to_knit_days=int(float(m.get("yarn_to_knit_days", 2))),
            knit_mc_minutes_per_day=int(float(m.get("knit_mc_minutes_per_day", 1020))),
            stage_lag={
                "linking": float(m.get("stage_lag_linking", 1.0)),
                "trimming_mending": float(m.get("stage_lag_mending", 0.5)),
                "washing": float(m.get("stage_lag_washing", 0.5)),
                "ironing": float(m.get("stage_lag_ironing", 0.5)),
                "packing": float(m.get("stage_lag_packing", 0.5)),
            },
            score_schedule_cap=float(m.get("score_schedule_cap", 50)),
            score_ta_cap=float(m.get("score_ta_cap", 20)),
            score_otd_cap=float(m.get("score_otd_cap", 15)),
            score_quality_cap=float(m.get("score_quality_cap", 10)),
            score_freshness_cap=float(m.get("score_freshness_cap", 5)),
            band_on_track_max=float(m.get("band_on_track_max", 25)),
            band_watch_max=float(m.get("band_watch_max", 50)),
            band_at_risk_max=float(m.get("band_at_risk_max", 75)),
            slip_forces_critical=int(float(m.get("slip_forces_critical", 7))),
            freshness_missed1=float(m.get("freshness_missed1", 3)),
            freshness_missed2plus=float(m.get("freshness_missed2plus", 5)),
            prob_floor=float(m.get("prob_floor", 0.02)),
            prob_ceiling=float(m.get("prob_ceiling", 0.98)),
        )
