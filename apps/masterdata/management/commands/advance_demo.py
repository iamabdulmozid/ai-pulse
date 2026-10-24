"""Advance the demo dataset to a later "today" (e.g. 25 Oct for a live demo).

Simulates, deterministically, what factories would have reported after the seed's last report day:

- daily production per open PO and stage, continuing each stage's recent rate and limited by the work the
  upstream stage has finished (one-day pipeline lag), carrying machine counts forward;
- inline / pre-final / final inspections (AQL II, 2.5 majors) with realistic pass rates;
- a shipment for every PO that finishes packing (on or near its planned ex-factory; late POs move to
  Sea-Air / Air with freight cost), which closes the PO;
- T&A actuals (start dates from production, final inspection, ex-factory; others with small slips);
- shipment status progression (At port -> In transit -> Delivered by ETD/ETA);
- a few factories stay behind on reporting so "who hasn't reported" still has an answer;
- the hero PO gets the recovery plan the engine recommended on 15 Oct (more linking machines + two
  Friday overtime days), so the demo can show the effect of acting on a recommendation.

Then runs the prediction engine and alert rules as of the new day. Refuses to run twice for the same range.
Set DEMO_TODAY to the same date so screens, assistant and engine agree.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from apps.orders.models import PurchaseOrder, TAMilestone
from apps.production.models import DailyProduction, Inspection, Shipment
from services.calendar import is_working_day, next_wd, prev_wd

STAGES = ["knitting", "linking", "trimming_mending", "washing", "ironing", "packing"]
HERO = {"po_no": "71010305", "link_machines": 18}
# Factories that fall behind on reporting: code -> working days before the latest expected report on which
# they last reported (None = never resumes).
QUIET = {"OKH": None, "SLM": 3, "PBB": 2, "WSM": 1}
SAMPLE = [(280, 32, 2), (500, 50, 3), (1200, 80, 5), (3200, 125, 7), (10000, 200, 10), (10 ** 9, 315, 14)]
VESSELS = ["Kestrel", "Harmony", "Meridian", "Orchid", "Pearl", "Sapphire", "Monsoon", "Bengal Star"]


def _sample(lot: int) -> tuple[int, int]:
    """AQL II general inspection sample size and accept number for majors at 2.5."""
    for limit, n, ac in SAMPLE:
        if lot <= limit:
            return n, ac
    return SAMPLE[-1][1:]


class Command(BaseCommand):
    help = "Simulate factory reports, inspections and shipments up to --to, then re-run predictions."

    def add_arguments(self, parser):
        parser.add_argument("--to", default=None, help="New 'today' (YYYY-MM-DD). Defaults to DEMO_TODAY.")
        parser.add_argument("--seed", type=int, default=2610)

    def handle(self, *args, **opts):
        today = date.fromisoformat(opts["to"]) if opts["to"] else settings.DEMO_TODAY
        if today != settings.DEMO_TODAY:
            self.stdout.write(self.style.WARNING(
                f"DEMO_TODAY is {settings.DEMO_TODAY}; set it to {today} so the app uses the new day."))
        last = DailyProduction.objects.aggregate(m=Max("report_date"))["m"]
        latest_expected = prev_wd(today)
        if last is None or last >= latest_expected:
            raise CommandError(f"Data already reaches {last}; nothing to advance to {today}.")
        self.rng = random.Random(opts["seed"])
        self.today, self.latest = today, latest_expected
        with transaction.atomic():
            self._advance(last)
            from services.alerting import evaluate_alerts
            from services.prediction.run import run_predictions

            run = run_predictions(trigger="daily", today=today)
            # The team worked the previous run's alerts; the new run re-raises whatever still applies.
            from apps.alerts.models import Alert

            Alert.objects.filter(state="open").exclude(run=run).update(state="acked")
            evaluate_alerts(run)
        self.stdout.write(self.style.SUCCESS(
            f"Advanced {last} -> {latest_expected}: {self.n_rows} daily rows, {self.n_insp} inspections, "
            f"{self.n_ship} shipments. Run as of {run.as_of:%d %b %Y %H:%M}, {run.pos_scored} open POs scored."))

    # ------------------------------------------------------------------ simulation
    def _advance(self, last: date):
        days = []
        d = next_wd(last)
        while d <= self.latest:
            days.append(d)
            d = next_wd(d)
        reporting_until = {}
        for code, back in QUIET.items():
            if back is None:
                reporting_until[code] = last  # never resumes
            else:
                u = self.latest
                for _ in range(back):
                    u = prev_wd(u)
                reporting_until[code] = u

        pos = list(PurchaseOrder.objects.filter(is_open=True).select_related("factory", "style").order_by("po_no"))
        po_ids = [p.id for p in pos]
        hist = defaultdict(lambda: defaultdict(list))  # po_id -> stage -> [(date, day, cum, machines)]
        for r in (DailyProduction.objects.filter(purchase_order_id__in=po_ids)
                  .order_by("report_date").values_list("purchase_order_id", "stage", "report_date", "day_pcs",
                                                       "cum_pcs", "machines")):
            hist[r[0]][r[1]].append((r[2], r[3], r[4], r[5]))
        ta = defaultdict(dict)
        for m in TAMilestone.objects.filter(purchase_order_id__in=po_ids):
            ta[m.purchase_order_id][m.milestone] = m

        state = {}
        for p in pos:
            h = hist[p.id]
            stages = [s for s in STAGES if s != "washing" or p.style.wash_required or h.get("washing")]
            st = {}
            for s in stages:
                rows = h.get(s, [])
                recent = [r[1] for r in rows[-6:] if r[1] > 0]
                st[s] = {"cum": rows[-1][2] if rows else 0, "rate": sum(recent) / len(recent) if recent else 0,
                         "machines": rows[-1][3] if rows else None, "started": bool(rows)}
            state[p.id] = {"po": p, "stages": stages, "st": st, "done": None, "packing_60": False}

        hero = next((p for p in pos if p.po_no == HERO["po_no"]), None)
        hero_days = set()
        if hero:
            # Recovery plan applied from the first working day: +machines, Friday overtime in the window.
            d = last + timedelta(days=1)
            while d <= self.latest and len(hero_days) < 2:
                if not is_working_day(d):
                    hero_days.add(d)
                d += timedelta(days=1)
            hs = state[hero.id]["st"]["linking"]
            if hs["machines"]:
                hs["rate"] *= HERO["link_machines"] / hs["machines"]
            hs["machines"] = HERO["link_machines"]

        self.inspectors = list(Inspection.objects.exclude(inspector="").values_list("inspector", flat=True)
                               .distinct().order_by("inspector")) or ["Karbar QA"]
        self.defects = list(Inspection.objects.exclude(main_defect="").values_list("main_defect", flat=True)
                            .distinct().order_by("main_defect")) or ["Uneven linking"]
        self.insp_seq = Inspection.objects.count()
        self.ship_seq = Shipment.objects.count()
        self.invoices = set(Shipment.objects.values_list("invoice_no", flat=True))
        self.daily_rows, self.insp_rows, self.ship_rows, self.first_rows = [], [], [], {}

        for d in sorted(set(days) | hero_days):
            for s in state.values():
                p = s["po"]
                if s["done"]:
                    continue
                if d in hero_days and p.id != hero.id:
                    continue
                if d > reporting_until.get(p.factory.code, self.latest):
                    continue
                self._produce_day(s, d, ta[p.id])
            if d in days:
                self._inline_inspections(state, d)

        self._ship(state)
        self._update_ta(state, ta)
        DailyProduction.objects.bulk_create(self.daily_rows, batch_size=1000)
        Inspection.objects.bulk_create(self.insp_rows, batch_size=500)
        Shipment.objects.bulk_create(self.ship_rows, batch_size=500)
        PurchaseOrder.objects.filter(id__in=[s.purchase_order_id for s in self.ship_rows]).update(is_open=False)
        self._progress_shipments()
        self.n_rows, self.n_insp, self.n_ship = len(self.daily_rows), len(self.insp_rows), len(self.ship_rows)

    def _produce_day(self, s, d, ta):
        rng, p = self.rng, s["po"]
        qty = p.order_qty
        start_of_day = {k: v["cum"] for k, v in s["st"].items()}
        for i, stage in enumerate(s["stages"]):
            v = s["st"][stage]
            if stage == "knitting":
                if not v["started"]:
                    ms = ta.get("Knitting start")
                    due = ms and (ms.revised_date or ms.planned_date)
                    if not due or due > d:
                        continue
                    v["rate"] = qty / rng.uniform(18, 24)
                avail = qty - v["cum"]
            else:
                up = s["stages"][i - 1]
                avail = min(start_of_day[up], qty) - v["cum"]
                if not v["rate"]:
                    v["rate"] = s["st"][up]["rate"] * 0.95
                elif stage not in ("knitting", "linking"):
                    # Labour stages after linking add operators to keep pace with the flow from upstream.
                    v["rate"] = max(v["rate"], s["st"][up]["rate"])
            pcs = 0
            if avail > 0 and v["rate"]:
                pcs = max(0, min(avail, int(round(v["rate"] * rng.uniform(0.88, 1.08) / 5) * 5)))
            if not v["started"] and pcs == 0:
                continue
            v["cum"] += pcs
            if not v["started"]:
                v["started"] = True
                self.first_rows[(p.id, stage)] = d
            self.daily_rows.append(DailyProduction(
                purchase_order=p, factory=p.factory, report_date=d, stage=stage, day_pcs=pcs, cum_pcs=v["cum"],
                machines=v["machines"] if stage in ("knitting", "linking") else None,
                remarks="Overtime (recovery plan)" if not is_working_day(d) else ""))
        pk = s["st"]["packing"]["cum"]
        if not s["packing_60"] and pk >= 0.6 * qty:
            s["packing_60"] = True
            self._inspect(p, next_wd(d) if next_wd(d) <= self.latest else d, "Pre-final", min(pk, qty), 0.9)
        if pk >= qty:
            s["done"] = d

    def _inline_inspections(self, state, d):
        active = [s for s in state.values() if not s["done"] and s["st"].get("linking", {}).get("cum", 0) > 0
                  and s["st"]["packing"]["cum"] < 0.5 * s["po"].order_qty]
        for s in self.rng.sample(active, min(6, len(active))):
            self._inspect(s["po"], d, "Inline", max(200, min(s["st"]["linking"]["cum"], 1500)), 0.9)

    def _inspect(self, p, d, kind, lot, pass_p) -> bool:
        rng = self.rng
        n, ac = _sample(lot)
        ok = rng.random() < pass_p
        major = rng.randint(0, ac) if ok else ac + rng.randint(1, 4)
        spec = int(round(float(p.style.weight_kg_pc) * 1000))
        self.insp_seq += 1
        self.insp_rows.append(Inspection(
            inspection_id=f"QA-{d:%y%m}-{self.insp_seq:05d}", inspection_date=d, inspection_type=kind,
            purchase_order=p, factory=p.factory, inspector=rng.choice(self.inspectors), lot_qty=lot,
            aql_level="II / 2.5 / 4.0", sample_size=n, major_accept=ac, critical_found=0, major_found=major,
            minor_found=rng.randint(0, ac), result="Pass" if ok else "Fail",
            main_defect=rng.choice(self.defects) if major or not ok else "", measurement_check="Pass",
            spec_weight_g=spec, avg_weight_g=int(spec * rng.uniform(0.98, 1.02))))
        return ok

    def _ship(self, state):
        rng = self.rng
        for s in state.values():
            if not s["done"]:
                continue
            p = s["po"]
            ship_day = max(next_wd(s["done"]), p.planned_exfactory - timedelta(days=rng.randint(0, 2)))
            while not is_working_day(ship_day):
                ship_day = next_wd(ship_day)
            final_day = prev_wd(ship_day) if prev_wd(ship_day) >= s["done"] else s["done"]
            if ship_day > self.latest:
                continue  # packed, waiting for its ex-factory date
            if not self._inspect(p, final_day, "Final", p.order_qty, 0.93):
                final_day = next_wd(final_day)
                ship_day = next_wd(final_day)
                if ship_day > self.latest:
                    continue
                self._inspect(p, final_day, "Final re-inspection", p.order_qty, 1.0)
            s["final_day"], s["ship_day"] = final_day, ship_day
            late = (ship_day - p.planned_exfactory).days
            mode, rate_kg, borne = p.planned_ship_mode, 0, "Karbar"
            if late >= 10 and mode == "Sea":
                mode, rate_kg, borne = "Air", 4.2, "Factory"
            elif late >= 5 and mode == "Sea":
                mode, rate_kg, borne = "Sea-Air", 2.1, "Factory"
            gross = round(p.order_qty * float(p.style.weight_kg_pc) * 1.15, 2)
            air = mode != "Sea"
            etd = ship_day + timedelta(days=1 if air else rng.randint(4, 7))
            eta = etd + timedelta(days=3 if mode == "Air" else (14 if mode == "Sea-Air" else rng.randint(26, 34)))
            self.ship_seq += 1
            inv = f"KB-INV-{ship_day:%y%m}-{rng.randint(1000, 9999)}"
            while inv in self.invoices:
                inv = f"KB-INV-{ship_day:%y%m}-{rng.randint(1000, 9999)}"
            self.invoices.add(inv)
            self.ship_rows.append(Shipment(
                shipment_id=f"SH-{ship_day:%y%m}-{self.ship_seq:04d}", purchase_order=p, factory=p.factory,
                planned_exfactory=p.planned_exfactory, actual_exfactory=ship_day, shipped_qty=p.order_qty,
                cartons=math.ceil(p.order_qty / 12), gross_weight_kg=gross, ship_mode=mode,
                port_of_loading=p.port_of_loading, destination=p.destination, etd=etd, eta=eta,
                vessel_flight=(f"EK {rng.randint(500, 599)}" if mode == "Air"
                               else f"MV Eastern {rng.choice(VESSELS)} V.{ship_day:%y%m}E"),
                invoice_no=inv, invoice_value_usd=p.fob_value_usd,
                air_freight_cost_usd=round(gross * rate_kg, 2) if rate_kg else None, freight_borne_by=borne,
                shipment_status="At port", remarks="Shipped late; air at factory cost" if rate_kg else ""))

    def _update_ta(self, state, ta):
        rng, changed = self.rng, []
        for sid, s in state.items():
            ms = ta[sid]
            actuals = {"Knitting start": self.first_rows.get((sid, "knitting")),
                       "Linking start": self.first_rows.get((sid, "linking")),
                       "Final inspection": s.get("final_day"), "Ex-factory": s.get("ship_day")}
            for name, m in ms.items():
                if m.actual_date:
                    continue
                due = m.revised_date or m.planned_date
                act = actuals.get(name)
                if name not in actuals and due <= self.latest:
                    act = due + timedelta(days=rng.choice([0, 0, 0, 1, 2, 4]))
                    act = act if act <= self.latest else None
                if act:
                    m.actual_date, m.status = act, "Done" if act <= due else "Done late"
                elif due < self.today:
                    m.status = "Overdue"
                else:
                    continue
                changed.append(m)
        TAMilestone.objects.bulk_update(changed, ["actual_date", "status"], batch_size=500)

    def _progress_shipments(self):
        Shipment.objects.filter(eta__lte=self.today).exclude(shipment_status="Delivered").update(
            shipment_status="Delivered")
        Shipment.objects.filter(etd__lte=self.today, eta__gt=self.today).update(shipment_status="In transit")
