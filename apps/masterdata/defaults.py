"""Canonical EngineParameter defaults = answer-key Parameters sheet (docs/ai/prediction-engine.md §8).

Values are strings to preserve exact decimals when written to DecimalField.
"""
from decimal import Decimal

ENGINE_PARAMETER_DEFAULTS: dict[str, tuple[str, str]] = {
    # key: (value, description)
    "air_usd_per_kg": ("6.0000", "Air freight cost per kg"),
    "sea_usd_per_kg": ("0.5000", "Sea freight cost per kg"),
    "rate_window_wd": ("7", "Working days in the weighted rate window"),
    "flow_limit_days": ("1.5", "Work-in-front threshold for a supply-limited stage"),
    "yarn_to_knit_days": ("2", "Days from yarn in-house to knitting start"),
    "knit_mc_minutes_per_day": ("1020", "Available knitting minutes per machine per day"),
    "stage_lag_linking": ("1.0", "Linking lag (working days)"),
    "stage_lag_mending": ("0.5", "Trimming & mending lag (working days)"),
    "stage_lag_washing": ("0.5", "Washing lag (working days)"),
    "stage_lag_ironing": ("0.5", "Ironing lag (working days)"),
    "stage_lag_packing": ("0.5", "Packing lag (working days)"),
    "score_schedule_cap": ("50", "Schedule component cap"),
    "score_ta_cap": ("20", "T&A component cap"),
    "score_otd_cap": ("15", "Factory OTD component cap"),
    "score_quality_cap": ("10", "Quality component cap"),
    "score_freshness_cap": ("5", "Freshness component cap"),
    "band_on_track_max": ("25", "Score < this = On track"),
    "band_watch_max": ("50", "Score < this = Watch"),
    "band_at_risk_max": ("75", "Score < this = At risk; else Critical"),
    "slip_forces_critical": ("7", "Slip >= this forces Critical"),
    "freshness_missed1": ("3", "Freshness points for 1 missed working day"),
    "freshness_missed2plus": ("5", "Freshness points for 2+ missed working days"),
    "prob_floor": ("0.02", "On-time probability floor"),
    "prob_ceiling": ("0.98", "On-time probability ceiling"),
}


def as_decimals() -> dict[str, Decimal]:
    return {k: Decimal(v[0]) for k, v in ENGINE_PARAMETER_DEFAULTS.items()}
