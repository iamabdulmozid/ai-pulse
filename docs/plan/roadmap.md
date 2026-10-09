# Karbar Pulse — Delivery roadmap (3 Oct → 15 Oct 2026)

**Owner:** Karbar Sourcing Bangladesh · **Status:** Phase 0 build sprint · **As of:** 3 Oct 2026
**Code freeze + dry run:** 14 Oct 2026 · **CEO demo:** 15 Oct 2026 (seeded dummy data, English only)

> **Source of truth.** `sample_data/` + `00_Answer_Key.xlsx` are canonical for every number, name and
> formula; `design/` is canonical for layout, components and interaction only. See `PRD.md`,
> `ai/prediction-engine.md`, `data/data-model.md`, `tech/urls-and-views.md`. Where the design prototype's
> illustrative data disagrees with the answer key, the answer key wins (PRD ASSUMPTION A-01).

## Calendar note (read first)

The demo clock `DEMO_TODAY` = **Thursday 15 Oct 2026** is load-bearing: the hero what-if adds the two
Fridays **16 & 23 Oct** as overtime. Weekday labels below are aligned to that canon. On this calendar the
only Friday *inside* the build window is **9 Oct** (the Bangladesh garment weekend). This is the Karbar
office/dev plan, so Friday 9 Oct is treated as a **working dev day** — the schedule is continuous from 3 Oct
to 15 Oct. (The task brief's "Fridays 3 & 10 Oct" is a weekday mislabel; keeping the engine calendar
consistent matters more, so we anchor on 15 Oct = Thursday.)

## How to read this plan

Each task is sized for one coding agent to pick up and finish. Columns:
- **ID** — stable task id (`T-01` …).
- **FR** — the FR module IDs it delivers (prefixes: FR-ACCT, FR-MASTER, FR-ORD, FR-FAC, FR-PROD,
  FR-PRED, FR-ALERT, FR-REP, FR-AI, FR-DASH).
- **Deps** — task ids that must be green first.
- **Acceptance** — pytest functions (named `test_<module>_<thing>`) that must pass, plus any manual check.

All business logic lives in the shared `services/` layer; no business logic in views, templates or
assistant tools (PRD §9). Pages read the latest `PredictionSnapshot` / `FactoryStat`; they never recompute.

---

## Build order (Must critical path)

```
models + seed  →  prediction service  →  Overview  →  PO detail  →  Factories  →  Upload  →  Assistant
```

Then the **Should** tier: Alerts → Shipment forecast → Factory performance.

---

## Day-by-day schedule

| Day | Date (2026) | Weekday | Focus | Tasks |
|---|---|---|---|---|
| 1 | 3 Oct | Sat | Scaffold + master data | T-01, T-02 |
| 2 | 4 Oct | Sun | Domain models + migrations | T-03 |
| 3 | 5 Oct | Mon | Seed + parity harness | T-04, T-05 |
| 4 | 6 Oct | Tue | Prediction engine (calendar + core) | T-06, T-07 |
| 5 | 7 Oct | Wed | Prediction engine (cost, recs, what-if) — **engine parity green** | T-08, T-09 |
| 6 | 8 Oct | Thu | App shell + Overview | T-10, T-11 |
| 7 | 9 Oct | Fri* | Overview finish + PO list — **headline numbers reproduced** | T-12, T-13 |
| 8 | 10 Oct | Sat | PO detail + what-if — **hero what-if works** | T-14, T-15 |
| 9 | 11 Oct | Sun | Factories + Upload | T-16, T-17 |
| 10 | 12 Oct | Mon | Assistant — **3 demo questions pass** | T-18, T-19 |
| 11 | 13 Oct | Tue | Should tier + demo hardening | T-20, T-21, T-22, T-23 |
| 12 | 14 Oct | Wed | **Code freeze + full dry run** | T-24 |
| 13 | 15 Oct | Thu | **CEO demo** | T-25 |

\* Friday = Bangladesh weekend; treated as a working dev day for this sprint (see Calendar note).

---

## Milestones

