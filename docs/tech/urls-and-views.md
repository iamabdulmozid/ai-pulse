# Karbar Pulse — URLs and views (replaces an API spec)

Server-rendered Django with HTMX partials and a few JSON/SSE endpoints. All responses carry `as_of` and
`reports_today`. Roles are Django groups: **Admin, Management, Merchandiser, QA** (personas → groups in
`PRD.md §3`). "Read: all" means any authenticated user in any of the four groups; **write actions** are
scoped to ownership in querysets (`tech/security.md`). All views require login.

Legend — **M** method, **Tmpl** full-page template, **Partial** HTMX fragment(s) returned, **Access**.

---

## Shell & auth (`accounts`, `dashboard`)

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/login/` | GET, POST | `login_view` | `accounts/login.html` | public |
| `/logout/` | POST | `logout_view` | → `/login/` | any |
| `/healthz/` | GET | `health` | JSON `{status, as_of}` | public |
| `/status/` | GET | `status_json` | JSON: `as_of`, `reports_today{received,expected}`, `factories_missing[]`, `alerts_open`, `user{name,role}` | read: all |
| `/palette/search/` | GET | `cmdk_search` (HTMX) | `partials/shell/cmdk_results.html` — entities + nav for ⌘K | read: all |

The ⌘K palette (Alpine) queries `/palette/search/?q=` and offers PO/factory jumps + "Ask the assistant".

---

## Executive Overview (`dashboard`) — FR-DASH

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/` | GET | `overview` | `dashboard/overview.html` | read: all |
| `/overview/briefing/` | GET | `briefing_partial` | `partials/dashboard/briefing.html` (AI briefing: text, `generated_at`, inputs, `why[]`, `sources[]`) | read: all |
| `/overview/outlook.json` | GET | `outlook_json` | ECharts option: 8-week stacked bar (`on_track/watch/at_risk/critical/late` pcs or USD) | read: all |
| `/overview/heatmap.json` | GET | `heatmap_json` | ECharts option: factory × 8-week cells 0–4, −1 = no update | read: all |
| `/overview/kpis/` | GET | `kpis_partial` | `partials/dashboard/kpi_row.html` (6 cards: key/value/unit/sub/delta/note/spark/drill) | read: all |

Query filters (all optional, HTMX): `month`, `season`, `dept`. KPI cards: Open POs, Open pcs, Open FOB,
October on-time %, Value at risk, Air-freight exposure. Also renders top-10 at-risk POs, factory
leaderboard, dept/gauge split. Data from `services.metrics.portfolio_kpis/outlook/heatmap`.

---

## Purchase Orders (`orders`) — FR-ORD

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/pos/` | GET | `po_list` | `orders/po_list.html` | read: all |
| `/pos/table/` | GET | `po_table_partial` | `partials/orders/po_table.html` (rows + `counts_by_status` chips) | read: all |
| `/pos/<po_no>/` | GET | `po_detail` | `orders/po_detail.html` | read: all |
| `/pos/<po_no>/ta/` | GET | `po_ta_partial` | `partials/orders/ta_gantt.html` (ECharts Gantt) | read: all |
| `/pos/<po_no>/curves.json` | GET | `po_curves_json` | ECharts option: stage cum curves + forecast + required line + p10/p90 band + markers | read: all |
| `/pos/<po_no>/whatif/` | POST | `po_whatif_partial` | `partials/orders/whatif_result.html` (`projected_exfactory, slip_days, on_time_prob, air_cost_usd`) | read: all (no write) |
| `/pos/<po_no>/comments/` | POST | `po_comment_create` | `partials/orders/comment_list.html` | **write:** PO owner / Management / Admin |
| `/pos/export.xlsx` | GET | `po_export` | xlsx of the filtered list | read: all |

**Filters** (server-side, HTMX): `dept[]`, `season[]`, `factory[]`, `gauge[]`, `status[]` (band),
`exf_month[]`, `merchandiser[]`, `q` (PO/style search). **Sort:** default `risk_score desc`; also
slip, exf date, fob. **Pagination:** cursor. Row fields per handoff: po_no, style_code/desc, dept,
season, status(band), factory, gauge, yarn, qty, fob/pc, fob_value, exf_date, exf_relative_days,
on_time_prob, slip_days, risk_score, inline AI note + `as_of`. Detail adds prediction, risk drivers,
T&A Gantt, stage curves, recommendation cards, what-if (linking machines slider + overtime), comments.
What-if calls `services.prediction.whatif` — the same engine; read-only, writes no snapshot.

---

## Factories (`factories`) — FR-FAC

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/factories/` | GET | `factory_list` | `factories/list.html` | read: all |
| `/factories/table/` | GET | `factory_table_partial` | `partials/factories/scorecards.html` | read: all |
| `/factories/<code>/` | GET | `factory_detail` | `factories/detail.html` | read: all |
| `/factories/<code>/output.json` | GET | `factory_output_json` | ECharts option: 14-day stage output lines | read: all |
| `/factories/<code>/notes/` | POST | `factory_note_create` | `partials/factories/notes.html` | **write:** factory owner / Management / Admin |

Scorecard fields: code, name, location, machines_by_gauge, knit_load_pct, otd_pct, aql_pass_pct,
reporting_compliance_pct, reported_today{status, at}, open_pos, open_pcs, exposure_usd, status, AI note.
Detail adds order book (PO rows), daily output (14 d), inspections, certificates, AI summary. Data from
`services.metrics.factory_scorecard/factory_detail`.

