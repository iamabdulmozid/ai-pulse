# AI Pulse — Security

Phase 0 (demo + pilot). Django 5.2 auth + groups, HTMX partials, an SSE assistant, and Excel upload.
This document specifies **how access is enforced**, **how uploads are validated**, **what leaves the
system to OpenAI**, and **what is audited**. The companion operational hardening (TLS, secrets on the
host, `.env` perms) is in `tech/deployment.md`; the full URL/view access table is in
`tech/urls-and-views.md`.

---

## 1. Role scoping lives in querysets, not only templates

The authorization rule for Phase 0 (PRD A-05): **every authenticated user reads the whole book**; every
**write** is scoped to **ownership + group**. Hiding a button in a template is not enough — a crafted
POST must also be rejected. So the scope is enforced where the rows are selected: a `services/` function
(or a model manager method) returns only the rows the user is **allowed to write**, and the view acts on
that queryset. If the target row is not in the write-eligible queryset, the view returns 403/404 — the
write never happens.

**Pattern.** Reads use the full book; writes go through a scoping helper:

```python
# services/scoping.py  (shape, not business code)

def readable_pos(user):
    # Read: all. Any authenticated user in any group sees the full order book.
    return PurchaseOrder.objects.all()

def writable_pos(user):
    # Write: Admin/Management -> all; Merchandiser/QA -> own only.
    if in_group(user, "Admin", "Management"):
        return PurchaseOrder.objects.all()
    if in_group(user, "Merchandiser"):
        return PurchaseOrder.objects.filter(merchandiser=user)          # PO owner
    if in_group(user, "QA"):
        return PurchaseOrder.objects.filter(inspection__isnull=False).distinct()  # inspected POs
    return PurchaseOrder.objects.none()
```

The view then selects the target **from the writable queryset**, so an out-of-scope id simply is not
found:

```python
# orders/views.py  (shape)
def po_comment_create(request, po_no):
    po = get_object_or_404(writable_pos(request.user), po_no=po_no)   # 404 if not writable
    # ... create Comment(author=request.user, purchase_order=po, text=...)
```

### Concrete cases

- **PO comments** (`POST /pos/<po_no>/comments/`): writable = PO's `merchandiser` **or**
  Management/Admin; **QA** may comment on POs they have inspected. Target PO is fetched from
  `writable_pos(user)`; otherwise 404. `author` is forced to `request.user` (never from the form).
- **Factory notes** (`POST /factories/<code>/notes/`): writable = the factory's `merchandiser` (owner)
  or Management/Admin — `writable_factories(user)` filters by `Factory.merchandiser=user`.
- **Alert actions** (`POST /alerts/<id>/ack|snooze|assign/`): **ack/snooze** scoped to the alert
  `owner` (or Management/Admin); **assign** is Management/Admin only. The alert is fetched from
  `actionable_alerts(user)`; `assign` additionally validates the target `user_id` is a real user. A
  Merchandiser POSTing `assign` gets 403 even though the endpoint exists.
- **Uploads** (`POST /uploads/`): allowed for Merchandiser/Management/Admin; **QA cannot upload**. The
  created `UploadBatch.uploaded_by` is forced to `request.user`; the batch **status** endpoint is
  limited to the batch owner.
- **Assistant** (`POST /assistant/stream/`): read tools run against `readable_*` (full book); the SSE
  view enforces the same per-user scope so a tool can never return or mutate out-of-scope rows, and
  threads (`/assistant/threads/...`) are limited to the requesting user.

### Role access matrix (summary — authoritative copy in `tech/urls-and-views.md`)

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Read all screens & data | ✓ | ✓ | ✓ | ✓ |
| Upload daily files | ✓ | ✓ | ✓ | – |
| Comment on PO / factory note | ✓ | ✓ | own only | own only (QA on inspected POs) |
| Ack / snooze alert | ✓ | ✓ | own only | own only |
| Assign alert | ✓ | ✓ | – | – |
| Edit master data / parameters (Django admin) | ✓ | – | – | – |
| Use assistant | ✓ | ✓ | ✓ | ✓ |

