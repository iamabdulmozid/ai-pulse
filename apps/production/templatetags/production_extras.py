from django import template

register = template.Library()

_STATUS_BADGE = {
    # UploadBatch statuses
    "done": "b-ok",
    "error": "b-crit",
    "running": "b-watch",
    "queued": "b-noupd",
    # Reporting-board statuses
    "reported": "b-ok",
    "late": "b-watch",
    "missing": "b-crit",
}


@register.filter
def status_badge(status):
    """Map an upload / reporting status to a components.css badge class."""
    return _STATUS_BADGE.get(status, "b-noupd")
