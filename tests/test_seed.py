"""T-04/T-09 acceptance (DB-backed): seed counts, hero present, snapshots reproduce the answer key."""
from collections import Counter
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def test_seed_counts(seeded):
    from apps.masterdata.models import Factory
    from apps.orders.models import PurchaseOrder

    assert Factory.objects.count() == 22
    assert PurchaseOrder.objects.count() == 1287
    open_qs = PurchaseOrder.objects.filter(is_open=True)
    assert open_qs.count() == 412
    assert open_qs.aggregate(s=Sum("order_qty"))["s"] == 1900020
    assert open_qs.aggregate(s=Sum("fob_value_usd"))["s"] == Decimal("18601449.36")


def test_seed_hero_and_donor_present(seeded):
    from apps.orders.models import PurchaseOrder

    hero = PurchaseOrder.objects.get(po_no="71010305")
    assert hero.factory.code == "GRL"
    assert hero.order_qty == 9600
    assert hero.style.gauge == 7
    assert hero.style.department.name == "Women"
    assert hero.planned_exfactory.isoformat() == "2026-10-29"
    assert hero.fob_value_usd == Decimal("158400.00")
    assert PurchaseOrder.objects.filter(po_no="71009573").exists()  # donor


def test_predictions_snapshot_kpis(seeded):
    from apps.predictions.models import FactoryStat, PredictionRun, PredictionSnapshot

    run = PredictionRun.objects.latest("as_of")
    qs = PredictionSnapshot.objects.filter(run=run)
    assert qs.count() == 412
    assert qs.aggregate(s=Sum("value_at_risk_usd"))["s"] == Decimal("2400006.24")
    assert qs.aggregate(s=Sum("air_freight_exposure_usd"))["s"] == Decimal("539720.28")
    bands = dict(Counter(qs.values_list("band", flat=True)))
    assert bands == {"On track": 354, "Watch": 10, "At risk": 28, "Critical": 13, "Late": 7}
    assert FactoryStat.objects.filter(run=run, reported_today=True).count() == 18


def test_predictions_hero_snapshot(seeded):
    from apps.predictions.models import PredictionRun, PredictionSnapshot

    run = PredictionRun.objects.latest("as_of")
    h = PredictionSnapshot.objects.get(run=run, purchase_order__po_no="71010305")
    assert h.band == "Critical"
    assert h.risk_score == 76
    assert h.projected_exfactory.isoformat() == "2026-11-07"
    assert h.slip_days == 9
    assert h.on_time_probability == Decimal("0.020")


def test_seed_personas_and_groups(seeded):
    from django.contrib.auth.models import Group, User

    assert set(Group.objects.values_list("name", flat=True)) >= {"Admin", "Management", "Merchandiser", "QA"}
    assert User.objects.filter(username="ceo").exists()
    assert User.objects.get(username="admin").is_superuser
