# Karbar Pulse — Excel upload templates and ingest

**Status:** v1 · **As of:** 15 Oct 2026 (factories report the previous working day, so the latest
expected report is 14 Oct 2026; Friday is the weekend).

Karbar factories already send daily Excel files; Pulse ingests those files unchanged. This document is
the contract for the six upload files: the columns each carries, the validation every row must pass, and
how the ingest writes them into the models in [`data-model.md`](data-model.md). Column dictionaries are
taken verbatim from each workbook's **Columns** sheet (`sample_data/*.xlsx`); the reference files in
`sample_data/` are a conforming example of every template below.

Conventions used in the tables:

- **Type** is the Excel cell type the factory supplies (`Text`, `Integer`, `Decimal`, `Date`, `Y/N`).
- **Required** `Yes` means the cell must be non-blank on every data row; `No` means it may be blank.
- Dates are read as Excel dates and stored UTC (displayed Asia/Dhaka). Money is stored as `Decimal`.
- Every file carries a **Columns** sheet as self-documentation; the ingest reads the data sheet(s) only.

---

## How a file is detected

The ingest does not trust the filename. On upload it opens the workbook and classifies it by the data
**sheet names and their header row**:

| Detected `kind` | Recognised by | `detected_factory` | `detected_date` |
|---|---|---|---|
| `order_book` | sheets `PO Header` + `PO Lines` | null (many factories) | null |
| `ta_calendar` | sheet `T&A Calendar` | null (many factories) | null |
| `daily_production` | sheet `Daily Production` | the single `Factory Code` in the file | the single `Report Date` in the file |
| `inspection` | sheet `Inspections` | null (may span factories) | max `Inspection Date` |
| `factory_master` | sheet `Factories` | null | null |
| `shipment` | sheet `Shipments` | null (may span factories) | max `Actual Ex-factory` |

- A **Daily Production** file is expected to be one factory for one report date (the real daily report).
  If it contains more than one `Factory Code` **or** more than one `Report Date`, that is a row error and
  the batch is rejected (see **Ingest rules**). `detected_factory` / `detected_date` populate the
  `UploadBatch` so the Daily Updates screen can show "Factory X reported for 14 Oct".
- If no sheet matches a known kind, the whole file is rejected with a single batch-level error.

---

## 1. Order Book — `01_Order_Book.xlsx`

Two sheets: **PO Header** (one row per PO) and **PO Lines** (one row per PO × colour, sizes in columns).
This is the master list of every PO, open and shipped. A PO is **open** when it has no row in the
Shipment Log.

### Sheet: PO Header → `orders.PurchaseOrder` (+ `Style`, `Season`, `Department`)

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| PO No | Text | Yes | Unique across the sheet; the natural key. | 71004521 |
| PO Date | Date | Yes | Valid date; ≤ Planned Ex-factory. | 12-Jun-2026 |
| Season | Text | Yes | `AW`/`HO`/`SS`/`SU` + 2-digit year. | AW26 |
| Department | Text | Yes | Enum `Men` / `Women` / `Kids`. | Women |
| Style No | Text | Yes | Karbar style number. | KAW26-W-1184 |
| Style Name | Text | Yes | Style description. | Lambswool V-neck Cardigan |
| Product Type | Text | Yes | Garment type. | V-neck Cardigan |
| Gauge | Integer | Yes | Enum `3`/`5`/`7`/`12`/`14`; must be a gauge the factory knits (Factory Master `Gauges`). | 7 |
| Yarn Composition | Text | Yes | Fibre content. | 100% Lambswool |
| Wash Required | Y/N | Yes | `Y` or `N`; `Y` means a washing stage exists. | Y |
| Weight kg/pc | Decimal | Yes | > 0; packed weight for freight. | 0.72 |
| Knitting Minutes/pc | Decimal | Yes | > 0; standard knit time, one piece, one machine. | 50.4 |
| Linking Std pcs/M/C/day | Integer | Yes | > 0; standard linking output per machine per 10-h day. | 32 |
| Factory Code | Text | Yes | **Must exist in Factory Master.** | GRL |
| Factory Name | No | No | Readability only; Factory Master is the source. | Greyloom Knitwear Ltd. |
| Order Qty | Integer | Yes | > 0; **= Σ of this PO's PO Lines `Line Qty`.** | 9600 |
| FOB USD/pc | Decimal | Yes | > 0. | 16.50 |
| FOB Value USD | Decimal | Yes | **= Order Qty × FOB USD/pc** (tolerance ±0.02). | 158400.00 |
| Planned Ex-factory | Date | Yes | Valid date; the on-time target. | 29-Oct-2026 |
| Planned Ship Mode | Text | Yes | Enum `Sea` / `Air` / `Sea-Air`. | Sea |
| Port of Loading | Text | Yes | e.g. `Chattogram`. | Chattogram |
| Destination | Text | Yes | Karbar DC. | Hamburg, Germany |
| Delivery Terms | Text | Yes | Incoterm. | FOB Chattogram |
| Merchandiser | Text | Yes | Karbar PO owner (matched to a `User`). | Farhana Rahman |

