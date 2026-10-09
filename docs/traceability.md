# AI Pulse — Traceability matrix

Maps **design screen → FR IDs → URLs/views → models → tests**. Every row of the design (and every FR)
must appear here; anything the design does not show is a flagged proposal (see "Proposals" at the end).

Design source: `design/Karbar Pulse.dc.html` (+ handoff `design/Karbar Pulse Handoff.dc.html`).
URLs/views: `tech/urls-and-views.md`. Models: `data/data-model.md`. Engine: `ai/prediction-engine.md`.
Test naming: `test_<module>_<thing>` (pytest-django), as used in `plan/roadmap.md`.

Tier: **M** = Must for 15 Oct, **S** = Should for 15 Oct, **L** = Later.

---

## 1. Screen → FR → URL/view → models → tests

### Login (accounts) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-ACCT-010 | Login form, errors, redirect to Overview | `/login/` `login_view` | `auth.User`, `UserProfile` | `test_accounts_login`, `test_accounts_login_invalid` |
| FR-ACCT-020 | Logout & session | `/logout/` `logout_view` | `auth.User` | `test_accounts_logout` |
| FR-ACCT-030 | Role-based nav & action visibility | all templates via context | `auth.Group`, `UserProfile` | `test_accounts_nav_by_role` |
| FR-ACCT-040 | Queryset write-scoping server-side | `services/` managers | `auth.Group`, `PurchaseOrder`, `Factory` | `test_role_write_scope` |
| FR-ACCT-050 | Audit log of security actions | middleware/service hooks | `AuditLog` | `test_accounts_audit_log` |
| FR-ACCT-060 | `/status` feed for freshness pill + alert badge | `/status/` `status_json` | `PredictionRun`, `FactoryStat`, `Alert` | `test_accounts_status_endpoint` |

### App shell + Executive Overview (dashboard) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-DASH-010 | Shell: header, sidebar, freshness pill | `base.html`, `/status/` | `PredictionRun`, `FactoryStat` | `test_dashboard_shell`, `test_dashboard_freshness_pill` |
| FR-DASH-020 | ⌘K command palette | `/palette/search/` `cmdk_search` | `PurchaseOrder`, `Factory` | `test_dashboard_cmdk_search` |
| FR-DASH-030 | Theme toggle (dark/light) | client (Alpine + CSS vars) | — | `test_dashboard_theme_toggle` (UI/smoke) |
| FR-DASH-040 | AI briefing + "Why?" (arithmetic + sources) | `/overview/briefing/` `briefing_partial` | `PredictionRun`, `PredictionSnapshot`, `FactoryStat` | `test_dashboard_briefing_sources` |
| FR-DASH-050 | 6 KPI cards (Open POs/pcs/FOB, Oct on-time %, VaR, air exposure) | `/overview/kpis/` `kpis_partial` | `PredictionSnapshot`, `FactoryStat` | `test_overview_kpis` |
| FR-DASH-060 | 8-week outlook stacked bar | `/overview/outlook.json` `outlook_json` | `PredictionSnapshot`, `PurchaseOrder` | `test_overview_outlook_matches_answer_key` |
| FR-DASH-070 | Factory×week heatmap (−1 = no update) | `/overview/heatmap.json` `heatmap_json` | `PredictionSnapshot`, `FactoryStat` | `test_overview_heatmap` |
| FR-DASH-080 | Top-10 at-risk POs | `/` `overview` | `PredictionSnapshot` | `test_overview_top_at_risk` |
| FR-DASH-090 | Factory leaderboard | `/` `overview` | `FactoryStat`, `Factory` | `test_overview_leaderboard` |
| FR-DASH-100 | Department / gauge split | `/` `overview` | `PurchaseOrder`, `PredictionSnapshot` | `test_overview_dept_gauge_split` |

### Purchase Orders list (orders) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-ORD-010 | List + filters (dept/season/factory/gauge/band/exf_month/merch/search) | `/pos/`, `/pos/table/` | `PurchaseOrder`, `PredictionSnapshot`, `Style`, `Season`, `Factory` | `test_po_list_filters` |
| FR-ORD-020 | Server-side sort (risk desc default) + cursor pagination | `/pos/table/` `po_table_partial` | same | `test_po_list_sort_paginate` |
| FR-ORD-030 | Risk status chips + counts_by_status | `/pos/table/` | `PredictionSnapshot` | `test_po_list_status_counts` |
| FR-ORD-110 | Excel export of filtered list | `/pos/export.xlsx` `po_export` | `PurchaseOrder`, `PredictionSnapshot` | `test_po_list_export` |

