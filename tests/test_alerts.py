"""T-20 acceptance: alerts are derived from the run, scoped on write, and deduped across runs."""
import pytest
from django.core.management import call_command

from apps.alerts.models import Alert
from services import metrics
from services.alerting import ensure_alerts, evaluate_alerts


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("seed_demo")
        yield


pytestmark = pytest.mark.django_db


def test_alerts_from_snapshots(seeded):
    run = metrics.latest_run()
    ensure_alerts(run)

    # Hero PO turned critical (predicted 9 days late).
    assert Alert.objects.filter(kind="po_critical", purchase_order__po_no="71010305").exists()

    # The quiet factories each raise a factory_missed_report alert.
    missing = {"SLM", "OKH", "HMR", "PBB"}
    got = set(
        Alert.objects.filter(kind="factory_missed_report").values_list("factory__code", flat=True)
    )
    assert missing <= got


def test_alert_action_scope(seeded, client, django_user_model):
    from django.contrib.auth.models import Group

    run = metrics.latest_run()
    ensure_alerts(run)
    alert = Alert.objects.filter(kind="factory_missed_report").first()

    merch_group, _ = Group.objects.get_or_create(name="Merchandiser")
    owner = django_user_model.objects.create_user("owner_m", password="x")
    owner.groups.add(merch_group)
    other = django_user_model.objects.create_user("other_m", password="x")
    other.groups.add(merch_group)
    alert.owner = owner
    alert.save(update_fields=["owner"])

    # A non-owner merchandiser cannot ack someone else's alert.
    client.force_login(other)
    resp = client.post(f"/alerts/{alert.id}/ack/", HTTP_HOST="localhost")
    assert resp.status_code in (403, 302)
    alert.refresh_from_db()
    assert alert.state == "open"

    # Admin can ack.
    admin = django_user_model.objects.get(username="admin")
    client.force_login(admin)
    resp = client.post(f"/alerts/{alert.id}/ack/", HTTP_HOST="localhost")
    assert resp.status_code == 200
    alert.refresh_from_db()
    assert alert.state == "acked"

    # Assign is Management / Admin only: a merchandiser is rejected.
    client.force_login(other)
    resp = client.post(f"/alerts/{alert.id}/assign/", {"user_id": owner.id}, HTTP_HOST="localhost")
    assert resp.status_code in (403, 302)

    # Management can assign.
    ceo = django_user_model.objects.get(username="ceo")
    client.force_login(ceo)
    resp = client.post(f"/alerts/{alert.id}/assign/", {"user_id": owner.id}, HTTP_HOST="localhost")
    assert resp.status_code == 200
    alert.refresh_from_db()
    assert alert.owner_id == owner.id
    assert alert.state == "assigned"


def test_alerts_dedupe(seeded):
    run = metrics.latest_run()
    ensure_alerts(run)
    before = Alert.objects.count()

    # Lazy ensure is a no-op once the run has alerts; a direct re-evaluation creates nothing new.
    assert ensure_alerts(run) == 0
    assert evaluate_alerts(run) == 0
    assert Alert.objects.count() == before