---

## Daily Updates (`production`) — FR-PROD

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/uploads/` | GET | `uploads_home` | `production/uploads.html` (drop zone, reporting status, history, templates) | read: all |
| `/uploads/` | POST | `upload_create` | `partials/production/batch_card.html` (creates `UploadBatch`, enqueues `ingest_file`) | **write:** Merchandiser / Management / Admin |
| `/uploads/<batch_id>/status/` | GET | `batch_status_partial` | `partials/production/batch_status.html` (poll: status, rows_accepted, warnings[], errors[], detected_factory/date) | write-role (owner of batch) |
| `/uploads/reporting/` | GET | `reporting_status_partial` | `partials/production/reporting.html` (per-factory reported/late/missing) | read: all |
| `/uploads/templates/` | GET | `templates_list` | `partials/production/templates.html` (download blank templates) | read: all |

Accepts the six file kinds; detects kind+factory+date from the workbook (see `data/excel-templates.md`).
Validation errors/warnings are per-row; a file with errors is rejected as a batch (no partial writes).

---

## Risk & Alerts (`alerts`) — FR-ALERT (Should)

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/alerts/` | GET | `alert_list` | `alerts/list.html` | read: all |
| `/alerts/feed/` | GET | `alert_feed_partial` | `partials/alerts/feed.html` (filter by kind/severity/state) | read: all |
| `/alerts/<id>/ack/` | POST | `alert_ack` | `partials/alerts/row.html` | **write:** owner / Management / Admin |
| `/alerts/<id>/assign/` | POST | `alert_assign` (`user_id`) | `partials/alerts/row.html` | **write:** Management / Admin |
| `/alerts/<id>/snooze/` | POST | `alert_snooze` (`until`) | `partials/alerts/row.html` | **write:** owner / Management / Admin |

Alert kinds: po_critical, factory_missed_report, yarn_late, inspection_failed, po_at_risk, compliance.

---

## Reports & Analytics (`reports`) — FR-REP (Should + Later)

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/reports/` | GET | `reports_home` | `reports/home.html` | read: all |
| `/reports/shipment-forecast/` | GET | `shipment_forecast` | `reports/shipment_forecast.html` (+ `.json` chart, `?export=xlsx`) | read: all |
| `/reports/factory-performance/` | GET | `factory_performance` | `reports/factory_performance.html` (+ export) | read: all |
| `/reports/<kind>/` (Later) | GET | `report_generic` | ta-delay, inspection, on-time-trend, plan-vs-actual, accuracy | read: all |

Shipment forecast rows: period, pos, pcs, fob_usd, on_time_pct, at_risk_usd (matches answer-key Weekly
Outlook). Factory performance: factory scorecard rows. Exports via `services.export` (xlsx; pdf Later).

---

## AI Assistant (`assistant`) — FR-AI

| URL | M | View | Tmpl / Partial | Access |
|---|---|---|---|---|
| `/assistant/` | GET | `assistant_page` | `assistant/page.html` (full page) | read: all |
| `/assistant/panel/` | GET | `assistant_panel` | `partials/assistant/slideover.html` (Alpine Sheet) | read: all |
| `/assistant/stream/` | POST | `assistant_stream` (async, SSE) | event stream (below) | read: all; scope enforced per user |
| `/assistant/threads/` | GET | `threads_list` | `partials/assistant/threads.html` | read: own threads |
| `/assistant/threads/<id>/` | GET | `thread_detail` | `partials/assistant/messages.html` | read: own thread |
| `/assistant/export.xlsx` | POST | `assistant_export` | xlsx of a returned table | read: all |

**Request:** `thread_id`, `message`, `context{route, entity_id}`. **SSE events** (match the design handoff):
`step{id,label,status,ms}`, `delta{text}`, `chart{ECharts option}`, `table{columns,rows}`, `sources[{name,as_of}]`,
`followups[]`, `error`, `done`. Numbers come only from tools that call `services/`; ChromaDB supplies
citations only. Conversations + token usage stored in Postgres. Full tool catalogue: `ai/assistant.md`.

> Note on endpoint naming: the design handoff uses `/api/...` paths. We serve the same shapes under the
> server-rendered routes above; where a pure-JSON contract matters (charts, chat SSE, exports) the shapes
> match the handoff's field lists exactly. This is a naming reconciliation only (ASSUMPTION, see PRD A-01).

---

## Admin (`masterdata` + others) — FR-MASTER

Django admin at `/admin/` (Admin group / staff). Registers: Department, Season, Factory, FactoryMachine,
HolidayCalendar, EngineParameter, TATemplate/TAMilestoneDef, AlertRule, Users & Groups. This is the only
"settings" surface in Phase 0 (no custom Settings screen).

---

## Role access matrix (summary)

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read all screens & data | ✓ | ✓ | ✓ | ✓ |
| Upload daily files | ✓ | ✓ | ✓ | – |
| Comment on PO / factory note | ✓ | ✓ | own only | own only (QA on inspected POs) |
| Ack / snooze alert | ✓ | ✓ | own only | own only |
| Assign alert | ✓ | ✓ | – | – |
| Edit master data / parameters (admin) | ✓ | – | – | – |
| Use assistant | ✓ | ✓ | ✓ | ✓ |

"own" = the PO's merchandiser or the factory's owner is the current user. Enforced in querysets and
service functions, not only in templates.