### Sheet: PO Lines → `orders.POLine` (+ `POLineSize`)

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| PO No | Text | Yes | **Must exist in PO Header** (same file). | 71004521 |
| Colour | Text | Yes | Colour name. | Navy |
| Colour Code | Text | Yes | Unique within the PO; `(PO No, Colour Code)` is the line key. | NAV-410 |
| XS, S, M, L, XL, XXL, 2-3Y, 4-5Y, 6-7Y, 8-9Y, 10-11Y | Integer | No | ≥ 0; blank when the size is not in range. Each non-blank size → one `POLineSize` row. | 120 |
| Line Qty | Integer | Yes | **= Σ of the 11 size columns** (blanks count as 0). | 3200 |

**Referential / cross-row rules**

- Every `Factory Code` in PO Header exists in Factory Master.
- Every `Gauge` is one the factory knits.
- For each PO: `Order Qty = Σ Line Qty` over its PO Lines, and each line's `Line Qty = Σ sizes`.
- `FOB Value USD = Order Qty × FOB USD/pc`.

**Ingest rules**

- **Upsert keys:** PO Header on **`PO No`**; PO Lines on **`(PO No, Colour Code)`**; sizes on
  `(PO line, size)`.
- Re-uploading the Order Book upserts headers and lines by key; lines or sizes absent from the new file
  for a re-uploaded PO are removed so the PO matches the file exactly.
- `Style`, `Season`, `Department` are get-or-created from the header's columns.
- `is_open` is set from the Shipment Log state: a PO with no `Shipment` row is open. Loading the Order
  Book does not by itself close a PO.
- An unknown `Factory Code`, a `PO No` in PO Lines with no header, or any broken cross-row rule is a
  **row error → the whole batch is rejected** (no partial writes).

---

## 2. T&A Calendar — `02_TA_Calendar.xlsx`

One sheet, **11 milestones per PO** (the standard sweater template, ASSUMPTION A-10).

### Sheet: T&A Calendar → `orders.TAMilestone`

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| PO No | Text | Yes | **Must exist in Order Book.** | 71004521 |
| Factory Code | Text | Yes | **Must exist in Factory Master**; should equal the PO's factory. | GRL |
| Seq | Integer | Yes | `1`–`11`; unique within the PO. | 6 |
| Milestone | Text | Yes | One of the 11 template names (below), matching `Seq`. | Yarn in-house |
| Responsible | Text | Yes | Who must complete it. | Factory / Yarn supplier |
| Planned Date | Date | Yes | From the template (days before ex-factory). | 14-Sep-2026 |
| Revised Date | Date | No | New committed date when a delay is flagged. | 20-Oct-2026 |
| Actual Date | Date | No | Blank while pending. | 22-Sep-2026 |
| Status | Text | Yes | Enum `Done` / `Done late` / `Pending` / `Overdue`. | Done late |
| Remarks | Text | No | Delay reason. | Dyed yarn delayed at spinner |

The 11 milestone names and their template offset (days before ex-factory): Yarn booking (95),
Yarn shade approval (85), Fit sample approval (80), Size set approval (60), PP sample approval (50),
Yarn in-house (45), PP meeting (42), Knitting start (40), Linking start (34), Final inspection (1),
Ex-factory (0).