"own" = the PO's merchandiser or the factory's owner is the current user. Enforced in querysets and
service functions, not only in templates.

---

## 2. Authentication & authorization

- **Auth:** `django.contrib.auth` with the four **groups** Admin / Management / Merchandiser / QA
  (PRD §10; personas → groups A-06). No custom user model in Phase 0.
- **Login required everywhere** except `/login/` and `/healthz/` (both public). This is enforced by a
  login-required default (middleware / `LoginRequiredMiddleware` or a base-view mixin), not per-view
  opt-in, so a new view is protected by default. `/admin/` is Django admin, restricted to the Admin
  group / staff.
- **Authorization** is the queryset scoping of §1 plus group checks on write endpoints.

### CSRF with HTMX

Django CSRF protection stays on for every unsafe method (POST). HTMX requests must carry the token.
The app uses the standard pattern: the token is rendered once and attached to all HTMX requests via
`hx-headers` on the body, so every `hx-post` partial (comments, notes, alert actions, upload, what-if,
assistant stream) is protected without per-form boilerplate:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

- The Django CSRF cookie + `X-CSRFToken` header are validated server-side on every POST partial.
- `CSRF_TRUSTED_ORIGINS` includes the HTTPS site origin (behind Caddy); `CSRF_COOKIE_SECURE=True` in
  prod.
- GET partials (tables, charts, status polls) are safe methods and need no token.

---

## 3. Upload validation & limits

Uploads are the main untrusted-input surface. Rules:

- **Extension / type:** only `.xlsx` is accepted (the six file kinds: order book, T&A calendar, daily
  production, inspection, factory master, shipment). The extension is checked **and** the file is
  parsed as a real workbook with openpyxl — a mislabelled file fails to parse and is rejected.
- **Max size:** a hard cap via `DATA_UPLOAD_MAX_MEMORY_SIZE` / an explicit size check in the upload view
  (e.g. a few MB — daily files are small); oversize uploads are rejected before any processing.
- **Parsing happens in the worker, not the web process.** `POST /uploads/` only (a) validates
  extension/size, (b) writes the file to the media volume, (c) creates an `UploadBatch` (status
  `queued`), and (d) enqueues `ingest_file(batch_id)` on django-q2. The actual openpyxl parse, kind/
  factory/date detection, and per-row validation run in the **worker** container. The web process is
  never blocked by a large or malicious workbook, and a parser hang cannot take down request serving.
- **Per-row validation + batch-level rejection:** `ingest_file` validates every row; warnings and
  errors are collected into `UploadBatch.warnings` / `.errors` as `[{row, message}]`. **A file with any
  error is rejected as a whole batch — there are no partial writes** (the upsert runs in a transaction;
  on error it rolls back and the batch goes to `status=error`). The UI shows per-row results via the
  HTMX status poll.
- **Filename sanitisation & storage:** the original filename is stored for display
  (`original_filename`) but the stored file is given a safe, generated name; uploads are written to the
  **media volume outside the web/static root** (`/app/media`, not served by WhiteNoise), so an uploaded
  file can never be fetched back as a static asset or executed.
- **No macros executed:** openpyxl reads cell values only; it does not evaluate VBA/macros.

---

## 4. OpenAI data handling

The assistant uses the OpenAI SDK with tool calling (model from `OPENAI_MODEL`, embeddings
`text-embedding-3-small`).

- **What is sent to OpenAI:** the user's question; the **tool call arguments** the model chooses; the
  **tool results** (computed figures returned by `services/` functions) and the **retrieved document
  chunks** from ChromaDB used for citations. That is all.
- **What is NOT sent:** no secrets (API keys, `SECRET_KEY`, DB credentials), no raw database dump, no
  bulk table exports — only the specific, scoped figures a tool returns for the question asked.
