# Karbar Pulse — Master data (PRD)

**App:** `masterdata` · **FR prefix:** `FR-MASTER` · **Tier:** Must for 15 Oct
**As of:** 3 Oct 2026 · **Depends on:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`, `ai/prediction-engine.md`

> Canon: `sample_data/` + `00_Answer_Key.xlsx` win on every number; `design/` wins on layout and interaction.
> **All master data is edited only in the Django admin.** There is no custom Settings screen in Phase 0
> (`PRD.md §5 non-goals`; `urls-and-views.md › Admin`). Editing is **Admin group / staff only**. Changing a
> parameter affects **future prediction runs only**; each run records a `params_hash` so a snapshot's
> inputs stay auditable (`prediction-engine.md §8, §9`).

---

## 1. Purpose & design screen(s)

This module defines the reference data the whole system reads: factories and their machines by gauge,
departments and seasons, the holiday calendar, the engine's weights and thresholds, the T&A template, and
the users and their group membership. It has **no bespoke UI** — the surface is the standard Django admin
at `/admin/`. The design handoff deliberately marks Settings as deferred ("Settings is deferred (LATER)");
this PRD records what must be editable there and the invariants the admin forms must protect, so that the
engine and screens keep reproducing the answer key after an edit.

Design screen: none bespoke. Reference surface: Django admin (`/admin/`), Admin / staff only.

---

## 2. User stories

- **FR-MASTER-010 — Factories & machines-by-gauge.** As an Admin, I want to add and edit factories and their
  knitting machines per gauge in the admin, so that capacity, load and location are correct for scoring and
  scorecards.
- **FR-MASTER-020 — Departments & seasons.** As an Admin, I want to manage departments and seasons, so that
  styles and POs classify correctly (Men / Women / Kids; AW / HO / SS / SU + year).
- **FR-MASTER-030 — Holiday calendar.** As an Admin, I want to maintain Bangladesh public holidays, so that
  the working-day calendar is correct; the Friday weekend is a rule, not data.
- **FR-MASTER-040 — EngineParameter weights/thresholds.** As an Admin, I want to edit the engine's weights,
  caps, costs and thresholds, so that policy can change without code; defaults equal the answer-key
  `Parameters` sheet.
- **FR-MASTER-050 — T&A template.** As an Admin, I want to maintain the 11-milestone T&A template with its
  offsets (days before ex-factory), so that every PO's planned calendar is generated consistently.
- **FR-MASTER-060 — Users & group membership.** As an Admin, I want to manage users and their groups, so that
  roles (Admin / Management / Merchandiser / QA) and ownership drive access.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-MASTER-010 Factories & machines-by-gauge
- **Given** an Admin in `/admin/`, **when** they open a `Factory`, **then** they can edit `code`, `name`,
  `area`, `district`, `gauges`, `linking_machines`, `washing` (In-house / Subcontract), shift / hours fields,
  `certifications`, `bsci_rating`, `merchandiser` (owner) and `status`, and edit `FactoryMachine` rows
  (gauge × count) inline.
- **Given** the demo seed, **when** the factory list is viewed, **then** there are **22 factories**
  (ASSUMPTION A-14), each with a unique `code` (natural key used in every upload file, e.g. `GRL`).
- **Given** a `FactoryMachine` edit, **when** the Admin tries to add a second row for the same factory +
  gauge, **then** the `unique_together(factory, gauge)` constraint rejects it.
- **Given** a change to a factory's machines-by-gauge, **when** the next prediction run executes, **then** the
  knitting capacity recomputes as `Σ_gauge(machines[gauge] × knit_mc_minutes_per_day) / knitting_minutes_pc`
  into `FactoryStat.knit_load_pct` (`prediction-engine.md §7`); the current snapshot is unchanged until that
  run.
- **Given** a factory `merchandiser` (owner), **when** it is set, **then** it drives factory-note write scope
  (`FR-FAC` / `FR-ACCT-040`).

### FR-MASTER-020 Departments & seasons
- **Given** an Admin, **when** they manage `Department`, **then** the set is Men / Women / Kids (`name`
  unique, 16 chars).
- **Given** an Admin, **when** they manage `Season`, **then** each has a unique `code` (e.g. `AW26`, `HO26`,
  `SS27`, `SU27`), a `kind` (AW / HO / SS / SU) and a 2-digit `year`, consistent with the generator's
  `season_for` rule (ASSUMPTION A-15).
- **Given** a season referenced by open POs, **when** an Admin attempts to delete it, **then** the admin
  protects referential integrity (deletion is blocked / protected rather than silently cascading open POs).

### FR-MASTER-030 Holiday calendar
- **Given** an Admin, **when** they add a `HolidayCalendar` row (`date` unique, `name`), **then** that date
  becomes non-working in `is_working_day` with **no formula change** (`prediction-engine.md §1`).
- **Given** the Friday-weekend rule, **when** holidays are considered, **then** Friday is treated as weekend
  by rule (not stored as rows); the seed uses a Friday-only weekend and loads public holidays separately.
- **Given** a holiday added inside a PO's remaining window, **when** the next run executes, **then** Available
  WD drops accordingly (e.g. the hero's `wd_between(15 Oct, 29 Oct)` = 12 would fall if a working day in that
  window became a holiday), changing projected ex-factory and slip on the next run only.
- **Given** a duplicate `date`, **when** an Admin tries to save it, **then** the unique constraint rejects it.

### FR-MASTER-040 EngineParameter weights/thresholds
- **Given** a fresh seed, **when** the `EngineParameter` set is inspected, **then** every default equals the
  answer-key `Parameters` sheet (`prediction-engine.md §8`), including: `air_usd_per_kg` 6.00,
  `sea_usd_per_kg` 0.50, `rate_window_wd` 7, `flow_limit_days` 1.5, `yarn_to_knit_days` 2,
  `knit_mc_minutes_per_day` 1020, `stage_lag_linking` 1.0, `stage_lag_mending/_washing/_ironing/_packing`
  0.5 each, component caps 50 / 20 / 15 / 10 / 5, band cut-offs 25 / 50 / 75, `slip_forces_critical` 7,
  `freshness_missed1` 3, `freshness_missed2plus` 5, `prob_floor` 0.02, `prob_ceiling` 0.98.
- **Given** the seeded parameters, **when** the engine runs, **then** it reproduces the hero PO exactly:
  bottleneck Linking at 411.1 pcs/day, required 680, Available WD 12, N 19, slack −7, projected ex-factory
  7 Nov 2026, slip 9, score 76 (50 + 12 + 12 + 0 + 0), band Critical, on-time probability 2%, air exposure
  USD 38,016 (`prediction-engine.md §3, §5`).
- **Given** an Admin changes `air_usd_per_kg` from 6.00, **when** they save, **then** a `param_change`
  `AuditLog` row is written (`FR-ACCT-050`); the **current** snapshot is unchanged, and only the **next**
  run uses the new value and stamps a new `params_hash` (`prediction-engine.md §8, §9`).
- **Given** two runs with different parameter sets, **when** their snapshots are compared, **then** their
  `params_hash` values differ, so each snapshot's inputs are auditable.

### FR-MASTER-050 T&A template
- **Given** an Admin, **when** they view `TATemplate` "Standard sweater", **then** it has **11**
  `TAMilestoneDef` rows (`seq` 1–11) with `days_before_exfactory` offsets **95, 85, 80, 60, 50, 45, 42, 40,
  34, 1, 0** and a `responsible` per milestone (`data-model.md`; ASSUMPTION A-10).
- **Given** the single standard template, **when** POs are seeded, **then** each open PO has 11 `TAMilestone`
  rows generated from the template relative to its `planned_exfactory`; washing-related timing applies only
  when the style's `wash_required = Y`.
- **Given** a duplicate `seq` within the template, **when** an Admin tries to save it, **then**
  `unique_together(template, seq)` rejects it.
- Note: the six production **stages** (knitting, linking, trimming & mending, washing, ironing, packing) are
  **not** milestones — they live in `daily_production` and their curves are computed forecasts, not stored
  here (A-10).

### FR-MASTER-060 Users & group membership
- **Given** an Admin, **when** they manage users, **then** they can create users and assign them to exactly
  the groups Admin / Management / Merchandiser / QA, and set each user's `UserProfile.display_role` (header
  pill only).
- **Given** the persona mapping, **when** seed users are created, **then** CEO + Head of Merchandising are in
  **Management**, each merchandiser in **Merchandiser**, QA head in **QA** (A-06); Shipping is Management
  read-only (A-07).
- **Given** a merchandiser user, **when** they are set as a PO's or factory's `merchandiser`, **then** that
  ownership drives write scope everywhere (`FR-ACCT-040`).
- **Given** a non-Admin user, **when** they attempt to reach `/admin/`, **then** access is denied (admin is
  Admin / staff only).

---

## 4. Design components

None bespoke. The surface is the standard Django admin: changelists, change forms, inline formsets
(`FactoryMachine` under `Factory`; `TAMilestoneDef` under `TATemplate`), and Django's built-in user/group
admin. Admin registrations (`urls-and-views.md › Admin`): Department, Season, Factory, FactoryMachine,
HolidayCalendar, EngineParameter, TATemplate / TAMilestoneDef, AlertRule (see `FR-ALERT-010`), Users &
Groups. AlertRule thresholds are admin-editable but documented in the alerts PRD.

---

## 5. Data read / write + URLs / partials

**Models (`data-model.md`):** `Department`, `Season`, `Factory`, `FactoryMachine`, `HolidayCalendar`,
`EngineParameter`, `TATemplate`, `TAMilestoneDef`; plus `auth.User`, `auth.Group`,
`accounts.UserProfile`. Related read-only context the engine consumes: `TAMilestone` (per-PO, generated),
`PredictionRun.params_hash` (audit of the parameter set used).

**URLs:** Django admin only — `/admin/` and its per-model routes (Admin / staff). No app URLs, no HTMX
partials; master data is **not** editable from any screen in `urls-and-views.md`. The engine reads a typed
snapshot of the active `EngineParameter` set at run time (`prediction-engine.md §0, §8`); the holiday
calendar feeds `is_working_day`.

---

## 6. Empty / error / stale-data states

- **Validation errors** surface as standard Django admin form errors (unique constraints on `Factory.code`,
  `Season.code`, `HolidayCalendar.date`, `EngineParameter.key`, `unique_together(factory, gauge)`,
  `unique_together(template, seq)`).
- **Referential protection:** deleting a `Season`, `Factory` or `Department` referenced by open POs is
  blocked / protected rather than cascading live data.
- **Stale by design:** a parameter / holiday / machine edit does **not** retro-change the current snapshot;
  screens keep showing the last run's numbers with that run's `as_of` until the next run executes. The admin
  change form should note that changes apply to the next run (so an editor does not expect live screens to
  move immediately).
- **Missing active parameter set:** if no active `EngineParameter` set exists, the engine falls back to the
  documented defaults rather than running with blanks.
- **Empty template:** a `TATemplate` with fewer than 11 milestone definitions is a configuration error;
  PO T&A generation should fail loudly rather than produce a partial calendar.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Open `/admin/` | ✓ (staff) | – | – | – |
| Edit factories / machines | ✓ | – | – | – |
| Edit departments / seasons | ✓ | – | – | – |
| Edit holiday calendar | ✓ | – | – | – |
| Edit EngineParameter | ✓ | – | – | – |
| Edit T&A template | ✓ | – | – | – |
| Manage users & groups | ✓ | – | – | – |

Master-data editing is Admin-only; every parameter change writes a `param_change` audit row (`FR-ACCT-050`).
Non-Admin roles read the *effects* of master data on the screens (`FR-DASH`, `FR-ORD`, `FR-FAC`) but cannot
edit it in Phase 0.
