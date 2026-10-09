# AI Pulse — Factories module PRD (`FR-FAC`)

**App:** `factories` · **FR prefix:** `FR-FAC` · **Tier:** Must for 15 Oct
**Source of truth:** `sample_data/` + `00_Answer_Key.xlsx` for all numbers (PRD A-01); `design/` for
layout/components only. Where the design handoff's illustrative data disagrees (probability-based status,
40% air split), the answer key wins.

---

## 1. Purpose & design screens

The Factories module is the per-supplier view of the book: one scorecard row per factory on the list, and
a detail page that assembles everything needed for a factory conversation (load, on-time history, AQL,
the factory's open order book, recent daily output, inspections, certificates, and an AI summary).

All figures on both screens are **read from the latest `PredictionRun`** (its `FactoryStat` rows and the
`PredictionSnapshot` rows of the factory's open POs); nothing is recomputed on request (see `FR-PRED-030`).
Every figure carries the run's `as_of`.

Design screens (from `design/Karbar Pulse Handoff.dc.html`):
- **Factories · list** — scorecard rows.
- **Factory detail** — header + KPIs, AI summary, order book, daily output, inspections, certificates.

Canonical worked example used throughout this PRD — **Greyloom Knitwear Ltd. (`GRL`)**: Konabari,
Gazipur; knitting gauges 5GG / 7GG / 12GG; OTD 68.1%; AQL pass 95%; 52 open POs; value at risk
USD 774,059 (the top factory by value at risk, part of the top-3 share of 70.0%). GRL is the hero PO's
factory (PO `71010305`, 7GG Lambswool V-neck Cardigan, 9,600 pcs, FOB USD 158,400). GRL **did** report
today (it is not among the four missing factories).

---

## 2. User stories

- **FR-FAC-010 — Factory list scorecards.** As a **merchandiser or manager**, I want one scorecard per
  factory showing code, name, location, machines by gauge, knitting load, OTD, AQL pass, reporting
  compliance, whether it reported today, open POs/pcs, exposure, status and a one-line AI note, so I can
  rank the whole supply base in one scan.
- **FR-FAC-020 — Factory detail header + KPIs.** As a **merchandiser or manager**, I want a factory
  header with its identity and the same KPIs as the list row plus total machines, so I have the full
  picture before a factory call.
- **FR-FAC-030 — Factory AI summary.** As a **manager**, I want a short English summary of the factory's
  current state with an `as_of`, so I can read the situation without assembling it myself.
- **FR-FAC-040 — Order book tab.** As a **merchandiser**, I want the factory's open PO rows (same fields
  as the PO list), so I can see which orders drive its exposure and open each one.
- **FR-FAC-050 — Daily output chart.** As a **merchandiser**, I want a 14-day chart of daily output by
  production stage, so I can see whether the floor is keeping pace and where it is stalling.
- **FR-FAC-060 — Inspections list.** As a **QA head**, I want the factory's recent inspections (PO, date,
  type, result, defect summary), so I can see quality's contribution to its risk.
- **FR-FAC-070 — Certificates.** As a **manager**, I want the factory's certifications with validity and
  status, so compliance is visible alongside delivery.
- **FR-FAC-080 — Factory notes.** As the **factory's owner (or Management/Admin)**, I want to add notes
  to a factory, so the next person has the context; other roles read them but cannot write.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-FAC-010 Factory list scorecards
- **Given** the seeded run as of 15 Oct 2026, **when** I open `/factories/`, **then** I see 22 scorecard
  rows, each with: `code`, `name`, `area`/`district` (location), `machines_by_gauge`, `knit_load_pct`,
  `otd_pct`, `aql_pass_pct`, `reporting_compliance_pct`, `reported_today` (status + time), `open_pos`,
  `open_pcs`, `exposure_usd`, `status`, and an AI note with `as_of`.
- **Given** the GRL row, **when** it renders, **then** it shows location "Konabari, Gazipur", gauges
  5/7/12, OTD **68.1%**, AQL **95%**, open POs **52**, and value at risk **USD 774,059**.
- **Given** the four factories that did not report today, **when** the list renders, **then** `SLM`, `OKH`,
  `HMR` and `PBB` show `reported_today = missing/late` (a "No update" stripe/pill), and the other 18 show
  reported today — totalling **18 of 22 reported** (SLM last reported 12 Oct, OKH 11 Oct, HMR and PBB
  13 Oct).