| M | Milestone | Day | Proven by |
|---|---|---|---|
| MS-1 | **Engine parity green** | 7 Oct (T-09) | `test_engine_matches_answer_key`, `test_kpis_match_answer_key`, `test_hero_whatif`, `test_calendar`, `test_pure_service` all pass |
| MS-2 | **Overview reproduces the headline numbers** | 9 Oct (T-12) | `test_overview_kpis` — 412 open POs, 1,900,020 pcs, USD 18,601,449 FOB, October on-time 86.25%, value at risk USD 2,400,006, top-3 70%, air exposure USD 539,720 |
| MS-3 | **Hero what-if works on screen** | 10 Oct (T-15) | `test_hero_whatif` green + manual: PO 71010305 current 7 Nov / slip 9 → +6 M/C (13→19) + Fridays 16 & 23 Oct → 29 Oct, on time, air USD 0, USD 38,016 avoided |
| MS-4 | **Assistant 3 demo questions pass** | 12 Oct (T-19) | `test_assistant_golden_questions` (30/30; 3/3 demo exact) |
| MS-5 | **Should tier delivered** | 13 Oct (T-22) | Alerts feed + both Should reports render from snapshots and tie to the answer key |
| MS-6 | **Freeze + dry run clean** | 14 Oct (T-24) | Full suite green, 3-minute path timed end to end incl. fallback |

---

## Tasks

### Day 1 — Sat 3 Oct — Scaffold + master data

**T-01 — Project scaffold and base shell/theme**
- FR: FR-DASH (shell), FR-ACCT (login plumbing)
- Deps: —
- Scope: Django 5.2 project; the ten apps (`accounts`, `masterdata`, `orders`, `factories`,
  `production`, `predictions`, `alerts`, `reports`, `assistant`, `dashboard`) plus a pure `services/`
  package. `docker-compose` (Django, PostgreSQL 16 / psycopg 3, django-q2 worker, ChromaDB).
  Tailwind CLI build; dark + light theme tokens as `[data-theme]` CSS variables copied from the design
  system (surface, border, text, accent, status.\*, stage.\*) into `globals.css` and `tailwind.config`.
  Vendored JS (Alpine, HTMX, ECharts) — no CDN at demo time. Base layout: header with freshness pill,
  sidebar, ⌘K palette shell, theme toggle. `settings.DEMO_TODAY = 2026-10-15`.
- Acceptance: `test_shell_boots` (app starts, `/healthz/` returns `{status, as_of}`), `test_theme_tokens`
  (both themes expose the token set); `docker-compose up` serves the base shell in both themes.

**T-02 — Master data models + Django admin**
- FR: FR-MASTER
- Deps: T-01
- Scope: `Department`, `Season`, `Factory`, `FactoryMachine`, `HolidayCalendar`, `EngineParameter`,
  `TATemplate`, `TAMilestoneDef`, `AlertRule`. Register all in `/admin/` (the only settings surface in
  Phase 0). `EngineParameter` defaults = answer-key `Parameters` sheet (engine §8): `air_usd_per_kg` 6.00,
  `sea_usd_per_kg` 0.50, `rate_window_wd` 7, `flow_limit_days` 1.5, `yarn_to_knit_days` 2,
  `knit_mc_minutes_per_day` 1020, stage lags (linking 1.0; mending/washing/ironing/packing 0.5), score
  caps 50/20/15/10/5, band cut-offs 25/50/75, `slip_forces_critical` 7, freshness 3/5, prob clamp
  0.02/0.98.
- Acceptance: `test_masterdata_admin_registered`, `test_engine_parameter_defaults` (defaults match §8);
  manual: all models editable in admin.

### Day 2 — Sun 4 Oct — Domain models + migrations

**T-03 — Core domain models + migrations**
- FR: FR-ORD, FR-FAC, FR-PROD, FR-PRED, FR-ALERT, FR-AI, FR-ACCT
- Deps: T-02
- Scope: all models in `data/data-model.md`: `Style`, `PurchaseOrder`, `POLine`, `POLineSize`,
  `TAMilestone`; `UploadBatch`, `DailyProduction`, `Inspection`, `Shipment`; `PredictionSnapshot`,
  `PredictionRun`, `FactoryStat`; `Alert`; `Comment`; `Conversation`, `ChatMessage`, `TokenUsage`;
  `UserProfile`, `AuditLog`. All indexes, `unique_together` constraints and the one-of
  (`purchase_order` / `factory`) check on `Comment`. `is_open` maintained on `Shipment` ingest. Money as
  `Decimal`; rates/weights as `Decimal` (never float). Django groups Admin/Management/Merchandiser/QA.
- Acceptance: `test_migrations_apply_clean`, `test_model_constraints` (unique_together + Comment check +
  `is_open` toggle), `test_decimal_fields` (no float on money/rate/weight).

