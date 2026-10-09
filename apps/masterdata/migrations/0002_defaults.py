from decimal import Decimal

from django.db import migrations

ENGINE_PARAMETER_DEFAULTS = {
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

# T&A template: (seq, milestone, days before ex-factory, responsible)
TA_TEMPLATE = [
    (1, "Yarn booking", 95, "Factory"),
    (2, "Yarn shade approval", 85, "Karbar Merchandising"),
    (3, "Fit sample approval", 80, "Karbar Merchandising"),
    (4, "Size set approval", 60, "Karbar Merchandising"),
    (5, "PP sample approval", 50, "Karbar Merchandising"),
    (6, "Yarn in-house", 45, "Factory / Yarn supplier"),
    (7, "PP meeting", 42, "Factory + Karbar QA"),
    (8, "Knitting start", 40, "Factory"),
    (9, "Linking start", 34, "Factory"),
    (10, "Final inspection", 1, "Karbar QA"),
    (11, "Ex-factory", 0, "Factory"),
]

GROUPS = ["Admin", "Management", "Merchandiser", "QA"]


def load_defaults(apps, schema_editor):
    EngineParameter = apps.get_model("masterdata", "EngineParameter")
    for key, (value, desc) in ENGINE_PARAMETER_DEFAULTS.items():
        EngineParameter.objects.update_or_create(
            key=key, defaults={"value": Decimal(value), "description": desc}
        )

    TATemplate = apps.get_model("masterdata", "TATemplate")
    TAMilestoneDef = apps.get_model("masterdata", "TAMilestoneDef")
    tpl, _ = TATemplate.objects.get_or_create(name="Standard sweater")
    for seq, name, days, resp in TA_TEMPLATE:
        TAMilestoneDef.objects.update_or_create(
            template=tpl, seq=seq,
            defaults={"milestone": name, "days_before_exfactory": days, "responsible": resp},
        )

    Group = apps.get_model("auth", "Group")
    for g in GROUPS:
        Group.objects.get_or_create(name=g)


def unload(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(load_defaults, unload)]