**Validation rules**

- Exactly 11 rows per PO, `Seq` 1–11 with the matching milestone name.
- `Status` must agree with the dates: with an `Actual Date`, `Done late` if actual > planned else `Done`;
  with no actual, `Overdue` if planned < today else `Pending`.
- When both are present, `Actual Date` ≥ `Planned Date` is not required (a milestone can land early), but
  `Revised Date`, if present, is the committed replacement date and is what the engine reads before the
  planned date.

**Ingest rules**

- **Upsert key: `(PO No, Seq)`** → `TAMilestone`. A re-upload overwrites that milestone row in place.
- `factory` is denormalised from `Factory Code`.
- Unknown `PO No` or `Factory Code`, or a `Seq` outside 1–11, is a row error → batch rejected.

---

## 3. Factory Daily Production Report — `03_Factory_Daily_Production_Report.xlsx`

One sheet. One **wide** row per PO per working day, carrying day and cumulative figures for all six
stages. On ingest the wide row is **pivoted to long form**: one `DailyProduction` row per stage that is
present (ASSUMPTION A-10). This is the file the live upload demo uses.

### Sheet: Daily Production → `production.DailyProduction` (one row per present stage)

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| Report Date | Date | Yes | Not a Friday; one date per file. | 14-Oct-2026 |
| Factory Code | Text | Yes | **Must exist in Factory Master**; one factory per file. | GRL |
| Factory Name | Text | No | Readability. | Greyloom Knitwear Ltd. |
| PO No | Text | Yes | **Must exist in Order Book**; its factory must equal `Factory Code`. | 71004521 |
| Style No | Text | No | Readability. | KAW26-W-1184 |
| Order Qty | Integer | No | Readability; Order Book is the source. | 9600 |
| Knitting Day | Integer | Yes | ≥ 0; = change in Knitting Cum since the PO's previous report. | 520 |
| Knitting Cum | Integer | Yes | Monotonic non-decreasing per PO; ≤ Order Qty. | 8900 |
| Knitting M/C | Integer | No | ≥ 0; machines on the PO that day. | 26 |
| Linking Day | Integer | Yes | ≥ 0. | 415 |
| Linking Cum | Integer | Yes | Monotonic; **≤ Knitting Cum**. | 2800 |
| Linking M/C | Integer | No | ≥ 0. | 13 |
| Trimming & Mending Day | Integer | Yes | ≥ 0. | 430 |
| Trimming & Mending Cum | Integer | Yes | Monotonic; ≤ Linking Cum. | 2700 |
| Washing Day | Integer | No | **Blank unless the style's Wash Required = Y**; else ≥ 0. | 420 |
| Washing Cum | Integer | No | Blank unless Wash Required = Y; monotonic; ≤ Trimming & Mending Cum. | 2600 |
| Ironing Day | Integer | Yes | ≥ 0. | 410 |
| Ironing Cum | Integer | Yes | Monotonic; ≤ upstream cum (washing if washed, else trimming & mending). | 2450 |
| Packing Day | Integer | Yes | ≥ 0. | 400 |
| Packing Cum | Integer | Yes | Monotonic; ≤ Ironing Cum; ready to ship when = Order Qty. | 2250 |
| Remarks | Text | No | Factory comment. | Need 6 more linking M/C |

**Validation rules (per PO across its report history)**

- All six (or five, when unwashed) `*_Day` ≥ 0; no negatives.
- Every `*_Cum` is **monotonic non-decreasing** over successive report dates and ≤ Order Qty.
- `*_Day = (today's Cum − previous report's Cum)` for that stage.
- Stage flow: `Packing ≤ Ironing ≤ Washing* ≤ Trimming & Mending ≤ Linking ≤ Knitting` cumulative.
  In particular **Linking Cum ≤ Knitting Cum** (a stage can never be ahead of its upstream stage).
- **Washing columns are blank unless `Wash Required = Y`** for the PO's style; blank washing columns
  cause the flow check to skip to the next upstream stage (ironing follows trimming & mending).
