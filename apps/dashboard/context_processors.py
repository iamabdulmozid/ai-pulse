"""Shell context: freshness pill, alert badge and user role for every page.

Reads the latest prediction run and factory reporting state. Degrades gracefully before any run
exists (e.g. a fresh database) so the shell always renders.
"""
from django.conf import settings


def shell(request):
    ctx = {
        "demo_today": settings.DEMO_TODAY,
        "as_of": None,
        "reports_today": {"received": 0, "expected": 0},
        "reports_missing": 0,
        "alerts_open": 0,
        "shell_role": None,
    }
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return ctx

    # Role for the header pill (from group membership / profile).
    groups = set(request.user.groups.values_list("name", flat=True))
    for g in ("Admin", "Management", "Merchandiser", "QA"):
        if g in groups:
            ctx["shell_role"] = g
            break

    try:
        from apps.predictions.models import FactoryStat, PredictionRun

        run = PredictionRun.objects.order_by("-as_of").first()
        if run:
            ctx["as_of"] = run.as_of
            stats = FactoryStat.objects.filter(run=run)
            expected = stats.count()
            received = stats.filter(reported_today=True).count()
            ctx["reports_today"] = {"received": received, "expected": expected}
            ctx["reports_missing"] = expected - received
    except Exception:
        # Models may not be migrated yet (early scaffold); keep the shell alive.
        pass

    try:
        from apps.alerts.models import Alert

        ctx["alerts_open"] = Alert.objects.filter(state="open").count()
    except Exception:
        pass

    return ctx