- **Numbers come from tools, not the model.** Every figure is computed by a `services/` function
  (the same ones the screens call) and passed to the model as a tool result; the model phrases the
  answer but does not invent numbers. ChromaDB supplies **unstructured text for citations only**.
- **Knowledge base is fabricated/fictional (Phase 0).** Per PRD A-08, no real unstructured documents
  exist; `seed_demo` deterministically fabricates clearly-fictional English documents (quality manual,
  T&A standards, 22 factory profiles, audit notes, PO comments). So the KB sent as context contains no
  real confidential supplier documents in Phase 0.
- **Key & model in env only:** `OPENAI_API_KEY` and `OPENAI_MODEL` come from `.env` (never in code or
  image); see `tech/deployment.md §3`.
- **Retention stance:** Pulse stores only its own conversation history and token counts in Postgres
  (`Conversation`, `ChatMessage`, `TokenUsage`). It relies on the OpenAI API's standard data handling
  (API traffic is not used for model training); no additional data is sent for retention. Token usage is
  metered per conversation for cost visibility.

---

## 5. Audit log

The append-only `AuditLog` model (`accounts`, see `data/data-model.md`) records security-relevant
actions. Fields: `user`, `at`, `action`, `target`, `meta` (JSON), `ip`.

**Recorded `action` values:** `login`, `upload`, `comment`, `alert_ack`, `alert_assign`,
`alert_snooze`, `param_change` (EngineParameter / master-data edits in admin), `export` (xlsx
downloads), `chat` (assistant use).

- The log is **append-only** — written by the views/tasks that perform each action, never updated or
  deleted in normal operation.
- **Who can view:** the audit trail is visible to the **Admin** group only (via Django admin). It is not
  exposed on any read-all screen.

---

## 6. Secrets & transport

- **HTTPS everywhere** via Caddy (automatic certs, HSTS header); `SECURE_SSL_REDIRECT=True` and
  `SECURE_PROXY_SSL_HEADER` set because TLS terminates at Caddy (`tech/deployment.md §2`).
- **DEBUG=False** in production (no tracebacks/SQL leaked to users).
- **`ALLOWED_HOSTS`** pinned to the real hostname; **`CSRF_TRUSTED_ORIGINS`** to the HTTPS origin.
- **Secure cookies:** `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`; cookies are HttpOnly by
  default. Security headers (`X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`) set at Caddy.
- **Secrets** (`SECRET_KEY`, `DATABASE_URL`/DB password, `OPENAI_API_KEY`) live only in the host `.env`
  (`chmod 600`, git-ignored), read via django-environ — not baked into the image or compose file.

---

## 7. Threat notes (Phase 0) and what is deferred

**Mitigated in Phase 0:**
- Broken access control on writes — queryset scoping + forced `author`/`uploaded_by` (§1).
- CSRF on HTMX POSTs — token header on every request (§2).
- Malicious/oversized uploads — extension + size + off-request parsing in the worker, no partial writes,
  storage outside web root (§3).
- Prompt-driven data exfiltration — the model only ever sees scoped tool results + fictional KB chunks;
  numbers are computed, not model-generated (§4).
- Transport/secret exposure — HTTPS, DEBUG off, secrets in `.env` only (§6).
- Accountability — append-only audit log of sensitive actions (§5).

**Deferred (post–Phase 0 / Later):**
- Factory self-upload portal and per-factory external accounts (merchandisers upload in Phase 0).
- A dedicated Shipping group (folds into Management read-only now, A-07); finer-grained per-field
  permissions.
- Email/WhatsApp/push alert delivery (alerts are an in-app feed only) and the out-of-band security that
  implies.
- Rate limiting / WAF, MFA, and SSO.
- Field-level encryption and formal data-retention/PII policy (Phase 0 data is seeded and fictional;
  real-supplier-data governance comes with the pilot on real files).
- Dependency/image scanning and secret rotation automation in CI.
