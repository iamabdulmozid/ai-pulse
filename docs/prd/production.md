# Karbar Pulse — Production / Daily Updates module PRD (`FR-PROD`)

**App:** `production` · **FR prefix:** `FR-PROD` · **Tier:** Must for 15 Oct
**Source of truth:** `sample_data/` + `00_Answer_Key.xlsx` for all numbers (PRD A-01); ingest rules and
column contracts in `data/excel-templates.md` and `sample_data/README.md`.

---

## 1. Purpose & design screen

Daily Updates is where merchandisers upload the Excel files the factories already send, and where the
office sees which factories have reported. Ingest is **asynchronous** (a django-q2 task), **atomic per
file** (a file with any error is rejected as a batch — no partial writes), and **idempotent** (re-sending
a day, or correcting an earlier day, upserts by key). Every successful ingest triggers a prediction run
(`FR-PRED-010`), so the dashboard refreshes with no manual step (success metric M3).

Design screen (from `design/Karbar Pulse Handoff.dc.html` → "Daily Updates"): one page
(`production/uploads.html`) with four regions — **drop zone**, **reporting status board**, **upload
history**, and **templates download**.

Context for acceptance criteria: as of 15 Oct 2026, **18 of 22** factories have reported the latest
expected day (14 Oct). The four missing are **SLM** (last reported 12 Oct), **OKH** (11 Oct), **HMR** and
**PBB** (both 13 Oct).

---

## 2. User stories

- **FR-PROD-010 — Upload drop zone.** As a **merchandiser**, I want to drag and drop one or more of the
  six factory file kinds and have them accepted as multipart uploads, so I can post the morning files
  quickly.
- **FR-PROD-020 — Async ingest + status poll.** As a **merchandiser**, I want each file to ingest in the
  background with a live status I can watch, so the page never blocks and I know when a file is done.
- **FR-PROD-030 — Validation result.** As a **merchandiser**, I want a clear per-file result — rows
  accepted, warnings, errors, and the detected factory and date — so I can see exactly what happened and
  fix a bad file.
- **FR-PROD-040 — Upsert rules.** As a **merchandiser**, I want re-sent days and corrections to earlier
  days to update cleanly by key, and genuinely bad rows (unknown PO, negative or non-monotonic figures) to
  be rejected, so the data stays trustworthy.
- **FR-PROD-050 — Reporting status board.** As a **manager**, I want to see which factories reported, which
  are late and which are missing, with 30-day compliance, so I can chase the quiet ones.
- **FR-PROD-060 — Upload history.** As a **merchandiser or manager**, I want a history of uploads (file,
  factory, who, when, rows, warnings, errors, status), so there is an audit trail.
- **FR-PROD-070 — Templates download.** As a **merchandiser**, I want blank templates for each file kind,
  so I can hand factories the exact column layout the system expects.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-PROD-010 Upload drop zone (six file kinds)
- **Given** the uploads page, **when** I drag files onto the drop zone or pick them, **then** each file
  POSTs to `/uploads/` as multipart and creates one `UploadBatch` per file.
- **Given** a workbook, **when** it is received, **then** the system detects its `kind` from the sheet
  structure — one of **`order_book`, `ta_calendar`, `daily_production`, `inspection`, `factory_master`,
  `shipment`** (the six kinds; see `data/excel-templates.md`) — plus `detected_factory` and
  `detected_date` where applicable.
- **Given** a file whose kind cannot be detected, **when** it is received, **then** the batch finishes with
  `status=error` and an error explaining the kind was not recognised; nothing is written.

### FR-PROD-020 Async ingest + HTMX status poll
- **Given** a created `UploadBatch`, **when** `upload_create` runs, **then** it enqueues the `ingest_file`
  django-q2 task and returns a batch card immediately with `status=queued`.
- **Given** a running batch, **when** the UI polls `/uploads/<batch_id>/status/` over HTMX, **then** the
  partial returns the live `status` (`queued` → `running` → `done`/`error`), `rows_accepted`, `warnings[]`,
  `errors[]`, `detected_factory`, `detected_date`; polling stops when `status` is `done` or `error`.
- **Given** a successful ingest, **when** the batch reaches `status=done`, **then** a prediction run is
  triggered (`FR-PRED-010`) so pages refresh from the new snapshot.

