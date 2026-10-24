"""advance_demo: moving the demo dataset from 15 Oct to 25 Oct keeps the data and the engine consistent."""
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Max

from services import metrics
from services.calendar import upcoming_fridays

pytestmark = pytest.mark.django_db


def test_date_helpers_follow_the_demo_clock(settings):
    assert upcoming_fridays(date(2026, 10, 15), 3) == [date(2026, 10, 16), date(2026, 10, 23), date(2026, 10, 30)]
    assert upcoming_fridays(date(2026, 10, 25), 2) == [date(2026, 10, 30), date(2026, 11, 6)]
    assert metrics.outlook_start(date(2026, 10, 15)) == date(2026, 10, 10)  # answer-key Weekly Outlook
    assert metrics.outlook_start(date(2026, 10, 25)) == date(2026, 10, 24)


def test_advance_demo_to_25_oct(settings):
    from apps.orders.models import PurchaseOrder
    from apps.production.models import DailyProduction, Shipment

    call_command("seed_demo")
    hero_before = metrics.po_snapshot(metrics.latest_run(), "71010305")["slip_days"]
    settings.DEMO_TODAY = date(2026, 10, 25)
    call_command("advance_demo", "--to", "2026-10-25")

    run = metrics.latest_run()
    assert run.as_of.date() == date(2026, 10, 25)
    assert DailyProduction.objects.aggregate(m=Max("report_date"))["m"] == date(2026, 10, 24)

    # New shipments close their POs; nothing ships after the last report day.
    new = Shipment.objects.filter(actual_exfactory__gt=date(2026, 10, 14))
    assert new.exists()
    assert not PurchaseOrder.objects.filter(id__in=new.values("purchase_order"), is_open=True).exists()
    assert not Shipment.objects.filter(actual_exfactory__gt=date(2026, 10, 24)).exists()

    # Downstream stages never pass the stage before them.
    order = ["knitting", "linking", "trimming_mending", "washing", "ironing", "packing"]
    latest = {}
    for po_id, stage, cum in (DailyProduction.objects.filter(report_date__gt=date(2026, 10, 14))
                              .order_by("report_date").values_list("purchase_order_id", "stage", "cum_pcs")):
        latest[(po_id, stage)] = cum
    for (po_id, stage), cum in latest.items():
        i = order.index(stage)
        ups = [latest.get((po_id, s)) for s in order[:i] if latest.get((po_id, s)) is not None]
        if ups:
            assert cum <= ups[-1], (po_id, stage)

    # Reporting story and the hero's recovery plan.
    assert {m["code"] for m in metrics.reports_today(run)["missing"]} == {"OKH", "SLM", "PBB", "WSM"}
    assert metrics.po_snapshot(run, "71010305")["slip_days"] < hero_before

    with pytest.raises(CommandError):
        call_command("advance_demo", "--to", "2026-10-25")
