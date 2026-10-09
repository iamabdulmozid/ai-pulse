# AI Pulse — Data model

**As of:** v1 · Django 5.2 / PostgreSQL 16 (psycopg 3). Field types are Django model fields.
Source columns in parentheses refer to `sample_data/*.xlsx` (see `data/excel-templates.md`).

Conventions:
- Money is `DecimalField(max_digits=14, decimal_places=2)`; per-piece money `decimal_places=2`.
- Rates/weights are `DecimalField` (never float) so the engine is reproducible; see `ai/prediction-engine.md`.
- Every ingested row carries `upload_batch` (provenance) and the models that feed numbers expose an
  `as_of` via their batch or snapshot. All times are stored UTC, displayed Asia/Dhaka.
- Users and roles use `django.contrib.auth` (`User` + `Group`); no custom user model in Phase 0.

Business logic does **not** live on models beyond trivial derived properties; the engine and queries
live in `services/` (`tech/architecture.md`).

---

## App: `masterdata`

### `Department`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `name` | CharField(16), unique | `Men` / `Women` / `Kids` (Dept column) |

### `Season`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `code` | CharField(8), unique | `AW26`, `HO26`, `SS27`, `SU27` (Season column) |
| `kind` | CharField(2) | AW/HO/SS/SU |
| `year` | SmallIntegerField | 2-digit year stored as int |

### `Factory`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `code` | CharField(8), unique, indexed | `GRL` (Factory Code) — the natural key used in every upload file |
| `name` | CharField(120) | `Greyloom Knitwear Ltd.` |
| `area` | CharField(80) | `Konabari` |
| `district` | CharField(40) | `Gazipur` |
| `address` | CharField(200), blank | |
| `supplier_since` | DateField, null | |
| `gauges` | CharField(40) | `5GG, 7GG, 12GG` (denormalised; machines in `FactoryMachine`) |
| `linking_machines` | PositiveIntegerField | total linking M/C |
| `washing` | CharField(12) | `In-house` / `Subcontract` |
| `knitting_shifts` | PositiveSmallIntegerField | |
| `knitting_hours_day` | PositiveSmallIntegerField | machine hours/day |
| `linking_hours_day` | PositiveSmallIntegerField | |
| `workforce` | PositiveIntegerField, null | |
| `certifications` | CharField(200), blank | `amfori BSCI, WRAP` |
| `bsci_rating` | CharField(2), blank | A–E |
| `last_social_audit` | DateField, null | |
| `contact_name` | CharField(80), blank | |
| `contact_title` | CharField(80), blank | |
| `merchandiser` | FK→`auth.User`, null | Karbar owner of the relationship (Karbar Merchandiser) |
| `status` | CharField(10) | `Active` / `Inactive` |

Indexes: `code`. 

### `FactoryMachine`
Knitting machines by gauge (one row per factory × gauge).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `factory` | FK→`Factory` | |
| `gauge` | PositiveSmallIntegerField | 3/5/7/12/14 |
| `count` | PositiveIntegerField | machines of that gauge (Knitting M/C <g>GG) |

Constraint: `unique_together(factory, gauge)`.

### `HolidayCalendar`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `date` | DateField, unique, indexed | Bangladesh public holiday (non-working) |
| `name` | CharField(80) | |

> The weekend (Friday) is a rule, not rows. The seed uses a Friday-only weekend; holidays are loaded here
> separately and consumed by the engine's working-day calendar.

### `EngineParameter`
Admin-editable weights/thresholds; the engine reads a typed snapshot of these (one active set).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `key` | CharField(60), unique | e.g. `air_usd_per_kg`, `sea_usd_per_kg`, `rate_window_wd`, `flow_limit_days`, `yarn_to_knit_days`, `knit_mc_minutes_per_day`, `stage_lag_linking`, score weights/caps, band cut-offs, freshness thresholds |
| `value` | DecimalField(12,4) | |
| `description` | CharField(200) | |
| `updated_by` / `updated_at` | audit | |

Default values are the answer-key `Parameters` sheet (see `ai/prediction-engine.md §8`).

---

## App: `orders`

