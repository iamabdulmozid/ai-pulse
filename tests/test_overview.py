"""T-11/T-12 acceptance: Executive Overview reproduces the headline numbers (MS-2)."""
import pytest
from django.core.management import call_command

from services import metrics


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def test_overview_kpis(seeded):
    run = metrics.latest_run()
    k = metrics.portfolio_kpis(run)
    assert k["open_pos"] == 412
    assert k["open_pcs"] == 1900020
    assert float(k["open_fob_usd"]) == 18601449.36
    assert k["october_on_time_pct"] == 0.8625
    assert float(k["value_at_risk_usd"]) == 2400006.24
    assert float(k["air_freight_exposure_usd"]) == 539720.28
    assert k["at_risk_pos"] == 48
    assert k["reports_today"]["received"] == 18
    assert {m["code"] for m in k["reports_today"]["missing"]} == {"SLM", "OKH", "HMR", "PBB"}


def test_overview_outlook_matches_answer_key(seeded):
    run = metrics.latest_run()
    ol = metrics.outlook(run)
    assert ol[0]["pos"] == 13
    assert round(ol[0]["fob_usd"]) == 503790
    assert ol[1]["pos"] == 37
    assert round(ol[1]["fob_usd"]) == 1817169


def test_overview_page_renders(seeded, client, django_user_model):
    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.get("/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "86.25%" in body
    assert "briefing" in body.lower()


def test_heatmap_noupdate(seeded):
    run = metrics.latest_run()
    rows = metrics.heatmap(run)
    not_reporting = {r["code"] for r in rows if not r["reported"]}
    assert {"SLM", "OKH", "HMR", "PBB"} & not_reporting  # the quiet factories are striped
    for r in rows:
        if not r["reported"]:
            assert all(c == -1 for c in r["cells"])
