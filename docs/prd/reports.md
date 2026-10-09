# AI Pulse — Reports & Analytics (PRD)

**App:** `reports` · **FR prefix:** `FR-REP` · **Tier:** Should (FR-REP-010/020/030) + Later (FR-REP-040)
**As of:** 3 Oct 2026 · **Depends on:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`, `ai/prediction-engine.md`

> Canon: `sample_data/` + `00_Answer_Key.xlsx` win on every number; `design/` wins on layout and interaction.
> Reports **read the latest prediction snapshot and factory stats** via `services/` — they never recompute
> the engine on request (`prediction-engine.md §9`). Every figure carries the run's `as_of`. The shipment
> forecast **must match the answer-key Weekly Outlook** exactly (`prediction-engine.md §11`
> `test_kpis_match_answer_key`).

---

## 1. Purpose & design screen(s)

Reports give the office two prepared views on top of the daily numbers: an 8-week **shipment forecast**
(what ships, when, for how much, how much on time, how much at risk) and a **factory performance**
scorecard (OTD, AQL, load, exposure). Both are exportable to Excel for circulation. A set of deeper
analytics (T&A delay, inspection, on-time trend, plan-vs-actual, prediction accuracy) is scoped as **Later**.

Design screen (from `design/Karbar Pulse Handoff.dc.html` › "Reports & Analytics"): a reports home that
links to each report; the shipment forecast and factory performance tables with a chart and an export
control. The handoff also lists the Later reports' shapes, carried here as intent.

---

## 2. User stories

- **FR-REP-010 — Shipment forecast report.** As Management / Shipping, I want an 8-week forecast by period —
  POs, pieces, FOB USD, on-time %, at-risk USD — so that I can plan bookings and see where value concentrates.
- **FR-REP-020 — Factory performance report.** As Management / QA, I want a factory scorecard report (OTD,
  AQL, load, reporting, exposure), so that I can rank factories and prepare factory conversations.
- **FR-REP-030 — Export (xlsx).** As any user, I want both reports exportable to Excel, so that I can share
  them outside the app.
- **FR-REP-040 — (Later) deeper analytics.** As the office, I want T&A delay, inspection, on-time trend,
  plan-vs-actual and prediction-accuracy reports, so that trends and model quality are visible over time.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-REP-010 Shipment forecast report
- **Given** the latest run, **when** `/reports/shipment-forecast/` loads, **then** it shows 8 weekly rows,
  each with `period`, `pos`, `pcs`, `fob_usd`, `on_time_pct`, `at_risk_usd`, and every row carries the run's
  `as_of`.
- **Given** the demo seed as of 15 Oct 2026, **when** the report renders, **then** the first two rows match
  the answer-key Weekly Outlook exactly:
  - **10–16 Oct:** **13** POs · **57,072** pcs · **503,790** FOB (USD).
  - **17–23 Oct:** **37** POs · **183,096** pcs · **1,817,169** FOB (USD).
- **Given** the figures are derived, **when** they are computed, **then** `pos` / `pcs` / `fob_usd` aggregate
  the POs whose projected (or planned) ex-factory falls in each weekly period from the snapshot, `on_time_pct`
  from predicted on-time (slip ≤ 0) within the period, and `at_risk_usd` from FOB of POs banded At risk /
  Critical / Late — all read from `PredictionSnapshot`, never recomputed (`prediction-engine.md §9`).
- **Given** the report, **when** the chart `.json` is requested, **then** it returns the same weekly series
  as the table (one source of numbers), consistent with the Overview's 8-week outlook (`FR-DASH`).

### FR-REP-020 Factory performance report
- **Given** the latest run, **when** `/reports/factory-performance/` loads, **then** it shows one row per
  factory (22 in the seed) with the scorecard fields: code, name, location, machines-by-gauge,
  `knit_load_pct`, `otd_pct`, `aql_pass_pct`, `reporting_compliance_pct`, `reported_today`, `open_pos`,
  `open_pcs`, `exposure_usd`, status — read from `FactoryStat` / `services.metrics.factory_scorecard`.
- **Given** OTD and AQL, **when** they are shown, **then** OTD is the factory's last-12-month on-time share
  from the Shipment Log and AQL is the 90-day pass rate (`prediction-engine.md §5, §7`;
  `data-model.md › FactoryStat`), each with the run's `as_of`.
- **Given** the demo values, **when** a factory is flagged no-update, **then** its `reported_today` shows the
  quiet state consistent with the alerts feed (`FR-ALERT`) and `/status/` (`FR-ACCT-060`).

### FR-REP-030 Export (xlsx)
- **Given** either report, **when** the user requests `?export=xlsx`, **then** `services.export` returns an
  `.xlsx` whose rows and totals equal the on-screen table (no re-derivation divergence), and an `export`
  `AuditLog` row is written (`FR-ACCT-050`).
- **Given** the shipment-forecast export, **when** it is opened, **then** the 10–16 Oct and 17–23 Oct rows
  carry 13 / 57,072 / 503,790 and 37 / 183,096 / 1,817,169 respectively.
- PDF export is **Later** (`urls-and-views.md`: "xlsx; pdf Later").

### FR-REP-040 (Later) deeper analytics
Scoped as Later (`PRD.md §8`), served under `/reports/<kind>/` → `report_generic` when built. Brief intent:
- **T&A delay** — rows `{milestone, pos_late, avg_delay_days, top_factories}`: which milestones slip most and
  where.
- **Inspection** — totals, pass rate, failed count, defect share `{type, share_pct}`.
- **On-time trend** — weekly `{week, predicted_pct, band_lo, band_hi}` against a target line.
- **Plan vs actual** — per stage `{stage, plan_pcs, actual_pcs}`.
- **Prediction accuracy** — per month `{pos, mae_days, within_2d_pct}`, computed from daily snapshots once
  more than one run exists (Phase 0 seeds a single run, so accuracy history is empty; `prediction-engine.md
  §9`, ASSUMPTION A-04).

---

## 4. Design components

- **Reports home** — cards / links to each report.
- **Shipment forecast** — a Table of the 8 weekly rows plus a stacked BarChart (same series as the Overview
  outlook); export control.
- **Factory performance** — a Table of factory scorecard rows (sortable); export control.
- **Export** — xlsx download button (pdf Later).
- Later reports reuse Table + the design's chart types (LineChart with Area band for on-time trend, etc.).

---

## 5. Data read + URLs / partials

**Models (`data-model.md`):** `PredictionSnapshot` (band, slip, projected / planned ex-factory, FOB, VaR),
`FactoryStat` (OTD, AQL, load, compliance, exposure, reporting), `PurchaseOrder` / `Factory` for labels,
`Shipment` (for OTD history). All access via `services.metrics` and `services.export`; no engine recompute.

**URLs / views (`urls-and-views.md`):**
- `GET /reports/` → `reports_home` → `reports/home.html` (read: all).
- `GET /reports/shipment-forecast/` → `shipment_forecast` → `reports/shipment_forecast.html` (+ `.json`
  chart, `?export=xlsx`) (read: all).
- `GET /reports/factory-performance/` → `factory_performance` → `reports/factory_performance.html`
  (+ export) (read: all).
- `GET /reports/<kind>/` → `report_generic` (Later): ta-delay, inspection, on-time-trend, plan-vs-actual,
  accuracy (read: all).

---

## 6. Empty / error / stale-data states

- **No run yet:** if no `PredictionRun` exists, the report shows "No prediction run yet — upload a daily
  file to generate numbers" rather than zeros presented as real.
- **Empty period:** a week with no POs shows 0 POs / 0 pcs / 0 FOB and a blank (not 100%) on-time % with a
  "no POs this period" note, so an empty week is not read as perfect on-time.
- **Stale run:** every row carries the latest run's `as_of`; if that run is old, the report shows the old
  `as_of` honestly (M4) rather than implying it is today's.
- **Export failure:** a failed xlsx build returns an error message and writes no `export` audit row; the
  on-screen table is unaffected.
- **Later reports:** the T&A delay / inspection / on-time-trend / plan-vs-actual / accuracy routes show a
  "Later" placeholder until built; prediction accuracy is empty while only one run exists (A-04).

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read shipment forecast | ✓ | ✓ | ✓ | ✓ |
| Read factory performance | ✓ | ✓ | ✓ | ✓ |
| Export xlsx | ✓ | ✓ | ✓ | ✓ |
| Read Later reports (when built) | ✓ | ✓ | ✓ | ✓ |

All reports are read-only for all four groups (read the whole book; ASSUMPTION A-05). Exports are audited
(`FR-ACCT-050`). There are no write actions in this module.
