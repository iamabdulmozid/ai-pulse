"""seed_demo — load the deterministic demo dataset (docs/data/seed-story.md).

Loads the six canonical workbooks in sample_data/ into the database (the same data the ingest produces),
seeds users/groups/persona logins, and runs the engine once as of DEMO_TODAY so every screen has data.

Deterministic: the source workbooks are fixed, so every run yields identical data. Re-running flushes the
demo tables first (idempotent).

    python manage.py seed_demo
"""
from __future__ import annotations

import pandas as pd
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.masterdata.models import Department, Factory, FactoryMachine, Season
from apps.orders.models import POLine, POLineSize, PurchaseOrder, Style, TAMilestone
from apps.production.models import DailyProduction, Inspection, Shipment

STAGE_COLS = {
    "knitting": ("Knitting Day", "Knitting Cum", "Knitting M/C"),
    "linking": ("Linking Day", "Linking Cum", "Linking M/C"),
    "trimming_mending": ("Trimming & Mending Day", "Trimming & Mending Cum", None),
    "washing": ("Washing Day", "Washing Cum", None),
    "ironing": ("Ironing Day", "Ironing Cum", None),
    "packing": ("Packing Day", "Packing Cum", None),
}
SIZE_COLS = ["XS", "S", "M", "L", "XL", "XXL", "2-3Y", "4-5Y", "6-7Y", "8-9Y", "10-11Y"]


def _d(v):
    return None if pd.isna(v) else pd.Timestamp(v).date()


def _s(v):
    return "" if pd.isna(v) else str(v).strip()


