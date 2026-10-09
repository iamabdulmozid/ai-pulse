"""Load the six sample workbooks, run the pure engine, and compare to 00_Answer_Key.xlsx.

Usage:  python scripts/engine_parity.py [--verbose]
This is the reference-data loader reused by tests/test_engine_matches_answer_key.py.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.prediction.aggregate import (  # noqa: E402
    build_contexts,
    compute_factory_stats,
    latest_inspection_by_po,
)
from services.prediction.params import EngineParams  # noqa: E402
from services.prediction.score import predict  # noqa: E402

SAMPLE = ROOT / "sample_data"
TODAY = date(2026, 10, 15)
LATEST_REPORT = date(2026, 10, 14)
HISTORY_START = date(2025, 10, 15)

STAGE_COLS = {
    "knitting": ("Knitting Day", "Knitting Cum", "Knitting M/C"),
    "linking": ("Linking Day", "Linking Cum", "Linking M/C"),
    "trimming_mending": ("Trimming & Mending Day", "Trimming & Mending Cum", None),
    "washing": ("Washing Day", "Washing Cum", None),
    "ironing": ("Ironing Day", "Ironing Cum", None),
    "packing": ("Packing Day", "Packing Cum", None),
}


def _d(v):
    if pd.isna(v):
        return None
    return pd.Timestamp(v).date()


def load_records():
    ob = pd.read_excel(SAMPLE / "01_Order_Book.xlsx", sheet_name="PO Header")
    ta = pd.read_excel(SAMPLE / "02_TA_Calendar.xlsx", sheet_name="T&A Calendar")
    dp = pd.read_excel(SAMPLE / "03_Factory_Daily_Production_Report.xlsx", sheet_name="Daily Production")
    insp = pd.read_excel(SAMPLE / "04_Inspection_Log.xlsx", sheet_name="Inspections")
    fm = pd.read_excel(SAMPLE / "05_Factory_Master.xlsx", sheet_name="Factories")
    ship = pd.read_excel(SAMPLE / "06_Shipment_Log.xlsx", sheet_name="Shipments")

    shipped_pos = set(ship["PO No"].astype(str))

    pos = []
    for _, r in ob.iterrows():
        po_no = str(r["PO No"])
        pos.append(
            {
                "po_no": po_no,
                "factory_code": str(r["Factory Code"]),
                "order_qty": int(r["Order Qty"]),
                "planned_exfactory": _d(r["Planned Ex-factory"]),
                "weight_kg_pc": float(r["Weight kg/pc"]),
                "fob_usd_pc": float(r["FOB USD/pc"]),
                "wash_required": str(r["Wash Required"]).strip().upper() == "Y",
                "is_open": po_no not in shipped_pos,
            }
        )

    milestones = []
    for _, r in ta.iterrows():
        milestones.append(
            {
                "po_no": str(r["PO No"]),
                "milestone": str(r["Milestone"]),
                "planned": _d(r["Planned Date"]),
                "revised": _d(r.get("Revised Date")),
                "actual": _d(r.get("Actual Date")),
            }
        )

    daily = []
    for _, r in dp.iterrows():
        po_no = str(r["PO No"])
        fc = str(r["Factory Code"])
        rd = _d(r["Report Date"])
        for stage, (dcol, ccol, _mc) in STAGE_COLS.items():
            if dcol not in r or pd.isna(r.get(ccol)):
                continue
            day = r.get(dcol)
            cum = r.get(ccol)
            if pd.isna(cum):
                continue
            mc = r.get(_mc) if _mc else None
            daily.append(
                {
                    "po_no": po_no,
                    "factory_code": fc,
                    "report_date": rd,
                    "stage": stage,
                    "day_pcs": int(day) if not pd.isna(day) else 0,
                    "cum_pcs": int(cum),
                    "machines": int(mc) if (mc is not None and not pd.isna(mc)) else None,
                }
            )

    inspections = [
        {
            "po_no": str(r["PO No"]),
            "factory_code": str(r["Factory Code"]),
            "inspection_date": _d(r["Inspection Date"]),
            "result": str(r["Result"]),
        }
        for _, r in insp.iterrows()
    ]

    shipments = [
        {
            "factory_code": str(r["Factory Code"]),
            "planned_exfactory": _d(r["Planned Ex-factory"]),
            "actual_exfactory": _d(r["Actual Ex-factory"]),
        }
        for _, r in ship.iterrows()
    ]

    factory_codes = [str(c) for c in fm["Factory Code"]]
    return pos, daily, milestones, shipments, inspections, factory_codes


def build_all(open_only=True):
    pos, daily, milestones, shipments, inspections, factory_codes = load_records()
    fstats = compute_factory_stats(
        factory_codes, daily, shipments, inspections, TODAY, HISTORY_START, LATEST_REPORT
    )
    last_insp = latest_inspection_by_po(inspections)
    contexts = build_contexts(pos, daily, milestones, fstats, last_insp, LATEST_REPORT, open_only=open_only)
    return {c.po_no: c for c in contexts}, pos, shipments


def run_engine():
    ctxs, _pos, _ship = build_all()
    params = EngineParams()
    return {po: predict(c, params, TODAY) for po, c in ctxs.items()}


def check_hero_whatif(verbose=False):
    from datetime import date as _date

    from services.prediction.whatif import simulate

    ctxs, _pos, _ship = build_all()
    params = EngineParams()
    hero = ctxs["71010305"]
    fridays = frozenset({_date(2026, 10, 16), _date(2026, 10, 23)})
    options = [
        ("Current plan", 13, frozenset()),
        ("+6 linking M/C (13 -> 19)", 19, frozenset()),
        ("2 Friday overtime days (16, 23 Oct)", 13, fridays),
        ("+6 linking M/C and 2 Friday overtime days", 19, fridays),
    ]
    ak = pd.read_excel(SAMPLE / "00_Answer_Key.xlsx", sheet_name="Hero What-if")
    ak_hero = {row["Option"]: row for _, row in ak.iterrows() if str(row["PO No"]) == "71010305"}
    bad = 0
    for label, mc, ot in options:
        r = simulate(hero, params, TODAY, link_machines=mc, overtime_days=ot)
        exp = ak_hero[label]
        ok = (
            r["projected_exfactory"] == pd.Timestamp(exp["Projected Ex-factory"]).date()
            and r["slip_days"] == int(exp["Slip Days"])
            and abs(r["linking_pcs_day"] - float(exp["Linking pcs/day"])) <= 0.15
            and r["completion_day_n"] == int(exp["Completion Day N"])
            and abs(float(r["air_freight_avoided_usd"]) - float(exp["Air freight avoided USD"])) <= 0.5
        )
        if not ok:
            bad += 1
        if verbose or not ok:
            print(f"  [{'OK' if ok else 'XX'}] {label}: exf={r['projected_exfactory']} slip={r['slip_days']} "
                  f"link={r['linking_pcs_day']} N={r['completion_day_n']} air_avoided={r['air_freight_avoided_usd']}")
    print(f"Hero what-if mismatches: {bad}")
    return bad


def compare(verbose=False):
    ak = pd.read_excel(SAMPLE / "00_Answer_Key.xlsx", sheet_name="Open PO Predictions")
    results = run_engine()
    checks = {
        "Band": lambda r: r.band,
        "Risk Score": lambda r: r.risk_score,
        "Slip Days": lambda r: r.slip_days,
        "Projected Ex-factory": lambda r: r.projected_exfactory,
        "Bottleneck Rate pcs/day": lambda r: r.bottleneck_rate,
        "Required Rate pcs/day": lambda r: r.required_rate,
        "On-time Probability": lambda r: r.on_time_probability,
        "Value at Risk USD": lambda r: r.value_at_risk_usd,
        "Air-freight Exposure USD": lambda r: r.air_freight_exposure_usd,
    }
    mismatches = {k: 0 for k in checks}
    examples = {k: [] for k in checks}
    missing = 0
    for _, row in ak.iterrows():
        po = str(row["PO No"])
        r = results.get(po)
        if r is None:
            missing += 1
            continue
        for col, fn in checks.items():
            got = fn(r)
            exp = row[col]
            if not _equal(col, got, exp):
                mismatches[col] += 1
                if len(examples[col]) < 5:
                    examples[col].append((po, got, exp))
    total = len(ak)
    print(f"Open POs in answer key: {total}; engine produced: {len(results)}; missing: {missing}")
    for col in checks:
        print(f"  {col:28s} mismatches: {mismatches[col]}")
        if verbose and examples[col]:
            for po, got, exp in examples[col]:
                print(f"      {po}: got={got!r} exp={exp!r}")
    return mismatches, missing, total


def _equal(col, got, exp):
    if col == "Projected Ex-factory":
        return got == (pd.Timestamp(exp).date() if not pd.isna(exp) else None)
    if col == "Band":
        return str(got) == str(exp)
    # numeric
    if got is None:
        return pd.isna(exp)
    if pd.isna(exp):
        return got is None
    if col in ("On-time Probability",):
        return abs(float(got) - float(exp)) <= 0.011
    if col in ("Value at Risk USD", "Air-freight Exposure USD"):
        return abs(float(got) - float(exp)) <= 0.5
    if col in ("Bottleneck Rate pcs/day", "Required Rate pcs/day"):
        return abs(float(got) - float(exp)) <= 0.15
    return abs(float(got) - float(exp)) <= 0.5


def check_kpis(verbose=False):
    from collections import Counter

    ctxs, pos, shipments = build_all()
    params = EngineParams()
    results = {po: predict(c, params, TODAY) for po, c in ctxs.items()}
    po_factory = {p["po_no"]: p["factory_code"] for p in pos}
    po_open = {p["po_no"]: p for p in pos if p["is_open"]}

    open_pos = len(results)
    open_qty = sum(po_open[po]["order_qty"] for po in results)
    open_fob = sum(round(po_open[po]["order_qty"] * po_open[po]["fob_usd_pc"], 2) for po in results)
    var = sum(r.value_at_risk_usd for r in results.values())
    air = sum(r.air_freight_exposure_usd for r in results.values())
    bands = Counter(r.band for r in results.values())

    by_factory = Counter()
    for po, r in results.items():
        by_factory[po_factory[po]] += r.value_at_risk_usd
    top3 = sorted(by_factory.values(), reverse=True)[:3]
    top3_share = sum(top3) / var if var else 0

    def in_oct(d):
        return d and d.year == 2026 and d.month == 10

    octo = [po for po in results if in_oct(po_open[po]["planned_exfactory"])]
    oct_open_on = sum(1 for po in octo if results[po].slip_days <= 0 and results[po].band != "Late")
    oct_ship = [s for s in shipments if in_oct(s["planned_exfactory"])]
    oct_ship_on = sum(1 for s in oct_ship if s["actual_exfactory"] <= s["planned_exfactory"])
    oct_total = len(octo) + len(oct_ship)
    oct_pct = (oct_ship_on + oct_open_on) / oct_total if oct_total else 0

    ak = pd.read_excel(SAMPLE / "00_Answer_Key.xlsx", sheet_name="KPIs")
    kv = {str(r["KPI"]): r["Value"] for _, r in ak.iterrows()}

    checks = [
        ("Open POs", open_pos, int(kv["Open POs"])),
        ("Open qty (pcs)", open_qty, int(kv["Open qty (pcs)"])),
        ("Open FOB value (USD)", round(open_fob, 2), round(float(kv["Open FOB value (USD)"]), 2)),
        ("October predicted on-time %", round(oct_pct, 4), round(float(kv["October predicted on-time %"]), 4)),
        ("Value at risk (USD)", round(var, 2), round(float(kv["Value at risk (USD) = FOB of At risk + Critical + Late"]), 2)),
        ("Top 3 share", round(top3_share, 4), round(float(kv["Top 3 share of value at risk"]), 4)),
        ("Air-freight exposure (USD)", round(air, 2), round(float(kv["Air-freight exposure (USD)"]), 2)),
    ]
    bad = 0
    for name, got, exp in checks:
        ok = (abs(got - exp) <= 0.5) if isinstance(exp, float) else (got == exp)
        if isinstance(exp, float):
            ok = abs(float(got) - float(exp)) <= (0.0001 if "%" in name or "share" in name else 0.5)
        if not ok:
            bad += 1
        print(f"  [{'OK' if ok else 'XX'}] {name:28s} got={got} exp={exp}")
    print(f"  Band counts: {dict(bands)}  (answer key: On track 354, Watch 10, At risk 28, Critical 13, Late 7)")
    exp_bands = {"On track": 354, "Watch": 10, "At risk": 28, "Critical": 13, "Late": 7}
    if dict(bands) != exp_bands:
        bad += 1
        print("  [XX] band counts differ")
    print(f"KPI mismatches: {bad}")
    return bad


if __name__ == "__main__":
    v = "--verbose" in sys.argv
    compare(verbose=v)
    print()
    check_hero_whatif(verbose=v)
    print()
    check_kpis(verbose=v)