- One `Factory Code` and one `Report Date` for the whole file; no Friday report dates.

**Cumulative vs daily figures**

Both are stored on each `DailyProduction` row (`day_pcs`, `cum_pcs`). The prediction engine uses the
**day** figures for stage rates (the last 7 working days, weighted) and the **cum** figures for remaining
work (`Order Qty − cum`). Keeping both means a single corrected report fixes both views.

**Ingest rules**

- **Upsert key: `(PO No, stage, Report Date)`** → `DailyProduction`. The wide row explodes into one row
  per stage that has data; `machines` is carried for knitting and linking only.
- **Corrections to an earlier day:** re-uploading a file for a date that was already ingested
  **re-upserts and overwrites** those `(PO, stage, date)` rows — the latest upload for a date wins. There
  is no duplication; the key makes it idempotent.
- **Duplicates within one file** (the same PO twice for the same date) are a row error → batch rejected.
- Unknown PO, PO whose factory ≠ `Factory Code`, negative day, decreasing cum, Linking Cum > Knitting
  Cum, or washing data on an unwashed style are each row errors → **whole batch rejected**.

---

## 4. Inspection Log — `04_Inspection_Log.xlsx`

One sheet; inline, pre-final, final and re-inspections at AQL II / 2.5 / 4.0.

### Sheet: Inspections → `production.Inspection`

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| Inspection ID | Text | Yes | Unique; the key. | QA-2610-01234 |
| Inspection Date | Date | Yes | Valid date. | 12-Oct-2026 |
| Inspection Type | Text | Yes | Enum `Inline` / `Pre-final` / `Final` / `Final re-inspection`. | Inline |
| PO No | Text | Yes | **Must exist in Order Book.** | 71004521 |
| Factory Code | Text | Yes | **Must exist in Factory Master.** | GRL |
| Inspector | Text | Yes | Karbar QA inspector. | Lipi Das |
| Lot Qty | Integer | Yes | > 0; pieces offered. | 9600 |
| AQL Level | Text | Yes | e.g. `II / 2.5 / 4.0`. | II / 2.5 / 4.0 |
| Sample Size | Integer | Yes | > 0; ANSI Z1.4 for the lot. | 200 |
| Major Accept (Ac) | Integer | Yes | ≥ 0; max majors to pass. | 10 |
| Critical Found | Integer | Yes | ≥ 0; any critical fails the lot. | 0 |
| Major Found | Integer | Yes | ≥ 0. | 6 |
| Minor Found | Integer | Yes | ≥ 0. | 9 |
| Result | Text | Yes | Enum `Pass` / `Fail`; must agree with Ac: `Pass` iff `Major Found ≤ Ac` (and no critical). | Pass |
| Main Defect | Text | No | Most frequent defect. | Dropped stitch |
| Measurement Check | Text | Yes | Enum `Pass` / `Fail`. | Pass |
| Spec Weight g | Integer | No | Target weight. | 680 |
| Avg Weight g | Integer | No | Measured. | 684 |
| Remarks | Text | No | Inspector comment. | |

**Ingest rules**

- **Upsert key: `Inspection ID`** → `Inspection`.
- A re-upload with the same `Inspection ID` overwrites that inspection; a new ID adds a row. The engine's
  quality score reads the **latest** inspection per PO (by date) and the factory's 90-day pass rate.
- Unknown PO or factory, or a `Result` that disagrees with the accept number, is a row error → batch
  rejected.

---

## 5. Factory Master — `05_Factory_Master.xlsx`

One sheet, one row per factory (22 in the demo). This is the referential anchor: `Factory Code` here is
the natural key every other file points to.

