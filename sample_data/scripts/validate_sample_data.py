"""Check the sample data set and re-derive the answer key from the Excel files alone.

    python scripts/validate_sample_data.py

Exits non-zero when a check fails. Every check reads the six upload files, never the
generator's memory, so a pass proves the answer key is reproducible from the uploads.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date

import pandas as pd

import generate_sample_data as g

D = g.OUT
failures: list[str] = []


def check(cond: bool, msg: str):
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def to_date(s):
    return s.dt.date if hasattr(s, "dt") else s


def load(name, sheet=0):
    df = pd.read_excel(D / name, sheet_name=sheet, dtype={"PO No": str})
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date
    return df


def main():
    head = load("01_Order_Book.xlsx", "PO Header")
    lines = load("01_Order_Book.xlsx", "PO Lines")
    ta = load("02_TA_Calendar.xlsx")
    dpr = load("03_Factory_Daily_Production_Report.xlsx")
    insp = load("04_Inspection_Log.xlsx")
    fac = load("05_Factory_Master.xlsx")
    ship = load("06_Shipment_Log.xlsx")
    key = load("00_Answer_Key.xlsx", "Open PO Predictions")
    kpis = dict(load("00_Answer_Key.xlsx", "KPIs").values)

    print("Order Book")
    check(head["PO No"].is_unique, "PO numbers are unique")
    lq = lines.groupby("PO No")["Line Qty"].sum()
    check((head.set_index("PO No")["Order Qty"] == lq.reindex(head["PO No"]).values).all(), "Order Qty equals the sum of PO Lines")
    sz = lines[g.ALL_SIZES].fillna(0).sum(axis=1)
    check((sz == lines["Line Qty"]).all(), "size columns sum to Line Qty")
    check(((head["Order Qty"] * head["FOB USD/pc"] - head["FOB Value USD"]).abs() < 0.02).all(), "FOB Value = Qty x FOB")
    check(set(head["Factory Code"]) <= set(fac["Factory Code"]), "every PO factory exists in Factory Master")
    gauges = {r["Factory Code"]: r["Gauges"] for _, r in fac.iterrows()}
    check(all(f"{r['Gauge']}GG" in gauges[r["Factory Code"]] for _, r in head.iterrows()), "every PO gauge is one its factory knits")

    print("Shipment Log")
    check(ship["PO No"].is_unique, "one shipment per shipped PO")
    check(set(ship["PO No"]) <= set(head["PO No"]), "shipments reference known POs")
    check((ship["Actual Ex-factory"] <= g.LAST_EXPECTED_REPORT).all(), "no shipment after the last report date")
    open_pos = head[~head["PO No"].isin(ship["PO No"])]
    check(len(open_pos) == 412, f"412 open POs (found {len(open_pos)})")
    check(abs(open_pos["FOB Value USD"].sum() - 18_600_000) < 50_000, f"open FOB ~ USD 18.6M ({open_pos['FOB Value USD'].sum():,.0f})")

    print("Daily Production Report")
    check(all(d.weekday() != 4 for d in dpr["Report Date"]), "no rows on a Friday")
    check(set(dpr["PO No"]) <= set(head["PO No"]), "DPR rows reference known POs")
    po_fac = head.set_index("PO No")["Factory Code"]
    check((dpr["Factory Code"].values == po_fac.reindex(dpr["PO No"]).values).all(), "DPR factory matches the PO's factory")
    stages = [("Knitting", None), ("Linking", "Knitting"), ("Trimming & Mending", "Linking"),
              ("Washing", "Trimming & Mending"), ("Ironing", "Washing"), ("Packing", "Ironing")]
    bad_mono = bad_flow = bad_day = 0
    for po, grp in dpr.sort_values("Report Date").groupby("PO No"):
        prev = None
        for _, r in grp.iterrows():
            for s, up in stages:
                c = r[f"{s} Cum"]
                if pd.isna(c):
                    continue
                if up and pd.isna(r[f"{up} Cum"]):
                    up = "Trimming & Mending"
                if up and c > r[f"{up} Cum"]:
                    bad_flow += 1
                if c > r["Order Qty"] or r[f"{s} Day"] < 0:
                    bad_flow += 1
                if prev is not None:
                    if c < prev[f"{s} Cum"]:
                        bad_mono += 1
                    if c - prev[f"{s} Cum"] != r[f"{s} Day"]:
                        bad_day += 1
            prev = r
    check(bad_mono == 0, f"cumulative figures never decrease ({bad_mono} breaks)")
    check(bad_day == 0, f"Day = change in Cum from the previous report ({bad_day} breaks)")
    check(bad_flow == 0, f"no stage ahead of its upstream stage or above order qty ({bad_flow} breaks)")
    last = dpr.groupby("Factory Code")["Report Date"].max()
    reported = int((last == g.LAST_EXPECTED_REPORT).sum())
    check(reported == 18, f"18 of 22 factories reported for {g.LAST_EXPECTED_REPORT:%d %b} (found {reported})")
    check(all(last[f.code] == f.last_report for f in g.FACTORIES if f.code in last), "last report dates match the story")

    print("T&A Calendar")
    check((ta.groupby("PO No").size() == 11).all(), "11 milestones per PO")
    st_ok = all(
        (r["Status"] == ("Done late" if r["Actual Date"] > r["Planned Date"] else "Done")) if pd.notna(r["Actual Date"])
        else (r["Status"] == ("Overdue" if r["Planned Date"] < g.TODAY else "Pending"))
        for _, r in ta.iterrows())
    check(st_ok, "Status agrees with the planned and actual dates")
    first = dpr[dpr["Knitting Day"] == dpr["Knitting Cum"]].groupby("PO No")["Report Date"].min()
    ks = ta[ta["Milestone"] == "Knitting start"].set_index("PO No")["Actual Date"]
    started_in_window = first[first > g.DPR_START]
    check((ks.reindex(started_in_window.index) == started_in_window).all(), "Knitting start actual = first DPR knitting day")

    print("Inspection Log")
    check((((insp["Result"] == "Pass") & (insp["Major Found"] <= insp["Major Accept (Ac)"])) |
           ((insp["Result"] == "Fail") & (insp["Major Found"] > insp["Major Accept (Ac)"]))).all(), "Result agrees with AQL accept number")

    print("Answer key, re-derived from the files")
    rows_by_po = defaultdict(list)
    for _, r in dpr.sort_values("Report Date").iterrows():
        out, cum = {}, {}
        for s, key_ in zip(g.ALL_STAGES, ["Knitting", "Linking", "Trimming & Mending", "Washing", "Ironing", "Packing"]):
            if pd.notna(r[f"{key_} Cum"]):
                out[s], cum[s] = int(r[f"{key_} Day"]), int(r[f"{key_} Cum"])
        rows_by_po[r["PO No"]].append({"date": r["Report Date"], "out": out, "cum": cum})
    ta_by_po = defaultdict(dict)
    for _, r in ta.iterrows():
        ta_by_po[r["PO No"]][r["Milestone"]] = {
            "planned": r["Planned Date"], "revised": r["Revised Date"] if pd.notna(r["Revised Date"]) else None,
            "actual": r["Actual Date"] if pd.notna(r["Actual Date"]) else None}
    opn = []
    for _, r in open_pos.iterrows():
        p = g.PO(r["PO No"], r["PO Date"], r["Season"], r["Department"], r["Product Type"], int(r["Gauge"]),
                 r["Yarn Composition"], "", r["Wash Required"], float(r["Weight kg/pc"]), float(r["Knitting Minutes/pc"]),
                 int(r["Linking Std pcs/M/C/day"]), r["Factory Code"], int(r["Order Qty"]), float(r["FOB USD/pc"]),
                 r["Planned Ex-factory"], r["Destination"], style_no=r["Style No"], style_name=r["Style Name"],
                 merch=r["Merchandiser"])
        p.rows = rows_by_po.get(p.po_no, [])
        opn.append(p)
    preds = pd.DataFrame(g.predict_all(opn, ta_by_po, ship, insp)).set_index("PO No")
    k = key.set_index("PO No")
    for col in ("Slip Days", "Risk Score", "Band", "Value at Risk USD"):
        same = (preds[col].reindex(k.index).values == k[col].values).all()
        check(bool(same), f"'{col}' matches the answer key for all {len(k)} open POs")
    var = preds["Value at Risk USD"].sum()
    check(abs(var - 2_400_000) < 25_000, f"value at risk ~ USD 2.4M ({var:,.0f})")
    top3 = preds.groupby("Factory Code")["Value at Risk USD"].sum().nlargest(3)
    check(set(top3.index) == {"GRL", "IRB", "SLM"} and 0.695 <= top3.sum() / var < 0.705,
          f"top 3 factories carry 70% of value at risk ({top3.sum() / var:.1%})")
    check(abs(float(kpis["October predicted on-time %"]) - 0.86) < 0.005, f"October on-time ~ 86% ({kpis['October predicted on-time %']})")
    hero = preds[(preds["Factory Code"] == "GRL") & (preds["Planned Ex-factory"] == date(2026, 10, 29)) & (preds["Order Qty"] == 9600)]
    check(len(hero) == 1 and hero["Slip Days"].iloc[0] == 9 and hero["Bottleneck Stage"].iloc[0] == "Linking",
          "hero PO: linking bottleneck, 9 days late")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    main()
