"""Risk & Alerts feed (FR-ALERT).

Read side: a filterable feed of alert rows with a nav badge of open alerts. Alerts are generated
lazily from the latest prediction run (services.alerting). Write side: acknowledge / assign / snooze,
each scoped to ownership in the view (not only the template) and audited.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from services import metrics
from services.alerting import ensure_alerts

from .models import Alert

KINDS = ["po_critical", "factory_missed_report", "yarn_late", "inspection_failed", "po_at_risk", "compliance"]
SEVERITIES = ["critical", "risk", "watch", "noupdate"]
STATES = ["open", "acked", "assigned", "snoozed"]

KIND_LABEL = {
    "po_critical": "PO critical",
    "factory_missed_report": "Factory missed report",
    "yarn_late": "Yarn in-house late",
    "inspection_failed": "Inspection failed",
    "po_at_risk": "PO at risk",
    "compliance": "Reporting compliance",
}
SEVERITY_CLASS = {"critical": "b-crit", "risk": "b-risk", "watch": "b-watch", "noupdate": "b-noupd"}
STATE_CLASS = {"open": "b-crit", "acked": "b-ok", "assigned": "b-watch", "snoozed": "b-ship"}


# --------------------------------------------------------------- scope -----
def _groups(user) -> set[str]:
    return set(user.groups.values_list("name", flat=True))


def _is_management(user) -> bool:
    return user.is_superuser or bool({"Admin", "Management"} & _groups(user))


def _can_ack(user, alert) -> bool:
    """Owner / Management / Admin. 'Own' = alert owner, or the linked PO/factory merchandiser."""
    if _is_management(user):
        return True
    if alert.owner_id == user.id:
        return True
    if alert.purchase_order_id and alert.purchase_order.merchandiser_id == user.id:
        return True
    if alert.factory_id and alert.factory.merchandiser_id == user.id:
        return True
    return False


def _can_assign(user, alert=None) -> bool:
    """Assign is Management / Admin only (FR-ALERT-040)."""
    return _is_management(user)


# --------------------------------------------------------------- feed ------
def _reopen_expired(now):
    """A snooze whose time has passed returns to the open list (FR-ALERT-050)."""
    Alert.objects.filter(state="snoozed", snooze_until__lte=now).update(state="open", snooze_until=None)


def _feed_queryset(request):
    now = timezone.now()
    _reopen_expired(now)
    qs = Alert.objects.select_related(
        "purchase_order", "purchase_order__merchandiser", "factory", "factory__merchandiser", "owner"
    ).all()
    kind = request.GET.get("kind")
    severity = request.GET.get("severity")
    state = request.GET.get("state")
    if kind in KINDS:
        qs = qs.filter(kind=kind)
    if severity in SEVERITIES:
        qs = qs.filter(severity=severity)
    if state in STATES:
        qs = qs.filter(state=state)
    else:
        # Default view hides a still-future snooze; everything else (incl. open) is shown.
        qs = qs.exclude(state="snoozed", snooze_until__gt=now)
    return qs


def _assignable_users():
    from django.contrib.auth.models import User

    return User.objects.filter(is_active=True).order_by("username")


def _row_ctx(request, alert):
    return {
        "a": alert,
        "can_ack": _can_ack(request.user, alert),
        "can_assign": _can_assign(request.user, alert),
        "assignable": _assignable_users() if _can_assign(request.user, alert) else [],
        "kind_label": KIND_LABEL.get(alert.kind, alert.kind),
        "sev_class": SEVERITY_CLASS.get(alert.severity, "b-watch"),
        "state_class": STATE_CLASS.get(alert.state, "b-ok"),
    }


@login_required
def alert_list(request):
    run = metrics.latest_run()
    ensure_alerts(run)
    alerts = list(_feed_queryset(request))
    ctx = {
        "as_of": run.as_of if run else None,
        "alerts": alerts,
        "kinds": KINDS,
        "severities": SEVERITIES,
        "states": STATES,
        "selected": {"kind": request.GET.get("kind", ""), "severity": request.GET.get("severity", ""),
                     "state": request.GET.get("state", "")},
        "rows": [_row_ctx(request, a) for a in alerts],
        "can_assign": _can_assign(request.user),
        "assignable": _assignable_users() if _can_assign(request.user) else [],
    }
    return render(request, "alerts/list.html", ctx)


@login_required
def alert_feed_partial(request):
    run = metrics.latest_run()
    ensure_alerts(run)
    alerts = list(_feed_queryset(request))
    ctx = {"rows": [_row_ctx(request, a) for a in alerts]}
    return render(request, "partials/alerts/feed.html", ctx)


# --------------------------------------------------------------- actions ---
def _audit(request, action, alert, **meta):
    try:
        from apps.accounts.models import AuditLog

        AuditLog.objects.create(user=request.user, action=action, target=f"alert:{alert.id}", meta=meta)
    except Exception:
        pass


def _render_row(request, alert, **extra):
    ctx = _row_ctx(request, alert)
    ctx.update(extra)
    return render(request, "partials/alerts/row.html", ctx)


def _get_alert(pk):
    return get_object_or_404(
        Alert.objects.select_related(
            "purchase_order", "purchase_order__merchandiser", "factory", "factory__merchandiser", "owner"
        ),
        pk=pk,
    )


@login_required
@require_POST
def alert_ack(request, pk):
    alert = _get_alert(pk)
    if not _can_ack(request.user, alert):
        return HttpResponseForbidden("You don't have permission to do this.")
    alert.state = "acked"
    alert.save(update_fields=["state"])
    _audit(request, "alert_ack", alert)
    return _render_row(request, alert)


@login_required
@require_POST
def alert_assign(request, pk):
    alert = _get_alert(pk)
    if not _can_assign(request.user, alert):
        return HttpResponseForbidden("You don't have permission to do this.")
    user_id = request.POST.get("user_id")
    from django.contrib.auth.models import User

    assignee = User.objects.filter(pk=user_id).first() if user_id else None
    if assignee is None:
        return _render_row(request, alert, error="Pick a user to assign to.")
    alert.owner = assignee
    alert.state = "assigned"
    alert.save(update_fields=["owner", "state"])
    _audit(request, "alert_assign", alert, user_id=assignee.id)
    return _render_row(request, alert)


@login_required
@require_POST
def alert_snooze(request, pk):
    alert = _get_alert(pk)
    if not _can_ack(request.user, alert):
        return HttpResponseForbidden("You don't have permission to do this.")
    raw = request.POST.get("until") or ""
    until = parse_datetime(raw)
    if until is not None and timezone.is_naive(until):
        until = timezone.make_aware(until, timezone.get_current_timezone())
    if until is None or until <= timezone.now():
        return _render_row(request, alert, error="Snooze time must be in the future.")
    alert.snooze_until = until
    alert.state = "snoozed"
    alert.save(update_fields=["snooze_until", "state"])
    _audit(request, "alert_snooze", alert, until=until.isoformat())
    return _render_row(request, alert)
