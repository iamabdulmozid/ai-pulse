# Karbar Pulse — PRD: Orders (module `orders`, prefix `FR-ORD`)

**Status:** Phase 0 (demo + pilot) · **Doc version:** v1 · **As of:** 3 Oct 2026
**Owning app:** `orders` · **Spine:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`,
`ai/prediction-engine.md`, `design/Karbar Pulse Handoff.dc.html`

> Source-of-truth rule (PRD A-01): every number and name here is the `sample_data/` + `00_Answer_Key.xlsx`
> canon. The design export governs layout, components and interaction only. The design prototype's
> illustrative labels (`PO-26-1187`, "Ananta Knitwear", probability-based bands, 40% air split at
> USD 4.10/kg) are discarded (PRD A-02, A-12, A-13); the answer key wins.

---

## 1. Purpose & the design screens it implements

The orders module delivers the two screens a merchandiser lives in:

- **PO list** — the at-risk queue across the whole book, with filters, server-side sort, risk status chips
  and cursor pagination, plus Excel export. Design screen: *"Purchase Orders · list"*
  (`GET /api/pos?filters…&cursor` in the handoff).
- **PO detail (with what-if)** — header + prediction, risk drivers, T&A Gantt, stage cumulative curves,
  recommendation cards, the live what-if, and comments. Design screen: *"PO detail"*
  (`GET /api/pos/{id}`).

This is the demo's deep-dive (click-path steps 1:00–1:40): open the hero PO, read why it is late per cause,
then apply the fix in the what-if. The hero PO is **71010305** (Greyloom / `GRL`, style `KAW26-W-1736`,
Lambswool V-neck Cardigan, Women's, 7GG, **9,600 pcs**, FOB **USD 158,400**, ex-factory **29 Oct**,
predicted **7 Nov**, slip **9**, band **Critical**, score **76**, on-time probability **2%**).
Demo "today" (`DEMO_TODAY`) is **15 Oct 2026**.

All predictions are read from the latest `PredictionSnapshot` via `services/`; pages never recompute the
engine on page load. The what-if alone re-runs `services.prediction.whatif` (the same `project()`), read-only
and writing no snapshot (`ai/prediction-engine.md §10`).

---

## 2. User stories

| FR ID | As a <role>, I want <x>, so that <y> |
|---|---|
| **FR-ORD-010** | As any user, I want to filter the PO list (dept, season, factory, gauge, status/band, exf month, merchandiser, text) so that I can narrow the whole book to the orders I care about. |
| **FR-ORD-020** | As any user, I want server-side sort (default risk_score desc) with cursor pagination so that the worst orders are first and the list stays fast across 412 POs. |
| **FR-ORD-030** | As any user, I want risk status chips with live counts so that I can see how the filtered book splits across bands and reporting state and one-click filter to each. |
| **FR-ORD-040** | As a Merchandiser, I want the PO detail header and prediction (predicted ex-factory, slip, on-time prob, band, score, model version, as_of) so that I know the committed vs predicted date and the confidence. |
| **FR-ORD-050** | As a Merchandiser, I want the ranked risk drivers (label, detail, impact days or prior, weight) so that I know *why* the PO is late, per cause, in days. |
| **FR-ORD-060** | As a Merchandiser, I want a T&A Gantt of the 11 milestones plus computed stage bars, flagging late milestones, so that I can see the schedule and where it slipped. |
| **FR-ORD-070** | As a Merchandiser, I want the stage cumulative curves with forecast, required line, a p10/p90 band and today/exf/predicted markers so that I can read the production trajectory against what is needed. |
| **FR-ORD-080** | As a Merchandiser, I want recommendation cards (reallocate machines, Friday overtime, subcontract, split shipment, air freight) each with a predicted date and cost so that I can compare fixes before acting. |
| **FR-ORD-090** | As a Merchandiser, I want a live what-if (linking-machines slider + Friday-overtime days) so that I can test a fix and watch the predicted date, probability and air cost change live. |
| **FR-ORD-100** | As a PO owner, I want to comment on a PO so that the production conversation lives with the order. |
| **FR-ORD-110** | As any user, I want to export the filtered PO list to Excel so that I can share or work the queue offline. |

---

## 3. Acceptance criteria (Given/When/Then)

### FR-ORD-010 — PO list with filters
- **Given** `/pos/`, **When** the page loads, **Then** `orders/po_list.html` renders the filter controls and
  the table (`/pos/table/` → `partials/orders/po_table.html`), showing the full open book (**412** POs)
  with the headline totals (**1,900,020 pcs**, **USD 18,601,449** FOB) consistent with the dashboard KPIs.
- **Given** the filters `dept[]`, `season[]`, `factory[]`, `gauge[]`, `status[]` (band), `exf_month[]`,
  `merchandiser[]`, `q` (PO/style search), **When** any changes, **Then** an HTMX request re-renders the
  table rows server-side and the filters are reflected in the URL (shareable, back-button safe).
- **Given** `status=critical&status=late` (from a dashboard VaR drill), **When** applied, **Then** the
  table shows only POs in those bands; the hero PO **71010305** appears under `critical`.
- **Given** `exf_month=2026-10`, **When** applied, **Then** only POs with planned ex-factory in October show,
  supporting the October on-time view.
- **Given** a row, **When** the user reads it, **Then** it shows `po_no`, `style_code`, `style_desc`, `dept`,
  `season`, `status` (band), `factory_name`, `gauge`, `yarn`, `qty_pcs`, `fob_usd` (per-pc), `fob_value_usd`,
  `exf_date`, `exf_relative_days`, `on_time_prob`, `slip_days`, `risk_score`, and an inline AI note with its
  `as_of` (handoff row field list).
- **Given** the bands shown, **When** rendered, **Then** they are the engine's score-bands with Late/slip
  overrides (engine §6), not the design's probability thresholds (PRD A-02).

### FR-ORD-020 — Server-side sort + cursor pagination
- **Given** the list, **When** first loaded with no sort chosen, **Then** rows are sorted `risk_score desc`
  (hero and the other Critical/Late POs at the top).
- **Given** a sortable column, **When** the user sorts by `slip_days`, `exf_date` or `fob_value_usd`, **Then**
  the server returns the re-sorted page; sorting is server-side, not client reshuffle.
- **Given** 412 rows, **When** the user scrolls/pages, **Then** the next page loads by cursor (not offset),
  keeping the current filter and sort; the cursor is stable under the fixed snapshot.
- **Given** a sort + filter combination, **When** exported (FR-ORD-110), **Then** the export honours the same
  order and filter.

### FR-ORD-030 — Risk status chips with counts
- **Given** the list, **When** rendered, **Then** a chip row shows `counts_by_status`:
  `all / critical / risk / late / watch / noupdate / ok / shipped` (handoff field list).
- **Given** the canon band counts (sum **412**: On track **354**, Watch **10**, At risk **28**,
  Critical **13**, Late **7**), **When** no filter is applied, **Then** the chips reflect those counts
  (critical 13, risk/at-risk 28, late 7, watch 10, ok/on-track 354).
- **Given** `noupdate` is a reporting flag, not a band (PRD A-03), **When** the chip is shown, **Then** it
  counts POs at factories that have not reported (SLM, OKH, HMR, PBB) — those POs still carry their
  score-band in the table; the band counts still sum to 412 with no "No update" bucket.
- **Given** a chip, **When** clicked, **Then** the list filters to that status and the counts recompute for
  the active filter.

### FR-ORD-040 — PO detail header + prediction
- **Given** `/pos/71010305/`, **When** loaded, **Then** the header shows `po_no`, `style_code`
  (`KAW26-W-1736`), `style_desc` (Lambswool V-neck Cardigan), dept (Women), season (AW26), gauge (7GG),
  yarn (Lambswool), `qty_pcs` (9,600), colours, size range, `fob_usd`/`fob_value_usd` (USD 158,400),
  factory `{code,name,location}` (GRL / Greyloom), `exf_date` (29 Oct), ship mode, port, merchandiser, and
  estimated weight.
- **Given** the prediction block, **When** rendered, **Then** it reads from the latest `PredictionSnapshot`:
  `predicted_exf` **7 Nov 2026**, `slip_days` **9**, `on_time_prob` **2%**, band **Critical**, `risk_score`
  **76**, `model_version` (e.g. `engine-1.0`), and `as_of` (run time, demo 15 Oct 2026). (Cross-ref
  predictions **FR-PRED-030**.)
- **Given** the prediction, **When** shown, **Then** it is read from the snapshot, never recomputed on page
  load; every figure carries `as_of` (**M4**).

### FR-ORD-050 — Risk drivers list
- **Given** the PO detail, **When** the drivers panel renders, **Then** it lists
  `drivers:[{label, detail, impact_days | "prior", weight}]` from `PredictionSnapshot.drivers`, ordered by
  weight.
- **Given** the hero PO, **When** the drivers render, **Then** they reflect the engine's score breakdown:
  schedule 50, T&A 12 (yarn in-house late), factory OTD 12, quality 0, freshness 0 = **76** (engine §5),
  each driver stating its day/prior impact and weight.
- **Given** a factory-level driver (e.g. OTD), **When** shown, **Then** its impact is marked `"prior"`
  (not a day count), distinguishing schedule-slip drivers (impact_days) from prior-risk drivers.

### FR-ORD-060 — T&A Gantt
- **Given** `/pos/71010305/ta/`, **When** requested, **Then** `partials/orders/ta_gantt.html` returns an
  ECharts Gantt of the **11 T&A milestones** (`TAMilestone`: Yarn booking … Ex-factory) plus the six
  **computed** production stage bars (knitting, linking, trimming & mending, washing, ironing, packing —
  forecasts, not stored milestones; PRD A-10).
- **Given** each milestone, **When** rendered, **Then** it shows plan vs actual/forecast and state
  (`done | running | pending`), with `late_days` and a `flagged` marker for late milestones
  (handoff field list).
- **Given** the hero PO, **When** the Gantt renders, **Then** the **Yarn in-house** milestone is flagged
  late (the +8-day T&A driver), consistent with the drivers and score.
- **Given** washing timing, **When** `wash_required = N` for a style, **Then** the washing stage bar does
  not appear (PRD A-10).

### FR-ORD-070 — Stage cumulative curves chart
- **Given** `/pos/71010305/curves.json`, **When** requested, **Then** it returns an ECharts option with per
  stage cumulative series, a forecast per stage, a required line, a p10/p90 completion band, and markers for
  **today**, **exf** and **predicted** (handoff `series/forecast/required_line/band/markers`).
- **Given** the hero PO, **When** the curves render, **Then** the predicted marker sits at **7 Nov**, the
  exf marker at **29 Oct**, and the required line reflects the bottleneck (linking) required rate of
  **680 pcs/day** vs measured **411.1 pcs/day** (engine §3 worked example).
- **Given** the p10/p90 band, **When** shown, **Then** it comes from the factory slip distribution used for
  on-time probability (engine §7), not a separate formula.

### FR-ORD-080 — Recommendation cards
- **Given** the PO detail, **When** the recommendation panel renders, **Then** it shows cards for:
  reallocate linking machines (with donor), Friday overtime, subcontract knitting, split shipment, and air
  freight — each with a predicted ex-factory date and a cost (handoff `options:[{title, body, impact_days,
  cost_usd, cost_note, risk, action}]`).
- **Given** the hero PO, **When** the reallocate card renders, **Then** it auto-selects donor PO
  **71009573** (same factory/gauge pool, positive slack; PRD A-11) and reports both POs' new dates.
- **Given** the air-freight card, **When** rendered, **Then** its cost equals the hero air exposure
  **USD 38,016** (`9,600 × 0.72 × 5.50`; engine §7, A-13) — never the design's 40% split at USD 4.10/kg.
- **Given** every card, **When** computed, **Then** its date/cost comes from re-running `project()` with
  overridden inputs, so cards and the what-if agree (engine §7).
- **Given** the cards, **When** shown, **Then** subcontract and split-shipment appear as read-only options
  with date + cost (the two live what-if inputs are linking machines and Friday overtime).

### FR-ORD-090 — What-if
- **Given** the PO detail, **When** the what-if panel renders, **Then** it offers a `linking_machines`
  slider (min/max/current) and `overtime_days` input, defaulting to the PO's current values (hero: 13
  linking machines, 0 overtime).
- **Given** the user changes an input, **When** submitted, **Then** `/pos/71010305/whatif/` (POST) calls
  `services.prediction.whatif` and returns `partials/orders/whatif_result.html` with
  `{projected_exfactory, slip_days, on_time_prob, air_cost_usd}`; it reads the PO's stored reported rows and
  writes no snapshot.
- **Given** the hero recovery plan (**+6 linking M/C: 13→19, and 2 Friday overtime days: 16 & 23 Oct**),
  **When** applied, **Then** the result snaps to predicted ex-factory **29 Oct**, **slip 0**, on-time
  (probability ~0.94), air cost **USD 0** — matching the answer-key Hero What-if row (engine §10).
- **Given** intermediate options, **When** applied, **Then** the engine reproduces the answer key: +6 M/C
  alone → 1 Nov (slip 3); 2 Fridays alone → 4 Nov (slip 6); current plan → 7 Nov (slip 9) (engine §10 table).
- **Given** the slider is dragged back to 13 machines / 0 overtime, **When** re-submitted, **Then** the
  result returns to 7 Nov live (demo click-path 1:40).
- **Given** the what-if is read-only, **When** any role uses it, **Then** no write permission is required and
  no `PredictionSnapshot` is created.

### FR-ORD-100 — PO comments
- **Given** the PO detail, **When** a user who is the PO's merchandiser, Management or Admin posts a comment,
  **Then** `/pos/<po_no>/comments/` (POST) creates a `Comment` (on `purchase_order`) and returns
  `partials/orders/comment_list.html` with the new comment (`author, role, at, text`).
- **Given** a QA user, **When** the PO is one QA inspected, **Then** QA may comment; otherwise the write is
  denied (role matrix in `urls-and-views.md`).
- **Given** a Merchandiser who does not own the PO, **When** they attempt to comment, **Then** the write is
  rejected in the queryset/service (not only the template), returning a permission error; they can still
  read all comments.
- **Given** a created PO comment, **When** saved, **Then** it is indexed into ChromaDB for the assistant
  (data-model note on `Comment`).

### FR-ORD-110 — PO list Excel export
- **Given** a filtered/sorted list, **When** the user clicks export, **Then** `/pos/export.xlsx`
  (`po_export`) returns an xlsx of the **filtered** list in the **current sort**, via `services.export`.
- **Given** the export, **When** opened, **Then** columns match the list row fields and the figures match the
  on-screen snapshot (same `as_of`), so the file and the screen never disagree (**G3**).
- **Given** an empty filter result, **When** exported, **Then** the file contains the header row only (no
  fabricated rows).

---

## 4. Design components used (from the handoff field lists)

- **List · Filters:** `dept[] · season[] · factory_id[] · gauge[] · status[] · exf_month[] ·
  merchandiser_id[]` (shadcn controls + Command-style factory/merch pickers).
- **List · Risk chips:** `counts_by_status:{all, critical, risk, late, watch, noupdate, ok, shipped}`
  (Badge status variants).
- **List · Row:** `po_id · style_code · style_desc · dept · season · status · factory_name · gauge · yarn ·
  qty_pcs · fob_usd · fob_value_usd · exf_date · exf_relative_days · on_time_prob · slip_days · risk_score`;
  inline AI note (`summary · as_of`); TanStack Table; server-side sort.
- **Detail · Header:** `po_id · style_code · style_desc · sketch_url · dept · season · gauge · yarn ·
  qty_pcs · colours · size_range · fob_usd · factory:{id,name,location} · exf_date · ship_mode · port ·
  merchandiser · weight_kg_est`.
- **Detail · Prediction:** `predicted_exf · slip_days · on_time_prob · band_days · air_cost_usd ·
  risk_score · model_version · as_of`.
- **Detail · Risk drivers:** `drivers:[{label, detail, impact_days | "prior", weight}]`.
- **Detail · T&A timeline:** `milestones:[{name, plan_start, plan_end, actual_start, actual_end,
  forecast, state, late_days, flagged}]` (custom CSS/ECharts Gantt).
- **Detail · Curves:** `series:{knitting…packing}:[{date,cum_pcs}] · forecast · required_line ·
  band:{p10,p90} · markers:{today, exf, predicted}` (ECharts ComposedChart equivalent).
- **Detail · Recommendation:** `summary · options:[{title, body, impact_days, cost_usd, cost_note, risk,
  action}]` (Card).
- **Detail · What-if:** inputs `linking_machines(min,max,current) · overtime_days` (shadcn Slider) →
  POST → `{predicted_exf, slip_days, on_time_prob, air_cost_usd}`.
- **Detail · Comments:** `comments:[{author, role, at, text}]` + POST.
- **Export:** xlsx action on the list.

---

## 5. Data read & URLs/partials

**URLs / partials (from `tech/urls-and-views.md`):**

| URL | M | View | Returns | Access |
|---|---|---|---|---|
| `/pos/` | GET | `po_list` | `orders/po_list.html` | read: all |
| `/pos/table/` | GET | `po_table_partial` | `partials/orders/po_table.html` (rows + `counts_by_status`) | read: all |
| `/pos/<po_no>/` | GET | `po_detail` | `orders/po_detail.html` | read: all |
| `/pos/<po_no>/ta/` | GET | `po_ta_partial` | `partials/orders/ta_gantt.html` (ECharts Gantt) | read: all |
| `/pos/<po_no>/curves.json` | GET | `po_curves_json` | ECharts curves option | read: all |
| `/pos/<po_no>/whatif/` | POST | `po_whatif_partial` | `partials/orders/whatif_result.html` | read: all (no write) |
| `/pos/<po_no>/comments/` | POST | `po_comment_create` | `partials/orders/comment_list.html` | **write:** owner / Management / Admin |
| `/pos/export.xlsx` | GET | `po_export` | xlsx of the filtered list | read: all |

List filters (server-side, HTMX): `dept[]`, `season[]`, `factory[]`, `gauge[]`, `status[]`, `exf_month[]`,
`merchandiser[]`, `q`. Sort: default `risk_score desc`; also slip, exf date, fob. Pagination: cursor.

**Models / fields read (from `data/data-model.md`):**

- `orders.PurchaseOrder` — `po_no`, `po_date`, `order_qty`, `fob_usd_pc`, `fob_value_usd`,
  `planned_exfactory`, `planned_ship_mode`, `port_of_loading`, `destination`, `delivery_terms`, `is_open`,
  `season`, `style`, `factory`, `merchandiser`.
- `orders.Style` — `style_no`, `style_name`, `product_type`, `gauge`, `yarn_short`, `wash_required`,
  `weight_kg_pc`, `linking_std_pcs_mc_day`, `knitting_minutes_pc`, `department`.
- `orders.POLine` / `orders.POLineSize` — `colour`, `colour_code`, `line_qty`, `size`, `qty` (colours +
  size range on the header).
- `masterdata.Department` / `masterdata.Season` / `masterdata.Factory` — names/codes/locations for rows,
  filters and the header.
- `orders.TAMilestone` — `seq`, `milestone`, `responsible`, `planned_date`, `revised_date`, `actual_date`,
  `status`, `remarks` (Gantt; 11 rows/PO).
- `production.DailyProduction` — `report_date`, `stage`, `day_pcs`, `cum_pcs`, `machines` (stage curves and
  what-if inputs; the engine's reported rows).
- `predictions.PredictionSnapshot` — `state`, `bottleneck_stage`, `bottleneck_rate`, `required_rate`,
  `projected_finish_wd`, `completion_day_n`, `available_wd`, `slack_wd`, `projected_exfactory`, `slip_days`,
  score components, `risk_score`, `band`, `on_time_probability`, `value_at_risk_usd`,
  `air_freight_exposure_usd`, `drivers`, `model_version`, `as_of` (prediction, drivers, curves markers).
- `predictions.FactoryStat` — `otd_12m`, `slip_distribution`, `reported_today`, `missed_wd` (probability
  band, reporting flag for `noupdate` chip).
- `orders.Comment` — `author`, `created_at`, `text` (comments).
- `production.Inspection` — latest `result` for the PO (quality driver surfaced in drivers).

What-if calls `services.prediction.whatif` (same `project()`); list/detail read the latest snapshot via
`services.metrics` / `services.prediction`. No business logic in views or templates (PRD §9).

---

## 6. States: empty / error / stale-data

- **A factory has not reported** (SLM, OKH, HMR, PBB): POs at those factories show the `noupdate` reporting
  flag (stripe/pill) in the list and on the detail header, but keep their score-band (PRD A-03). The stage
  curves/what-if use the PO's reported rows up to the factory's `last_report`; a banner notes "Last report
  <date> — factory has not reported today," so no figure is shown as fresher than its source (**M4**).
- **A snapshot is missing** (no `PredictionSnapshot` for the PO, e.g. a closed/shipped PO or before the
  first run): the detail prediction, drivers, curves and recommendations show "No prediction available —
  this PO is shipped/closed or has not yet been scored"; the what-if is disabled with the reason. No
  fabricated prediction.
- **A filter returns nothing:** the table shows "No open POs match this filter" with the active filter
  named and a clear-filters action; `counts_by_status` shows zeros for the filtered set (full-book chip
  still available via `all`). Export produces a header-only file.
- **What-if error / invalid input** (machines out of min–max, non-date overtime): the partial returns an
  inline validation message and leaves the last valid result; it never writes a snapshot.
- **Curves/TA/export endpoint error:** the affected panel shows an inline error with retry; other panels
  (independent partials) still render.
- **Comment write denied** (non-owner, non-QA-on-inspected-PO): the form shows a permission message; read
  of all comments remains available.

---

## 7. Permissions (read vs write by role)

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| View PO list, chips, detail, prediction, drivers, Gantt, curves, recommendations | ✓ | ✓ | ✓ | ✓ |
| Run what-if (read-only, no snapshot) | ✓ | ✓ | ✓ | ✓ |
| Export filtered list (xlsx) | ✓ | ✓ | ✓ | ✓ |
| Comment on a PO | ✓ | ✓ | own POs only | own (QA on inspected POs) |

"Own" = the PO's `merchandiser` is the current user. Read is the whole book for every role (PRD A-05);
write (comments) is scoped to ownership and enforced in querysets/service functions, not only templates
(`tech/security.md`). The what-if is read-only and needs no write permission. All views require login.

---

## Cross-references

- Engine formulas, bands, scores, probability, air exposure, hero worked example, what-if table:
  `ai/prediction-engine.md`; predictions **FR-PRED-030** (snapshot read contract), **FR-PRED-040**
  (what-if via same engine).
- PO list entry points: dashboard KPI/top-10/leaderboard drills **FR-DASH-050 / FR-DASH-080 /
  FR-DASH-090**, ⌘K palette **FR-DASH-020**.
- "Ask the assistant" with PO context from the detail: assistant **FR-AI-030** (`/assistant/panel/`).
- T&A milestones vs computed stages, donor selection, air-freight constants: PRD A-10, A-11, A-13.
- Reported production rows and freshness: production **FR-PROD** (uploads + reporting status).
- Comment indexing for the assistant: assistant `FR-AI` / ChromaDB (PRD A-08).
