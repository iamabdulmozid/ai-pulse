# AI Pulse — PRD: Dashboard (module `dashboard`, prefix `FR-DASH`)

**Status:** Phase 0 (demo + pilot) · **Doc version:** v1 · **As of:** 3 Oct 2026
**Owning app:** `dashboard` · **Spine:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`,
`ai/prediction-engine.md`, `design/Karbar Pulse Handoff.dc.html`

> Source-of-truth rule (PRD A-01): every number and name here is the `sample_data/` + `00_Answer_Key.xlsx`
> canon. The design export governs layout, components and interaction only. Where the design prototype's
> illustrative data (`pulse-data.js`, handoff notes — e.g. 86%, 1,912,400 pcs, probability-based bands,
> factory names "Ananta/Meghna") disagrees with the answer key, the answer key wins.

---

## 1. Purpose & the design screens it implements

The dashboard module delivers the two screens a user meets on every visit:

- **App shell** — header, sidebar (with alert badge), freshness pill, ⌘K command palette, theme toggle,
  user menu. Design screen: *"Shell · header, sidebar, freshness"* (`GET /api/status` in the handoff).
- **Executive Overview** — the three-sentence morning state of the business with the evidence one click
  away: AI briefing, 6 KPI cards, 8-week shipment outlook, factory×week heatmap, top-10 at-risk POs,
  factory leaderboard, department/gauge split. Design screen: *"Executive Overview"*
  (`GET /api/overview?month&season&dept`).

This is Goal **G1** (the 3-minute CEO demo opens here) and **G3/M4** (one source of numbers; every figure
carries a source and an `as_of`). Demo "today" (`DEMO_TODAY`) is **Thu 15 Oct 2026, 09:40 Dhaka**; the
latest expected factory report is **14 Oct 2026**.

All business logic reads the latest `PredictionRun` through `services.metrics` (`portfolio_kpis`,
`outlook`, `heatmap`, `factory_scorecard`); pages never recompute the engine on request
(`ai/prediction-engine.md §9`).

---

## 2. User stories

| FR ID | As a <role>, I want <x>, so that <y> |
|---|---|
| **FR-DASH-010** | As any user, I want a persistent app shell (header, sidebar with an alert badge, a freshness pill, a user menu) so that I always know what is fresh, where to go, and how many alerts are open. |
| **FR-DASH-020** | As any user, I want a ⌘K command palette so that I can jump to a PO or factory, or ask the assistant, from any screen without hunting through navigation. |
| **FR-DASH-030** | As any user, I want a dark/light theme toggle that is remembered so that the tool reads well in a morning stand-up (dark) and as a daily working tool (light). |
| **FR-DASH-040** | As Management (CEO), I want a three-sentence AI briefing with a "Why?" that shows the arithmetic and sources so that I can state the business and defend every number in one breath. |
| **FR-DASH-050** | As any user, I want a 6-card KPI row (Open POs, Open pcs, Open FOB, October on-time %, Value at risk, Air-freight exposure) so that the headline state is visible at a glance and each card drills to its detail. |
| **FR-DASH-060** | As Management, I want an 8-week shipment outlook stacked by risk band so that I can see where late/at-risk volume concentrates in the coming weeks. |
| **FR-DASH-070** | As a Merchandiser, I want a factory×week risk heatmap that also shows which factories went quiet so that I can see concentration and silence together. |
| **FR-DASH-080** | As Management, I want a top-10 at-risk PO table so that I can go straight to the worst exposure and its owner. |
| **FR-DASH-090** | As the Head of Merchandising, I want a factory leaderboard (OTD, knit load, reporting status) so that I can rank factories and prepare the right conversations. |
| **FR-DASH-100** | As Management, I want a department/gauge split (share %, at-risk %) so that I can see which part of the book carries the value and the risk. |

---

## 3. Acceptance criteria (Given/When/Then)

### FR-DASH-010 — App shell
- **Given** an authenticated user in any of Admin/Management/Merchandiser/QA, **When** any page renders,
  **Then** the shell shows a header, a left sidebar with nav, and a user menu showing the user's name and
  display role pill (`UserProfile.display_role`: ceo / management / merch / qa / shipping).
- **Given** the sidebar, **When** there are open alerts, **Then** the alert badge shows `alerts_open`
  from `/status/` (count of `Alert.state = open`); when zero, no badge.
- **Given** the freshness pill, **When** the page loads, **Then** it reads `as_of` (the latest
  `PredictionRun.as_of`, displayed Asia/Dhaka, demo **15 Oct 2026 09:40**) and `reports_today`
  as **18 of 22** received (`received:18, expected:22`), matching the canon that 18 of 22 factories
  reported today.
- **Given** the four factories that have not reported (**SLM, OKH, HMR, PBB**), **When** the user opens
  the pill, **Then** `factories_missing[]` lists exactly those four by code and name.
- **Given** the shell, **When** any number is shown anywhere, **Then** it carries a source and an `as_of`
  (success metric **M4**); a factory that has not reported is flagged, never shown as silently fresh.

### FR-DASH-020 — ⌘K command palette
- **Given** any screen, **When** the user presses ⌘K (Ctrl+K on Windows), **Then** an Alpine-driven
  Command dialog opens with a text input and focus trapped.
- **Given** the user types a query, **When** input changes, **Then** the palette calls
  `/palette/search/?q=` (HTMX) and renders `partials/shell/cmdk_results.html` with matching POs
  (by `po_no`/style), factories (by `code`/name), and navigation entries.
- **Given** a PO result (e.g. `71010305`), **When** selected, **Then** navigate to `/pos/71010305/`.
- **Given** the "Ask the assistant" entry, **When** selected, **Then** the assistant slide-over opens with
  the current route + entity id as context (cross-ref assistant **FR-AI-030** / `/assistant/panel/`).
- **Given** the palette receives the current route and entity id, **When** opened on a PO or factory page,
  **Then** that entity is offered first.

### FR-DASH-030 — Theme toggle
- **Given** the shell, **When** the user clicks the theme toggle, **Then** the `data-theme` attribute
  flips between `dark` and `light`, colors change via CSS variables only (surface/surface2/surface3,
  border, hair, text/text2, muted, faint, accent, ai, status.*, stage.*), and no layout shifts.
- **Given** a theme is chosen, **When** the user returns, **Then** the preference is persisted client-side
  and re-applied before first paint (no flash).
- **Given** either theme, **When** charts render, **Then** ECharts options pick up the theme tokens so
  outlook, heatmap and sparklines are legible in both.

### FR-DASH-040 — AI briefing
- **Given** the Overview, **When** `/overview/briefing/` loads (`partials/dashboard/briefing.html`),
  **Then** it shows a 3-sentence morning state naming the October on-time %, the value at risk, and the
  factories driving it, with `generated_at`, `inputs:{reports, pos}`, `why[]` and `sources[]`.
- **Given** the canon, **When** the briefing renders, **Then** it states **October on-time 86.25%**,
  **value at risk USD 2,400,006 across 48 POs**, and that the **top 3 factories (GRL, IRB, SLM) hold 70%**
  of the risk, and notes **4 of 22 factories have not reported** (SLM, OKH, HMR, PBB).
- **Given** the "Why?" control, **When** clicked, **Then** it expands `why[]` showing the arithmetic
  (e.g. on-time % = shipped-on-time + open-predicted-on-time ÷ all October-planned POs) and `sources[]`
  each with a `name` and `as_of`.
- **Given** the OpenAI path is slow/unavailable, **When** the briefing is requested in the demo,
  **Then** the pre-stored answer is served (robustness metric **M5**), identical in numbers.
- **Given** the briefing text references entities, **When** rendered, **Then** PO/factory mentions are
  links (markdown with bold + entity links per the handoff field list).

### FR-DASH-050 — KPI row (6 cards)
- **Given** the Overview, **When** `/overview/kpis/` loads (`partials/dashboard/kpi_row.html`), **Then**
  it renders exactly 6 cards, each with `key`, `value`, `unit`, `sub`, `delta:{value,label}`, `note` (AI),
  `spark: number[7]`, and a `drill` route.
- **Given** the canon, **When** the cards render, **Then** the values are:
  - **Open POs** = **412** (drill → `/pos/`).
  - **Open pcs** = **1,900,020** (drill → `/pos/`).
  - **Open FOB** = **USD 18,601,449** (drill → `/pos/`).
  - **October on-time %** = **86.25%** (drill → `/pos/?exf_month=2026-10`).
  - **Value at risk** = **USD 2,400,006** with sub **48 POs** (drill → `/pos/?status=at_risk&status=critical&status=late`).
  - **Air-freight exposure** = **USD 539,720** (drill → the predicted-late PO set).
- **Given** any KPI card, **When** the user hovers the source tooltip, **Then** it shows the metric's
  definition and the run `as_of`; numbers come only from `services.metrics.portfolio_kpis` (**G3**).
- **Given** the filters `month`, `season`, `dept` (optional, HTMX), **When** applied, **Then** the KPI
  values recompute for the filter from the same service and still carry `as_of`.
- **Given** a card's `drill` route, **When** clicked, **Then** the PO list opens pre-filtered to that card.

### FR-DASH-060 — 8-week shipment outlook
- **Given** the Overview, **When** the outlook chart requests `/overview/outlook.json`, **Then** it
  returns an ECharts stacked-bar option over 8 weeks with series `on_track / watch / at_risk / critical /
  late` (pcs or USD per the handoff `weeks[]` field list: `week_start, label, on_track_pcs, at_risk_pcs,
  critical_pcs, late_pcs`).
- **Given** the stacking uses the canonical bands, **When** rendered, **Then** the band vocabulary is the
  engine's five bands (On track / Watch / At risk / Critical / Late) — never the design's probability
  thresholds (PRD A-02).
- **Given** the `month`/`season`/`dept` filters, **When** applied, **Then** the outlook recomputes under
  the same filter.
- **Given** a bar segment, **When** hovered, **Then** the tooltip shows the week, band and quantity with
  the run `as_of`.

### FR-DASH-070 — Factory×week heatmap
- **Given** the Overview, **When** the heatmap requests `/overview/heatmap.json`, **Then** it returns an
  ECharts option with one row per factory and 8 week columns, cell values **0–4** (risk intensity) and
  **−1 = no update** (handoff: `factories:[{id, name, cells:int[8]}]`).
- **Given** a factory that has not reported (SLM, OKH, HMR, PBB), **When** the heatmap renders, **Then**
  that factory's row is shown as no-update (−1 / striped), distinguishing "quiet" from "on track" — "no
  update" is a reporting flag, not a band (PRD A-03, engine §6).
- **Given** a cell, **When** hovered, **Then** the tooltip names the factory, week and risk level (or
  "no report") with `as_of`.

### FR-DASH-080 — Top-10 at-risk POs table
- **Given** the Overview, **When** rendered, **Then** a table lists the 10 open POs with the highest
  `risk_score` (desc), each row showing `po_no`, `style_desc`, `factory_name`, `risk_score`, `slip_days`,
  `band` (status), top driver, and merchandiser (handoff field list).
- **Given** the canon, **When** the table renders, **Then** the hero PO **71010305** (Greyloom, Lambswool
  V-neck Cardigan, 7GG, score **76**, slip **9**, band **Critical**) appears, with its top driver surfaced
  from `PredictionSnapshot.drivers`.
- **Given** a row, **When** clicked, **Then** navigate to `/pos/<po_no>/`.
- **Given** the band values, **When** shown, **Then** they are the engine's score-bands with Late/slip
  overrides (engine §6), not probability bands.

### FR-DASH-090 — Factory leaderboard
- **Given** the Overview, **When** rendered, **Then** a leaderboard lists factories with `name`,
  `location`, `otd_pct` (`FactoryStat.otd_12m`), `knit_load_pct` (`FactoryStat.knit_load_pct`) and
  reporting status `reported | late | missing` (from `FactoryStat.reported_today` / `missed_wd`).
- **Given** the canon, **When** sorted by risk/exposure, **Then** **GRL, IRB, SLM** surface as the
  concentration (they hold 70% of value at risk), and **SLM, OKH, HMR, PBB** show reporting status
  `missing`.
- **Given** a leaderboard row, **When** clicked, **Then** navigate to `/factories/<code>/` (cross-ref
  factories **FR-FAC-010**).

### FR-DASH-100 — Department/gauge split
- **Given** the Overview, **When** rendered, **Then** a split panel shows rows per department (Men / Women
  / Kids) and per gauge with `share_pct` (of open value or pcs) and `at_risk_pct`, from
  `services.metrics.portfolio_kpis` (handoff: `rows:[{name, open_value_usd|open_pcs, share_pct,
  at_risk_pct}]`).
- **Given** the shares, **When** rendered, **Then** department shares sum to 100% within rounding and each
  `at_risk_pct` is computed from the same value-at-risk definition used by the KPI card (**G3**
  consistency).
- **Given** the `dept`/`season`/`month` filters, **When** applied, **Then** the split recomputes under the
  filter.

---

## 4. Design components used (from the handoff field lists)

- **Shell:** header, sidebar with nav badge, freshness pill (`as_of`, `reports_today:{received,expected}`),
  no-update list (`factories_missing:[{id,name}]`), user menu (`user:{name,role}`), theme toggle.
- **shadcn:** Dialog + Command (⌘K), Tooltip (source tooltip on KPIs/briefing), Card (KPI + panels),
  Badge with status variants (band chips), Table (TanStack) for top-10 and leaderboard, Tabs where used.
- **ECharts:** 8-week outlook (stacked bar), factory×week heatmap (custom grid), KPI sparkline
  (64×22 line, no axes). (Design names Recharts; Pulse serves ECharts options per `urls-and-views.md`.)
- **AI briefing block:** text (markdown, bold + entity links), `generated_at`, `inputs:{reports,pos}`,
  `why:[{title,body}]`, `sources:[{name,as_of}]`.
- **KPI card ×6:** `key · value · unit · sub · delta:{value,label} · note · spark:number[7] · drill`.
- **Dept/gauge split:** `rows:[{name, open_value_usd|open_pcs, share_pct, at_risk_pct}]`.

---

## 5. Data read & URLs/partials

**URLs / partials (from `tech/urls-and-views.md`):**

| URL | View | Returns | Access |
|---|---|---|---|
| `/status/` | `status_json` | `as_of`, `reports_today{received,expected}`, `factories_missing[]`, `alerts_open`, `user{name,role}` | read: all |
| `/palette/search/` | `cmdk_search` (HTMX) | `partials/shell/cmdk_results.html` | read: all |
| `/` | `overview` | `dashboard/overview.html` | read: all |
| `/overview/briefing/` | `briefing_partial` | `partials/dashboard/briefing.html` | read: all |
| `/overview/kpis/` | `kpis_partial` | `partials/dashboard/kpi_row.html` | read: all |
| `/overview/outlook.json` | `outlook_json` | ECharts stacked-bar option | read: all |
| `/overview/heatmap.json` | `heatmap_json` | ECharts heatmap option (cells 0–4, −1 no update) | read: all |

Overview query filters (optional, HTMX): `month`, `season`, `dept`.

**Models / fields read (from `data/data-model.md`):**

- `predictions.PredictionRun` — `as_of`, `trigger`, `params_hash` (latest run drives every figure).
- `predictions.PredictionSnapshot` — `risk_score`, `band`, `slip_days`, `on_time_probability`,
  `value_at_risk_usd`, `air_freight_exposure_usd`, `drivers`, `projected_exfactory`, `model_version`
  (top-10, outlook, KPI roll-ups).
- `predictions.FactoryStat` — `otd_12m`, `aql_pass_90d`, `last_report_date`, `reported_today`, `missed_wd`,
  `knit_load_pct`, `open_pos`, `open_pcs`, `exposure_usd`, `value_at_risk_usd` (leaderboard, heatmap,
  freshness, dept/gauge aggregates).
- `orders.PurchaseOrder` — `po_no`, `order_qty`, `fob_value_usd`, `planned_exfactory`, `is_open`,
  `season`, `factory`, `merchandiser` (counts, filters, drill routes).
- `orders.Style` / `masterdata.Department` / `masterdata.Season` — `style_name`, `gauge`, `yarn_short`,
  `department.name`, `season.code` (table rows, dept/gauge split).
- `masterdata.Factory` — `code`, `name`, `area`, `district`, `merchandiser` (leaderboard, heatmap labels,
  missing list).
- `alerts.Alert` — `state` (for `alerts_open` badge count).
- `accounts.UserProfile` — `display_role` (header pill); `auth.User`/`Group` for identity and access.

All aggregates come through `services.metrics.portfolio_kpis / outlook / heatmap / factory_scorecard`;
the AI briefing's numbers come from the same services (ChromaDB supplies citations only).

---

## 6. States: empty / error / stale-data

- **A factory has not reported** (SLM, OKH, HMR, PBB): the freshness pill reads 18 of 22; the no-update
  list names the four; the heatmap row shows −1 (striped "no update"); the leaderboard shows reporting
  status `missing`. "No update" is a reporting flag, never a PO band — POs at a quiet factory still carry
  their score-band (PRD A-03, engine §6). This is a surfaced state, not an error.
- **A snapshot/run is missing** (no `PredictionRun` yet, or `services.metrics` returns nothing): KPI
  cards, outlook, heatmap and tables show a "No prediction run yet — numbers unavailable" state rather
  than zeros; the freshness pill shows no `as_of`; the briefing shows "Briefing unavailable — awaiting the
  first run." No fabricated figures (**M4** freshness honesty).
- **A filter returns nothing** (e.g. a `season`/`dept` combination with no open POs): KPI cards show 0 with
  the active filter named; outlook/heatmap/tables show an empty-but-labelled state ("No open POs match this
  filter"); the user can clear filters. Totals without a filter still show the full-book canon.
- **Chart endpoint error** (`outlook.json` / `heatmap.json` fails): the chart area shows an inline error
  with a retry, and does not block the rest of the Overview (partials are independent).
- **Assistant/briefing LLM slow or down:** the pre-stored demo briefing is served (**M5**); numbers are
  identical to the live services.

---

## 7. Permissions (read vs write by role)

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| View shell, Overview, all KPIs/charts/tables | ✓ | ✓ | ✓ | ✓ |
| Use ⌘K palette (jump + ask assistant) | ✓ | ✓ | ✓ | ✓ |
| Toggle theme (client preference) | ✓ | ✓ | ✓ | ✓ |
| View briefing + "Why?" | ✓ | ✓ | ✓ | ✓ |

The dashboard module is **read-only for every role** (PRD A-05: all roles read the whole book). It contains
no write actions; writes live in other modules (uploads `FR-PROD`, comments `FR-ORD-100`, alert actions
`FR-ALERT`) and are queryset-scoped to ownership there. Drill-downs inherit the target module's
permissions. All views require login.

---

## Cross-references

- Prediction numbers, bands, VaR, air exposure, probability: `ai/prediction-engine.md`, predictions
  module **FR-PRED-030** (snapshot read contract).
- "Ask the assistant" from ⌘K and the briefing: assistant **FR-AI-030** (`/assistant/panel/`).
- KPI/top-10/leaderboard drill-downs: orders **FR-ORD-010** (list + filters), factories **FR-FAC-010**.
- Alert badge count: alerts **FR-ALERT-010**.
- Theme tokens and shell login: accounts `FR-ACCT` (login + app shell).
