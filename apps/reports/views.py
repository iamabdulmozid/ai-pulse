"""Reports & Analytics (FR-REP).

Both reports read the latest prediction snapshot / factory stats via services.metrics — the engine is
never recomputed on request, and every figure carries the run's as_of. Each report exports to .xlsx
(?export=xlsx) whose rows equal the on-screen table, and the export is audited.
"""
from __future__ import annotations

import io
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from services import charts, metrics


def _audit_export(request, report):
    try:
        from apps.accounts.models import AuditLog

        AuditLog.objects.create(user=request.user, action="export", target=f"report:{report}",
                                meta={"format": "xlsx"})
    except Exception:
        pass


def _xlsx_response(filename, title, headers, rows, as_of=None):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    if as_of is not None:
        ws.append([f"{title} — as of {as_of:%d %b %Y %H:%M}"])
        ws.append([])
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    resp = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@login_required
def reports_home(request):
    run = metrics.latest_run()
    return render(request, "reports/home.html", {"as_of": run.as_of if run else None})


@login_required
def shipment_forecast(request):
    run = metrics.latest_run()
    if run is None:
        return render(request, "reports/shipment_forecast.html", {"no_data": True})
    rows = metrics.shipment_forecast(run)

    if request.GET.get("export") == "xlsx":
        _audit_export(request, "shipment-forecast")
        headers = ["Period", "POs", "Pieces", "FOB USD", "On-time %", "At-risk USD"]
        data = [
            [r["label"], r["pos"], r["pcs"], round(r["fob_usd"], 2), r["on_time_pct"], round(r["at_risk_usd"], 2)]
            for r in rows
        ]
        return _xlsx_response("shipment-forecast.xlsx", "Shipment forecast", headers, data, run.as_of)

    ctx = {
        "no_data": False,
        "as_of": run.as_of,
        "rows": rows,
        "outlook_option": json.dumps(charts.outlook_option(rows)),
    }
    return render(request, "reports/shipment_forecast.html", ctx)


@login_required
def factory_performance(request):
    run = metrics.latest_run()
    if run is None:
        return render(request, "reports/factory_performance.html", {"no_data": True})
    rows = metrics.factory_performance(run)

    if request.GET.get("export") == "xlsx":
        _audit_export(request, "factory-performance")
        headers = ["Code", "Name", "Location", "OTD %", "AQL pass %", "Knit load %",
                   "Reported today", "Open POs", "Open pcs", "Exposure USD", "Value at risk USD"]
        data = [
            [r["code"], r["name"], r["location"], round(r["otd_pct"], 1), round(r["aql_pass_pct"], 1),
             round(r["knit_load_pct"], 1), "Yes" if r["reported_today"] else "No",
             r["open_pos"], r["open_pcs"], round(r["exposure_usd"], 2), round(r["value_at_risk_usd"], 2)]
            for r in rows
        ]
        return _xlsx_response("factory-performance.xlsx", "Factory performance", headers, data, run.as_of)

    ctx = {"no_data": False, "as_of": run.as_of, "rows": rows}
    return render(request, "reports/factory_performance.html", ctx)