### FR-PROD-030 Validation result — the two demo files exactly
- **Given** **`DPR_PBB_2026-10-14.xlsx`** (clean, 3 rows), **when** it ingests, **then** `status=done`,
  `rows_accepted = 3`, `errors = []`, `detected_factory = PBB`, `detected_date = 2026-10-14`; the reporting
  board moves **"reported today" from 18 to 19 of 22**, and **no headline KPI changes** (open POs 412, open
  pcs 1,900,020, open FOB USD 18,601,449, value at risk USD 2,400,006, air exposure USD 539,720 all
  unchanged).
- **Given** **`DPR_HMR_2026-10-14_with_errors.xlsx`** (8 rows), **when** it ingests, **then** `status=error`,
  `rows_accepted = 0` (no partial writes), and `errors[]` reports exactly **three** problems:
  1. **unknown PO `71999999`** (no matching `PurchaseOrder`),
  2. a **negative Linking Day** value, and
  3. a **Knitting Cum that goes down** (violates monotonic cumulative per PO×stage).
- **Given** the rejected HMR batch, **when** it finishes, **then** HMR remains **missing** on the reporting
  board (still "last reported 13 Oct"), the headline KPIs are unchanged, and no prediction run is triggered.

### FR-PROD-040 Upsert rules
- **Given** a `daily_production` row, **when** it is ingested, **then** it is upserted on the key
  **(`purchase_order`, `stage`, `report_date`)**; re-sending the same day overwrites in place (no
  duplicate rows), and a correction to an earlier day updates that day's row.
- **Given** `inspection` / `shipment` rows, **when** ingested, **then** they upsert on their natural keys
  (`inspection_id`, `shipment_id`); a `shipment` row sets its PO `is_open=False`.
- **Given** a row referencing an **unknown PO or factory**, **when** validated, **then** it is an **error**
  and the whole batch is rejected (no partial writes).