### Sheet: Factories → `masterdata.Factory` (+ `FactoryMachine`)

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| Factory Code | Text | Yes | Unique; the key. | GRL |
| Factory Name | Text | Yes | Legal name. | Greyloom Knitwear Ltd. |
| Area | Text | Yes | Industrial area. | Konabari |
| District | Text | Yes | District. | Gazipur |
| Address | Text | No | Postal address. | Plot 14, Konabari, Gazipur |
| Supplier Since | Date | No | First Karbar order. | 01-Mar-2018 |
| Gauges | Text | Yes | Gauges knitted, e.g. `5GG, 7GG, 12GG`. | 5GG, 7GG, 12GG |
| Knitting M/C 3GG / 5GG / 7GG / 12GG / 14GG | Integer | Yes | ≥ 0; machines by gauge. Each > 0 → one `FactoryMachine` row. | 60 |
| Total Knitting M/C | Integer | Yes | **= Σ of the five gauge columns.** | 330 |
| Linking M/C | Integer | Yes | ≥ 0. | 160 |
| Washing | Text | Yes | Enum `In-house` / `Subcontract`. | In-house |
| Knitting Shifts | Integer | Yes | > 0. | 2 |
| Knitting Hours/Day | Integer | Yes | > 0. | 20 |
| Linking Hours/Day | Integer | Yes | > 0. | 10 |
| Workforce | Integer | No | ≥ 0. | 2400 |
| Certifications | Text | No | e.g. `amfori BSCI, WRAP`. | amfori BSCI, WRAP |
| amfori BSCI Rating | Text | No | `A`–`E`. | B |
| Last Social Audit | Date | No | Latest social audit. | 14-May-2026 |
| Factory Contact | Text | No | Main contact. | Nazmul Haque |
| Contact Title | Text | No | | GM - Merchandising |
| Karbar Merchandiser | Text | Yes | Karbar owner of the relationship. | Farhana Rahman |
| Status | Text | Yes | Enum `Active` / `Inactive`. | Active |

**Ingest rules**

- **Upsert key: `Factory Code`** → `Factory`. The five gauge columns upsert `FactoryMachine`
  `(factory, gauge)` rows; a gauge with 0 machines has no row.
- Load this file **first** when bootstrapping, since every other file references `Factory Code`.
- `Total Knitting M/C ≠ Σ gauge columns`, or a non-enum `Washing` / `Status`, is a row error → batch
  rejected.

---

## 6. Shipment Log — `06_Shipment_Log.xlsx`

One sheet, one row per shipped PO. **A shipment row closes its PO** (`is_open = False`).

### Sheet: Shipments → `production.Shipment`

| Column | Type | Required | Validation | Example |
|---|---|---|---|---|
| Shipment ID | Text | Yes | Unique; the key. | SH-2610-0412 |
| PO No | Text | Yes | **Must exist in Order Book**; one shipment per PO. | 71004521 |
| Factory Code | Text | Yes | **Must exist in Factory Master.** | GRL |
| Planned Ex-factory | Date | Yes | From the Order Book, repeated for audit. | 29-Oct-2026 |
| Actual Ex-factory | Date | Yes | On time iff ≤ Planned Ex-factory. | 29-Oct-2026 |
| Shipped Qty | Integer | Yes | > 0. | 9600 |
| Cartons | Integer | Yes | > 0. | 534 |
| Gross Weight kg | Decimal | Yes | > 0. | 7552.8 |
| Ship Mode | Text | Yes | Enum `Sea` / `Air` / `Sea-Air`. | Sea |
| Port of Loading | Text | Yes | `Chattogram` or `Dhaka (HSIA)`. | Chattogram |
| Destination | Text | Yes | Karbar DC. | Hamburg, Germany |
| ETD | Date | Yes | Estimated departure. | 03-Nov-2026 |
| ETA | Date | Yes | Estimated arrival; ≥ ETD. | 07-Dec-2026 |
| Vessel / Flight | Text | No | Vessel/voyage or AWB. | MV Coral Horizon V.2611E |
| Invoice No | Text | Yes | Commercial invoice. | KB-INV-2610-4412 |
| Invoice Value USD | Decimal | Yes | Shipped Qty × FOB. | 158400.00 |
| Air Freight Cost USD | Decimal | No | **Set only when Ship Mode = Air**; blank otherwise. | 45316.80 |
| Freight Cost Borne By | Text | Yes | Enum `Karbar` / `Factory`. | Factory |
| Shipment Status | Text | Yes | Enum `At port` / `In transit` / `Delivered`. | In transit |
| Remarks | Text | No | | Shipped 6 days late - air freight at factory cost |

