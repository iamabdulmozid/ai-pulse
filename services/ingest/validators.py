"""Per-file validation for the upload ingest (docs/data/excel-templates.md).

``validate_daily_production`` resolves referential keys (Factory Code -> Factory, PO No -> PurchaseOrder)
and applies the Daily Production rules from the spec. It returns ``(accepted_rows, warnings, errors)``;
when ``errors`` is non-empty the batch is rejected as a whole (the caller writes nothing).

A file with any error writes nothing, so validation reports **one error per offending row** (the first
failing check for that row) — the row-level panel the Daily Updates screen shows. Structural/batch-level
problems (unrecognised kind, multiple factories/dates, a Friday report date) are reported with ``row = 0``.

Other file kinds get their own ``validate_<kind>`` here; the ingest dispatches by kind.
"""
from __future__ import annotations

from services.ingest.readers import STAGE_ORDER, DailyRow, ReadResult

STAGE_LABEL = {
    "knitting": "Knitting",
    "linking": "Linking",
    "trimming_mending": "Trimming & Mending",
    "washing": "Washing",
    "ironing": "Ironing",
    "packing": "Packing",
}
FRIDAY = 4  # date.weekday(): Mon=0 … Fri=4


def validate_daily_production(rr: ReadResult) -> tuple[list[dict], list[dict], list[dict]]:
    warnings: list[dict] = []

    # Structural problems from the reader (unrecognised kind, etc.) reject immediately.
    if rr.errors:
        return [], warnings, list(rr.errors)
    if not rr.rows:
        return [], warnings, [{"row": 0, "message": "No data rows found in the Daily Production sheet."}]

    # One factory and one report date for the whole file; no Friday report dates.
    batch_errors: list[dict] = []
    codes = {r.factory_code for r in rr.rows if r.factory_code}
    if len(codes) > 1:
        batch_errors.append(
            {"row": 0, "message": f"File has multiple Factory Codes {sorted(codes)}; one factory per file."}
        )
    dates = {r.report_date for r in rr.rows if r.report_date}
    if len(dates) > 1:
        batch_errors.append({"row": 0, "message": "File has multiple Report Dates; one date per file."})
    for d in dates:
        if d.weekday() == FRIDAY:
            batch_errors.append({"row": 0, "message": f"Report Date {d:%d-%b-%Y} is a Friday (weekend)."})
    if batch_errors:
        return [], warnings, batch_errors

    from apps.orders.models import PurchaseOrder
    from apps.production.models import DailyProduction

    po_nos = [r.po_no for r in rr.rows if r.po_no]
    po_map = {
        p.po_no: p
        for p in PurchaseOrder.objects.select_related("factory", "style").filter(po_no__in=po_nos)
    }
    report_date = next(iter(dates)) if dates else None

    # Latest known cumulative per (PO, stage) strictly before this report date (monotonicity baseline).
    prior: dict[tuple[int, str], int] = {}
    if report_date is not None:
        qs = (
            DailyProduction.objects.filter(purchase_order__po_no__in=po_nos, report_date__lt=report_date)
            .order_by("report_date")
            .values_list("purchase_order_id", "stage", "cum_pcs")
        )
        for po_id, stage, cum in qs:
            prior[(po_id, stage)] = cum  # ascending order -> ends on the latest prior report

    errors: list[dict] = []
    accepted: list[dict] = []
    seen: set[str] = set()
    for r in rr.rows:
        err = _row_error(r, po_map, prior, seen)
        if err:
            errors.append({"row": r.row, "message": err})
            continue
        seen.add(r.po_no)
        po = po_map[r.po_no]
        for stage, cell in r.stages.items():
            if not cell.present:
                continue
            accepted.append(
                {
                    "purchase_order": po,
                    "factory": po.factory,
                    "report_date": r.report_date,
                    "stage": stage,
                    "day_pcs": cell.day or 0,
                    "cum_pcs": cell.cum or 0,
                    "machines": cell.machines,
                    "remarks": r.remarks,
                }
            )

    if errors:
        return [], warnings, errors
    return accepted, warnings, []


def _row_error(r: DailyRow, po_map, prior, seen) -> str | None:
    if not r.report_date:
        return "Report Date is required."

    po = po_map.get(r.po_no)
    if po is None:
        return f"PO {r.po_no} not found in Order Book."
    if r.factory_code and po.factory.code != r.factory_code:
        return f"PO {r.po_no} belongs to factory {po.factory.code}, not {r.factory_code}."
    if r.po_no in seen:
        return f"Duplicate PO {r.po_no} for {r.report_date:%d-%b-%Y} in the same file."

    # Non-negative day (and machine) figures.
    for stage in STAGE_ORDER:
        cell = r.stages.get(stage)
        if not cell:
            continue
        if cell.day is not None and cell.day < 0:
            return f"{STAGE_LABEL[stage]} Day must be ≥ 0 (got {cell.day})."
        if cell.machines is not None and cell.machines < 0:
            return f"{STAGE_LABEL[stage]} M/C must be ≥ 0 (got {cell.machines})."

    # Cumulative figures are monotonic non-decreasing per (PO, stage).
    for stage in STAGE_ORDER:
        cell = r.stages.get(stage)
        if not cell or not cell.present:
            continue
        last = prior.get((po.id, stage))
        if last is not None and cell.cum is not None and cell.cum < last:
            return f"{STAGE_LABEL[stage]} Cum must not decrease (got {cell.cum}, was {last})."

    # A stage can never be ahead of its upstream stage: Linking Cum ≤ Knitting Cum.
    knit = r.stages.get("knitting")
    link = r.stages.get("linking")
    if (
        knit
        and link
        and knit.present
        and link.present
        and link.cum is not None
        and knit.cum is not None
        and link.cum > knit.cum
    ):
        return f"Linking Cum ({link.cum}) must be ≤ Knitting Cum ({knit.cum})."

    # Washing columns are blank unless the style requires washing.
    wash = r.stages.get("washing")
    if not po.style.wash_required and wash and (wash.day is not None or wash.cum is not None):
        return f"Washing data present but style {po.style.style_no} does not require washing."

    return None
