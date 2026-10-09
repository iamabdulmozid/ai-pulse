"""Build engine inputs (POContext + factory stats) from plain records.

Pure Python — no Django/pandas imports. Both the answer-key parity harness (xlsx → dicts) and the ORM
adapter (DB → dicts) feed the same plain structures here, so they produce identical engine inputs.

Record shapes (all dates are datetime.date):
  factories:   [{"code"}]
  pos:         [{"po_no","factory_code","order_qty","planned_exfactory","weight_kg_pc","fob_usd_pc",
                 "wash_required","is_open"}]
  daily:       [{"po_no","factory_code","report_date","stage","day_pcs","cum_pcs"}]
  milestones:  [{"po_no","milestone","planned","revised","actual"}]
  shipments:   [{"factory_code","planned_exfactory","actual_exfactory"}]
  inspections: [{"po_no","factory_code","inspection_date","result"}]
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from services.calendar import next_wd, wd_between
from services.prediction.engine import Milestone, POContext


@dataclass
class FactoryStats:
    code: str
    otd_12m: float
    aql_pass_90d: float
    slip_distribution: list[int]
    last_report_date: date | None
    reported_today: bool
    missed_wd: int


def compute_factory_stats(
    factory_codes: list[str],
    daily: list[dict],
    shipments: list[dict],
    inspections: list[dict],
    today: date,
    history_start: date,
    latest_expected_report: date,
    holidays: frozenset[date] = frozenset(),
) -> dict[str, FactoryStats]:
    last_report: dict[str, date] = {}
    for r in daily:
        d = r["report_date"]
        c = r["factory_code"]
        if c not in last_report or d > last_report[c]:
            last_report[c] = d

    slips: dict[str, list[int]] = defaultdict(list)
    for s in shipments:
        a = s["actual_exfactory"]
        if a and history_start <= a <= latest_expected_report:
            slips[s["factory_code"]].append((a - s["planned_exfactory"]).days)

    insp_cut = today - timedelta(days=90)
    passes: dict[str, list[bool]] = defaultdict(list)
    for i in inspections:
        if i["inspection_date"] >= insp_cut:
            passes[i["factory_code"]].append(i["result"] == "Pass")

    out: dict[str, FactoryStats] = {}
    for c in factory_codes:
        sl = slips.get(c, [])
        otd = sum(1 for v in sl if v <= 0) / len(sl) if sl else 0.0
        p = passes.get(c, [])
        aql = sum(1 for v in p if v) / len(p) if p else 1.0
        lr = last_report.get(c)
        reported_today = lr == latest_expected_report if lr else False
        missed = (
            wd_between(next_wd(lr, holidays), next_wd(latest_expected_report, holidays), holidays) if lr else 0
        )
        out[c] = FactoryStats(c, otd, aql, sl, lr, reported_today, missed)
    return out


def latest_inspection_by_po(inspections: list[dict]) -> dict[str, str]:
    best: dict[str, tuple[date, str]] = {}
    for i in inspections:
        po = i["po_no"]
        if po not in best or i["inspection_date"] >= best[po][0]:
            best[po] = (i["inspection_date"], i["result"])
    return {po: res for po, (_d, res) in best.items()}


def build_contexts(
    pos: list[dict],
    daily: list[dict],
    milestones: list[dict],
    fstats: dict[str, FactoryStats],
    last_insp: dict[str, str],
    latest_expected_report: date,
    open_only: bool = True,
) -> list[POContext]:
    # Index daily rows and milestones by PO.
    daily_by_po: dict[str, list[dict]] = defaultdict(list)
    for r in daily:
        daily_by_po[r["po_no"]].append(r)
    ms_by_po: dict[str, dict[str, Milestone]] = defaultdict(dict)
    for m in milestones:
        ms_by_po[m["po_no"]][m["milestone"]] = Milestone(
            planned=m.get("planned"), revised=m.get("revised"), actual=m.get("actual")
        )

    contexts: list[POContext] = []
    for po in pos:
        if open_only and not po.get("is_open", True):
            continue
        fc = po["factory_code"]
        fs = fstats[fc]
        last_rep = fs.last_report_date or latest_expected_report
        rows = [r for r in daily_by_po.get(po["po_no"], []) if r["report_date"] <= last_rep]
        day_pcs: dict[str, dict[date, int]] = defaultdict(dict)
        cum_latest: dict[str, tuple[date, int]] = {}
        link_mc_latest: tuple[date, int] | None = None
        for r in rows:
            st = r["stage"]
            day_pcs[st][r["report_date"]] = r["day_pcs"]
            if st not in cum_latest or r["report_date"] > cum_latest[st][0]:
                cum_latest[st] = (r["report_date"], r["cum_pcs"])
            if st == "linking" and r.get("machines") is not None:
                if link_mc_latest is None or r["report_date"] > link_mc_latest[0]:
                    link_mc_latest = (r["report_date"], int(r["machines"]))
        cum = {st: v[1] for st, v in cum_latest.items()}

        contexts.append(
            POContext(
                po_no=po["po_no"],
                order_qty=po["order_qty"],
                planned_exfactory=po["planned_exfactory"],
                weight_kg_pc=float(po["weight_kg_pc"]),
                fob_usd_pc=float(po["fob_usd_pc"]),
                wash_required=bool(po["wash_required"]),
                day_pcs={k: dict(v) for k, v in day_pcs.items()},
                cum=cum,
                last_report=last_rep,
                milestones=ms_by_po.get(po["po_no"], {}),
                factory_otd_12m=fs.otd_12m,
                factory_aql_pass_90d=fs.aql_pass_90d,
                slip_distribution=fs.slip_distribution,
                factory_last_report=last_rep,
                latest_expected_report=latest_expected_report,
                latest_inspection_result=last_insp.get(po["po_no"]),
                link_machines_current=link_mc_latest[1] if link_mc_latest else None,
            )
        )
    return contexts
