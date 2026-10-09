"""Workbook readers for the upload ingest (docs/data/excel-templates.md).

A file is classified by its sheet structure, not its name. For the Daily Production file we also read the
single Factory Code and Report Date (the real daily report is one factory for one date) and explode each
wide row into per-stage cells, mirroring ``seed_demo``'s ``STAGE_COLS`` pivot. Other kinds can be added by
following the same ``detect`` + ``read_*`` shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import openpyxl
import pandas as pd

# Sheet-structure -> kind (docs/data/excel-templates.md "How a file is detected").
_KIND_BY_SHEETS: list[tuple[str, set[str]]] = [
    ("order_book", {"PO Header", "PO Lines"}),
    ("ta_calendar", {"T&A Calendar"}),
    ("daily_production", {"Daily Production"}),
    ("inspection", {"Inspections"}),
    ("factory_master", {"Factories"}),
    ("shipment", {"Shipments"}),
]

# Wide stage columns -> (day col, cum col, machines col). Same mapping seed_demo uses.
STAGE_COLS: dict[str, tuple[str, str, str | None]] = {
    "knitting": ("Knitting Day", "Knitting Cum", "Knitting M/C"),
    "linking": ("Linking Day", "Linking Cum", "Linking M/C"),
    "trimming_mending": ("Trimming & Mending Day", "Trimming & Mending Cum", None),
    "washing": ("Washing Day", "Washing Cum", None),
    "ironing": ("Ironing Day", "Ironing Cum", None),
    "packing": ("Packing Day", "Packing Cum", None),
}
STAGE_ORDER: list[str] = list(STAGE_COLS)
DAILY_PRODUCTION_SHEET = "Daily Production"


@dataclass
class StageCell:
    day: int | None
    cum: int | None
    machines: int | None
    present: bool  # the cumulative figure is non-blank (this stage has data on the row)


@dataclass
class DailyRow:
    row: int  # 1-based data-row number, for per-row error messages
    po_no: str
    factory_code: str
    report_date: date | None
    style_no: str
    order_qty: int | None
    stages: dict[str, StageCell]
    remarks: str


@dataclass
class ReadResult:
    kind: str
    factory_code: str | None
    report_date: date | None
    rows: list[DailyRow] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)  # structural / batch-level [{row, message}]


def _num(v) -> int | None:
    if v is None or pd.isna(v):
        return None
    return int(round(float(v)))


def _code(v) -> str:
    if pd.isna(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _date(v) -> date | None:
    if v is None or pd.isna(v):
        return None
    return pd.Timestamp(v).date()


def detect_kind(sheetnames) -> str:
    names = set(sheetnames)
    for kind, required in _KIND_BY_SHEETS:
        if required <= names:
            return kind
    return ""


def detect(path) -> dict:
    """Classify a workbook and, for a daily report, pull its single factory + report date.

    Used by the upload view to stamp the ``UploadBatch`` before the async task runs.
    """
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        kind = detect_kind(wb.sheetnames)
    finally:
        wb.close()

    factory_code: str | None = None
    report_date: date | None = None
    if kind == "daily_production":
        df = pd.read_excel(path, sheet_name=DAILY_PRODUCTION_SHEET)
        codes = {c for c in (_code(v) for v in df.get("Factory Code", [])) if c}
        factory_code = next(iter(codes)) if len(codes) == 1 else (sorted(codes)[0] if codes else None)
        dates = sorted({d for d in (_date(v) for v in df.get("Report Date", [])) if d})
        report_date = dates[0] if len(dates) == 1 else (dates[-1] if dates else None)
    return {"kind": kind, "factory_code": factory_code, "report_date": report_date}


def read_daily_production(path) -> ReadResult:
    """Read the Daily Production sheet into per-row records with per-stage cells."""
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        kind = detect_kind(wb.sheetnames)
    finally:
        wb.close()
    if kind != "daily_production":
        return ReadResult(
            kind=kind,
            factory_code=None,
            report_date=None,
            errors=[{"row": 0, "message": "File kind not recognised as a Daily Production report."}],
        )

    df = pd.read_excel(path, sheet_name=DAILY_PRODUCTION_SHEET)
    rows: list[DailyRow] = []
    for i, r in df.iterrows():
        stages: dict[str, StageCell] = {}
        for stage, (dcol, ccol, mcol) in STAGE_COLS.items():
            day = _num(r[dcol]) if dcol in r else None
            cum = _num(r[ccol]) if ccol in r else None
            machines = _num(r[mcol]) if (mcol and mcol in r) else None
            stages[stage] = StageCell(day=day, cum=cum, machines=machines, present=cum is not None)
        rows.append(
            DailyRow(
                row=int(i) + 1,
                po_no=_code(r.get("PO No")),
                factory_code=_code(r.get("Factory Code")),
                report_date=_date(r.get("Report Date")),
                style_no=_code(r.get("Style No")),
                order_qty=_num(r.get("Order Qty")),
                stages=stages,
                remarks="" if pd.isna(r.get("Remarks")) else str(r.get("Remarks")).strip(),
            )
        )

    codes = {rw.factory_code for rw in rows if rw.factory_code}
    dates = {rw.report_date for rw in rows if rw.report_date}
    return ReadResult(
        kind=kind,
        factory_code=next(iter(codes)) if len(codes) == 1 else None,
        report_date=next(iter(dates)) if len(dates) == 1 else None,
        rows=rows,
    )