- **Given** any scorecard number, **when** I inspect it, **then** it equals the corresponding `FactoryStat`
  field from the latest run and carries that run's `as_of`; it is never recomputed on the request.

### FR-FAC-020 Factory detail header + KPIs
- **Given** `/factories/GRL/`, **when** it loads, **then** the header shows code `GRL`, name "Greyloom
  Knitwear Ltd.", location "Konabari, Gazipur", gauges 5GG/7GG/12GG, and the same KPIs as the list row
  **plus `machines_total`** (the sum across `FactoryMachine` rows).
- **Given** a factory code that does not exist, **when** I request it, **then** I get HTTP 404.

### FR-FAC-030 Factory AI summary
- **Given** the GRL detail page, **when** the AI summary renders, **then** it is English prose with a
  visible `as_of` equal to the latest run's `as_of` (15 Oct 2026 for the seed), and it does not state any
  number that contradicts the factory's `FactoryStat` (e.g. it must not claim GRL is on track given value
  at risk USD 774,059).

### FR-FAC-040 Order book tab
- **Given** GRL has 52 open POs, **when** I open the order-book tab, **then** I see 52 PO rows using the
  PO-list row shape (po_no, style, dept, season, band/status, gauge, yarn, qty, fob/pc, fob_value,
  exf_date, slip_days, on_time_prob, risk_score, inline AI note), each linking to its PO detail
  (`FR-ORD`).
- **Given** PO `71010305` is open at GRL, **when** the order book renders, **then** it appears with band
  **Critical**, risk score **76**, slip **9**, projected ex-factory **7 Nov 2026**.

### FR-FAC-050 Daily output chart
- **Given** `/factories/GRL/output.json`, **when** the chart loads, **then** it returns an ECharts option
  with one line per stage (`knitting`, `linking`, `trimming_mending`, `washing`, `ironing`, `packing`)
  over the last 14 calendar days ending at the factory's `last_report_date`, plotting `DailyProduction.day_pcs`.
- **Given** a stage with no output in the window, **when** the chart renders, **then** that stage's line
  shows 0 for those days (not a gap), consistent with the engine's "missing day = 0" rule.

### FR-FAC-060 Inspections list
- **Given** the GRL detail page, **when** the inspections list renders, **then** each row shows `po_no`,
  `inspection_date`, `inspection_type` (Inline / Pre-final / Final / Final re-inspection), `result`
  (Pass / Fail) and a defect summary (`main_defect` + counts), newest first.
- **Given** a Fail result, **when** the row renders, **then** it is visually flagged so QA can find failed
  lots quickly.

### FR-FAC-070 Certificates
- **Given** the GRL detail page, **when** the certificates block renders, **then** it lists each
  certification parsed from `Factory.certifications` (e.g. amfori BSCI, WRAP) with a `valid_to` date and a
  `status` (Valid / Expiring / Expired). BSCI rating and last social-audit date are shown alongside.
- **Note:** Phase 0 has no dedicated Certificate model; `name` comes from `Factory.certifications`,
  `bsci_rating`, `last_social_audit`, and `valid_to`/`status` are seeded/derived values (see §5).

### FR-FAC-080 Factory notes
- **Given** I am GRL's owner (`Factory.merchandiser`), Management or Admin, **when** I POST a note to
  `/factories/GRL/notes/`, **then** a `Comment` is created with `factory=GRL`, `author=me`, and the notes
  partial re-renders with my note at the top.
- **Given** I am a merchandiser who does **not** own GRL (or a QA user), **when** I attempt to POST a
  note, **then** the write is rejected (403 / form not served); I can still read existing notes.

---

## 4. Design components

From the design system / handoff (shadcn + ECharts; the handoff names Recharts for the prototype, the app
serves ECharts options per `tech/urls-and-views.md`):
- **List:** Card-based scorecard grid; status Badge variants (On track / Watch / At risk / Critical / Late
  / No-update stripe); reporting pill (reported / late / missing) with time; machines-by-gauge chip group;
  sparkline-free compact KPIs; inline AI-note line with a source Tooltip carrying `as_of`.
- **Detail:** header block + KPI row (Cards); Tabs for Order book / Daily output / Inspections /
  Certificates / Notes; AI-summary panel with source Tooltip; ECharts LineChart for 14-day stage output;
  Table (order book, inspections); certificate rows with status Badge; notes list + composer (owner only).