### `Style`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `style_no` | CharField(24), unique, indexed | `KAW26-W-1736` |
| `style_name` | CharField(120) | `Lambswool V-neck Cardigan` |
| `product_type` | CharField(60) | `V-neck Cardigan` |
| `department` | FK→`Department` | |
| `gauge` | PositiveSmallIntegerField | 3/5/7/12/14 |
| `yarn_composition` | CharField(80) | `100% Lambswool` |
| `yarn_short` | CharField(40) | `Lambswool` (derived) |
| `wash_required` | BooleanField | drives whether washing stage exists |
| `weight_kg_pc` | DecimalField(5,3) | packed weight/pc (freight) |
| `knitting_minutes_pc` | DecimalField(6,2) | standard knit time/pc on one machine |
| `linking_std_pcs_mc_day` | PositiveIntegerField | standard linking output per M/C per 10-h day |

### `PurchaseOrder`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `po_no` | CharField(12), unique, indexed | `71010305` |
| `po_date` | DateField | |
| `season` | FK→`Season` | |
| `style` | FK→`Style` | |
| `factory` | FK→`Factory`, indexed | |
| `merchandiser` | FK→`auth.User`, null, indexed | PO owner (write scope) |
| `order_qty` | PositiveIntegerField | = Σ po_lines |
| `fob_usd_pc` | DecimalField(8,2) | |
| `fob_value_usd` | DecimalField(14,2) | = qty × fob/pc |
| `planned_exfactory` | DateField, indexed | on-time target |
| `planned_ship_mode` | CharField(8) | Sea/Air/Sea-Air |
| `port_of_loading` | CharField(40) | |
| `destination` | CharField(80) | |
| `delivery_terms` | CharField(40) | Incoterm |
| `is_open` | BooleanField, indexed | derived: no row in `Shipment` (maintained on ingest) |

Indexes: `po_no`, `(factory, planned_exfactory)`, `(is_open, planned_exfactory)`, `season`.

### `POLine`
Colour × size breakdown (one row per PO × colour; sizes are columns → stored as rows, see below).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order` | FK→`PurchaseOrder` | |
| `colour` | CharField(40) | `Navy` |
| `colour_code` | CharField(16) | `NAV-410` |
| `line_qty` | PositiveIntegerField | Σ sizes |

Constraint: `unique_together(purchase_order, colour_code)`.

### `POLineSize`
One row per PO line × size (normalises the wide size columns XS…10-11Y).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `po_line` | FK→`POLine` | |
| `size` | CharField(8) | `XS` … `10-11Y` |
| `qty` | PositiveIntegerField | |

Constraint: `unique_together(po_line, size)`.

---

## App: `masterdata` (T&A templates) / `orders` (T&A milestones)

### `TATemplate` and `TAMilestoneDef`
One standard template for all sweaters (ASSUMPTION A-10).
| `TATemplate` | Type | Notes |
|---|---|---|
| `id` / `name` | PK / CharField | `Standard sweater` |

| `TAMilestoneDef` | Type | Notes |
|---|---|---|
| `template` | FK→`TATemplate` | |
| `seq` | PositiveSmallIntegerField | 1–11 |
| `milestone` | CharField(40) | Yarn booking … Ex-factory (11 names) |
| `days_before_exfactory` | PositiveSmallIntegerField | offset (95,85,80,60,50,45,42,40,34,1,0) |
| `responsible` | CharField(60) | |

Constraint: `unique_together(template, seq)`.

### `TAMilestone`
Actual T&A calendar per PO (11 rows/PO).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order` | FK→`PurchaseOrder`, indexed | |
| `factory` | FK→`Factory` | denormalised (owner) |
| `seq` | PositiveSmallIntegerField | 1–11 |
| `milestone` | CharField(40) | |
| `responsible` | CharField(60) | |
| `planned_date` | DateField | from template |
| `revised_date` | DateField, null | committed new date |
| `actual_date` | DateField, null | blank while pending |
| `status` | CharField(12) | Done / Done late / Pending / Overdue |
| `remarks` | CharField(200), blank | |

Constraint: `unique_together(purchase_order, seq)`. Index: `(purchase_order, seq)`.

---

## App: `production`

### `UploadBatch`
| Field | Type | Notes |
|---|---|---|
| `id` | PK (UUID) | polled by the UI |
| `kind` | CharField(24) | `order_book` / `ta_calendar` / `daily_production` / `inspection` / `factory_master` / `shipment` |
| `original_filename` | CharField(200) | |
| `uploaded_by` | FK→`auth.User` | |
| `uploaded_at` | DateTimeField, indexed | |
| `detected_factory` | FK→`Factory`, null | from the file |
| `detected_date` | DateField, null | report date |
| `status` | CharField(12), indexed | `queued` / `running` / `done` / `error` |
| `rows_accepted` | IntegerField, default 0 | |
| `warnings` | JSONField | `[{row, message}]` |
| `errors` | JSONField | `[{row, message}]` |
| `finished_at` | DateTimeField, null | |