class Command(BaseCommand):
    help = "Load the deterministic demo dataset and run the prediction engine."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="Do not flush existing demo data first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        d = settings.SAMPLE_DATA_DIR
        if not opts["keep"]:
            self._flush()

        self.stdout.write("Loading workbooks…")
        ob = pd.read_excel(d / "01_Order_Book.xlsx", sheet_name="PO Header")
        lines = pd.read_excel(d / "01_Order_Book.xlsx", sheet_name="PO Lines")
        ta = pd.read_excel(d / "02_TA_Calendar.xlsx", sheet_name="T&A Calendar")
        dp = pd.read_excel(d / "03_Factory_Daily_Production_Report.xlsx", sheet_name="Daily Production")
        insp = pd.read_excel(d / "04_Inspection_Log.xlsx", sheet_name="Inspections")
        fm = pd.read_excel(d / "05_Factory_Master.xlsx", sheet_name="Factories")
        ship = pd.read_excel(d / "06_Shipment_Log.xlsx", sheet_name="Shipments")

        users = self._seed_people(ob, fm)
        self._factories(fm, users)
        self._orders(ob, users)
        self._po_lines(lines)
        self._ta(ta)
        self._daily(dp)
        self._inspections(insp)
        self._shipments(ship)

        self.stdout.write("Running the prediction engine (seed run)…")
        from services.prediction.run import run_predictions

        run = run_predictions(trigger="seed")
        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {PurchaseOrder.objects.count()} POs "
            f"({PurchaseOrder.objects.filter(is_open=True).count()} open), "
            f"{run.pos_scored} scored. Run as of {run.as_of:%d %b %Y %H:%M}."
        ))

    # ---- flush -----------------------------------------------------------
    def _flush(self):
        from apps.alerts.models import Alert
        from apps.predictions.models import FactoryStat, PredictionRun, PredictionSnapshot

        for model in (Alert, PredictionSnapshot, FactoryStat, PredictionRun,
                      DailyProduction, Inspection, Shipment, TAMilestone, POLineSize, POLine,
                      PurchaseOrder, Style, FactoryMachine, Factory, Season, Department):
            model.objects.all().delete()

    # ---- people ----------------------------------------------------------
    def _seed_people(self, ob, fm):
        names = set(ob["Merchandiser"].dropna().astype(str)) | set(fm["Karbar Merchandiser"].dropna().astype(str))
        merch_group, _ = Group.objects.get_or_create(name="Merchandiser")
        users: dict[str, User] = {}
        for name in sorted(names):
            uname = slugify(name).replace("-", ".")[:150] or f"user{len(users)}"
            u, created = User.objects.get_or_create(
                username=uname, defaults={"first_name": name.split()[0], "last_name": " ".join(name.split()[1:])}
            )
            if created:
                u.set_password("demo12345")
                u.save()
            u.groups.add(merch_group)
            users[name] = u
        # Persona logins.
        self._persona("admin", "Admin", superuser=True)
        self._persona("ceo", "Management", first="Karbar", last="CEO")
        self._persona("headmerch", "Management", first="Head", last="Merchandising")
        self._persona("qahead", "QA", first="QA", last="Head")
        return users

    def _persona(self, username, group, superuser=False, first="", last=""):
        u, created = User.objects.get_or_create(
            username=username, defaults={"first_name": first, "last_name": last,
                                         "is_staff": superuser, "is_superuser": superuser}
        )
        if created:
            u.set_password("demo12345")
            u.save()
        g, _ = Group.objects.get_or_create(name=group)
        u.groups.add(g)
        return u

    # ---- factories -------------------------------------------------------
    def _factories(self, fm, users):
        for _, r in fm.iterrows():
            fac = Factory.objects.create(
                code=_s(r["Factory Code"]), name=_s(r["Factory Name"]), area=_s(r["Area"]),
                district=_s(r["District"]), address=_s(r.get("Address")),
                supplier_since=_d(r.get("Supplier Since")), gauges=_s(r["Gauges"]),
                linking_machines=int(r["Linking M/C"]), washing=_s(r["Washing"]),
                knitting_shifts=int(r["Knitting Shifts"]), knitting_hours_day=int(r["Knitting Hours/Day"]),
                linking_hours_day=int(r["Linking Hours/Day"]),
                workforce=None if pd.isna(r.get("Workforce")) else int(r["Workforce"]),
                certifications=_s(r.get("Certifications")), bsci_rating=_s(r.get("amfori BSCI Rating")),
                last_social_audit=_d(r.get("Last Social Audit")), contact_name=_s(r.get("Factory Contact")),
                contact_title=_s(r.get("Contact Title")), status=_s(r["Status"]),
                merchandiser=users.get(_s(r.get("Karbar Merchandiser"))),
            )
            machines = []
            for g in (3, 5, 7, 12, 14):
                col = f"Knitting M/C {g}GG"
                cnt = int(r[col]) if col in r and not pd.isna(r[col]) else 0
                if cnt:
                    machines.append(FactoryMachine(factory=fac, gauge=g, count=cnt))
            FactoryMachine.objects.bulk_create(machines)

    # ---- orders ----------------------------------------------------------
    def _orders(self, ob, users):
        depts = {n: Department.objects.get_or_create(name=n)[0] for n in ob["Department"].dropna().unique()}
        seasons = {}
        for code in ob["Season"].dropna().unique():
            code = str(code)
            seasons[code] = Season.objects.get_or_create(
                code=code, defaults={"kind": code[:2], "year": int(code[2:]) if code[2:].isdigit() else 0}
            )[0]
        styles: dict[str, Style] = {}
        facs = {f.code: f for f in Factory.objects.all()}
        pos = []
        for _, r in ob.iterrows():
            sno = _s(r["Style No"])
            if sno not in styles:
                styles[sno] = Style.objects.create(
                    style_no=sno, style_name=_s(r["Style Name"]), product_type=_s(r["Product Type"]),
                    department=depts[_s(r["Department"])], gauge=int(r["Gauge"]),
                    yarn_composition=_s(r["Yarn Composition"]),
                    yarn_short=_s(r["Yarn Composition"]).replace("100% ", "")[:40],
                    wash_required=_s(r["Wash Required"]).upper() == "Y",
                    weight_kg_pc=r["Weight kg/pc"], knitting_minutes_pc=r["Knitting Minutes/pc"],
                    linking_std_pcs_mc_day=int(r["Linking Std pcs/M/C/day"]),
                )
            pos.append(PurchaseOrder(
                po_no=_s(r["PO No"]), po_date=_d(r["PO Date"]), season=seasons[_s(r["Season"])],
                style=styles[sno], factory=facs[_s(r["Factory Code"])],
                merchandiser=users.get(_s(r.get("Merchandiser"))), order_qty=int(r["Order Qty"]),
                fob_usd_pc=r["FOB USD/pc"], fob_value_usd=r["FOB Value USD"],
                planned_exfactory=_d(r["Planned Ex-factory"]), planned_ship_mode=_s(r["Planned Ship Mode"]),
                port_of_loading=_s(r["Port of Loading"]), destination=_s(r["Destination"]),
                delivery_terms=_s(r["Delivery Terms"]), is_open=True,
            ))
        PurchaseOrder.objects.bulk_create(pos, batch_size=500)

    def _po_lines(self, lines):
        po_map = {p.po_no: p for p in PurchaseOrder.objects.all()}
        pl_objs, size_rows = [], []
        for _, r in lines.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            pl_objs.append(POLine(purchase_order=po, colour=_s(r["Colour"]),
                                  colour_code=_s(r["Colour Code"]), line_qty=int(r["Line Qty"])))
        POLine.objects.bulk_create(pl_objs, batch_size=500)
        pl_map = {(pl.purchase_order_id, pl.colour_code): pl for pl in POLine.objects.all()}
        for _, r in lines.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            pl = pl_map[(po.id, _s(r["Colour Code"]))]
            for s in SIZE_COLS:
                if s in r and not pd.isna(r[s]):
                    size_rows.append(POLineSize(po_line=pl, size=s, qty=int(r[s])))
        POLineSize.objects.bulk_create(size_rows, batch_size=1000)

    def _ta(self, ta):
        po_map = {p.po_no: p for p in PurchaseOrder.objects.select_related("factory").all()}
        rows = []
        for _, r in ta.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            rows.append(TAMilestone(
                purchase_order=po, factory=po.factory, seq=int(r["Seq"]), milestone=_s(r["Milestone"]),
                responsible=_s(r["Responsible"]), planned_date=_d(r["Planned Date"]),
                revised_date=_d(r.get("Revised Date")), actual_date=_d(r.get("Actual Date")),
                status=_s(r["Status"]), remarks=_s(r.get("Remarks")),
            ))
        TAMilestone.objects.bulk_create(rows, batch_size=1000)

    def _daily(self, dp):
        po_map = {p.po_no: p for p in PurchaseOrder.objects.select_related("factory").all()}
        rows = []
        for _, r in dp.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            rd = _d(r["Report Date"])
            for stage, (dcol, ccol, mc) in STAGE_COLS.items():
                if ccol not in r or pd.isna(r[ccol]):
                    continue
                day = r.get(dcol)
                machines = r.get(mc) if mc else None
                rows.append(DailyProduction(
                    purchase_order=po, factory=po.factory, report_date=rd, stage=stage,
                    day_pcs=0 if pd.isna(day) else int(day), cum_pcs=int(r[ccol]),
                    machines=None if (machines is None or pd.isna(machines)) else int(machines),
                    remarks=_s(r.get("Remarks")),
                ))
        DailyProduction.objects.bulk_create(rows, batch_size=1000)

    def _inspections(self, insp):
        po_map = {p.po_no: p for p in PurchaseOrder.objects.select_related("factory").all()}
        rows = []
        for _, r in insp.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            rows.append(Inspection(
                inspection_id=_s(r["Inspection ID"]), inspection_date=_d(r["Inspection Date"]),
                inspection_type=_s(r["Inspection Type"]), purchase_order=po, factory=po.factory,
                inspector=_s(r["Inspector"]), lot_qty=int(r["Lot Qty"]), aql_level=_s(r["AQL Level"]),
                sample_size=int(r["Sample Size"]), major_accept=int(r["Major Accept (Ac)"]),
                critical_found=int(r["Critical Found"]), major_found=int(r["Major Found"]),
                minor_found=int(r["Minor Found"]), result=_s(r["Result"]), main_defect=_s(r.get("Main Defect")),
                measurement_check=_s(r["Measurement Check"]),
                spec_weight_g=None if pd.isna(r.get("Spec Weight g")) else int(r["Spec Weight g"]),
                avg_weight_g=None if pd.isna(r.get("Avg Weight g")) else int(r["Avg Weight g"]),
                remarks=_s(r.get("Remarks")),
            ))
        Inspection.objects.bulk_create(rows, batch_size=1000)

    def _shipments(self, ship):
        po_map = {p.po_no: p for p in PurchaseOrder.objects.select_related("factory").all()}
        rows, shipped = [], []
        for _, r in ship.iterrows():
            po = po_map.get(_s(r["PO No"]))
            if not po:
                continue
            shipped.append(po.po_no)
            rows.append(Shipment(
                shipment_id=_s(r["Shipment ID"]), purchase_order=po, factory=po.factory,
                planned_exfactory=_d(r["Planned Ex-factory"]), actual_exfactory=_d(r["Actual Ex-factory"]),
                shipped_qty=int(r["Shipped Qty"]), cartons=int(r["Cartons"]),
                gross_weight_kg=r["Gross Weight kg"], ship_mode=_s(r["Ship Mode"]),
                port_of_loading=_s(r["Port of Loading"]), destination=_s(r["Destination"]),
                etd=_d(r.get("ETD")), eta=_d(r.get("ETA")), vessel_flight=_s(r.get("Vessel / Flight")),
                invoice_no=_s(r["Invoice No"]), invoice_value_usd=r["Invoice Value USD"],
                air_freight_cost_usd=None if pd.isna(r.get("Air Freight Cost USD")) else r["Air Freight Cost USD"],
                freight_borne_by=_s(r["Freight Cost Borne By"]), shipment_status=_s(r["Shipment Status"]),
                remarks=_s(r.get("Remarks")),
            ))
        Shipment.objects.bulk_create(rows, batch_size=500)
        PurchaseOrder.objects.filter(po_no__in=shipped).update(is_open=False)
