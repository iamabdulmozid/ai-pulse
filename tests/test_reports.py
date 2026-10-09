"""T-21/T-22 acceptance: the two Should-tier reports tie to the services and export to xlsx."""
import pytest
from django.core.management import call_command

from services import metrics


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def test_shipment_forecast_matches_outlook(seeded, client, django_user_model):
    run = metrics.latest_run()
    rows = metrics.shipment_forecast(run)

    # First two weekly rows match the answer-key Weekly Outlook exactly.
    assert rows[0]["pos"] == 13
    assert round(rows[0]["fob_usd"]) == 503790
    assert rows[1]["pos"] == 37
    assert round(rows[1]["fob_usd"]) == 1817169

    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)

    resp = client.get("/reports/shipment-forecast/", HTTP_HOST="localhost")
    assert resp.status_code == 200

    resp = client.get("/reports/shipment-forecast/?export=xlsx", HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert resp.content[:2] == b"PK"  # xlsx is a zip container


def test_factory_performance_report(seeded, client, django_user_model):
    run = metrics.latest_run()
    rows = metrics.factory_performance(run)

    grl = next(r for r in rows if r["code"] == "GRL")
    assert round(grl["value_at_risk_usd"], 2) == 774058.56

    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.get("/reports/factory-performance/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    resp = client.get("/reports/factory-performance/?export=xlsx", HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