### `DailyProduction`
**PO × stage × date** (long form; the wide Excel is pivoted on ingest — ASSUMPTION A-10 / templates doc).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order` | FK→`PurchaseOrder`, indexed | |
| `factory` | FK→`Factory` | denormalised |
| `report_date` | DateField, indexed | production date |
| `stage` | CharField(16) | `knitting`/`linking`/`trimming_mending`/`washing`/`ironing`/`packing` |
| `day_pcs` | IntegerField | pieces that day (may be 0) |
| `cum_pcs` | IntegerField | cumulative; monotonic per (PO, stage) |
| `machines` | PositiveIntegerField, null | knitting/linking only (`Knitting M/C`, `Linking M/C`) |
| `remarks` | CharField(200), blank | |
| `upload_batch` | FK→`UploadBatch` | provenance |

Constraints: `unique_together(purchase_order, stage, report_date)`.
Indexes: `(purchase_order, stage, report_date)`, `(factory, report_date)`.

### `Inspection`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `inspection_id` | CharField(20), unique | `QA-2610-01234` |
| `inspection_date` | DateField, indexed | |
| `inspection_type` | CharField(20) | Inline / Pre-final / Final / Final re-inspection |
| `purchase_order` | FK→`PurchaseOrder`, indexed | |
| `factory` | FK→`Factory`, indexed | |
| `inspector` | CharField(60) | |
| `lot_qty` | PositiveIntegerField | |
| `aql_level` | CharField(20) | `II / 2.5 / 4.0` |
| `sample_size` | PositiveIntegerField | |
| `major_accept` | PositiveIntegerField | Ac |
| `critical_found` / `major_found` / `minor_found` | PositiveIntegerField | |
| `result` | CharField(4), indexed | Pass / Fail |
| `main_defect` | CharField(60), blank | |
| `measurement_check` | CharField(4) | Pass / Fail |
| `spec_weight_g` / `avg_weight_g` | PositiveIntegerField, null | |
| `remarks` | CharField(200), blank | |
| `upload_batch` | FK→`UploadBatch` | |

### `Shipment`
Presence of a shipment row ⇒ the PO is closed (`is_open=False`).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `shipment_id` | CharField(20), unique | `SH-2610-0412` |
| `purchase_order` | FK→`PurchaseOrder`, indexed | |
| `factory` | FK→`Factory`, indexed | |
| `planned_exfactory` | DateField | |
| `actual_exfactory` | DateField, indexed | on time if ≤ planned |
| `shipped_qty` | PositiveIntegerField | |
| `cartons` | PositiveIntegerField | |
| `gross_weight_kg` | DecimalField(10,2) | |
| `ship_mode` | CharField(8) | Sea / Air / Sea-Air |
| `port_of_loading` | CharField(40) | |
| `destination` | CharField(80) | |
| `etd` / `eta` | DateField | |
| `vessel_flight` | CharField(60), blank | |
| `invoice_no` | CharField(24) | |
| `invoice_value_usd` | DecimalField(14,2) | |
| `air_freight_cost_usd` | DecimalField(12,2), null | air only |
| `freight_borne_by` | CharField(10) | Karbar / Factory |
| `shipment_status` | CharField(12) | At port / In transit / Delivered |
| `remarks` | CharField(200), blank | |
| `upload_batch` | FK→`UploadBatch` | |

Index: `(factory, actual_exfactory)` for OTD/slip-distribution queries.

---

## App: `predictions`

### `PredictionSnapshot`
One row per open PO per run; kept for accuracy (Later). Pages read the latest snapshot; never recompute.
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order` | FK→`PurchaseOrder`, indexed | |
| `as_of` | DateTimeField, indexed | run time (= `DEMO_TODAY` for the seed) |
| `run` | FK→`PredictionRun` | |
| `state` | CharField(16) | `In production` / `Pre-production` |
| `bottleneck_stage` | CharField(16), blank | |
| `bottleneck_rate` | DecimalField(8,1), null | pcs/day |
| `required_rate` | DecimalField(8,1), null | pcs/day |
| `projected_finish_wd` | DecimalField(6,2), null | |
| `completion_day_n` | IntegerField, null | |
| `available_wd` | IntegerField | |
| `slack_wd` | DecimalField(5,1), null | |
| `projected_exfactory` | DateField | |
| `slip_days` | IntegerField | calendar days |
| `score_schedule` / `score_ta` / `score_otd` / `score_quality` / `score_freshness` | DecimalField(4,1) | components |
| `risk_score` | PositiveSmallIntegerField, indexed | 0–100 |
| `band` | CharField(10), indexed | On track/Watch/At risk/Critical/Late |
| `on_time_probability` | DecimalField(4,3) | 0.02–0.98 |
| `value_at_risk_usd` | DecimalField(14,2) | FOB if band∈{At risk,Critical,Late} else 0 |
| `air_freight_exposure_usd` | DecimalField(12,2) | if late/predicted late else 0 |
| `drivers` | JSONField | `[{label, detail, impact_days|"prior", weight}]` |
| `model_version` | CharField(12) | e.g. `engine-1.0` |