**Ingest rules**

- **Upsert key: `Shipment ID`** → `Shipment`. On write, the PO's `is_open` is set to `False`.
- One shipment per PO; a second shipment row for an already-shipped PO (different `Shipment ID`, same
  `PO No`) is a row error → batch rejected.
- `Air Freight Cost USD` present on a non-Air mode, or unknown PO/factory, is a row error → batch
  rejected.

---

## Ingest execution model

The upload flow (`FR-PROD`, `production` app) is the same for all six files.

1. **Upload.** A merchandiser drag-drops a file. Pulse creates an `UploadBatch` (`status = queued`,
   `original_filename`, `uploaded_by`), detects the `kind`, `detected_factory`, `detected_date`, and
   enqueues a **django-q2** task.
2. **Validate, then write — all or nothing.** The task (`status = running`) parses every row, resolves
   referential keys (Factory Code → Factory, PO No → PurchaseOrder), and runs the per-file validations
   above **inside one database transaction**. If **any** row has an error, nothing is written: the
   transaction rolls back, `status = error`, and `errors` holds `[{row, message}]` for every bad row.
   On success all rows are upserted by their keys, `status = done`, `rows_accepted` is set, and `warnings`
   holds any non-fatal notes.
3. **Poll.** The Daily Updates screen polls the `UploadBatch` by UUID over **HTMX** and renders the
   per-row result (accepted count, or the error list) when the task finishes.
4. **Re-run predictions.** A successful ingest triggers a `PredictionRun` (trigger `upload`, linked to the
   batch); pages read the refreshed snapshot. A rejected batch triggers nothing.

**Key principles**

- **A file with any error is rejected as a whole — no partial writes.** This keeps the order book and the
  production history internally consistent and makes a correction a simple re-upload.
- **Idempotent upserts.** Re-uploading the same or a corrected file overwrites rows by their upsert key;
  it never duplicates. Corrections to an earlier day re-upsert that day's rows.
- **Unknown POs / factories reject the batch.** A row that references a `PO No` not in the Order Book or a
  `Factory Code` not in Factory Master is a row error, so Factory Master and the Order Book must be loaded
  before the files that point to them.

---

## Demo upload files and their expected outcomes

Two ready-made Daily Production files in `sample_data/demo_uploads/` drive the live upload demo. Both are
for **14 Oct 2026**, the reports that were missing as of 15 Oct for factories PBB and HMR. Before upload,
**18 of 22** factories have reported for 14 Oct (missing: SLM last 12 Oct, OKH 11 Oct, HMR 13 Oct,
PBB 13 Oct).

### `DPR_PBB_2026-10-14.xlsx` — clean, accepted

- Pebblebrook Knit Ltd. (PBB), **3 rows**, Report Date 14-Oct-2026, all validations pass.
- **Outcome:** batch `done`, 3 rows accepted, PBB's `last_report_date` becomes 14 Oct. "Reported today"
  moves from **18 to 19 of 22**. PBB carries no at-risk POs in the demo, so **no headline KPI changes**
  (open counts, value at risk, air exposure, band counts, hero are all unchanged). A `PredictionRun`
  fires; the numbers are identical, demonstrating a clean refresh.

### `DPR_HMR_2026-10-14_with_errors.xlsx` — rejected

- Highmoor Sweaters Ltd. (HMR), **8 rows**, Report Date 14-Oct-2026, with **three deliberate errors**:
  1. **Unknown PO `71999999`** on row 1 — the `PO No` is not in the Order Book (referential error).
  2. **Negative Linking Day** (−40) on row 2 — a day figure below zero.
  3. **Knitting Cum decreases** on row 3 — cumulative drops ~500 below the PO's previous report
     (monotonic-cum violation).
- **Outcome:** batch `error`, **0 rows written**, `errors` lists the three offending rows with messages
  ("PO 71999999 not found in Order Book", "Linking Day must be ≥ 0", "Knitting Cum must not decrease").
  HMR stays missing for 14 Oct; "reported today" stays at 19 of 22; no prediction run. The Daily Updates
  screen shows the per-row error panel. Correcting the file and re-uploading accepts all 8 rows.