### Day 3 — Mon 5 Oct — Seed + parity harness

**T-04 — `seed_demo` management command**
- FR: FR-MASTER, FR-ORD, FR-FAC, FR-PROD, FR-PRED, FR-AI
- Deps: T-03
- Scope: `seed_demo` loads the pilot-shaped dataset deterministically: 22 factories, 1,287 total POs
  (412 open), 1,900,020 open pcs, USD 18,601,449 open FOB; 12-month shipped history for OTD; daily
  production to 14 Oct; inspections; T&A milestones (11/PO). Seed users + groups + four persona logins.
  Fabricate the clearly-fictional English KB docs for ChromaDB (quality manual, T&A standards, 22
  factory profiles, audit notes, PO comments — PRD A-08). Hero PO **71010305** and donor **71009573**
  seeded exactly per A-11/A-12. (Prediction snapshots are written by T-09's seed run, not here.)
- Acceptance: `test_seed_counts` (22 / 1287 / 412 / 1,900,020 / 18,601,449), `test_seed_hero_present`
  (71010305 + 71009573 with the A-12 attributes), `test_seed_idempotent` (re-run = same data).

**T-05 — Answer-key parity test harness**
- FR: FR-PRED (test infrastructure)
- Deps: T-04
- Scope: fixtures that load `00_Answer_Key.xlsx` sheets (`Open PO Predictions`, `KPIs`, `Hero What-if`,
  `Parameters`, `Weekly Outlook`) into comparable structures; rounding-aware comparison helpers. Stubs for
  `test_engine_matches_answer_key`, `test_kpis_match_answer_key`, `test_hero_whatif` (xfail until T-09).
- Acceptance: `test_answer_key_loads` (every sheet parses); the three parity stubs are collected and
  xfail-marked.

### Day 4 — Tue 6 Oct — Prediction engine (calendar + core)

**T-06 — Working-day calendar**
- FR: FR-PRED
- Deps: T-03 (reads `HolidayCalendar`, `EngineParameter`)
- Scope: pure functions `is_working_day`, `wd_between` (half-open `[a,b)`), `nth_wd`, `next_wd` with
  Friday-only weekend + holiday calendar + what-if overtime days (engine §1).
- Acceptance: `test_calendar` (hand-checked dates incl. overtime & holidays; `wd_between(15 Oct, 29 Oct)`
  = 12 with Fridays 16 & 23 excluded).

**T-07 — Prediction engine core (rates, projection, scoring, bands)**
- FR: FR-PRED
- Deps: T-06
- Scope: pure-Python `services/prediction/` (no ORM/view imports). Stage rates with 7-WD weighted window
  (§2); in-production projection with flow-limit/starvation, stage lags, bottleneck, completion N,
  `projected_exfactory`, slack, slip (§3); pre-production projection (§4); five-component risk score (§5);
  bands with slip/Late overrides (§6). Decimal throughout; rounding only at output.
- Acceptance: `test_pure_service` (engine imports no Django ORM/view symbols); unit tests for projection,
  scoring and band overrides on the hero worked example (bottleneck Linking, rate 411.1, required 680,
  N 19, available 12, slack −7, projected 7 Nov, slip 9, score 76, Critical).

### Day 5 — Wed 7 Oct — Prediction engine (cost, recommendations, what-if) → **MS-1**

**T-08 — Probability, VaR, air exposure, recommendations, what-if, donor, run writer**
- FR: FR-PRED
- Deps: T-07
- Scope: on-time probability from the factory 12-month slip distribution clamped 0.02–0.98 (§7); value at
  risk; air-freight exposure `qty × kg/pc × (6.00−0.50)`; recommendation rules incl. auto donor selection
  (hero → 71009573) and the linking-machine / Friday-overtime what-if that re-runs `project()` (§7, §10).
  ORM adapter: load rows → dataclasses → write `PredictionRun` + `PredictionSnapshot` + `FactoryStat`
  with `params_hash`. Wire `seed_demo` to emit one `seed`-trigger run as of 15 Oct 2026 (A-04).
- Acceptance: `test_whatif_hero` (all six `Hero What-if` rows: current 7 Nov/9; +6 M/C → 1 Nov/3; 2
  Fridays → 4 Nov/6; both → 29 Oct/0 on time, air avoided USD 38,016; donor 71009573 stays early);
  `test_air_exposure_hero` (USD 38,016); `test_donor_autoselect` (resolves to 71009573).

**T-09 — Engine parity milestone (MS-1)**
- FR: FR-PRED
- Deps: T-08, T-05
- Scope: run the full engine over the seed and reconcile to the answer key; un-xfail the parity tests.
- Acceptance: **`test_engine_matches_answer_key`** (every `Open PO Predictions` row within rounding:
  band, score, projected ex-factory, slip, bottleneck, rates, probability, VaR, air exposure),
  **`test_kpis_match_answer_key`** (open counts, October on-time 86.25%, VaR USD 2,400,006, top-3 share
  70%, air exposure USD 539,720, band counts On track 354 / Watch 10 / At risk 28 / Critical 13 / Late 7,
  weekly outlook), **`test_hero_whatif`** — all green. Milestone **MS-1**.

### Day 6 — Thu 8 Oct — App shell + Overview

**T-10 — App shell, auth, status, ⌘K, write-scope enforcement**
- FR: FR-ACCT, FR-DASH
- Deps: T-09
- Scope: `/login/`, `/logout/`, `/healthz/`, `/status/` (as_of, reports_today{received,expected},
  factories_missing[], alerts_open, user{name,role}), `/palette/search/` (⌘K: PO/factory jumps + "Ask the
  assistant"). Header freshness pill, theme toggle (persisted), sidebar with alert badge. Queryset-level
  write-scope base (owner / Management / Admin) for use by later write endpoints.
- Acceptance: `test_status_json` (payload shape + as_of), `test_cmdk_search` (PO/factory hits),
  **`test_role_write_scope`** (read-all for all four groups; write scoped to ownership — enforced in
  querysets, not just templates).

**T-11 — Executive Overview (structure + KPIs)**
- FR: FR-DASH
- Deps: T-10
- Scope: `/` overview page; `kpis_partial` (6 cards: Open POs, Open pcs, Open FOB, October on-time %,
  Value at risk, Air-freight exposure — each key/value/unit/sub/delta/note/spark/drill); AI briefing
  partial (text, generated_at, inputs, why[], sources[]); top-10 at-risk table; factory leaderboard;
  dept/gauge split. Optional `month`/`season`/`dept` HTMX filters. All numbers from
  `services.metrics.portfolio_kpis`.
- Acceptance: `test_overview_kpis` (asserts the six cards reproduce the headline numbers), `test_briefing_sources`
  (briefing carries as_of + sources).

### Day 7 — Fri 9 Oct — Overview finish + PO list → **MS-2**

**T-12 — Overview charts (outlook + heatmap) — headline numbers milestone (MS-2)**
- FR: FR-DASH
- Deps: T-11
- Scope: `/overview/outlook.json` (8-week stacked bar on_track/watch/at_risk/critical/late),
  `/overview/heatmap.json` (factory × 8-week cells 0–4, −1 = no update; 18 of 22 reported, missing
  SLM/OKH/HMR/PBB striped). Freshness honesty: every figure shows `as_of`.
- Acceptance: **`test_overview_kpis`** green on all headline values (412 / 1,900,020 / USD 18,601,449 /
  86.25% / USD 2,400,006 / top-3 70% [GRL 774,059 / IRB 477,578 / SLM 428,400] / air USD 539,720);
  `test_heatmap_noupdate` (4 striped rows, SLM/OKH/HMR/PBB = −1). Milestone **MS-2**.

**T-13 — Purchase Orders list**
- FR: FR-ORD
- Deps: T-10
- Scope: `/pos/` + `/pos/table/` (HTMX rows + `counts_by_status` chips). Server-side filters
  (dept[], season[], factory[], gauge[], status[], exf_month[], merchandiser[], q), default sort
  `risk_score desc` (also slip/exf/fob), cursor pagination. Row fields per handoff incl. inline AI note +
  as_of. `/pos/export.xlsx`.
- Acceptance: `test_po_list_filters` (each filter + sort + cursor paginate correctly; band chips sum to
  412), `test_po_export` (xlsx matches the filtered set).

### Day 8 — Sat 10 Oct — PO detail + what-if → **MS-3**

**T-14 — PO detail + T&A Gantt + stage curves**
- FR: FR-ORD
- Deps: T-13
- Scope: `/pos/<po_no>/` detail (header, prediction block, risk drivers, recommendation cards),
  `/pos/<po_no>/ta/` (ECharts Gantt, 11 milestones with forecast stage bars — A-10),
  `/pos/<po_no>/curves.json` (stage cum curves + forecast + required line + p10/p90 band + markers:
  today, exf, predicted). `/pos/<po_no>/comments/` (write: PO owner / Management / Admin).
- Acceptance: `test_po_detail_hero` (71010305 shows predicted 7 Nov, slip 9, Critical, score 76, prob 2%;
  drivers yarn/linking per engine), `test_po_comment_scope` (write scope enforced).

**T-15 — What-if partial — hero what-if milestone (MS-3)**
- FR: FR-ORD, FR-PRED
- Deps: T-14, T-08
- Scope: `/pos/<po_no>/whatif/` (POST, read-only, writes no snapshot) — linking-machines slider + Friday
  overtime days → `{projected_exfactory, slip_days, on_time_probability, air_cost_usd}` via
  `services.prediction.whatif` (same engine). "Apply recommendation" preset: machines 13→19, overtime
  Fridays 16 & 23 Oct.
- Acceptance: **`test_hero_whatif`** green + manual: apply plan → 29 Oct, on time, air USD 0, USD 38,016
  avoided; drag machines back to 13 → recomputes live to 7 Nov / slip 9. Milestone **MS-3**.

### Day 9 — Sun 11 Oct — Factories + Upload

**T-16 — Factories list + detail**
- FR: FR-FAC
- Deps: T-10
- Scope: `/factories/` + `/factories/table/` (scorecards: code, name, location, machines_by_gauge,
  knit_load_pct, otd_pct, aql_pass_pct, reporting_compliance_pct, reported_today, open_pos, open_pcs,
  exposure_usd, status, AI note). `/factories/<code>/` detail (order book, 14-day daily output via
  `output.json`, inspections, certificates, AI summary). `/factories/<code>/notes/` (write scope).
  All from `services.metrics.factory_scorecard/factory_detail`.
- Acceptance: `test_factory_scorecard` (GRL exposure/top-3 contribution, knit_load_pct, OTD tie to answer
  key), `test_factory_note_scope`.

**T-17 — Daily Updates (upload + async ingest)**
- FR: FR-PROD
- Deps: T-03, T-09
- Scope: `/uploads/` home (drop zone, reporting status, history, templates); `upload_create` POST
  (write: Merchandiser / Management / Admin) creates `UploadBatch`, enqueues `ingest_file` on django-q2;
  `batch_status_partial` poll (status, rows_accepted, warnings[], errors[], detected_factory/date);
  `reporting_status_partial` (per-factory reported/late/missing); `templates_list`. Detect
  kind+factory+date from workbook; per-row validation; a file with errors is rejected as a batch (no
  partial writes); a clean upload triggers an `upload` prediction run. Stage the demo file
  `DPR_PBB_2026-10-14.xlsx` (clean).
- Acceptance: **`test_upload_rejects_bad_batch`** (any row error → whole batch rejected, zero writes),
  `test_upload_clean_pbb` (DPR_PBB_2026-10-14.xlsx ingests → reported moves 18→19 of 22, no headline
  change), `test_upload_scope` (QA cannot upload).

### Day 10 — Mon 12 Oct — Assistant → **MS-4**

**T-18 — Assistant backend (SSE, tools over `services/`)**
- FR: FR-AI
- Deps: T-09, T-10
- Scope: `/assistant/stream/` (async SSE: step, delta, chart, table, sources, followups, error, done);
  tool catalogue calling `services/` only (numbers), ChromaDB for citations only; threads
  (`/assistant/threads/`), `/assistant/export.xlsx`. Conversations + `TokenUsage` persisted. Scope
  enforced per user.
- Acceptance: `test_assistant_tools_use_services` (no number originates outside `services/`),
  `test_assistant_sources` (every answer carries sources with as_of).

**T-19 — Assistant UI + golden-question eval — demo-questions milestone (MS-4)**
- FR: FR-AI
- Deps: T-18
- Scope: `/assistant/` page + `/assistant/panel/` slide-over; ⌘K "Ask the assistant" wiring; render
  steps → text → chart/table → sources. 30-question golden eval + the 3 demo questions (PRD A-09).
- Acceptance: **`test_assistant_golden_questions`** (30/30 return expected; 3/3 demo exact — October
  misses by factory; why 71010305 is late + fastest fix; October on-time 86.25% + where USD 2.4M
  concentrates). Milestone **MS-4**.

### Day 11 — Tue 13 Oct — Should tier + demo hardening → **MS-5**

**T-20 — Alerts feed**
- FR: FR-ALERT
- Deps: T-09
- Scope: `/alerts/` + `/alerts/feed/` (filter kind/severity/state) derived from snapshots + reporting via
  `AlertRule`; `ack` / `assign` / `snooze` with write scope; dedupe across runs. Kinds: po_critical,
  factory_missed_report, yarn_late, inspection_failed, po_at_risk, compliance.
- Acceptance: `test_alerts_from_snapshots` (hero → po_critical; SLM/OKH/HMR/PBB → factory_missed_report),
  `test_alert_action_scope` (ack own-only; assign Management/Admin only).

**T-21 — Shipment forecast report**
- FR: FR-REP
- Deps: T-09
- Scope: `/reports/shipment-forecast/` (+ `.json` chart, `?export=xlsx`): 8-week rows period, pos, pcs,
  fob_usd, on_time_pct, at_risk_usd — matching the answer-key Weekly Outlook.
- Acceptance: `test_shipment_forecast_matches_outlook`.

**T-22 — Factory performance report (MS-5)**
- FR: FR-REP
- Deps: T-16
- Scope: `/reports/factory-performance/` (+ export): factory scorecard rows, OTD, AQL, exposure.
- Acceptance: `test_factory_performance_report` (rows tie to `FactoryStat`/answer key). Milestone **MS-5**.

**T-23 — Demo hardening + AI fallback**
- FR: FR-AI, FR-DASH
- Deps: T-19, T-12, T-15
- Scope: pre-store the 3 demo-question answers (`ai/assistant.md`) for the OpenAI-slow fallback; bookmark
  hero PO 71010305; pre-set dark theme; stage `DPR_PBB_2026-10-14.xlsx`; confirm offline (vendored JS, no
  CDN). Align with `plan/demo-script.md`.
- Acceptance: `test_assistant_fallback` (with OpenAI disabled, the 3 demo questions return the pre-stored
  answers verbatim); manual: 3-minute path runs offline.

### Day 12 — Wed 14 Oct — Code freeze + full dry run (MS-6)

**T-24 — Code freeze + full dry run**
- FR: all
- Deps: T-01…T-23
- Scope: **code freeze.** Full pytest suite green (all `test_*_match*`/scope/engine/overview/whatif/
  assistant/upload tests). Fresh `seed_demo` on the demo database, single `seed` run as of 15 Oct 2026.
  Full 3-minute dry run end to end **including the fallback path**, following `plan/demo-script.md` and the
  demo-day freeze in `tech/deployment.md`. Fix only blockers; no new scope.
- Acceptance: whole suite green; dry run timed ≤ 3 min; fallback rehearsed. Milestone **MS-6**.

### Day 13 — Thu 15 Oct — CEO demo

**T-25 — CEO demo**
- FR: all (G1)
- Deps: T-24
- Scope: run `plan/demo-script.md` click-path on the seeded database, English only. Fallback ready.
- Acceptance: the click-path reproduces the answer-key numbers live, including the hero what-if.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **OpenAI latency / outage during the live demo** | Assistant step stalls on stage | Pre-stored answers for the 3 demo questions (T-23, `ai/assistant.md`); demo script FALLBACK section; vendored JS so the app runs offline. |
| **Data drift** (seed or engine change silently moves a number) | Numbers stop matching the answer key | Parity tests are the gate: `test_engine_matches_answer_key`, `test_kpis_match_answer_key`, `test_hero_whatif` run in CI and at freeze (T-09, T-24). `params_hash` per run makes inputs auditable. |
| **Scope creep** (Later items pulled into the sprint) | Must path slips past 14 Oct | Strict tiers (PRD §8): Must critical path first, Should only after MS-4, Later explicitly excluded. Freeze on 14 Oct. |
| **Engine parity slips past 7 Oct** | Every downstream screen blocked | Engine is the earliest critical-path item (T-06…T-09); parity harness (T-05) ready before the engine so failures surface immediately. |
| **Ingest edge cases on upload** | Demo upload step fails | Batch-reject-on-error (no partial writes) + staged clean `DPR_PBB_2026-10-14.xlsx`; `test_upload_rejects_bad_batch` + `test_upload_clean_pbb`. |
| **Theme/offline assets fail on demo machine** | Dark theme or charts blank | Dark theme pre-set and vendored JS verified in the 14 Oct dry run (T-23, T-24). |
