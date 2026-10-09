# Karbar Pulse — Risk & Alerts (PRD)

**App:** `alerts` · **FR prefix:** `FR-ALERT` · **Tier:** Should for 15 Oct
**As of:** 3 Oct 2026 · **Depends on:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`, `ai/prediction-engine.md`

> Canon: `sample_data/` + `00_Answer_Key.xlsx` win on every number; `design/` wins on layout and interaction.
> Alerts are an **in-app feed only** — no email / WhatsApp / push delivery in Phase 0 (`PRD.md §5`). Alerts
> are **derived from the prediction run plus reporting facts**, raised from admin-editable `AlertRule`s, and
> **deduped across runs** by `dedupe_key` (`data-model.md › Alert`). "No update" is a **factory reporting
> flag**, not a PO band (`prediction-engine.md §6`; ASSUMPTION A-03).

---

## 1. Purpose & design screen(s)

Alerts turn the morning's prediction snapshot and reporting status into a short, actionable queue: which POs
just turned critical, which factories went quiet, which yarn came in late, which inspection failed, which POs
turned at risk, and where reporting compliance has fallen. The feed lets an owner acknowledge, Management
assign, and anyone with rights snooze — so nothing important is lost between the daily files and the Monday
factory call.

Design screen (from `design/Karbar Pulse Handoff.dc.html` › "Risk & Alerts"): a filterable feed of alert
rows (kind / severity / state), per-alert actions, and an AI note. The nav alert badge comes from `/status/`
(`FR-ACCT-060`). Alert kinds and the example alerts come from the design and engine:

- **PO turned critical** — e.g. PO **71010305** predicted **9 days late** (band Critical).
- **Factory missed report** — the quiet factories **SLM / OKH / HMR / PBB**.
- **Yarn in-house late** — a PO whose yarn in-house milestone slipped.
- **Inspection failed** — a failed **final AQL** inspection.
- **PO turned at risk** — a PO whose band moved to At risk.
- **Reporting compliance** — a factory below the compliance threshold.

---

## 2. User stories

- **FR-ALERT-010 — Evaluation from AlertRule.** As the system, I want to raise alerts from enabled
  `AlertRule`s during each prediction run and dedupe them, so that one condition yields one live alert, not a
  duplicate every run.
- **FR-ALERT-020 — Feed with filters + badge.** As any user, I want a feed I can filter by kind, severity and
  state, with a nav badge of open alerts, so that I see the day's exceptions at a glance.
- **FR-ALERT-030 — Acknowledge.** As an owner / Management / Admin, I want to acknowledge an alert, so that
  the team knows it is seen and being handled.
- **FR-ALERT-040 — Assign.** As Management / Admin, I want to assign an alert to a user, so that one person
  clearly owns the follow-up.
- **FR-ALERT-050 — Snooze.** As an owner / Management / Admin, I want to snooze an alert until a time, so that
  a known, scheduled item stops cluttering the open feed until then.
- **FR-ALERT-060 — AI note per alert.** As any user, I want a short AI note on an alert with its `as_of`, so
  that I get a one-line summary of why it fired and what it affects, with the time it was computed.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-ALERT-010 Evaluation & dedupe
- **Given** a completed `PredictionRun`, **when** scoring and `FactoryStat` are written, **then** enabled
  `AlertRule`s are evaluated and matching `Alert` rows are created, each linked to that `run`
  (`prediction-engine.md §9`: "then raise `Alert`s from `AlertRule`s").
- **Given** the hero PO `71010305` with slip 9 and band Critical, **when** the `po_critical` rule
  (`threshold` e.g. slip ≥ 7) evaluates, **then** a `po_critical` alert is raised reading, in effect, "PO
  71010305 predicted 9 days late" with severity `critical`.
- **Given** factories with `FactoryStat.reported_today = False` and `missed_wd ≥ 1`, **when** the
  `factory_missed_report` rule evaluates, **then** one alert per quiet factory is raised (SLM / OKH / HMR /
  PBB in the seed) with severity `noupdate`.
- **Given** a PO whose yarn in-house milestone is late, a PO whose latest inspection `result = Fail` (final
  AQL), a PO whose band moved to At risk, and a factory below the compliance threshold, **when** the
  respective rules (`yarn_late`, `inspection_failed`, `po_at_risk`, `compliance`) evaluate, **then** one
  alert each is raised with the rule's `default_severity`.
- **Given** the same condition persists across two runs, **when** the second run evaluates, **then** the
  stable `dedupe_key` prevents a second `Alert` row (the existing alert is kept with its state), so the feed
  does not grow a duplicate every night.
- **Given** a disabled `AlertRule`, **when** a run evaluates, **then** no alerts of that kind are raised.

### FR-ALERT-020 Feed with filters + badge
- **Given** the feed `/alerts/`, **when** it loads, **then** it lists alerts newest first (index
  `(state, severity, created_at)`) and the partial `/alerts/feed/` can be filtered by **kind**
  (po_critical / factory_missed_report / yarn_late / inspection_failed / po_at_risk / compliance),
  **severity** (critical / risk / watch / noupdate) and **state** (open / acked / assigned / snoozed).
- **Given** open alerts, **when** `/status/` is read, **then** `alerts_open` equals the count of alerts in
  state `open` and drives the nav badge (`FR-ACCT-060`); acknowledging, assigning or snoozing reduces it.
- **Given** a snoozed alert whose `snooze_until` is in the future, **when** the default (open) view is shown,
  **then** it is hidden from the open list until `snooze_until` passes, after which it returns to open.
- **Given** an alert tied to a PO or factory, **when** a user clicks it, **then** it links to that PO detail
  (`/pos/<po_no>/`) or factory detail (`/factories/<code>/`).

### FR-ALERT-030 Acknowledge
- **Given** an alert, **when** the owner / Management / Admin POSTs `/alerts/<id>/ack/`, **then** `state`
  becomes `acked`, the row partial re-renders, `alerts_open` drops by one, and an `alert_ack` `AuditLog` row
  is written (`FR-ACCT-050`).
- **Given** a Merchandiser or QA who is **not** the alert owner, **when** they POST ack, **then** it is
  rejected 403 (owner-only for those roles), enforced in the queryset (`FR-ACCT-040`).

### FR-ALERT-040 Assign
- **Given** Management / Admin, **when** they POST `/alerts/<id>/assign/` with `user_id`, **then** `owner`
  is set to that user, `state` becomes `assigned`, the row re-renders, and an `alert_assign` `AuditLog` row
  is written.
- **Given** a Merchandiser or QA, **when** they attempt assign, **then** it is rejected 403 (Management /
  Admin only), and the Assign control is not shown to them (`FR-ACCT-030`).

### FR-ALERT-050 Snooze
- **Given** an alert, **when** the owner / Management / Admin POSTs `/alerts/<id>/snooze/` with `until`,
  **then** `snooze_until` is set, `state` becomes `snoozed`, the alert leaves the open list until that time,
  and the action is audited.
- **Given** a snooze `until` in the past, **when** it is submitted, **then** it is rejected with a validation
  message and the alert stays open.
- **Given** a snoozed alert, **when** `snooze_until` passes and the feed is next viewed (or the next run
  executes), **then** it reappears as open.

### FR-ALERT-060 AI note per alert
- **Given** any alert, **when** its AI note renders, **then** it shows a short summary and an `as_of` time
  equal to the raising run's `as_of` (M4 freshness honesty); every number in the note traces to `services/`
  (one source of numbers, `PRD.md §G3`).
- **Given** the hero `po_critical` alert, **when** its note renders, **then** it summarises the cause in the
  engine's terms (e.g. late yarn + linking shortfall driving a 9-day slip) consistent with the PO's drivers
  (`prediction-engine.md §5`) — the note never invents a number the snapshot does not hold.

---

## 4. Design components

- **Alert feed** — list of alert rows, each with kind icon, **severity Badge** (critical / risk / watch /
  noupdate variants), text, linked PO / factory, state, `created_at`, and an AI note with `as_of`.
- **Filters** — kind / severity / state controls driving the HTMX `/alerts/feed/` partial.
- **Row actions** — Acknowledge, Assign (Management / Admin only), Snooze (with a time picker), rendered per
  permission; actions re-render `partials/alerts/row.html`.
- **Nav badge** — open-alert count from `/status/`.
- Toast (from the design component list) may confirm an action; the canonical surface is the feed.

---

## 5. Data read / write + URLs / partials

**Models (`data-model.md`):**
- `AlertRule` — `kind`, `enabled`, `threshold` (JSON rule params, e.g. slip ≥ 7, compliance < 0.8),
  `default_severity` (admin-editable, `FR-MASTER`).
- `Alert` — `kind`, `severity`, `created_at`, `text`, `purchase_order?`, `factory?`, `owner?`, `state`
  (open / acked / assigned / snoozed), `snooze_until`, `run`, `dedupe_key` (unique).
- Reads for evaluation: `PredictionSnapshot` (`band`, `slip_days`, drivers), `FactoryStat`
  (`reported_today`, `missed_wd`, compliance), `Inspection` (`result`), `TAMilestone` (yarn in-house).
- Ownership for scoping: `Alert.owner`, and the linked `PurchaseOrder.merchandiser` /
  `Factory.merchandiser`.

**URLs / views (`urls-and-views.md`):**
- `GET /alerts/` → `alert_list` → `alerts/list.html` (read: all).
- `GET /alerts/feed/` → `alert_feed_partial` → `partials/alerts/feed.html` (filter kind / severity / state).
- `POST /alerts/<id>/ack/` → `alert_ack` → `partials/alerts/row.html` (write: owner / Management / Admin).
- `POST /alerts/<id>/assign/` → `alert_assign` (`user_id`) → row partial (write: Management / Admin).
- `POST /alerts/<id>/snooze/` → `alert_snooze` (`until`) → row partial (write: owner / Management / Admin).
- Badge source: `GET /status/` (`alerts_open`).

---

## 6. Empty / error / stale-data states

- **Empty feed:** when no alerts match the filter (or none are open), the feed shows "No alerts" and the nav
  badge is hidden (`alerts_open = 0`).
- **Write denied:** a non-permitted action returns 403 and the row partial shows "You don't have permission
  to do this"; the alert is unchanged.
- **Invalid snooze:** a past `until` is rejected with an inline validation message.
- **Stale run:** alert text and AI notes carry the raising run's `as_of`; if no newer run has executed, the
  feed shows that older `as_of` rather than implying freshness (M4). A factory that has not reported appears
  as a `factory_missed_report` / `noupdate` alert rather than being silently dropped.
- **Orphaned link:** if a linked PO closes (ships) between runs, the alert remains with its text but the link
  resolves to the (now closed) PO; the next run's dedupe/evaluation reconciles the open set.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read feed & badge | ✓ | ✓ | ✓ | ✓ |
| Acknowledge | ✓ | ✓ | own only | own only |
| Snooze | ✓ | ✓ | own only | own only |
| Assign | ✓ | ✓ | – | – |
| Edit AlertRule (admin) | ✓ | – | – | – |

"Own" = the current user is the alert's `owner`, or the merchandiser of the linked PO / factory. All
write actions are enforced in querysets and audited (`FR-ACCT-040`, `FR-ACCT-050`); template visibility
follows `FR-ACCT-030`.