- **Given** a `daily_production` row whose `cum_pcs` for a (PO, stage) is **less than the last known
  cumulative** (non-monotonic), **when** validated, **then** it is an **error** (the HMR "Knitting Cum goes
  down" case).
- **Given** a negative `day_pcs` / machine count, **when** validated, **then** it is an **error** (the HMR
  "negative Linking Day" case).
- **Given** both daily and cumulative figures in one row, **when** stored, **then** both `day_pcs` and
  `cum_pcs` are kept (the engine's rate window uses `day_pcs`; cum is validated for monotonicity). Detailed
  column rules: `data/excel-templates.md`.

### FR-PROD-050 Reporting status board
- **Given** `/uploads/reporting/`, **when** it renders, **then** each of the 22 factories shows
  `status` (**reported / late / missing**), `received_at`, `compliance_30d`, and open POs.
- **Given** the seed state, **when** the board renders, **then** **18 of 22** show reported; **SLM, OKH,
  HMR, PBB** show missing/late with their last report dates (SLM 12 Oct, OKH 11 Oct, HMR 13 Oct, PBB
  13 Oct).
- **Given** a successful PBB upload (`FR-PROD-030`), **when** the board re-renders, **then** PBB flips to
  reported and the count reads **19 of 22**.

### FR-PROD-060 Upload history
- **Given** the uploads page, **when** the history renders, **then** each `UploadBatch` row shows
  `original_filename`, `detected_factory`, `uploaded_by`, `uploaded_at`, `rows_accepted`, warning count,
  error count and `status`, newest first.
- **Given** the rejected HMR batch, **when** it appears in history, **then** it shows `status=error`,
  `rows_accepted = 0`, error count 3.

### FR-PROD-070 Templates download
- **Given** `/uploads/templates/`, **when** it renders, **then** it offers a downloadable blank template
  for each of the six file kinds, matching the column contract in `data/excel-templates.md` (each workbook
  carries its **Columns** sheet).

---

## 4. Design components

- **Drop zone:** drag-and-drop area accepting multiple files; on drop, one batch Card per file appears with
  a status chip (queued / running / done / error), progress and the detected factory/date.
- **Batch status:** HTMX-polled partial (`batch_status.html`); accepted-rows count, collapsible
  warnings[] and errors[] lists (each `{row, message}`), Toast on completion.
- **Reporting board:** table of 22 factories with reported/late/missing Badge, received-at time,
  compliance-30d value, open POs; "No update" stripe matches the Overview heatmap and header pill.
- **History:** TanStack-style Table of `UploadBatch` rows.
- **Templates:** list of download links (`{name, version, url}`) per kind.
- Freshness (`as_of`, `reports_today {received, expected}`) is shared with the header pill and every other
  screen.

---

## 5. Data read / written (models/fields) + URLs/partials

| URL | Method | View | Template / Partial | Access | FR |
|---|---|---|---|---|---|
| `/uploads/` | GET | `uploads_home` | `production/uploads.html` | read: all | 010/050/060/070 |
| `/uploads/` | POST | `upload_create` | `partials/production/batch_card.html` | write: Merch/Mgmt/Admin | 010/020 |
| `/uploads/<batch_id>/status/` | GET | `batch_status_partial` | `partials/production/batch_status.html` | batch owner (write role) | 020/030 |
| `/uploads/reporting/` | GET | `reporting_status_partial` | `partials/production/reporting.html` | read: all | 050 |
| `/uploads/templates/` | GET | `templates_list` | `partials/production/templates.html` | read: all | 070 |

Models:
- **`UploadBatch`** (written): `kind`, `original_filename`, `uploaded_by`, `uploaded_at`,
  `detected_factory`, `detected_date`, `status`, `rows_accepted`, `warnings` (JSON `[{row, message}]`),
  `errors` (JSON), `finished_at`. Polled by the UI (PK is a UUID).
- **Target models** (written on success, with `upload_batch` provenance): `DailyProduction`
  (unique `(purchase_order, stage, report_date)`), `Inspection` (unique `inspection_id`), `Shipment`
  (unique `shipment_id`; sets PO `is_open`), plus `order_book`→`PurchaseOrder`/`POLine`/`POLineSize`,
  `ta_calendar`→`TAMilestone`, `factory_master`→`Factory`/`FactoryMachine`.
- **`FactoryStat`** (read by the reporting board): `reported_today`, `last_report_date`, `missed_wd`,
  `open_pos`; `compliance_30d` derived from reporting history.
- **`PredictionRun`** (written indirectly): a successful ingest creates a run with `trigger='upload'`,
  `upload_batch` set (`FR-PRED-010`).

Cross-references: successful ingest → `FR-PRED-010` (run after upload); reporting state is the same data
surfaced on the Factories scorecards (`FR-FAC-010`) and the Overview heatmap (`FR-DASH`); upsert keys and
monotonic-cum rule feed the engine's rate window (`FR-PRED-040`, engine §2).

---

## 6. Empty / error / stale-data states

- **No uploads yet:** history shows "No uploads"; reporting board still renders from the latest run
  (`FactoryStat`), or shows "No run yet" if none exists.
- **File with errors (HMR case):** whole batch rejected, `rows_accepted=0`, `status=error`, `errors[]`
  lists each problem with its row; nothing written; no prediction run; a Toast flags the failure.
- **Wrong / unrecognised file kind:** `status=error` with a "kind not recognised" message; no writes.
- **Unknown PO / factory in a row:** batch rejected with a row-level error naming the unknown key.
- **Duplicate / corrected day:** not an error — upserts in place (`FR-PROD-040`); a warning may note the
  overwrite.
- **Late report (factory missing):** the reporting board shows missing/late with the last report date; the
  figure is never silently treated as current (metric M4).
- **Task backend down (django-q2):** batch stays `queued`; the poll shows "queued" with a hint that the
  worker is not processing; no data is lost.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| View uploads page, reporting board, history, templates | ✓ | ✓ | ✓ | ✓ |
| Upload daily files (`FR-PROD-010/020`) | ✓ | ✓ | ✓ | – |
| Poll a batch status (`FR-PROD-030`) | ✓ | ✓ | own batches | – |
| Download templates (`FR-PROD-070`) | ✓ | ✓ | ✓ | ✓ |

QA is read-only here (no upload, per the role matrix in `tech/urls-and-views.md`). Write scope is enforced
in views/services, not only templates (`tech/security.md`, PRD A-05).
