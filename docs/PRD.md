# AI Pulse — Product Requirements (master)

**Owner:** Karbar Sourcing Bangladesh · **Status:** Phase 0 (demo + pilot) · **Doc version:** v1 · **As of:** 3 Oct 2026
**Demo day:** 15 Oct 2026 · **Demo "today" (`DEMO_TODAY`):** 15 Oct 2026 (Thursday; reports up to 14 Oct)

> Source-of-truth rule for this programme (confirmed): the files in `sample_data/` and the
> `00_Answer_Key.xlsx` are canonical for **every number, name, and formula**. The design export in
> `design/` is canonical for **layout, components, interaction and visual tokens only**. Where the
> design prototype's illustrative data (`pulse-data.js`, handoff notes) disagrees with the answer key,
> the answer key wins. See [ASSUMPTION list](#assumptions) for each reconciliation.

---

## 1. Problem

Karbar Sourcing Bangladesh is the single-brand sourcing office for the apparel brand **Karbar**. It
buys **sweaters** from about **22 independent Bangladesh factories**. Every morning the merchandising
team receives daily Excel production reports from the factories. Today those reports are read by hand,
one file at a time. There is no single view of:

- which purchase orders (POs) will miss their committed ex-factory date, and by how many days;
- how much FOB value is at risk this month, and which factories concentrate that risk;
- which factories have gone quiet (no report), which is itself an early warning;
- what concrete action (machines, overtime, mode change) recovers a late PO, and at what cost.

By the time a slip is visible in a spreadsheet it is usually too late to act without **air freight**,
which Karbar often absorbs. The office needs the problem surfaced early enough to move machines or add
overtime instead of paying to fly goods.

## 2. Vision

One screen every morning that states the business in three sentences — on-time %, value at risk, the
factories driving it — with the evidence one click away, and a prediction for every open PO that says
not just *late* but *why, in days, per cause*, plus the cheapest fix. The same numbers answer plain-English
questions in an assistant, so the dashboard and the chat never disagree. It runs on the Excel files the
factories already send; there is no new system for the factories in Phase 0.

## 3. Personas

| Persona | Role in the office | What they need from Pulse | Django group |
|---|---|---|---|
| **CEO** (Mr. Karim, demo) | Owns the brand's delivery and margin | The 3-sentence morning state; where risk concentrates; proof a fix exists before a factory call | Management |
| **Head of Merchandising** | Runs the merchandiser team | The at-risk queue across the whole book; which merchandiser owns each slip; where to push | Management |
| **Merchandiser** | Owns ~a quarter of the book (POs + factory relationships) | Their POs' predictions, drivers, what-if; upload the daily files; comment and act | Merchandiser |
| **QA head** | Owns inspections and AQL | Failed/again-due inspections, factory AQL trend, quality's contribution to risk | QA |
| **Shipping** | Books sea/air, invoices | Shipment forecast, air-freight exposure, what shifts to air if nothing changes | Management (read-only, Phase 0) |

All five personas **read the whole book**. Write actions (comments, alert acknowledge/assign, uploads)
are **scoped to ownership** and enforced in querysets, not only templates (see `tech/security.md`).
There is no dedicated Shipping group in Phase 0 (see ASSUMPTION A-07).

## 4. Goals

- **G1 — CEO demo (15 Oct 2026).** A 3-minute click-path on seeded dummy data, English only, that
  reproduces the answer-key numbers exactly, including the hero PO what-if.
- **G2 — Pilot on real data.** The same app ingests the six real factory Excel files and produces the
  same calculations without code changes to the engine.
- **G3 — One source of numbers.** Every figure on every screen and in the assistant comes from the
  shared `services/` layer, carries a source and an "as of" time, and matches the answer key.

## 5. Non-goals (Phase 0)

- No factory login or factory self-upload portal (merchandisers upload). 
- No email/WhatsApp/push alert delivery (alerts are an in-app feed).
- No machine-learning model; the prediction engine is deterministic formulas (ML is Phase 2 with a backtest).
- No custom Settings screens; all master data and thresholds are edited in the Django admin.
- No multi-brand, no non-sweater products, no multi-language.
- No mobile app / PWA (the web UI is responsive to 390 px for key screens only).

## 6. Success metrics

| # | Metric | Target for the demo / pilot | Source |
|---|---|---|---|
| M1 | Answer-key parity | 100% of answer-key KPIs and the 412 open-PO predictions reproduced within rounding | `tests` vs `00_Answer_Key.xlsx` |
| M2 | Golden-question parity | 30/30 assistant golden questions return the expected answer; 3/3 demo questions exact | `assistant` eval suite |
| M3 | Ingest reliability | A valid daily file ingests and refreshes predictions with no manual step; errors are reported per row | upload flow |
| M4 | Freshness honesty | Every number shows an `as_of`; a factory that has not reported is flagged, not silently stale | all screens |
| M5 | Demo robustness | The 3-minute path runs offline for the AI fallback (pre-stored answers) | `plan/demo-script.md` |

Pilot (post-demo) adds: prediction accuracy (MAE days, % within 2 days) tracked from daily snapshots — **Later**.

## 7. Glossary — one definition per metric

All definitions are the canonical ones from `00_Answer_Key.xlsx › Parameters` and the reference engine.
Full formulas: `ai/prediction-engine.md`.

| Term | Definition (exactly one) |
|---|---|
| **Working day (WD)** | Any calendar day except **Friday** (the Bangladesh garment weekend), plus any date explicitly added as an overtime day. Bangladesh public holidays are also non-working once loaded into the holiday calendar (the seed uses a Friday-only weekend; holidays are loaded separately). |
| **Available WD** | Working days from `DEMO_TODAY` **up to but not including** the planned ex-factory date. |
| **Slip days** | `projected ex-factory − planned ex-factory`, in **calendar days**. A PO is **on time** when slip ≤ 0. |
| **Slack days (slack WD)** | `Available WD − Completion Day N` (working days). Positive = buffer; ≤ 0 = none. |
| **On-time %** (October) | `(October POs already shipped on time + open October POs predicted on time) ÷ all POs with planned ex-factory in October`. Demo value **86.25%**. |
| **OTD** (on-time delivery) | A factory's share of its **last-12-month shipments** whose actual ex-factory ≤ planned ex-factory. Computed from the Shipment Log. |
| **Risk score** | Integer **0–100**, the sum of five capped components (schedule 50, T&A 20, factory OTD 15, quality 10, freshness 5). See engine §5. |
| **Band** | Score bucket: **On track** < 25 · **Watch** 25–49 · **At risk** 50–74 · **Critical** ≥ 75, with overrides: any slip > 0 → at least At risk; slip ≥ 7 → Critical; planned ex-factory in the past and not shipped → **Late**. |
| **No update** | A **factory reporting state** (not a PO band): the factory has missed the latest expected working-day report (≥ 1 missed working day). Shown as a stripe/pill and raised as an alert. POs always keep a score-band. |
| **Value at risk** | Total **FOB value** of open POs whose band is **At risk, Critical, or Late**. Demo value **USD 2,400,006**. |
| **Air-freight exposure** | For POs predicted late or already late: `order qty × weight kg/pc × (air USD/kg − sea USD/kg)`, with air **6.00** and sea **0.50** USD/kg (admin-editable). Demo total **USD 539,720**. |
| **Required daily rate** | Pieces the bottleneck stage must produce per working day to still make the ex-factory date: `bottleneck remaining ÷ (Available WD − lags of the stages after it)`. |
| **Bottleneck stage** | The **last** production stage whose projected finish is set by its own rate (not by waiting on an upstream stage). |
| **Completion Day N** | `ceil(projected packing finish)` in working days, counting today as day 1. Projected ex-factory = the working day **after** the N-th working day. |

## 8. Scope by tier

Screens trace to the design export; every FR traces to a design screen in `traceability.md`.

### Must for 15 Oct

| Screen / capability | Module (FR prefix) | Notes |
|---|---|---|
| Login + app shell (header, sidebar, freshness pill, ⌘K palette, theme toggle) | accounts `FR-ACCT`, dashboard `FR-DASH` | Dark + light themes via CSS variables |
| Executive Overview | dashboard `FR-DASH` | AI briefing, 6 KPI cards, 8-week outlook, factory×week heatmap, top-10 at-risk, leaderboard, dept/gauge split |
| PO list + detail (with what-if) | orders `FR-ORD` | Filters/sort/pagination (HTMX), prediction, risk drivers, T&A Gantt, stage curves, recommendation, what-if partial, comments |
| Factories list + detail | factories `FR-FAC` | Scorecards, machine load, OTD, AQL, order book, daily output, inspections, certificates, AI summary |
| Daily Updates (upload + ingest) | production `FR-PROD` | Drag-drop, async ingest via django-q2, HTMX status poll, validation result, reporting status, history |
| AI Assistant (page + slide-over) | assistant `FR-AI` | SSE streaming, tool calls over `services/`, charts/tables, sources, Excel export |
| Master data in Django admin | masterdata `FR-MASTER` | Factories, machines, seasons, holidays, thresholds, users — no custom Settings screen |
| Prediction engine + snapshots | predictions `FR-PRED` | Pure-Python service; runs post-upload and nightly; pages read snapshots |

### Should for 15 Oct

| Screen / capability | Module | Notes |
|---|---|---|
| Alerts feed | alerts `FR-ALERT` | Acknowledge / assign / snooze; derived from snapshots + reporting |
| Shipment forecast report | reports `FR-REP` | 8-week by period: POs, pcs, FOB, on-time %, at-risk USD |
| Factory performance report | reports `FR-REP` | Factory scorecards, OTD, AQL, exposure |

### Later

Analytics / prediction accuracy (daily-snapshot trend, MAE, % within 2 days); custom Settings screens;
remaining reports (T&A delay, inspection, plan-vs-actual, on-time trend); factory self-upload portal;
email / WhatsApp / push alert delivery; PWA; gradient-boosting ML model with backtest; distinct Shipping group.

## 9. Modules and FR numbering

Each module has one PRD in `prd/`. User stories are `FR-<PREFIX>-NNN` (NNN from 010, step 10).

| Module | App | FR prefix | PRD |
|---|---|---|---|
| Accounts & access | `accounts` | `FR-ACCT` | `prd/accounts.md` |
| Master data | `masterdata` | `FR-MASTER` | `prd/masterdata.md` |
| Orders (PO list/detail/what-if) | `orders` | `FR-ORD` | `prd/orders.md` |
| Factories | `factories` | `FR-FAC` | `prd/factories.md` |
| Production (uploads + ingest) | `production` | `FR-PROD` | `prd/production.md` |
| Predictions | `predictions` | `FR-PRED` | `prd/predictions.md` |
| Alerts | `alerts` | `FR-ALERT` | `prd/alerts.md` |
| Reports | `reports` | `FR-REP` | `prd/reports.md` |
| Assistant | `assistant` | `FR-AI` | `prd/assistant.md` |
| Dashboard (Overview + shell) | `dashboard` | `FR-DASH` | `prd/dashboard.md` |

Business logic for all of these lives in a shared **`services/`** layer that both views and assistant
tools call (see `tech/architecture.md`). No business logic in views, templates, or assistant tools.

## 10. Roles (Django groups)

`Admin`, `Management`, `Merchandiser`, `QA`. Mapping of personas → groups is in §3. Permissions and
queryset scoping are specified in `tech/security.md` and per-module in `prd/`.

---

## Assumptions

Every item below is an **ASSUMPTION** made to resolve a gap or a conflict between the design export, the
sample data, and the brief. Each can be overturned by Karbar.

- **ASSUMPTION A-01 — Source of truth.** `sample_data/` + `00_Answer_Key.xlsx` are canonical for all
  numbers, names and formulas; `design/` is canonical for layout/UX only. Confirmed with stakeholder.
- **ASSUMPTION A-02 — Band model.** Bands are score-based (<25 / 25–49 / 50–74 / ≥75) with Late and
  slip overrides, per the answer key — **not** the probability-based thresholds in the design handoff.
- **ASSUMPTION A-03 — "No update".** "No update" is a factory reporting flag, not a fifth PO band. Band
  counts sum to 412 (On track 354, Watch 10, At risk 28, Critical 13, Late 7) with no "No update" bucket.
- **ASSUMPTION A-04 — Snapshots for the demo.** `seed_demo` writes one prediction snapshot per open PO,
  as of 15 Oct 2026. OTD and factory stats come from the 12-month shipped history. Daily-snapshot
  accuracy history is Later.
- **ASSUMPTION A-05 — Read scope.** All roles read the full order book and factory data; write actions
  are scoped to ownership. (Alternative — read scoped per role — was declined.)
- **ASSUMPTION A-06 — Persona→group.** CEO and Head of Merchandising → Management; merchandiser →
  Merchandiser; QA head → QA.
- **ASSUMPTION A-07 — Shipping.** The Shipping persona folds into Management (read-only) for Phase 0; a
  dedicated Shipping group is Later.
- **ASSUMPTION A-08 — Assistant knowledge base.** No unstructured documents exist in `sample_data/`.
  `seed_demo` deterministically fabricates clearly-fictional English documents (sweater quality manual,
  T&A standards, 22 factory profiles, audit notes, PO comments) for ChromaDB so citations work.
- **ASSUMPTION A-09 — Demo questions.** The three demo questions are: (1) "Which factories will miss
  October ex-factory and by how much?"; (2) "Why is PO 71010305 late and what's the fastest way to make
  it on time?"; (3) "What's our October on-time %, and where is the USD 2.4M at risk concentrated?"
  Pre-computed answers are stored for the OpenAI-slow fallback.
- **ASSUMPTION A-10 — T&A model.** `ta_milestone` stores the 11 T&A-calendar milestones. The six
  production **stages** (knitting, linking, trimming & mending, washing, ironing, packing) live only in
  `daily_production`; stage curves and the Gantt's stage bars are **computed forecasts**, not stored
  milestones. `ta_template` is one standard offset table (days before ex-factory) applied to all sweaters;
  washing-related timing applies only when `Wash Required = Y`.
- **ASSUMPTION A-11 — Donor selection.** The machine-reallocation recommendation auto-selects a donor PO
  (same factory, same gauge/linking pool, positive slack, enough spare machines). For the hero PO this
  deterministically resolves to donor PO `71009573`.
- **ASSUMPTION A-12 — Hero PO identity.** The hero PO is `71010305` (Greyloom, style `KAW26-W-1736`,
  Lambswool V-neck Cardigan, Women's, 7GG, 9,600 pcs, FOB USD 158,400, ex-factory 29 Oct), predicted
  7 Nov (slip 9, band Critical, score 76, on-time probability 2%). The design prototype's `PO-26-1187`
  / "Ananta Knitwear" labels are discarded.
- **ASSUMPTION A-13 — Air-freight constants.** Air 6.00 and sea 0.50 USD/kg; weight kg/pc from the
  order book (hero 0.72). The design's "40% split at 4.10 USD/kg, 0.69 kg/pc" is discarded.
- **ASSUMPTION A-14 — Pilot scale.** The demo dataset is the pilot-shaped dataset: 22 factories, 1,287
  total POs (412 open), 1,900,020 open pcs, USD 18,601,449 open FOB. Factory machine counts are sized
  to Karbar's own load and are smaller than a factory's full floor.
- **ASSUMPTION A-15 — Season model.** Seasons are AW/HO/SS/SU + 2-digit year, derived from ex-factory
  date by the generator's `season_for` rule; stored as master data.
- **ASSUMPTION A-16 — Freshness threshold N.** A factory is flagged "No update" when it has missed the
  latest expected working-day report (N = 1 missed working day). The freshness **score** component uses
  the same missed-WD count (1 → 3, ≥ 2 → 5). Admin-editable.
