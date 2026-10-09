"""Factories screens (FR-FAC). Read-side numbers come only from services.metrics;
nothing is recomputed on the request. Write scope (notes) is enforced here, not only in templates.
"""
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from services import metrics
from services.charts import AXIS, STAGE_COLORS

STAGES = ["knitting", "linking", "trimming_mending", "washing", "ironing", "packing"]


def _can_write_notes(user, factory) -> bool:
    """Management/Admin, or the factory's own merchandiser (FR-FAC-080)."""
    groups = set(user.groups.values_list("name", flat=True))
    if user.is_superuser or {"Admin", "Management"} & groups:
        return True
    return factory.merchandiser_id == user.id


def _ai_summary(card) -> str:
    """Deterministic one-line summary from the scorecard numbers (no OpenAI call)."""
    if not card:
        return "No prediction run yet."
    name = card["name"]
    bits = (
        f"{name} ({card['code']}) carries {card['open_pos']} open POs "
        f"({card['open_pcs']:,} pcs), with ${card['value_at_risk_usd']:,.0f} at risk "
        f"against ${card['exposure_usd']:,.0f} of exposure. "
        f"OTD {card['otd_pct']:.1f}%, AQL pass {card['aql_pass_pct']:.0f}%, "
        f"knitting load {card['knit_load_pct']:.0f}%."
    )
    if card["reported_today"]:
        bits += " Reported today."
    else:
        last = card["last_report"]
        when = last.strftime("%d %b") if last else "an earlier date"
        bits += f" No update today — last reported {when}."
    return bits


@login_required
def factory_list(request):
    run = metrics.latest_run()
    if not run:
        return render(request, "factories/list.html", {"no_data": True})
    scorecards = metrics.factory_scorecards(run)
    ctx = {"no_data": False, "as_of": run.as_of, "scorecards": scorecards,
           "reports_today": metrics.reports_today(run)}
    return render(request, "factories/list.html", ctx)


@login_required
def factory_table_partial(request):
    run = metrics.latest_run()
    scorecards = metrics.factory_scorecards(run) if run else []
    return render(request, "partials/factories/scorecards.html", {"scorecards": scorecards})


def _get_factory_or_404(code):
    from apps.masterdata.models import Factory

    try:
        return Factory.objects.get(code=code)
    except Factory.DoesNotExist:
        raise Http404(f"No factory with code {code!r}") from None


@login_required
def factory_detail(request, code):
    run = metrics.latest_run()
    factory = _get_factory_or_404(code)
    if not run:
        return render(request, "factories/detail.html",
                      {"no_data": True, "factory": {"code": factory.code, "name": factory.name}})
    detail = metrics.factory_detail(run, code)
    ctx = {
        "no_data": False,
        "as_of": run.as_of,
        "detail": detail,
        "card": detail["card"],
        "factory": detail["factory"],
        "ai_summary": _ai_summary(detail["card"]),
        "notes": factory.notes.select_related("author").all(),
        "can_write": _can_write_notes(request.user, factory),
    }
    return render(request, "factories/detail.html", ctx)


def _output_option(output_series: dict) -> dict:
    """Multi-line ECharts option: one line per stage over the output window."""
    dates = sorted({p["date"] for pts in output_series.values() for p in pts})
    series = []
    for st in STAGES:
        by_date = {p["date"]: p["pcs"] for p in output_series.get(st, [])}
        series.append({
            "name": st.replace("_", " ").title(), "type": "line", "smooth": True, "showSymbol": False,
            "itemStyle": {"color": STAGE_COLORS.get(st, "#888")},
            "data": [by_date.get(d, 0) for d in dates],
        })
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"textStyle": {"color": "#9a9388"}, "top": 0, "type": "scroll"},
        "grid": {"left": 56, "right": 16, "top": 32, "bottom": 28},
        "xAxis": {"type": "category", "data": dates, **AXIS},
        "yAxis": {"type": "value", "name": "pcs/day", "nameTextStyle": {"color": "#9a9388"}, **AXIS},
        "series": series,
    }


@login_required
def factory_output_json(request, code):
    run = metrics.latest_run()
    _get_factory_or_404(code)
    output = metrics.factory_detail(run, code)["output"] if run else {}
    return JsonResponse(_output_option(output))


@login_required
@require_POST
def factory_note_create(request, code):
    factory = _get_factory_or_404(code)
    if not _can_write_notes(request.user, factory):
        return HttpResponseForbidden("You cannot add notes to this factory.")
    text = (request.POST.get("text") or "").strip()
    if text:
        from apps.orders.models import Comment

        Comment.objects.create(factory=factory, author=request.user, text=text)
    ctx = {
        "notes": factory.notes.select_related("author").all(),
        "can_write": True,
        "factory": {"code": factory.code, "name": factory.name},
    }
    return render(request, "partials/factories/notes.html", ctx)
