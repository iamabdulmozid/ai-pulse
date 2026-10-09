from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


@login_required
def status_json(request):
    """Freshness + badge payload for the shell (FR-ACCT-060). Expanded in T-10."""
    from apps.dashboard.context_processors import shell

    ctx = shell(request)
    as_of = ctx.get("as_of")
    return JsonResponse(
        {
            "as_of": as_of.isoformat() if as_of else None,
            "reports_today": ctx.get("reports_today"),
            "alerts_open": ctx.get("alerts_open", 0),
            "user": {"name": request.user.get_username(), "role": ctx.get("shell_role")},
        }
    )


@login_required
def cmdk_search(request):
    """⌘K palette search stub (wired in T-10)."""
    return JsonResponse({"results": []})
