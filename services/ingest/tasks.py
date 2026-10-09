"""django-q2 task entry point for the upload ingest.

``ingest_file`` is what ``upload_create`` enqueues (``async_task``). It is a plain importable function, so
tests call it directly (synchronously) instead of relying on a running ``qcluster``. It loads the batch,
marks it running and dispatches to the per-kind ingest.
"""
from __future__ import annotations

from django.utils import timezone

from services.ingest.ingest import ingest_daily_production

# Per-kind dispatch. Only daily_production is wired for the live upload demo; add others here.
_DISPATCH = {
    "daily_production": ingest_daily_production,
}


def ingest_file(batch_id) -> str:
    """Ingest one uploaded file by batch id. Returns the final status string."""
    from apps.production.models import UploadBatch

    batch = UploadBatch.objects.get(id=batch_id)
    batch.status = "running"
    batch.save(update_fields=["status"])

    handler = _DISPATCH.get(batch.kind)
    try:
        if handler is None:
            message = (
                "File kind was not recognised."
                if not batch.kind
                else f"Ingest for '{batch.get_kind_display()}' files is not available yet."
            )
            batch.status = "error"
            batch.errors = [{"row": 0, "message": message}]
            batch.rows_accepted = 0
            batch.finished_at = timezone.now()
            batch.save()
        else:
            handler(batch)
    except Exception as exc:  # pragma: no cover - defensive; keep a failed task visible, never silent
        batch.refresh_from_db()
        batch.status = "error"
        batch.errors = [{"row": 0, "message": f"Ingest failed: {exc}"}]
        batch.rows_accepted = 0
        batch.finished_at = timezone.now()
        batch.save()

    batch.refresh_from_db()
    return batch.status