### PO detail + what-if (orders) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-ORD-040 | Header + prediction (predicted_exf, slip, prob, band, score, as_of) | `/pos/<po_no>/` `po_detail` | `PurchaseOrder`, `PredictionSnapshot`, `Style`, `POLine`, `POLineSize` | `test_po_detail_prediction` |
| FR-ORD-050 | Risk drivers | `/pos/<po_no>/` | `PredictionSnapshot.drivers` | `test_po_detail_drivers` |
| FR-ORD-060 | T&A Gantt (11 milestones + stage bars) | `/pos/<po_no>/ta/` `po_ta_partial` | `TAMilestone`, `DailyProduction` | `test_po_detail_ta_gantt` |
| FR-ORD-070 | Stage cumulative curves + forecast + required + band | `/pos/<po_no>/curves.json` `po_curves_json` | `DailyProduction`, `PredictionSnapshot` | `test_po_detail_curves` |
| FR-ORD-080 | Recommendation cards (machines/donor, overtime, subcontract, split, air) | `/pos/<po_no>/` | `PredictionSnapshot`, `PurchaseOrder` (donor) | `test_recommendation_donor`, `test_po_detail_recommendations` |
| FR-ORD-090 | What-if (linking machines + overtime) HTMX partial | `/pos/<po_no>/whatif/` `po_whatif_partial` | `DailyProduction`, `EngineParameter` | `test_hero_whatif`, `test_po_whatif_partial` |
| FR-ORD-100 | PO comments (write scoped) | `/pos/<po_no>/comments/` `po_comment_create` | `Comment` | `test_po_comments_scope` |

### Factories list + detail (factories) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-FAC-010 | Scorecard list | `/factories/`, `/factories/table/` | `Factory`, `FactoryMachine`, `FactoryStat` | `test_factory_list_scorecards` |
| FR-FAC-020 | Detail header + KPIs (+ machines_total) | `/factories/<code>/` `factory_detail` | `Factory`, `FactoryMachine`, `FactoryStat` | `test_factory_detail_kpis` |
| FR-FAC-030 | AI summary (+ as_of) | `/factories/<code>/` | `FactoryStat`, kb | `test_factory_ai_summary` |
| FR-FAC-040 | Order book tab | `/factories/<code>/` | `PurchaseOrder`, `PredictionSnapshot` | `test_factory_order_book` |
| FR-FAC-050 | Daily output chart (14 d) | `/factories/<code>/output.json` `factory_output_json` | `DailyProduction` | `test_factory_output_chart` |
| FR-FAC-060 | Inspections | `/factories/<code>/` | `Inspection` | `test_factory_inspections` |
| FR-FAC-070 | Certificates | `/factories/<code>/` | `Factory` | `test_factory_certificates` |
| FR-FAC-080 | Factory notes (write scoped) | `/factories/<code>/notes/` `factory_note_create` | `Comment` | `test_factory_notes_scope` |

### Daily Updates upload (production) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-PROD-010 | Drop zone (six file kinds) | `/uploads/` `uploads_home`/`upload_create` | `UploadBatch` | `test_upload_accepts_six_kinds` |
| FR-PROD-020 | Async ingest task + HTMX status poll | `/uploads/<id>/status/` `batch_status_partial` | `UploadBatch` | `test_upload_status_poll` |
| FR-PROD-030 | Validation result (rows/warnings/errors/detected) | `batch_status_partial` | `UploadBatch` | `test_upload_rejects_bad_batch`, `test_upload_clean_pbb` |
| FR-PROD-040 | Upsert rules & corrections | `services/ingest/` | `DailyProduction`, `Inspection`, `Shipment`, `PurchaseOrder`, `TAMilestone` | `test_ingest_upsert_keys`, `test_ingest_cum_monotonic` |
| FR-PROD-050 | Reporting status board | `/uploads/reporting/` `reporting_status_partial` | `FactoryStat`, `Factory` | `test_upload_reporting_status` |
| FR-PROD-060 | Upload history | `/uploads/` | `UploadBatch` | `test_upload_history` |
| FR-PROD-070 | Templates download | `/uploads/templates/` `templates_list` | — | `test_upload_templates` |

