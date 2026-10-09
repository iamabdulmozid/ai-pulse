# AI Pulse — Accounts & access (PRD)

**App:** `accounts` · **FR prefix:** `FR-ACCT` · **Tier:** Must for 15 Oct
**As of:** 3 Oct 2026 · **Depends on:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`, `tech/security.md`

> Canon: `sample_data/` + `00_Answer_Key.xlsx` win on every number; `design/` wins on layout and interaction.
> Roles are Django groups **Admin / Management / Merchandiser / QA**. All four groups **read the whole
> book**; write actions are **scoped to ownership and enforced in querysets and service functions, not only
> in templates** (`PRD.md §3, §10`; ASSUMPTION A-05). Persona→group mapping: CEO + Head of Merchandising →
> Management; merchandiser → Merchandiser; QA head → QA; Shipping folds into Management read-only
> (ASSUMPTION A-06, A-07). No custom user model in Phase 0 — `django.contrib.auth.User` + `Group` plus a
> thin `UserProfile` for the header pill (`data-model.md`).

---

## 1. Purpose & design screen(s)

This module is the front door and the access-control spine of AI Pulse. It authenticates the user,
puts them on the Executive Overview, and then governs everything else: which navigation items and write
actions appear, which querysets a user may write to, what gets recorded in the audit trail, and the
single `/status/` feed that drives the header freshness pill, the alert badge and the role label.

Design screens (from `design/Karbar Pulse Handoff.dc.html` and the prototype):

- **Login** — a single username/password form, product mark, error region.
- **App shell user menu** — the header region that shows the user name + role pill, the freshness pill
  (`as_of` + `reports_today {received, expected}`), the nav alert badge, the ⌘K palette entry, the theme
  toggle, and logout. The shell is shared with the `dashboard` module (`FR-DASH`); this PRD owns only the
  identity, freshness and access-control behaviour of the shell, not the Overview content.

The shell is dark + light themed via CSS variables; theme is a persisted client preference and is not an
access concern.

---

## 2. User stories

- **FR-ACCT-010 — Login.** As any staff user, I want to sign in with my username and password and land on
  the Overview, so that I start every morning on the three-sentence state of the business.
- **FR-ACCT-020 — Logout & session handling.** As any signed-in user, I want to sign out and have idle
  sessions expire, so that an unattended screen does not leave the book open.
- **FR-ACCT-030 — Role-based navigation & action visibility.** As a user in a specific group, I want to see
  only the write actions my role is allowed to use, so that the interface matches what I can actually do.
- **FR-ACCT-040 — Queryset-level write scoping.** As the business owner of the data, I want every write to
  be checked server-side against ownership and role, so that a hidden or forged button cannot change data
  the user does not own.
- **FR-ACCT-050 — Audit log.** As Admin / Management, I want security-relevant actions recorded with user,
  time and target, so that I can see who logged in, uploaded, commented, acted on an alert, changed a
  parameter, exported, or used the assistant.
- **FR-ACCT-060 — /status endpoint.** As the app shell, I want one JSON endpoint that returns freshness,
  open-alert count and the current user's role, so that the freshness pill, alert badge and role label
  never disagree with the screens.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-ACCT-010 Login
- **Given** a registered merchandiser on `/login/`, **when** they submit correct credentials, **then** they
  are authenticated and redirected to `/` (Executive Overview), and an `AuditLog` row `action="login"` is
  written with their user and IP.
- **Given** a user on `/login/`, **when** they submit a wrong password or unknown username, **then** the
  page re-renders with a single non-enumerating error ("Your username and password did not match") and no
  indication of which field was wrong, and no `login` audit row is written.
- **Given** an unauthenticated request to any protected URL (for example `/`, `/pos/`, `/alerts/`), **when**
  it is made, **then** the user is redirected to `/login/?next=<path>` and, after a successful login, sent on
  to that `next` path (defaulting to `/` when `next` is absent or not a safe local path).
- **Given** an already-authenticated user, **when** they open `/login/`, **then** they are redirected to `/`.
- **Given** the demo seed users, **when** the CEO (Management group) signs in, **then** the header shows
  display role "CEO" from `UserProfile.display_role` while the enforced group remains Management.

### FR-ACCT-020 Logout & session handling
- **Given** a signed-in user, **when** they POST `/logout/`, **then** the session is flushed and they are
  redirected to `/login/`; a GET to `/logout/` does not log out (POST only, CSRF-protected).
- **Given** a signed-in session that has been idle past the configured timeout, **when** the next request is
  made, **then** the session is treated as expired and the user is redirected to `/login/?next=<path>`.
- **Given** any protected page, **when** it is served, **then** it is marked non-cacheable so that pressing
  Back after logout does not reveal book data.

### FR-ACCT-030 Role-based navigation & action visibility
- **Given** a **Merchandiser**, **when** they view a PO they own, **then** the comment form is visible; on a
  PO owned by another merchandiser the comment form is hidden (`/pos/<po_no>/comments/` write is PO owner /
  Management / Admin per `urls-and-views.md`).
- **Given** a **QA** user, **when** they view the Daily Updates screen, **then** no upload control is shown
  (upload is Merchandiser / Management / Admin; QA cannot upload per the role matrix).
- **Given** a **Merchandiser** or **QA** user, **when** they view an alert, **then** Acknowledge and Snooze
  appear only on alerts they own, and **Assign** never appears (assign is Management / Admin only;
  `FR-ALERT-040`).
- **Given** a non-Admin user, **when** they look at the navigation, **then** no link to `/admin/` is shown
  (master-data editing is Admin-only; `FR-MASTER-*`).
- **Given** Shipping (folded into Management read-only, A-07), **when** they view any screen, **then** read
  is full and no write control is shown beyond what Management is granted; distinct Shipping group is Later.
- Visibility rules here are a convenience only; the authoritative check is **FR-ACCT-040**.

### FR-ACCT-040 Queryset-level write scoping (server-side)
- **Given** a Merchandiser who does **not** own PO `71010305`, **when** they POST a comment to
  `/pos/71010305/comments/` directly (bypassing the hidden form), **then** the server rejects it with 403
  and writes no `Comment` row. "Own" = the PO's `merchandiser` is the current user.
- **Given** a Merchandiser, **when** they POST `/uploads/`, **then** it is accepted (Merchandiser is an
  upload role); **given** a QA user doing the same, **then** it is rejected 403.
- **Given** any user, **when** they POST `/alerts/<id>/assign/`, **then** it succeeds only for Management /
  Admin and is 403 otherwise, regardless of ownership.
- **Given** a QA user, **when** they comment, **then** it is allowed only on POs they are tied to via
  inspection (QA on inspected POs per the role matrix), enforced in the queryset, not the template.
- **Given** any write endpoint, **when** access is denied, **then** the denial happens in the service /
  queryset layer so the same rule holds for the assistant and any future client, and no partial write
  occurs.
- The what-if endpoint `/pos/<po_no>/whatif/` is **read-only for all** (writes no snapshot) and is therefore
  not scope-gated for writes.

### FR-ACCT-050 Audit log
- **Given** any of the security-relevant actions, **when** it succeeds, **then** exactly one append-only
  `AuditLog` row is written with `user`, `at`, `action`, `target`, `meta`, `ip`. Tracked `action` values:
  `login`, `upload`, `comment`, `alert_ack`, `alert_assign`, `param_change`, `export`, `chat`
  (`data-model.md › AuditLog`). (`alert_snooze` is recorded under the alert-action family alongside
  `alert_ack`.)
- **Given** an export of the filtered PO list (`/pos/export.xlsx`) or a report xlsx (`FR-REP-030`) or an
  assistant table (`FR-AI-060`), **when** it completes, **then** an `export` audit row records the user and
  what was exported.
- **Given** an assistant query (`FR-AI-*`), **when** the stream completes, **then** a `chat` audit row is
  written for the user.
- **Given** a parameter change in Django admin (`FR-MASTER-040`), **when** it is saved, **then** a
  `param_change` audit row is written in addition to Django admin's own `LogEntry`.
- `AuditLog` is append-only: rows are never edited or deleted through the app.

### FR-ACCT-060 /status endpoint
- **Given** a signed-in user, **when** the shell calls `GET /status/`, **then** it returns JSON with
  `as_of`, `reports_today {received, expected}`, `factories_missing[]`, `alerts_open`, and
  `user {name, role}` (`urls-and-views.md`).
- **Given** the demo seed as of `DEMO_TODAY` 15 Oct 2026 (latest expected report 14 Oct), **when**
  `/status/` is read, **then** `reports_today.expected` equals the count of factories expected to report and
  `factories_missing[]` lists the quiet factories (the four named in the design: SLM / OKH / HMR / PBB),
  so the freshness pill shows "received of expected" with those four flagged "No update".
- **Given** open alerts, **when** `/status/` is read, **then** `alerts_open` equals the count of alerts in
  state `open` and drives the nav badge (`FR-ALERT-020`).
- **Given** the signed-in user, **when** `/status/` returns, **then** `user.role` is the display role used
  for the header pill; all numbers carry the same `as_of` used everywhere else (M4 freshness honesty).
- `/status/` requires login (read: all four groups); `/healthz/` is the only public JSON health endpoint
  and returns `{status, as_of}` without user data.

---

## 4. Design components

- **Login:** single Card with username + password fields, submit button, inline error region, product mark.
  Follows the design-system tokens (`surface`, `border`, `text`, `accent`); dark + light.
- **Shell user menu:** header with product mark, nav with **alert badge** (count from `/status/`),
  **freshness pill** (Tooltip showing `as_of` + `reports_today`), **role pill** (`UserProfile.display_role`),
  **⌘K** Command palette entry, **theme toggle**, and a user menu containing **Logout** (POST).
- **Badge** (status variants) for the role and alert count; **Tooltip** for the freshness source; **Command
  / Dialog** for ⌘K. No custom settings surface (A — master data lives in Django admin, `FR-MASTER-*`).

---

## 5. Data read + URLs / partials

**Models (`data-model.md`):**
- `auth.User`, `auth.Group` (Admin / Management / Merchandiser / QA) — identity and role.
- `accounts.UserProfile` — `user`, `display_role` (ceo / management / merch / qa / shipping; header pill only).
- `accounts.AuditLog` — `user`, `at`, `action`, `target`, `meta`, `ip` (append-only).
- Read for `/status/`: latest `PredictionRun` / `FactoryStat` (`reported_today`, `missed_wd`,
  `last_report_date`) for freshness and `factories_missing[]`; `alerts.Alert` (state `open`) for
  `alerts_open`.
- Write scoping reads ownership from `PurchaseOrder.merchandiser`, `Factory.merchandiser`,
  `Alert.owner`, `UploadBatch.uploaded_by`.

**URLs / views (`urls-and-views.md`):**
- `GET, POST /login/` → `login_view` → `accounts/login.html` (public).
- `POST /logout/` → `logout_view` → `/login/` (any).
- `GET /status/` → `status_json` (read: all).
- `GET /healthz/` → `health` → `{status, as_of}` (public).
- `GET /palette/search/` → `cmdk_search` → `partials/shell/cmdk_results.html` (read: all) — ⌘K entity + nav
  search; respects read scope (all).
- Admin surface `/admin/` is Admin / staff only (see `FR-MASTER-*`).

---

## 6. Empty / error / stale-data states

- **Login error:** one non-enumerating message; the username is preserved, the password is cleared; no audit
  row on failure.
- **Session expired:** silent redirect to `/login/?next=<path>`; after login the user resumes at `next`.
- **Write denied:** 403 with a plain message; for HTMX write partials the fragment shows "You don't have
  permission to do this" and the underlying data is unchanged.
- **/status/ degraded:** if the latest `PredictionRun` is missing or stale, `/status/` still returns
  `as_of` of the most recent run and the shell shows the pill with that (older) `as_of` rather than implying
  freshness; `factories_missing[]` reflects the same run (M4 — never silently stale).
- **No open alerts:** `alerts_open = 0`, the nav badge is hidden.
- **No profile row:** if a user has no `UserProfile`, the role pill falls back to the user's primary group
  name; access is still driven by group membership, not the pill.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Log in, read all screens & `/status/` | ✓ | ✓ | ✓ | ✓ |
| See upload control | ✓ | ✓ | ✓ | – |
| See comment form | ✓ | ✓ | own POs/factories | own (QA on inspected POs) |
| See Acknowledge / Snooze on alert | ✓ | ✓ | own only | own only |
| See Assign on alert | ✓ | ✓ | – | – |
| See `/admin/` link & edit master data | ✓ | – | – | – |
| View audit log | ✓ | ✓ (read) | – | – |

All write permissions are enforced in querysets and service functions (`FR-ACCT-040`), with template
visibility (`FR-ACCT-030`) as a convenience only. "Own" = the PO's `merchandiser` / the factory's
`merchandiser` is the current user. Shipping is Management read-only in Phase 0 (A-07).