Constraints: `unique_together(purchase_order, run)`. Index: `(as_of, band)`, `(run, band)`.

### `PredictionRun`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `as_of` | DateTimeField, indexed | |
| `trigger` | CharField(12) | `nightly` / `upload` / `seed` / `manual` |
| `upload_batch` | FK→`UploadBatch`, null | if upload-triggered |
| `pos_scored` | IntegerField | |
| `params_hash` | CharField(64) | hash of the `EngineParameter` set used |

### `FactoryStat`
Per-run cached factory aggregates used by scoring and screens (OTD, AQL, slip distribution).
| Field | Type | Notes |
|---|---|---|
| `run` | FK→`PredictionRun` | |
| `factory` | FK→`Factory` | |
| `otd_12m` | DecimalField(4,3) | share of last-12-month shipments on time |
| `aql_pass_90d` | DecimalField(4,3) | |
| `slip_distribution` | JSONField | list of slip days (last 12 months) for probability |
| `last_report_date` | DateField, null | |
| `reported_today` | BooleanField | |
| `missed_wd` | PositiveSmallIntegerField | working days missed (freshness) |
| `knit_load_pct` | DecimalField(5,1) | |
| `open_pos` / `open_pcs` | IntegerField | |
| `exposure_usd` / `value_at_risk_usd` | DecimalField(14,2) | |

Constraint: `unique_together(run, factory)`.

---

## App: `alerts`

### `AlertRule`
Admin-editable thresholds that turn snapshot/reporting facts into alerts.
| Field | Type | Notes |
|---|---|---|
| `id` / `kind` | PK / CharField(24) | `po_critical`, `factory_missed_report`, `yarn_late`, `inspection_failed`, `po_at_risk`, `compliance` |
| `enabled` | BooleanField | |
| `threshold` | JSONField | rule params (e.g. slip≥7, compliance<0.8) |
| `default_severity` | CharField(10) | |

### `Alert`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `kind` | CharField(24), indexed | matches rule kinds |
| `severity` | CharField(10) | critical/risk/watch/noupdate |
| `created_at` | DateTimeField, indexed | |
| `text` | CharField(240) | |
| `purchase_order` | FK→`PurchaseOrder`, null | |
| `factory` | FK→`Factory`, null | |
| `owner` | FK→`auth.User`, null | |
| `state` | CharField(10), indexed | open/acked/assigned/snoozed |
| `snooze_until` | DateTimeField, null | |
| `run` | FK→`PredictionRun`, null | the run that raised it |
| `dedupe_key` | CharField(80), unique | prevents duplicate alerts across runs |

Index: `(state, severity, created_at)`.

---

## App: shared / `orders`

### `Comment`
Polymorphic-ish comment on a PO or factory (Phase 0 = PO comments + factory notes).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `purchase_order` | FK→`PurchaseOrder`, null, indexed | |
| `factory` | FK→`Factory`, null, indexed | |
| `author` | FK→`auth.User` | |
| `created_at` | DateTimeField | |
| `text` | TextField | |

Exactly one of `purchase_order` / `factory` is set (DB check constraint). PO comments are also indexed
into ChromaDB for the assistant (`ai/assistant.md`).

---

## App: `assistant`

### `Conversation`
| Field | Type | Notes |
|---|---|---|
| `id` | PK (UUID) | |
| `user` | FK→`auth.User`, indexed | |
| `title` | CharField(120) | |
| `created_at` / `updated_at` | DateTimeField | |

