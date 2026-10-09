"""T-02 acceptance: master data admin + engine parameter defaults."""
import pytest
from django.contrib import admin

from apps.masterdata.defaults import ENGINE_PARAMETER_DEFAULTS
from apps.masterdata.models import (
    Department,
    EngineParameter,
    Factory,
    HolidayCalendar,
    Season,
    TATemplate,
)

pytestmark = pytest.mark.django_db


def test_masterdata_admin_registered():
    for model in (Factory, EngineParameter, TATemplate, HolidayCalendar, Department, Season):
        assert model in admin.site._registry, f"{model.__name__} not registered in admin"


def test_engine_parameter_defaults():
    for key, (value, _desc) in ENGINE_PARAMETER_DEFAULTS.items():
        row = EngineParameter.objects.get(key=key)
        assert str(row.value) == str(float(value)) or row.value == __import__("decimal").Decimal(value), key
    # Spot-check the load-bearing ones.
    assert EngineParameter.objects.get(key="air_usd_per_kg").value == __import__("decimal").Decimal("6.0000")
    assert EngineParameter.objects.get(key="sea_usd_per_kg").value == __import__("decimal").Decimal("0.5000")
    assert EngineParameter.objects.get(key="rate_window_wd").value == __import__("decimal").Decimal("7")