- **Freshness:** every card and the AI note read the same `as_of` / `reports_today` as the header pill.
- Responsive to 390 px is not required for Factories in Phase 0 (Overview, PO detail, Alerts, Assistant
  only).

---

## 5. Data read (models/fields) + URLs/partials

Served by `services.metrics.factory_scorecard` (list) and `services.metrics.factory_detail` (detail);
both read the **latest** `PredictionRun`.

| URL | Method | View | Template / Partial | FR |
|---|---|---|---|---|
| `/factories/` | GET | `factory_list` | `factories/list.html` | FR-FAC-010 |
| `/factories/table/` | GET | `factory_table_partial` | `partials/factories/scorecards.html` | FR-FAC-010 |
| `/factories/<code>/` | GET | `factory_detail` | `factories/detail.html` | FR-FAC-020/030/040/060/070 |
| `/factories/<code>/output.json` | GET | `factory_output_json` | ECharts option | FR-FAC-050 |
| `/factories/<code>/notes/` | POST | `factory_note_create` | `partials/factories/notes.html` | FR-FAC-080 |

Models / fields read:
- **`FactoryStat`** (latest run): `otd_12m` → `otd_pct`, `aql_pass_90d` → `aql_pass_pct`, `knit_load_pct`,
  `reported_today`, `last_report_date`, `missed_wd`, `open_pos`, `open_pcs`, `exposure_usd`,
  `value_at_risk_usd`. Reporting compliance (`reporting_compliance_pct`) derived from reporting history /
  `missed_wd`.
- **`Factory`**: `code`, `name`, `area`, `district`, `address`, `gauges`, `certifications`, `bsci_rating`,
  `last_social_audit`, `merchandiser` (owner, for write scope), `status`.
- **`FactoryMachine`**: `gauge`, `count` → `machines_by_gauge` and `machines_total` (FR-FAC-020).
- **`PurchaseOrder`** + latest **`PredictionSnapshot`** for the factory's open POs → order-book rows
  (FR-FAC-040) and the band/score/slip/projected fields (via `FR-PRED`).
- **`DailyProduction`**: `report_date`, `stage`, `day_pcs` → 14-day output chart (FR-FAC-050).
- **`Inspection`**: `purchase_order`, `inspection_date`, `inspection_type`, `result`, `main_defect`,
  `critical_found`/`major_found`/`minor_found` → inspections list (FR-FAC-060).
- **`Comment`** (`factory` FK) → notes (FR-FAC-080).
- AI note / summary text: generated by the briefing/summary service, stamped with the run's `as_of`
  (FR-FAC-030); numbers in it come only from `services/` (one source of numbers, PRD G3).

Cross-references: order-book rows reuse `FR-ORD` (PO list/detail); band/score/slip/projected/VaR/exposure
come from `FR-PRED-030`/`FR-PRED-040`; reporting state mirrors `FR-PROD-050`.

---

## 6. Empty / error / stale-data states

- **No run yet** (before any `PredictionRun`): scorecards and detail show an empty state "No prediction
  run yet — run the engine or upload a daily file"; no numbers are invented.
- **Factory with no open POs:** scorecard shows open POs 0, open pcs 0, exposure USD 0, value at risk
  USD 0; order-book tab shows "No open POs"; band chips absent.
- **Factory that has not reported today** (SLM, OKH, HMR, PBB): reporting pill shows "No update" with the
  last report date; the AI note / summary states the factory is quiet; numbers still render from the last
  run but are explicitly marked stale by the `as_of` and the "No update" flag (never silently stale,
  metric M4).
- **No daily production in the 14-day window:** output chart shows an empty-series message; stages present
  but flat at 0.
- **No inspections / no certificates:** the respective block shows "None recorded".
- **Unknown factory code:** 404.
- **Stale run:** if the latest run's `as_of` is older than expected, the header freshness pill and every
  card show the real `as_of`; nothing is relabelled as current.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read factory list & detail (all factories) | ✓ | ✓ | ✓ | ✓ |
| Read order book, output, inspections, certs, notes | ✓ | ✓ | ✓ | ✓ |
| Add factory note (`FR-FAC-080`) | ✓ | ✓ | own factory only | – |

"Own factory" = `Factory.merchandiser == request.user`. Write scope is enforced in the queryset /
service, not only in the template (`tech/security.md`, PRD A-05). All four groups read the whole supply
base.
