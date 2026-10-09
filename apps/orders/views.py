"""Purchase Orders screens (FR-ORD-010..110).

Server-rendered with HTMX partials. Every number comes from services/ (metrics, prediction, charts);
views never recompute the engine on page load. The what-if alone re-runs the pure engine, read-only.
"""
from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from services import charts, metrics
from services.metrics import POFilters

# Chip key -> engine band name (chips carry band names in the `band`/`status` query param).
CHIP_BANDS = [
    ("all", "All", None),
    ("critical", "Critical", "Critical"),
    ("risk", "At risk", "At risk"),
    ("late", "Late", "Late"),
    ("watch", "Watch", "Watch"),
    ("ok", "On track", "On track"),
]
MAX_MACHINES_ADD = 12


# --------------------------------------------------------------------- helpers
def is_po_writer(user, po) -> bool:
    """Write-scope for PO comments: Management/Admin (or superuser), or the PO's own merchandiser."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name__in=("Management", "Admin")).exists():
        return True
    return po.merchandiser_id is not None and po.merchandiser_id == user.id


def _filters_from_request(request) -> POFilters:
    g = request.GET
    gauges = []
    for v in g.getlist("gauge"):
        try:
            gauges.append(int(v))
        except (TypeError, ValueError):
            continue
    # The status chips and dashboard VaR drill both carry band names; accept either key.
    bands = g.getlist("status") + g.getlist("band")
    return POFilters(
        dept=g.getlist("dept") or None,
        season=g.getlist("season") or None,
        factory=g.getlist("factory") or None,
        gauge=gauges or None,
        band=bands or None,
        exf_month=g.getlist("exf_month") or None,
        merchandiser=g.getlist("merchandiser") or None,
        q=(g.get("q") or "").strip() or None,
        sort=g.get("sort") or "risk",
    )


def _facet_options(run):
    """Distinct filter values for the controls, from the current run's open book."""
    rows = metrics.po_list(run)
    depts, seasons, gauges, months = set(), set(), set(), set()
    factories, merchs = {}, {}
    for r in rows:
        depts.add(r["department"])
        seasons.add(r["season"])
        gauges.add(r["gauge"])
        months.add(r["exf_date"].strftime("%Y-%m"))
        factories[r["factory_code"]] = r["factory_name"]
        if r["merchandiser"]:
            merchs[r["merchandiser"]] = r["merchandiser"]
    return {
        "depts": sorted(depts),
        "seasons": sorted(seasons),
        "gauges": sorted(gauges),
        "factories": sorted(factories.items()),
        "exf_months": sorted(months),
        "merchandisers": sorted(merchs),
    }


def _chips(run, active_bands):
    counts = metrics.status_counts(run)
    active = set(active_bands or [])
    out = []
    for key, label, band in CHIP_BANDS:
        out.append({
            "key": key, "label": label, "band": band,
            "count": counts["all"] if band is None else counts.get(key, 0),
            "active": (band in active) if band else (not active),
        })
    return out


def _add_relative_days(rows, today):
    for r in rows:
        r["exf_relative_days"] = (r["exf_date"] - today).days
    return rows


# ------------------------------------------------------------------- PO list
@login_required
def po_list(request):
    run = metrics.latest_run()
    if run is None:
        return render(request, "orders/po_list.html", {"no_data": True})
    filters = _filters_from_request(request)
    rows = _add_relative_days(metrics.po_list(run, filters), _today())
    ctx = {
        "run": run,
        "as_of": run.as_of,
        "rows": rows,
        "chips": _chips(run, filters.band),
        "counts": metrics.status_counts(run),
        "facets": _facet_options(run),
        "filters": filters,
        "sort": filters.sort,
        "querystring": request.GET.urlencode(),
    }
    return render(request, "orders/po_list.html", ctx)


@login_required
def po_table_partial(request):
    run = metrics.latest_run()
    if run is None:
        return render(request, "partials/orders/po_table.html", {"no_data": True, "rows": [], "counts": {}})
    filters = _filters_from_request(request)
    rows = _add_relative_days(metrics.po_list(run, filters), _today())
    ctx = {
        "run": run,
        "as_of": run.as_of,
        "rows": rows,
        "chips": _chips(run, filters.band),
        "counts": metrics.status_counts(run),
        "filters": filters,
        "sort": filters.sort,
    }
    return render(request, "partials/orders/po_table.html", ctx)


# ------------------------------------------------------------------- PO detail
@login_required
def po_detail(request, po_no):
    run = metrics.latest_run()
    if run is None:
        return render(request, "orders/po_detail.html", {"no_data": True, "po_no": po_no})
    try:
        snap = metrics.po_snapshot(run, po_no)
    except Exception:
        return render(request, "orders/po_detail.html", {"no_prediction": True, "po_no": po_no, "as_of": run.as_of})

    current = _current_link_machines(po_no)
    comments = _comment_rows(po_no)
    from services.prediction.recommend import recommend

    ctx = {
        "run": run,
        "as_of": snap["as_of"],
        "po_no": po_no,
        "snap": snap,
        "drivers": snap.get("drivers") or [],
        "recommendations": recommend(po_no, run, _today()),
        "link_current": current,
        "link_min": max(1, current - 6),
        "link_max": current + MAX_MACHINES_ADD,
        "overtime_fridays": [date(2026, 10, 16), date(2026, 10, 23)],
        "comments": comments,
        "can_comment": is_po_writer(request.user, _po(po_no)),
    }
    return render(request, "orders/po_detail.html", ctx)


