"""T-17 acceptance: Daily Updates upload + async ingest (FR-PROD).

The ingest task is called synchronously (directly), not via a running qcluster. Seeding is module-scoped
(as in test_overview); the two demo files drive the clean-accept and whole-batch-reject paths.
"""
import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from services import metrics


@pytest.fixture(scope="module")
def seeded(django_db_setup, django_db_blocker):
    # seed_demo commits outside the per-test transaction; flush on teardown so this module leaves no
    # committed rows behind for order-independent isolation (the suite runs under pytest-randomly).
    with django_db_blocker.unblock():
        call_command("seed_demo")
        try:
            yield
        finally:
            call_command("flush", "--no-input")


pytestmark = pytest.mark.django_db

DEMO_UPLOADS = settings.SAMPLE_DATA_DIR / "demo_uploads"


def _make_batch(user, src_name):
    """Mirror upload_create's file handling: create the batch, save the file, stamp detection."""
    from apps.production.models import UploadBatch
    from services.ingest.ingest import apply_detection, batch_media_path, save_upload

    batch = UploadBatch.objects.create(original_filename=src_name, uploaded_by=user, status="queued")
    with (DEMO_UPLOADS / src_name).open("rb") as fh:
        save_upload(batch, File(fh))
    apply_detection(batch, batch_media_path(batch))
    batch.save()
    return batch


def test_upload_clean_pbb(seeded, django_user_model):
    from apps.predictions.models import FactoryStat, PredictionRun
    from services.ingest.tasks import ingest_file

    user = django_user_model.objects.get(username="headmerch")
    batch = _make_batch(user, "DPR_PBB_2026-10-14.xlsx")
    assert batch.kind == "daily_production"
    assert batch.detected_factory.code == "PBB"

    status = ingest_file(batch.id)
    batch.refresh_from_db()
    assert status == "done"
    assert batch.status == "done"
    assert batch.errors == []
    assert batch.rows_accepted == 3

    # A prediction run fired for this batch; the board now reads 19 of 22 reported, PBB included.
    run = PredictionRun.objects.get(upload_batch=batch)
    assert run.trigger == "upload"
    rt = metrics.reports_today(run)
    assert rt["received"] == 19
    assert rt["expected"] == 22
    assert "PBB" not in {m["code"] for m in rt["missing"]}
    assert FactoryStat.objects.get(run=run, factory__code="PBB").reported_today is True

    # Re-scoring is deterministic: the headline numbers do not move.
    k = metrics.portfolio_kpis(run)
    assert k["open_pos"] == 412
    assert k["open_pcs"] == 1900020
    assert float(k["open_fob_usd"]) == 18601449.36
    assert float(k["value_at_risk_usd"]) == 2400006.24
    assert float(k["air_freight_exposure_usd"]) == 539720.28


def test_upload_rejects_bad_batch(seeded, django_user_model):
    from apps.production.models import DailyProduction
    from services.ingest.tasks import ingest_file

    user = django_user_model.objects.get(username="headmerch")
    before = DailyProduction.objects.count()

    batch = _make_batch(user, "DPR_HMR_2026-10-14_with_errors.xlsx")
    assert batch.detected_factory.code == "HMR"

    status = ingest_file(batch.id)
    batch.refresh_from_db()
    assert status == "error"
    assert batch.status == "error"
    assert batch.rows_accepted == 0

    messages = " | ".join(e["message"] for e in batch.errors)
    assert "71999999" in messages  # unknown PO (referential)
    assert "Linking Day" in messages  # negative day value
    assert "Knitting Cum" in messages  # non-monotonic cumulative

    # No partial writes: nothing was written for the rejected batch.
    assert DailyProduction.objects.count() == before
    assert DailyProduction.objects.filter(upload_batch=batch).count() == 0


def test_uploads_page_and_partials_render(seeded, client, django_user_model):
    client.force_login(django_user_model.objects.get(username="headmerch"))

    page = client.get(reverse("production:uploads_home"), HTTP_HOST="localhost")
    assert page.status_code == 200
    body = page.content.decode()
    assert "Daily Updates" in body
    assert "Reporting status" in body
    assert "of 22 reported" in body

    rep = client.get(reverse("production:reporting_status_partial"), HTTP_HOST="localhost")
    assert rep.status_code == 200

    tpl = client.get(reverse("production:templates_list"), HTTP_HOST="localhost")
    assert tpl.status_code == 200
    assert "03_Factory_Daily_Production_Report.xlsx" in tpl.content.decode()


def test_upload_scope(seeded, client, django_user_model):
    qa = django_user_model.objects.create_user("qa_tester", password="x")
    qa.groups.add(Group.objects.get_or_create(name="QA")[0])
    client.force_login(qa)

    upload = SimpleUploadedFile(
        "DPR_PBB_2026-10-14.xlsx",
        b"not-a-real-xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp = client.post(reverse("production:upload_create"), {"file": upload}, HTTP_HOST="localhost")
    assert resp.status_code in (302, 403)