### `ChatMessage`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `conversation` | FK→`Conversation`, indexed | |
| `role` | CharField(10) | user / assistant / tool |
| `content` | TextField | |
| `tool_calls` | JSONField, null | tool name + args + grain |
| `artifacts` | JSONField, null | chart/table specs rendered |
| `sources` | JSONField, null | `[{name, as_of}]` |
| `created_at` | DateTimeField | |

### `TokenUsage`
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `conversation` | FK→`Conversation` | |
| `message` | FK→`ChatMessage`, null | |
| `model` | CharField(40) | from env |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | IntegerField | |
| `created_at` | DateTimeField | |

---

## App: `accounts`

Uses `django.contrib.auth.User` + `Group` (Admin / Management / Merchandiser / QA). A thin
`UserProfile` holds display role for the header pill.

### `UserProfile`
| Field | Type | Notes |
|---|---|---|
| `user` | OneToOne→`auth.User` | |
| `display_role` | CharField(16) | ceo / management / merch / qa / shipping (header pill only) |

### `AuditLog`
Append-only security/audit trail (`tech/security.md`).
| Field | Type | Notes |
|---|---|---|
| `id` | PK | |
| `user` | FK→`auth.User`, null | |
| `at` | DateTimeField, indexed | |
| `action` | CharField(40) | login, upload, comment, alert_ack, alert_assign, param_change, export, chat |
| `target` | CharField(80) | entity ref |
| `meta` | JSONField | |
| `ip` | GenericIPAddressField, null | |

---

## Entity-relationship diagram

```mermaid
erDiagram
    User ||--o{ PurchaseOrder : "merchandiser"
    User ||--o{ Factory : "owns"
    User ||--o{ Comment : authors
    User ||--o{ Conversation : has
    User ||--o{ AuditLog : acts

    Department ||--o{ Style : classifies
    Season ||--o{ PurchaseOrder : buys
    Style ||--o{ PurchaseOrder : ordered_as

    Factory ||--o{ FactoryMachine : has
    Factory ||--o{ PurchaseOrder : makes
    Factory ||--o{ DailyProduction : reports
    Factory ||--o{ Inspection : inspected
    Factory ||--o{ Shipment : ships
    Factory ||--o{ TAMilestone : owns
    Factory ||--o{ FactoryStat : summarised

    TATemplate ||--o{ TAMilestoneDef : defines

    PurchaseOrder ||--o{ POLine : "colour lines"
    POLine ||--o{ POLineSize : "size qty"
    PurchaseOrder ||--o{ TAMilestone : schedule
    PurchaseOrder ||--o{ DailyProduction : "stage x date"
    PurchaseOrder ||--o{ Inspection : inspected
    PurchaseOrder ||--o| Shipment : "closed by"
    PurchaseOrder ||--o{ PredictionSnapshot : predicted
    PurchaseOrder ||--o{ Comment : discussed
    PurchaseOrder ||--o{ Alert : raises

    PredictionRun ||--o{ PredictionSnapshot : contains
    PredictionRun ||--o{ FactoryStat : contains
    PredictionRun ||--o{ Alert : raises

    UploadBatch ||--o{ DailyProduction : ingests
    UploadBatch ||--o{ Inspection : ingests
    UploadBatch ||--o{ Shipment : ingests
    UploadBatch ||--o| PredictionRun : triggers

    AlertRule ||--o{ Alert : parameterises
    Conversation ||--o{ ChatMessage : contains
    Conversation ||--o{ TokenUsage : meters

    HolidayCalendar }o--o{ PurchaseOrder : "working-day calendar (rule)"
    EngineParameter }o--o{ PredictionRun : "params_hash"
```

> `HolidayCalendar` and `EngineParameter` are consumed by the engine at run time (not FK-linked per PO);
> the diagram shows the logical dependency.

## Derived / not stored

- **PO open/closed**: `is_open` maintained when a `Shipment` row is ingested for the PO.
- **Stage curves, forecasts, bottleneck, slack, required rate, bands, probability, VaR, air exposure**:
  computed by the engine into `PredictionSnapshot` / `FactoryStat`; never recomputed on page load.
- **Knitting capacity / load**: `Σ(machines by gauge × knit_mc_minutes_per_day) ÷ knitting_minutes_pc`
  vs required — computed into `FactoryStat.knit_load_pct`.
