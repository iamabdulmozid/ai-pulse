"""Ingest orchestration (docs/data/excel-templates.md "Ingest execution model").

Validate-then-write, all or nothing: a file with any error marks the batch ``error`` and writes nothing;
a clean file upserts its rows inside one transaction, marks the batch ``done``, sets ``rows_accepted`` and
re-scores via the prediction engine (trigger ``upload``). Upserts are idempotent on the file's natural key,
so re-sending a day — or correcting an earlier one — overwrites in place instead of duplicating.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from services.ingest.readers import detect, read_daily_production
from services.ingest.validators import validate_daily_production


def batch_media_path(batch) -> Path:
    """Where the uploaded file for a batch lives: MEDIA_ROOT/uploads/<batch_id>/<filename>."""
    return Path(settings.MEDIA_ROOT) / "uploads" / str(batch.id) / batch.original_filename


def save_upload(batch, django_file) -> Path:
    """Persist an uploaded file under MEDIA_ROOT/uploads/ for the async task to read."""
    dest = batch_media_path(batch)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in django_file.chunks():
            fh.write(chunk)
    return dest


def apply_detection(batch, path) -> None:
    """Stamp kind / detected_factory / detected_date on the batch from the workbook."""
    from apps.masterdata.models import Factory

    info = detect(path)
    batch.kind = info["kind"] or ""
    batch.detected_date = info["report_date"]
    batch.detected_factory = (
        Factory.objects.filter(code=info["factory_code"]).first() if info["factory_code"] else None
    )


def _finish(batch, *, status, rows_accepted, warnings, errors) -> None:
    batch.status = status
    batch.rows_accepted = rows_accepted
    batch.warnings = warnings
    batch.errors = errors
    batch.finished_at = timezone.now()
    batch.save()


@transaction.atomic
def ingest_daily_production(batch):
    """Validate a Daily Production file and, if clean, upsert its rows + re-score."""
    rr = read_daily_production(batch_media_path(batch))
    accepted, warnings, errors = validate_daily_production(rr)

    if errors:
        # Reject the whole batch: write no production rows.
        _finish(batch, status="error", rows_accepted=0, warnings=warnings, errors=errors)
        return batch

    from apps.production.models import DailyProduction

    for a in accepted:
        DailyProduction.objects.update_or_create(
            purchase_order=a["purchase_order"],
            stage=a["stage"],
            report_date=a["report_date"],
            defaults={
                "factory": a["factory"],
                "day_pcs": a["day_pcs"],
                "cum_pcs": a["cum_pcs"],
                "machines": a["machines"],
                "remarks": a["remarks"],
                "upload_batch": batch,
            },
        )

    _finish(batch, status="done", rows_accepted=len(rr.rows), warnings=warnings, errors=[])

    # A successful ingest re-scores the portfolio from the fresh snapshot (FR-PRED-010).
    from services.prediction.run import run_predictions

    run_predictions(trigger="upload", upload_batch=batch)
    return batch