@login_required
def po_ta_partial(request, po_no):
    today = _today()
    milestones = []
    for m in metrics.po_ta(po_no):
        forecast = m["actual"] or m["revised"] or m["planned"]
        late_days = 0
        if m["actual"] and m["planned"]:
            late_days = max(0, (m["actual"] - m["planned"]).days)
        elif not m["actual"] and m["planned"] and m["planned"] < today:
            late_days = max(0, (today - m["planned"]).days)
        status = (m["status"] or "").lower()
        done = m["actual"] is not None or "done" in status
        flagged = ("late" in status) or late_days > 0
        milestones.append({
            **m, "forecast": forecast, "late_days": late_days, "flagged": flagged,
            "state": "done" if done else ("running" if (m["planned"] and m["planned"] <= today) else "pending"),
        })
    span_lo = min((m["planned"] for m in milestones if m["planned"]), default=today)
    span_hi = max((m["forecast"] for m in milestones if m["forecast"]), default=today)
    total = max(1, (span_hi - span_lo).days)
    for m in milestones:
        start = m["planned"] or span_lo
        end = m["forecast"] or start
        m["left_pct"] = round((start - span_lo).days / total * 100, 2)
        m["width_pct"] = round(max(2, (end - start).days) / total * 100, 2)
    return render(request, "partials/orders/ta_gantt.html",
                  {"milestones": milestones, "span_lo": span_lo, "span_hi": span_hi, "today": today})


@login_required
def po_curves_json(request, po_no):
    run = metrics.latest_run()
    required = None
    try:
        snap = metrics.po_snapshot(run, po_no)
        required = snap.get("required_rate")
    except Exception:
        pass
    option = charts.curves_option(metrics.po_curves(po_no), {}, required)
    return JsonResponse(option)


@login_required
@require_POST
def po_whatif_partial(request, po_no):
    from apps.masterdata.models import HolidayCalendar
    from services.prediction.run import _load_params, build_po_context
    from services.prediction.whatif import simulate

    today = _today()
    ctx = build_po_context(po_no, today)
    if ctx is None:
        return render(request, "partials/orders/whatif_result.html",
                      {"error": "No prediction available for this PO."})

    current = ctx.link_machines_current or 1
    link_machines = current
    raw = request.POST.get("link_machines")
    if raw not in (None, ""):
        try:
            link_machines = int(raw)
        except ValueError:
            return render(request, "partials/orders/whatif_result.html",
                          {"error": "Linking machines must be a whole number."})
    lo, hi = max(1, current - 6), current + MAX_MACHINES_ADD
    if not (lo <= link_machines <= hi):
        return render(request, "partials/orders/whatif_result.html",
                      {"error": f"Linking machines must be between {lo} and {hi}."})

    overtime = set()
    for v in request.POST.getlist("overtime"):
        try:
            overtime.add(date.fromisoformat(v))
        except ValueError:
            return render(request, "partials/orders/whatif_result.html",
                          {"error": "Invalid overtime date."})

    holidays = frozenset(HolidayCalendar.objects.values_list("date", flat=True))
    params = _load_params()
    result = simulate(ctx, params, today, link_machines=link_machines,
                      overtime_days=frozenset(overtime), holidays=holidays)
    return render(request, "partials/orders/whatif_result.html",
                  {"result": result, "link_machines": link_machines})


@login_required
@require_POST
def po_comment_create(request, po_no):
    from apps.orders.models import Comment

    po = _po(po_no)
    if po is None:
        return HttpResponseForbidden("Unknown PO.")
    if not is_po_writer(request.user, po):
        return HttpResponseForbidden("You can only comment on your own POs.")
    text = (request.POST.get("text") or "").strip()
    if text:
        Comment.objects.create(purchase_order=po, author=request.user, text=text)
    return render(request, "partials/orders/comment_list.html",
                  {"comments": _comment_rows(po_no), "po_no": po_no, "can_comment": True})


@login_required
def po_export(request):
    import io

    from openpyxl import Workbook

    run = metrics.latest_run()
    rows = metrics.po_list(run, _filters_from_request(request)) if run else []
    wb = Workbook()
    ws = wb.active
    ws.title = "Purchase Orders"
    headers = ["PO No", "Style", "Description", "Dept", "Season", "Band", "Factory", "Gauge",
               "Yarn", "Qty (pcs)", "FOB/pc", "FOB value", "Ex-factory", "On-time prob",
               "Slip days", "Risk score"]
    ws.append(headers)
    for r in rows:
        ws.append([
            r["po_no"], r["style_no"], r["style_name"], r["department"], r["season"], r["band"],
            r["factory_name"], r["gauge"], r["yarn"], r["qty_pcs"], r["fob_usd_pc"], r["fob_value_usd"],
            r["exf_date"].isoformat(), r["on_time_prob"], r["slip_days"], r["risk_score"],
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = 'attachment; filename="purchase-orders.xlsx"'
    return resp


# --------------------------------------------------------------------- private
def _today() -> date:
    from django.conf import settings

    return settings.DEMO_TODAY


def _po(po_no):
    from apps.orders.models import PurchaseOrder

    return PurchaseOrder.objects.select_related("merchandiser").filter(po_no=po_no).first()


def _current_link_machines(po_no) -> int:
    from apps.production.models import DailyProduction

    row = (
        DailyProduction.objects.filter(purchase_order__po_no=po_no, stage="linking",
                                       machines__isnull=False)
        .order_by("-report_date").first()
    )
    return row.machines if row and row.machines else 13


def _comment_rows(po_no) -> list[dict]:
    from apps.orders.models import Comment

    out = []
    for c in Comment.objects.filter(purchase_order__po_no=po_no).select_related("author").order_by("created_at"):
        role = ", ".join(c.author.groups.values_list("name", flat=True)) or "User"
        out.append({"author": c.author.get_full_name() or c.author.get_username(),
                    "role": role, "at": c.created_at, "text": c.text})
    return out
