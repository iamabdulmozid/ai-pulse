"""Daily Updates (FR-PROD) — upload drop zone, async ingest status, reporting board, history, templates.

Uploads are write-scoped (Merchandiser / Management / Admin; QA is read-only). Each file creates one
``UploadBatch`` and enqueues the ``ingest_file`` django-q2 task; the batch card polls its status over HTMX
until it reaches ``done``/``error``.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_http_methods

from apps.production.models import UploadBatch
from services import metrics
from services.ingest.ingest import apply_detection, batch_media_path, save_upload
from services.ingest.tasks import ingest_file

WRITE_GROUPS = {"Merchandiser", "Management", "Admin"}

# The six file kinds + their reference workbooks (FR-PROD-070).
TEMPLATE_KINDS = [
    ("factory_master", "Factory Master", "05_Factory_Master.xlsx"),
    ("order_book", "Order Book", "01_Order_Book.xlsx"),
    ("ta_calendar", "T&A Calendar", "02_TA_Calendar.xlsx"),
    ("daily_production", "Factory Daily Production Report", "03_Factory_Daily_Production_Report.xlsx"),
    ("inspection", "Inspection Log", "04_Inspection_Log.xlsx"),
    ("shipment", "Shipment Log", "06_Shipment_Log.xlsx"),
]


def _groups(user) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _can_upload(user) -> bool:
    return bool(user.is_superuser or (_groups(user) & WRITE_GROUPS))


def _templates() -> list[dict]:
    return [{"kind": k, "label": label, "filename": fn, "version": "v1"} for k, label, fn in TEMPLATE_KINDS]


def _reporting_rows(run) -> list[dict]:
    if run is None:
        return []
    from apps.predictions.models import FactoryStat

    rows = []
    for fs in (
        FactoryStat.objects.filter(run=run)
        .select_related("factory")
        .order_by("reported_today", "-value_at_risk_usd", "factory__code")
    ):
        if fs.reported_today:
            status = "reported"
        elif fs.last_report_date is not None and fs.missed_wd <= 1:
            status = "late"
        else:
            status = "missing"
        rows.append(
            {
                "code": fs.factory.code,
                "name": fs.factory.name,
                "status": status,
                "reported_today": fs.reported_today,
                "last_report": fs.last_report_date,
                "missed_wd": fs.missed_wd,
                "open_pos": fs.open_pos,
                "exposure_usd": float(fs.exposure_usd),
                "compliance_30d": round(max(0.0, 1 - min(fs.missed_wd, 30) / 30.0) * 100),
            }
        )
    return rows


def _reporting_context(run) -> dict:
    rows = _reporting_rows(run)
    received = sum(1 for r in rows if r["reported_today"])
    return {"reporting": rows, "reporting_received": received, "reporting_expected": len(rows), "run": run}


@login_required
def uploads_home(request):
    # The drop zone POSTs to this same URL ("/uploads/"); dispatch writes to upload_create.
    if request.method == "POST":
        return upload_create(request)
    run = metrics.latest_run()
    ctx = {
        "can_upload": _can_upload(request.user),
        "batches": UploadBatch.objects.select_related("detected_factory", "uploaded_by")[:50],
        "templates": _templates(),
    }
    ctx.update(_reporting_context(run))
    return render(request, "production/uploads.html", ctx)


@login_required
@require_http_methods(["POST"])
def upload_create(request):
    if not _can_upload(request.user):
        raise PermissionDenied("Uploading daily files requires the Merchandiser, Management or Admin role.")

    upload = request.FILES.get("file")
    if upload is None:
        raise PermissionDenied("No file was supplied.")

    name = get_valid_filename(upload.name) or "upload.xlsx"
    batch = UploadBatch.objects.create(original_filename=name, uploaded_by=request.user, status="queued")

    # Extension / size guards (docs/tech/security.md): reject before touching disk, as a finished batch.
    if not name.lower().endswith(".xlsx"):
        _reject_now(batch, "Only .xlsx workbooks are accepted.")
        return render(request, "partials/production/batch_card.html", {"b": batch})
    if upload.size > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        _reject_now(batch, f"File exceeds the {mb:.0f} MB upload limit.")
        return render(request, "partials/production/batch_card.html", {"b": batch})

    save_upload(batch, upload)
    apply_detection(batch, batch_media_path(batch))
    batch.save()

    # Async by default; call synchronously in DEBUG so a demo works without a running qcluster.
    if getattr(settings, "DEBUG", False):
        ingest_file(batch.id)
        batch.refresh_from_db()
    else:
        from django_q.tasks import async_task

        async_task("services.ingest.tasks.ingest_file", batch.id)

    return render(request, "partials/production/batch_card.html", {"b": batch})


def _reject_now(batch, message: str) -> None:
    batch.status = "error"
    batch.errors = [{"row": 0, "message": message}]
    batch.finished_at = timezone.now()
    batch.save()


@login_required
def batch_status_partial(request, batch_id):
    batch = get_object_or_404(UploadBatch.objects.select_related("detected_factory"), id=batch_id)
    is_owner = batch.uploaded_by_id == request.user.id
    is_manager = request.user.is_superuser or bool(_groups(request.user) & {"Management", "Admin"})
    if not (is_owner or is_manager):
        raise PermissionDenied("You can only view the status of your own uploads.")
    return render(request, "partials/production/batch_status.html", {"b": batch})


@login_required
def reporting_status_partial(request):
    run = metrics.latest_run()
    return render(request, "partials/production/reporting.html", _reporting_context(run))


@login_required
def templates_list(request):
    return render(request, "partials/production/templates.html", {"templates": _templates()})
