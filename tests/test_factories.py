"""T-16 acceptance: Factories list + detail (FR-FAC)."""
import pytest
from django.core.management import call_command

from services import metrics


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def test_factory_list_scorecards(seeded, client, django_user_model):
    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.get("/factories/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    body = resp.content.decode()
    # GRL (top exposure / value at risk) is present and rendered.
    assert "GRL" in body
    assert "Greyloom Knitwear Ltd." in body
    # A factory that did not report today shows the "No update" stripe/pill.
    assert "No update" in body
    # GRL is the top row by value at risk (service orders desc).
    scorecards = metrics.factory_scorecards(metrics.latest_run())
    assert scorecards[0]["code"] == "GRL"


def test_factory_scorecard_values(seeded):
    run = metrics.latest_run()
    grl = next(c for c in metrics.factory_scorecards(run) if c["code"] == "GRL")
    assert grl["open_pos"] == 52
    assert round(grl["otd_pct"], 1) == 68.1
    assert abs(grl["value_at_risk_usd"] - 774058.56) <= 1
    assert grl["reported_today"] is True  # GRL did report today (canon)


def test_factory_detail(seeded, client, django_user_model):
    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.get("/factories/GRL/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Hero PO in the order book.
    assert "71010305" in body
    # Inspections and certificates blocks render.
    assert "Inspections" in body
    assert "Certificates" in body
    # Unknown factory 404s.
    assert client.get("/factories/ZZZ/", HTTP_HOST="localhost").status_code == 404


def test_factory_output_json(seeded, client, django_user_model):
    u = django_user_model.objects.get(username="ceo")
    client.force_login(u)
    resp = client.get("/factories/GRL/output.json", HTTP_HOST="localhost")
    assert resp.status_code == 200
    opt = resp.json()
    stage_names = {s["name"] for s in opt["series"]}
    assert "Knitting" in stage_names
    assert len(opt["series"]) == 6


def test_factory_note_scope(seeded, client, django_user_model):
    from apps.masterdata.models import Factory
    from apps.orders.models import Comment

    grl = Factory.objects.get(code="GRL")
    # A merchandiser who does NOT own GRL is blocked.
    non_owner = (
        django_user_model.objects.filter(groups__name="Merchandiser")
        .exclude(pk=grl.merchandiser_id)
        .exclude(groups__name__in=["Admin", "Management"])
        .first()
    )
    assert non_owner is not None
    client.force_login(non_owner)
    resp = client.post("/factories/GRL/notes/", {"text": "blocked note"}, HTTP_HOST="localhost")
    assert resp.status_code == 403
    assert not Comment.objects.filter(factory=grl, text="blocked note").exists()

    # Admin can add a note.
    admin = django_user_model.objects.get(username="admin")
    client.force_login(admin)
    resp = client.post("/factories/GRL/notes/", {"text": "admin note"}, HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert Comment.objects.filter(factory=grl, text="admin note", author=admin).exists()
    assert "admin note" in resp.content.decode()