### Predictions (predictions) — Tier M (no direct screen; powers all)
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-PRED-010 | Run after each successful upload | task `run_predictions('upload')` | `PredictionRun`, `PredictionSnapshot` | `test_predictions_run_on_upload` |
| FR-PRED-020 | Nightly scheduled run | django-q2 schedule | `PredictionRun` | `test_predictions_nightly_schedule` |
| FR-PRED-030 | Store snapshots; pages read latest, never recompute | `services/metrics` | `PredictionSnapshot` | `test_predictions_pages_read_snapshot` |
| FR-PRED-040 | FactoryStat (OTD/AQL/slip dist/freshness/load) | task | `FactoryStat` | `test_factory_stats` |
| FR-PRED-050 | Answer-key parity | engine tests | all | `test_engine_matches_answer_key`, `test_kpis_match_answer_key`, `test_hero_whatif` |
| FR-PRED-060 | Apply admin parameters; record params_hash | `EngineParameter` → run | `EngineParameter`, `PredictionRun` | `test_predictions_params_applied` |

### Master data in admin (masterdata) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-MASTER-010 | Factories & machines by gauge | `/admin/` | `Factory`, `FactoryMachine` | `test_admin_factory_crud` |
| FR-MASTER-020 | Departments & seasons | `/admin/` | `Department`, `Season` | `test_admin_master_crud` |
| FR-MASTER-030 | Holiday calendar | `/admin/` | `HolidayCalendar` | `test_calendar` (holiday path) |
| FR-MASTER-040 | Engine parameters/thresholds | `/admin/` | `EngineParameter` | `test_admin_param_change` |
| FR-MASTER-050 | T&A template (11 milestones, offsets) | `/admin/` | `TATemplate`, `TAMilestoneDef` | `test_admin_ta_template` |
| FR-MASTER-060 | Users & group membership | `/admin/` | `auth.User`, `auth.Group` | `test_admin_users_groups` |

### Risk & Alerts (alerts) — Tier S
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-ALERT-010 | Evaluate from rules each run (deduped) | task `evaluate_alerts` | `AlertRule`, `Alert` | `test_alerts_evaluation`, `test_alerts_dedupe` |
| FR-ALERT-020 | Feed + filters + nav badge | `/alerts/`, `/alerts/feed/` | `Alert` | `test_alerts_feed_filters` |
| FR-ALERT-030 | Acknowledge (scoped) | `/alerts/<id>/ack/` | `Alert` | `test_alerts_ack_scope` |
| FR-ALERT-040 | Assign (Management/Admin) | `/alerts/<id>/assign/` | `Alert`, `auth.User` | `test_alerts_assign_scope` |
| FR-ALERT-050 | Snooze (scoped) | `/alerts/<id>/snooze/` | `Alert` | `test_alerts_snooze` |
| FR-ALERT-060 | AI note per alert | feed partial | `Alert`, kb | `test_alerts_ai_note` |

### Reports & Analytics (reports) — Tier S (+ L)
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-REP-010 | Shipment forecast (8-week) | `/reports/shipment-forecast/` | `PredictionSnapshot`, `PurchaseOrder` | `test_report_shipment_forecast_matches_answer_key` |
| FR-REP-020 | Factory performance | `/reports/factory-performance/` | `FactoryStat` | `test_report_factory_performance` |
| FR-REP-030 | Export xlsx | `?export=xlsx` | — | `test_report_export` |
| FR-REP-040 | (L) T&A delay, inspection, on-time trend, plan-vs-actual, accuracy | `/reports/<kind>/` | various | *Later* |

