"""Audit-log middleware (docs/tech/security.md, FR-ACCT-050).

Phase 0: records authenticated unsafe requests (POST/PUT/PATCH/DELETE) to the AuditLog. Kept defensive
so a logging failure never breaks a request. Fleshed out per-action in T-10.
"""


class AuditLogMiddleware:
    SAFE = {"GET", "HEAD", "OPTIONS", "TRACE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            user = getattr(request, "user", None)
            if (
                request.method not in self.SAFE
                and user is not None
                and user.is_authenticated
                and not request.path.startswith("/admin/")
            ):
                from apps.accounts.models import AuditLog

                AuditLog.objects.create(
                    user=user,
                    action=request.method.lower(),
                    target=request.path[:80],
                    ip=request.META.get("REMOTE_ADDR"),
                    meta={},
                )
        except Exception:
            pass
        return response
