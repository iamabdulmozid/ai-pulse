from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from services import briefing, charts, metrics


def health(request):
    """Liveness probe (docs/tech/deployment.md). Public."""
    return JsonResponse({"status": "ok", "as_of": timezone.now().isoformat()})


@login_required
def overview(request):
    run = metrics.latest_run()
    if run is None:
        return render(request, "dashboard/overview.html", {"no_data": True})
    kpis = metrics.portfolio_kpis(run)
    lb = metrics.leaderboard(run)
    total_var = sum(f["value_at_risk_usd"] for f in lb) or 1
    top3 = lb[:3]
    concentration = {
        "share_pct": round(sum(f["value_at_risk_usd"] for f in top3) / total_var * 100),
        "codes": " · ".join(f["code"] for f in top3),
    }
    ctx = {
        "run": run,
        "kpis": kpis,
        "concentration": concentration,
        "briefing": briefing.overview_briefing(run),
        "outlook": metrics.outlook(run),
        "outlook_option": charts.outlook_option(metrics.outlook(run)),
        "heatmap": metrics.heatmap(run),
        "top_at_risk": metrics.top_at_risk(run, 10),
        "leaderboard": lb[:10],
        "splits": metrics.dept_gauge_split(run),
    }
    return render(request, "dashboard/overview.html", ctx)


@login_required
def outlook_json(request):
    run = metrics.latest_run()
    return JsonResponse(charts.outlook_option(metrics.outlook(run)))


@login_required
def heatmap_json(request):
    run = metrics.latest_run()
    return JsonResponse({"rows": metrics.heatmap(run)})
