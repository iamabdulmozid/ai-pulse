# Karbar Pulse — Predictions module PRD (`FR-PRED`)

**App:** `predictions` · **FR prefix:** `FR-PRED` · **Tier:** Must for 15 Oct
**Source of truth:** `ai/prediction-engine.md` (formulas) + `sample_data/00_Answer_Key.xlsx` (the test).
The engine must reproduce every row of `Open PO Predictions` and every `KPIs` / `Hero What-if` value
within rounding. Design handoff numbers that disagree (probability-based bands, 40% air split) are
discarded (PRD A-01/A-02/A-13).

---

## 1. Purpose & design screens

Predictions has **no screen of its own**. It is the deterministic engine and its stored results that
**power every other screen and the assistant**: the Overview KPIs/outlook/heatmap (`FR-DASH`), the PO list,
detail, drivers and what-if (`FR-ORD`), the factory scorecards and detail (`FR-FAC`), and the alerts feed
(`FR-ALERT`).

Core contract: the engine runs **after every successful upload** and **nightly**, writes one
`PredictionRun` with its `PredictionSnapshot` (one per open PO) and `FactoryStat` (one per factory) rows,
and **all consumers read the latest snapshot — they never recompute on request** (PRD G3, engine §9). Every
figure shown carries the run's `as_of`.

Business logic lives in a pure-Python service (`services/prediction/`) with no ORM/view symbols inside the
formulas (engine §0, test `test_pure_service`); a thin adapter loads ORM rows in and writes results out.

For the demo there is **one seed run** as of **15 Oct 2026** (trigger `seed`); the latest expected report
is 14 Oct. OTD, AQL and slip distribution come from the 12-month shipped history (PRD A-04).

---

## 2. User stories

- **FR-PRED-010 — Run after each successful upload.** As the **system**, I want the ingest task to trigger
  a prediction run when a file ingests cleanly, so screens refresh with no manual step.
- **FR-PRED-020 — Nightly scheduled run.** As the **system**, I want a nightly django-q2 run, so numbers
  stay current even on a day with no uploads.
- **FR-PRED-030 — Store and read snapshots.** As a **developer/consumer**, I want results stored in
  `PredictionSnapshot` / `PredictionRun` and read as the latest snapshot by every page and the assistant,
  so the dashboard and chat never disagree and nothing is recomputed on a request.
- **FR-PRED-040 — Compute FactoryStat.** As the **engine**, I want per-factory aggregates (OTD 12m, AQL
  90d, slip distribution, last report, missed working days, knit load, exposure) computed per run, so
  scoring and the factory screens read one consistent set.
- **FR-PRED-050 — Answer-key parity.** As a **tester**, I want automated tests that reproduce the answer
  key (Open PO Predictions, KPIs, Hero What-if) within rounding, so parity is guaranteed before the demo.
- **FR-PRED-060 — Editable parameters + audit.** As an **admin**, I want the engine to read an
  admin-editable `EngineParameter` set and record a `params_hash` per run, so changes affect future runs
  only and every snapshot's inputs are auditable.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-PRED-010 Run after each successful upload
- **Given** an `UploadBatch` that reaches `status=done` (`FR-PROD-020`), **when** ingest completes,
  **then** a `PredictionRun` is created with `trigger='upload'` and `upload_batch` set, scoring all open
  POs and writing its snapshots/factory stats.
- **Given** the clean PBB demo file, **when** it ingests, **then** a run occurs and the headline KPIs are
  unchanged (open POs 412, open pcs 1,900,020, open FOB USD 18,601,449, value at risk USD 2,400,006, air
  exposure USD 539,720) while "reported today" becomes 19 of 22.
- **Given** a **rejected** batch (HMR, `status=error`), **when** ingest fails, **then** **no run is
  triggered** and the latest snapshot is unchanged.

### FR-PRED-020 Nightly scheduled run
- **Given** the django-q2 schedule, **when** the nightly time arrives, **then** a `PredictionRun` with
  `trigger='nightly'` runs end-to-end (FactoryStat for all 22 factories → score all open POs → raise
  alerts) with no manual step.
- **Given** a nightly run, **when** it finishes, **then** pages read the new run's `as_of`; the previous
  run's snapshots are retained (kept per run for accuracy, Later).

### FR-PRED-030 Store and read snapshots; never recompute
- **Given** a run, **when** it writes results, **then** there is exactly one `PredictionSnapshot` per open
  PO for that run (unique `(purchase_order, run)`) and one `FactoryStat` per factory (unique
  `(run, factory)`).