### AI Assistant (assistant) — Tier M
| FR | Capability | URL / view | Models | Tests |
|---|---|---|---|---|
| FR-AI-010 | Page + slide-over | `/assistant/`, `/assistant/panel/` | `Conversation`, `ChatMessage` | `test_assistant_page` |
| FR-AI-020 | SSE streaming events | `/assistant/stream/` `assistant_stream` | `ChatMessage` | `test_assistant_sse_events` |
| FR-AI-030 | Tools call the same `services/` functions | `services/metrics`, `services/prediction` | all metric models | `test_assistant_tools_use_services` |
| FR-AI-040 | Source + as_of per number; "I don't have that"; role scope | stream view | `PredictionRun` | `test_assistant_provenance`, `test_assistant_refuses_unknown` |
| FR-AI-050 | ChromaDB citations | `services/kb` | kb (Chroma) | `test_assistant_citations` |
| FR-AI-060 | Excel export of a table | `/assistant/export.xlsx` | — | `test_assistant_export` |
| FR-AI-070 | Conversations + token usage stored | — | `Conversation`, `ChatMessage`, `TokenUsage` | `test_assistant_token_usage` |
| FR-AI-080 | Role scope honored per user | stream view | `auth.Group` | `test_assistant_role_scope` |
| FR-AI-090 | 30 golden questions (incl. 3 demo) | eval suite | all | `test_assistant_golden_questions` |
| FR-AI-100 | Offline fallback for 3 demo questions | config flag | pre-stored JSON | `test_assistant_demo_fallback` |

---

## 2. Design artifact coverage

| Design screen (handoff) | Covered by |
|---|---|
| Shell · header, sidebar, freshness | FR-DASH-010/020/030, FR-ACCT-060 |
| Executive Overview | FR-DASH-040…100 |
| Purchase Orders · list | FR-ORD-010/020/030/110 |
| PO detail | FR-ORD-040…100 |
| Factories · list | FR-FAC-010 |
| Factory detail | FR-FAC-020…080 |
| Daily Updates | FR-PROD-010…070 |
| AI Assistant · page + slide-over | FR-AI-010…100 |
| Risk & Alerts | FR-ALERT-010…060 (Should) |
| Reports & Analytics | FR-REP-010/020/030 (Should); FR-REP-040 (Later) |
| Login (Q Digital baseline pattern) | FR-ACCT-010/020 |

Every design screen traces to at least one FR. The prediction engine (FR-PRED-*) and master data
(FR-MASTER-*) have no standalone design screen by design: the engine is headless and master data uses the
Django admin (per brief).

## 3. Proposals (not shown in the design — flagged)

These are proposed additions required by the brief or the data but not drawn in the design export. Each is
marked ASSUMPTION in `PRD.md`.

| Proposal | Rationale | Where |
|---|---|---|
| Django admin as the only settings surface | Brief requires no custom Settings screen for the demo | FR-MASTER-*, A-01 |
| Factory reporting "No update" as a flag, not a band | Reconciles design's `noupdate` status with the answer-key band set | A-03 |
| Single seed snapshot (no daily history) | Demo scope; accuracy trend is Later | A-04 |
| Fabricated ChromaDB knowledge base | No source documents exist in `sample_data/` | FR-AI-050, A-08 |
| Auto-donor selection for machine reallocation | Generalises the hero recommendation | FR-ORD-080, A-11 |
| Audit log | Security requirement not in the design | FR-ACCT-050 |

## 4. Golden-data anchors (used across tests)

| Anchor | Value | Primary test |
|---|---|---|
| Open POs / pcs / FOB | 412 / 1,900,020 / 18,601,449.36 | `test_kpis_match_answer_key` |
| October on-time % | 86.25% | `test_kpis_match_answer_key` |
| Value at risk / # POs | 2,400,006.24 / 48 | `test_kpis_match_answer_key` |
| Top-3 share | GRL 774,059 · IRB 477,578 · SLM 428,400 = 70.0% | `test_kpis_match_answer_key` |
| Air-freight exposure | 539,720.28 | `test_kpis_match_answer_key` |
| Band counts | 354 / 10 / 28 / 13 / 7 | `test_engine_matches_answer_key` |
| Reported today | 18 of 22 (missing SLM, OKH, HMR, PBB) | `test_upload_reporting_status` |
| Hero 71010305 | 7 Nov, slip 9, Critical, score 76, prob 2% | `test_engine_matches_answer_key` |
| Hero on-time plan | +6 linking M/C + 2 Fridays → 29 Oct, air USD 38,016 avoided | `test_hero_whatif` |
