"""T-13/T-14/T-15 acceptance: Purchase Orders list, detail, what-if, comments, export (FR-ORD-010..110)."""
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

HERO = "71010305"


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def _login(client, username):
    client.force_login(User.objects.get(username=username))


def test_po_list_filters(seeded, client):
    _login(client, "ceo")

    # Critical band filter returns only Critical rows.
    resp = client.get("/pos/table/", {"band": "Critical"}, HTTP_HOST="localhost")
    assert resp.status_code == 200
    rows = resp.context["rows"]
    assert rows and all(r["band"] == "Critical" for r in rows)
    assert HERO in {r["po_no"] for r in rows}

    # Status chip counts sum to the canon 412.
    counts = resp.context["counts"]
    assert counts["all"] == 412
    assert counts["critical"] + counts["risk"] + counts["late"] + counts["watch"] + counts["ok"] == 412
    assert counts["critical"] == 13

    # Default sort is risk desc.
    full = client.get("/pos/table/", HTTP_HOST="localhost")
    scores = [r["risk_score"] for r in full.context["rows"]]
    assert scores == sorted(scores, reverse=True)
    assert len(scores) == 412

    # A factory filter narrows the rows.
    grl = client.get("/pos/table/", {"factory": "GRL"}, HTTP_HOST="localhost")
    grl_rows = grl.context["rows"]
    assert grl_rows and all(r["factory_code"] == "GRL" for r in grl_rows)
    assert len(grl_rows) < 412

    # The visible "All" options submit empty values, which must not exclude orders.
    all_options = client.get("/pos/table/", {
        "dept": "", "season": "", "factory": "", "gauge": "",
        "exf_month": "", "merchandiser": "", "band": "Critical",
    }, HTTP_HOST="localhost")
    assert len(all_options.context["rows"]) == counts["critical"]
    assert 'name="band" value="Critical"' in all_options.content.decode()


def test_po_detail_hero(seeded, client):
    _login(client, "ceo")
    resp = client.get(f"/pos/{HERO}/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "7 Nov" in body          # predicted ex-factory
    assert "Critical" in body       # band
    assert "76" in body             # risk score
    assert "2%" in body             # on-time probability


def test_hero_whatif(seeded, client):
    _login(client, "ceo")

    # Recovery plan: +6 linking machines (13->19) + Friday overtime 16 & 23 Oct -> on time 29 Oct.
    plan = client.post(
        f"/pos/{HERO}/whatif/",
        {"link_machines": 19, "overtime": ["2026-10-16", "2026-10-23"]},
        HTTP_HOST="localhost",
    )
    assert plan.status_code == 200
    body = plan.content.decode()
    assert 'data-ontime="true"' in body
    assert 'data-projected="2026-10-29"' in body
    assert 'data-air="38016"' in body

    # Baseline: 13 machines, no overtime -> slip 9 / 7 Nov.
    base = client.post(f"/pos/{HERO}/whatif/", {"link_machines": 13}, HTTP_HOST="localhost")
    base_body = base.content.decode()
    assert 'data-slip="9"' in base_body
    assert 'data-projected="2026-11-07"' in base_body
    assert 'data-ontime="false"' in base_body


def test_po_comment_scope(seeded, client):
    # A merchandiser who does NOT own the hero PO is blocked.
    hero_owner = User.objects.get(username="farhana.rahman")
    other = User.objects.filter(groups__name="Merchandiser").exclude(pk=hero_owner.pk).first()
    _login(client, other.username)
    denied = client.post(f"/pos/{HERO}/comments/", {"text": "not allowed"}, HTTP_HOST="localhost")
    assert denied.status_code == 403

    # An Admin can comment.
    _login(client, "admin")
    allowed = client.post(f"/pos/{HERO}/comments/", {"text": "admin says ship it"}, HTTP_HOST="localhost")
    assert allowed.status_code == 200
    assert "admin says ship it" in allowed.content.decode()


def test_po_export(seeded, client):
    _login(client, "ceo")
    resp = client.get("/pos/export.xlsx", HTTP_HOST="localhost")
    assert resp.status_code == 200
    assert "spreadsheetml.sheet" in resp["Content-Type"]