- **Given** any page or assistant tool, **when** it needs a prediction figure, **then** it reads the
  **latest** run's snapshot via `services/` and does **not** recompute on the request; the figure carries
  the run's `as_of`.
- **Given** the seed, **when** `seed_demo` runs, **then** there is one run as of 15 Oct 2026 with 412 open
  snapshots and band counts summing to 412: **On track 354 · Watch 10 · At risk 28 · Critical 13 ·
  Late 7**.
- **Given** the hero PO `71010305`, **when** its snapshot is read, **then** it shows `bottleneck_stage`
  Linking, `bottleneck_rate` 411.1, `required_rate` 680, `completion_day_n` 19, `available_wd` 12,
  `slack_wd` −7, `projected_exfactory` 2026-11-07, `slip_days` 9, `risk_score` 76, `band` Critical,
  `on_time_probability` 0.02, `air_freight_exposure_usd` 38,016.

### FR-PRED-040 Compute FactoryStat
- **Given** a run, **when** FactoryStat is computed, **then** each factory row has `otd_12m`,
  `aql_pass_90d`, `slip_distribution` (list of last-12-month slip days), `last_report_date`,
  `reported_today`, `missed_wd`, `knit_load_pct`, `open_pos`, `open_pcs`, `exposure_usd`,
  `value_at_risk_usd`.
- **Given** GRL (Greyloom), **when** its FactoryStat is read, **then** `otd_12m = 0.681`,
  `aql_pass_90d = 0.95`, `open_pos = 52`, `value_at_risk_usd = 774,059`, and `reported_today = True`
  (GRL is not among the four missing factories).
- **Given** the four quiet factories, **when** FactoryStat is computed, **then** `reported_today = False`
  and `missed_wd ≥ 1` for SLM, OKH, HMR, PBB (last reports 12 Oct, 11 Oct, 13 Oct, 13 Oct) — surfaced as
  "No update" (not a band), per engine §6.
- **Given** FactoryStat is computed before scoring, **when** POs are scored, **then** the schedule/OTD/
  quality/freshness components read these aggregates (OTD → factory-OTD cap 15; AQL<0.85 → quality 5;
  missed_wd → freshness 3/5), so the factory screens and the PO scores use one consistent set.

### FR-PRED-050 Answer-key parity tests
- **Given** `test_engine_matches_answer_key`, **when** it runs, **then** every row of `Open PO
  Predictions` is reproduced within rounding (band, score, projected ex-factory, slip, bottleneck, rates,
  probability, VaR, air exposure).
- **Given** `test_kpis_match_answer_key`, **when** it runs, **then** the `KPIs` sheet is reproduced: open
  POs **412**, open pcs **1,900,020**, open FOB **USD 18,601,449**, October on-time **86.25%**, value at
  risk **USD 2,400,006** (48 POs), top-3 factory share **70.0%** (GRL 774k, IRB 478k, SLM 428k), air
  exposure **USD 539,720**, band counts (354/10/28/13/7), and the 8-week outlook.
- **Given** `test_hero_whatif`, **when** it runs, **then** all six `Hero What-if` rows are reproduced,
  including **+6 linking M/C (13→19) and 2 Friday overtime days → ex-factory 29 Oct, slip 0, on time,
  air avoided USD 38,016**, and donor PO **`71009573`** moving from 9 days early to 5 days early.
- **Given** `test_calendar`, **when** it runs, **then** `wd_between`, `nth_wd`, `next_wd` match
  hand-checked dates including overtime and holidays (e.g. `wd_between(15 Oct, 29 Oct) = 12`).
- **Given** `test_pure_service`, **when** it runs, **then** the engine module imports no Django ORM/view
  symbols.

### FR-PRED-060 Editable parameters + params_hash
- **Given** the active `EngineParameter` set, **when** a run executes, **then** the engine reads a typed
  snapshot of those values (defaults = answer-key `Parameters`: `air_usd_per_kg` 6.00, `sea_usd_per_kg`
  0.50, `rate_window_wd` 7, `flow_limit_days` 1.5, `yarn_to_knit_days` 2, `knit_mc_minutes_per_day` 1020,
  stage lags, score caps 50/20/15/10/5, band cut-offs 25/50/75, `slip_forces_critical` 7, freshness 3/5,
  prob clamp 0.02/0.98) and records a `params_hash` on the `PredictionRun`.
- **Given** an admin changes a parameter in the Django admin, **when** the next run executes, **then** only
  that future run is affected (prior snapshots keep their `params_hash`), so a snapshot's inputs stay
  auditable.

---

## 4. Design components

