"""T-03 acceptance: migrations clean, model constraints, decimal fields."""
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, models

from apps.masterdata.models import Department, Factory, Season
from apps.orders.models import Comment, PurchaseOrder, Style

pytestmark = pytest.mark.django_db


def test_migrations_apply_clean():
    out = StringIO()
    # No missing migrations should be detected.
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)


def _po():
    # Use identifiers that never collide with seed_demo data, so this test is order-independent.
    dep, _ = Department.objects.get_or_create(name="Women")
    s, _ = Season.objects.get_or_create(code="TS26", defaults={"kind": "TS", "year": 26})
    fac = Factory.objects.create(code="TSTF", name="Test Knit", area="Testville", district="Dhaka", gauges="7GG")
    st = Style.objects.create(
        style_no="TST-W-0001", style_name="Test Cardigan", product_type="V-neck Cardigan",
        department=dep, gauge=7, yarn_composition="100% Lambswool", yarn_short="Lambswool",
        wash_required=True, weight_kg_pc=Decimal("0.720"), knitting_minutes_pc=Decimal("50.40"),
        linking_std_pcs_mc_day=32,
    )
    return PurchaseOrder.objects.create(
        po_no="90000001", po_date="2026-06-12", season=s, style=st, factory=fac, order_qty=9600,
        fob_usd_pc=Decimal("16.50"), fob_value_usd=Decimal("158400.00"), planned_exfactory="2026-10-29",
        destination="Hamburg, Germany",
    )


def test_comment_constraint_requires_exactly_one_target(django_user_model):
    _po()
    user = django_user_model.objects.create_user("u1", password="x")
    # Both null -> violates check
    with pytest.raises(IntegrityError):
        Comment.objects.create(author=user, text="bad: no target")


def test_is_open_toggles_on_shipment():
    from apps.production.models import Shipment

    po = _po()
    assert po.is_open is True
    Shipment.objects.create(
        shipment_id="SH-1", purchase_order=po, factory=po.factory, planned_exfactory="2026-10-29",
        actual_exfactory="2026-10-29", shipped_qty=9600, ship_mode="Sea", port_of_loading="Chattogram",
        destination="Hamburg, Germany", invoice_no="INV-1", invoice_value_usd=Decimal("158400.00"),
    )
    po.refresh_from_db()
    assert po.is_open is False


def test_decimal_fields_on_money_and_rates():
    """Money/rate/weight must be DecimalField (reproducible), never float."""
    checks = {
        PurchaseOrder: ["fob_usd_pc", "fob_value_usd"],
        Style: ["weight_kg_pc", "knitting_minutes_pc"],
    }
    for model, fields in checks.items():
        for f in fields:
            field = model._meta.get_field(f)
            assert isinstance(field, models.DecimalField), f"{model.__name__}.{f} must be Decimal"