No UI of its own. Its outputs render through other modules' components: KPI Cards, outlook stacked
BarChart and factory×week heatmap (`FR-DASH`); PO-list band/score chips and PO-detail prediction panel,
risk-driver list, stage-curve ComposedChart and what-if slider (`FR-ORD`); factory scorecards and 14-day
output chart (`FR-FAC`); alert rows (`FR-ALERT`). The only operational surface is the Django admin for
`EngineParameter` (`FR-MASTER`) and an admin "re-run" action (trigger `manual`).

---

## 5. Data read / written (models/fields)

Written per run:
- **`PredictionRun`**: `as_of`, `trigger` (`nightly`/`upload`/`seed`/`manual`), `upload_batch` (if
  upload-triggered), `pos_scored`, `params_hash`.
- **`PredictionSnapshot`** (one per open PO, unique `(purchase_order, run)`): `state`, `bottleneck_stage`,
  `bottleneck_rate`, `required_rate`, `projected_finish_wd`, `completion_day_n`, `available_wd`, `slack_wd`,
  `projected_exfactory`, `slip_days`, `score_schedule`/`_ta`/`_otd`/`_quality`/`_freshness`, `risk_score`,
  `band`, `on_time_probability`, `value_at_risk_usd`, `air_freight_exposure_usd`, `drivers` (JSON
  `[{label, detail, impact_days|"prior", weight}]`), `model_version`.
- **`FactoryStat`** (one per factory, unique `(run, factory)`): `otd_12m`, `aql_pass_90d`,
  `slip_distribution`, `last_report_date`, `reported_today`, `missed_wd`, `knit_load_pct`, `open_pos`,
  `open_pcs`, `exposure_usd`, `value_at_risk_usd`.
- **`Alert`** rows raised from `AlertRule`s at the end of a run (`FR-ALERT`), tagged with `run`.

Read as inputs (via the adapter, engine §0):
- `PurchaseOrder` / `Style` (order facts), `DailyProduction` (reported day/cum by stage),
  `TAMilestone` (11 milestones), `Inspection` (latest result), `Shipment` (12-month history for OTD / slip
  distribution), `Factory` / `FactoryMachine` (capacity), `HolidayCalendar` (working-day calendar),
  `EngineParameter` (parameters).

Consumers (all read the latest run, never recompute): `services.metrics.portfolio_kpis/outlook/heatmap`
(`FR-DASH`), `services.prediction` read paths (`FR-ORD` list/detail/drivers/curves), `services.prediction.whatif`
(`FR-ORD` what-if — same `project()` with overridden inputs, writes no snapshot),
`services.metrics.factory_scorecard/factory_detail` (`FR-FAC`), and the assistant tools (`FR-AI`).

Cross-references: triggered by `FR-PROD-020` (ingest) → `FR-PRED-010`; reporting state (`reported_today`,
`missed_wd`) matches `FR-PROD-050` and `FR-FAC-010`; parameters are edited in `FR-MASTER` (Django admin).

---

## 6. Empty / error / stale-data states

- **No run yet:** consumers show "No prediction run yet" and render no invented figures; the seed
  guarantees one run exists for the demo.
- **Upload-triggered run fails mid-compute:** the partial run is not published as latest; the previous
  latest snapshot remains authoritative; the failure is logged and (optionally) alerted; data is not left
  half-written (the run is written atomically).
- **Factory with no 12-month history:** `otd_12m` / `slip_distribution` degrade safely; `on_time_probability`
  is clamped to the 0.02–0.98 floor/ceiling so it is never 0 or 1.
- **Quiet factory (no report today):** scored from the last known production; freshness component applies
  (missed_wd 1→3, ≥2→5); the snapshot's `as_of` and the factory's "No update" flag mark it as not fresh
  (metric M4) — never silently stale.
- **Parameter change between runs:** older snapshots keep their `params_hash`; mixing figures across runs is
  avoided because consumers always read a single latest run.
- **Nightly worker down:** no new run; latest remains the last good run with its real `as_of`; the
  freshness pill shows the true age.

---

## 7. Permissions

Predictions has no end-user screen, so there are no per-screen read/write rules of its own; its outputs
inherit the read scope of the screen that shows them (all four groups read the whole book, PRD A-05).

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read prediction outputs (via any screen/assistant) | ✓ | ✓ | ✓ | ✓ |
| Edit `EngineParameter` (Django admin, `FR-MASTER`) | ✓ | – | – | – |
| Trigger a manual re-run (admin action) | ✓ | – | – | – |

Automatic runs (upload-triggered, nightly, seed) are system actions, not user actions. Parameter edits and
re-runs are Admin-only and recorded (`params_hash` per run; audit via `AuditLog` `param_change`).
