# Karbar Pulse — AI Assistant (technical specification)

**Module:** `assistant` · **FR prefix:** `FR-AI` · **Status:** Phase 0 (demo + pilot) · **Doc version:** v1
**As of:** 3 Oct 2026 · **Demo "today" (`DEMO_TODAY`):** 15 Oct 2026, 09:40 Asia/Dhaka (reports up to 14 Oct)

> **Authority.** This document is governed by `PRD.md` (A-01: `sample_data/` + `00_Answer_Key.xlsx` are
> canonical for every number), `tech/architecture.md` (the `services/` layer), `tech/urls-and-views.md`
> (the assistant endpoints and SSE events), `data/data-model.md` (`Conversation`, `ChatMessage`,
> `TokenUsage`), `ai/prediction-engine.md` (the numbers the tools return), and the design export
> (`design/Karbar Pulse Handoff.dc.html`) for SSE events and chat UX. Where any illustrative prototype data
> disagrees with the answer key, the answer key wins.

---

## 1. Overview & principles

The assistant answers plain-English questions about the sweater order book and factories. It is a thin
orchestration layer over the OpenAI SDK with **tool calling**; it holds no business logic of its own. It
exists to make the same numbers that appear on the screens answerable in conversation, so **chat and
screens never disagree** (PRD G3, M2).

Four non-negotiable principles:

1. **Numbers come only from tools.** Every figure the assistant states is produced by a tool that calls
   the exact same `services/` function a view calls (`services.metrics.*`, `services.prediction.*`). There
   is **no free-form text-to-SQL, no model arithmetic, and no estimation**. If a number is not returned by
   a tool, the assistant does not state it. The model's job is to choose tools, pass arguments, and
   compose prose — not to compute.
2. **Provenance on every number.** Each numeric tool result carries an `as_of` timestamp (the originating
   `PredictionRun.as_of`) and a `source` label (e.g. `Prediction run · as of 15 Oct 2026 09:40`). The
   assistant surfaces these in the `sources` SSE event and in-line where helpful. Document answers carry a
   citation (§5).
3. **Honesty over guessing.** When a tool returns no data, an out-of-scope entity, or an error, the
   assistant says **"I don't have that"** (and, where possible, what it *does* have). It never fabricates a
   PO number, a factory, a date, or a figure. It never "rounds up" a missing value to a plausible one.
4. **Role scope.** Reads are full-book for all four groups in Phase 0 (Admin, Management, Merchandiser,
   QA — PRD A-05); **write-adjacent context and any future write tools are scoped to ownership** and the
   scope is injected into the tool layer, not just the prompt (§4). The current user's identity and group
   are passed to every tool call so service functions enforce the same queryset scoping the views use.

Conversations, messages, tool calls, artifacts, sources, and token usage are stored in **PostgreSQL**
(`Conversation`, `ChatMessage`, `TokenUsage` — `data/data-model.md`). ChromaDB holds **documents only**
(§5); it never holds a number that a screen shows.

---

## 2. Models & configuration

The assistant uses the **OpenAI Python SDK** with chat completions + tool calling, and
**`text-embedding-3-small`** for document embeddings. All model choices are environment-driven; nothing is
hard-coded.

| Setting | Env var | Default (demo) | Notes |
|---|---|---|---|
| Chat model | `OPENAI_CHAT_MODEL` | *(set per env)* | Model name only; the code never pins a model literal. |
| Embedding model | `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Fixed by canon; used by `reindex_kb` and query embedding. |
| API key | `OPENAI_API_KEY` | — | Required; absence triggers the fallback (§9). |
| API base (optional) | `OPENAI_BASE_URL` | — | For a proxy/gateway if used. |
| Chat temperature | `ASSISTANT_TEMPERATURE` | `0.2` | Low; the model composes, it does not invent. |
| Max tool-call rounds | `ASSISTANT_MAX_TOOL_ROUNDS` | `5` | Hard cap on the tool loop (§4); then the model must answer or decline. |
| Max tools per round | `ASSISTANT_MAX_TOOLS_PER_ROUND` | `4` | Parallel tool calls allowed within a round. |
| Per-tool timeout | `ASSISTANT_TOOL_TIMEOUT_S` | `8` | A slow `services/` call is cancelled and surfaced as a tool error, not a hang. |
| OpenAI request timeout | `OPENAI_REQUEST_TIMEOUT_S` | `30` | Per request; a timeout trips the fallback for the 3 demo questions (§9). |
| Overall turn budget | `ASSISTANT_TURN_BUDGET_S` | `45` | Wall-clock for a full answer; exceeding emits `error` then `done`. |
| Max output tokens | `ASSISTANT_MAX_OUTPUT_TOKENS` | `1200` | Streamed `delta` text. |
| ChromaDB host/port | `CHROMA_HOST` / `CHROMA_PORT` | `chroma` / `8000` | Server mode (not embedded). |
| Retrieval top-k | `KB_TOP_K` | `6` | Chunks returned per `search_documents`. |

Token usage for every OpenAI call is written to `TokenUsage` (model from env, prompt/completion/total
tokens, linked to the `ChatMessage`), for cost tracking.

---

## 3. Tool catalogue

Every tool is a thin Python function registered with the OpenAI SDK. Each one:

- declares a **grain** — the altitude of the answer: **portfolio** / **department** / **factory** / **PO** /
  **style**;
- calls exactly one (or a small, named set of) `services/` function(s) — the **same** function a view uses;
- returns a JSON object; every **numeric** tool includes `as_of` (ISO-8601, the originating run) and
  `source` (a human label shown to the user).

Common envelope returned by every numeric tool:

```json
{
  "as_of": "2026-10-15T09:40:00+06:00",
  "source": "Prediction run (seed) · as of 15 Oct 2026 09:40 Dhaka",
  "data": { "...tool-specific..." }
}
```

Shared argument conventions: `month` is `YYYY-MM`; `band` ∈ `["On track","Watch","At risk","Critical","Late"]`;
`dept` ∈ `["Men","Women","Kids"]`; `factory` / `code` is the 3-letter `Factory.code` (e.g. `GRL`).

---

### 3.1 `get_portfolio_kpis`

- **Purpose:** the six headline KPIs for the Overview, optionally filtered.
- **Grain:** portfolio.
- **Calls:** `services.metrics.portfolio_kpis(filters, user)` — the same function behind `kpis_partial`.

```json
{
  "name": "get_portfolio_kpis",
  "description": "Headline portfolio KPIs: open POs, open pcs, open FOB USD, October on-time %, value at risk USD, air-freight exposure USD. Use for any 'overall' or 'headline' question.",
  "parameters": {
    "type": "object",
    "properties": {
      "month":  {"type": "string", "description": "Optional YYYY-MM filter on planned ex-factory."},
      "season": {"type": "string", "description": "Optional season code, e.g. AW26."},
      "dept":   {"type": "string", "enum": ["Men", "Women", "Kids"]}
    },
    "additionalProperties": false
  }
}
```

Returns (`data`):
```json
{
  "open_pos": 412, "open_pcs": 1900020, "open_fob_usd": 18601449.00,
  "october_on_time_pct": 86.25, "value_at_risk_usd": 2400006.00,
  "air_freight_exposure_usd": 539720.00,
  "band_counts": {"On track": 354, "Watch": 10, "At risk": 28, "Critical": 13, "Late": 7},
  "reports_today": {"received": 18, "expected": 22}
}
```

---

### 3.2 `get_october_ontime`

- **Purpose:** the October on-time % and its arithmetic (shipped-on-time + open-predicted-on-time ÷ all
  October-planned POs).
- **Grain:** portfolio.
- **Calls:** `services.metrics.october_on_time(user)` (the same computation `portfolio_kpis` uses for the card).

```json
{
  "name": "get_october_ontime",
  "description": "October on-time percentage with its numerator/denominator breakdown.",
  "parameters": {"type": "object", "properties": {}, "additionalProperties": false}
}
```

Returns (`data`): `{"on_time_pct": 86.25, "october_planned_pos": <n>, "shipped_on_time": <n>, "open_predicted_on_time": <n>, "predicted_late": <n>}`.

---

### 3.3 `get_value_at_risk`

- **Purpose:** total value at risk and its concentration by factory (the top-3 share).
- **Grain:** portfolio → factory breakdown.
- **Calls:** `services.metrics.value_at_risk(filters, user)` (sums `PredictionSnapshot.value_at_risk_usd`
  over bands At risk/Critical/Late, grouped by factory).

```json
{
  "name": "get_value_at_risk",
  "description": "Total FOB value at risk (bands At risk, Critical, Late) with a per-factory breakdown and the top-3 concentration share.",
  "parameters": {
    "type": "object",
    "properties": {
      "top_n": {"type": "integer", "default": 3, "description": "How many factories to list by value at risk."},
      "month": {"type": "string"}, "dept": {"type": "string", "enum": ["Men","Women","Kids"]}
    },
    "additionalProperties": false
  }
}
```

Returns (`data`):
```json
{
  "total_usd": 2400006.00, "pos_at_risk": 48,
  "top_n_share_pct": 70.0,
  "by_factory": [
    {"code": "GRL", "name": "Greyloom Knitwear Ltd.", "value_at_risk_usd": 774059.00, "pos": 7},
    {"code": "IRB", "name": "Interbright Knitwear",   "value_at_risk_usd": 477578.00, "pos": 6},
    {"code": "SLM", "name": "Silkmoor Sweaters",      "value_at_risk_usd": 428400.00, "pos": 5}
  ]
}
```
*(GRL + IRB + SLM = 1,680,037 = 70.0% of 2,400,006. Factory names other than GRL = "matches services output".)*

---

### 3.4 `list_at_risk_pos`

- **Purpose:** the at-risk PO queue, filterable — the chat equivalent of the PO list.
- **Grain:** PO.
- **Calls:** `services.metrics.list_pos(filters, user)` — the **same** queryset builder behind
  `po_table_partial` (default band filter = At risk/Critical/Late when `band` omitted).

```json
{
  "name": "list_at_risk_pos",
  "description": "List open POs at risk, with filters. Returns rows identical to the PO list screen.",
  "parameters": {
    "type": "object",
    "properties": {
      "factory":   {"type": "string", "description": "Factory code, e.g. GRL."},
      "dept":      {"type": "string", "enum": ["Men", "Women", "Kids"]},
      "band":      {"type": "string", "enum": ["On track","Watch","At risk","Critical","Late"]},
      "exf_month": {"type": "string", "description": "Planned ex-factory month, YYYY-MM."},
      "limit":     {"type": "integer", "default": 25, "maximum": 100}
    },
    "additionalProperties": false
  }
}
```

Returns (`data`): `{"count": <n>, "rows": [{"po_no","style_code","style_desc","dept","factory","gauge","qty_pcs","fob_value_usd","exf_date","slip_days","on_time_prob","risk_score","band","top_driver"}]}`.

---

### 3.5 `get_po_prediction`

- **Purpose:** one PO's full prediction and risk drivers.
- **Grain:** PO.
- **Calls:** `services.prediction.get_snapshot(po_no, user)` (reads the latest `PredictionSnapshot`; never
  recomputes).

```json
{
  "name": "get_po_prediction",
  "description": "Full prediction for one PO: bottleneck, rates, projected ex-factory, slip, band, score, probability, value at risk, air exposure, and ranked risk drivers.",
  "parameters": {
    "type": "object",
    "properties": {"po_no": {"type": "string", "description": "Purchase order number, e.g. 71010305."}},
    "required": ["po_no"], "additionalProperties": false
  }
}
```

Returns (`data`), hero example:
```json
{
  "po_no": "71010305", "factory": "GRL", "style_code": "KAW26-W-1736",
  "style_desc": "Lambswool V-neck Cardigan (Women's, 7GG)", "order_qty": 9600, "fob_value_usd": 158400.00,
  "state": "In production", "bottleneck_stage": "linking", "bottleneck_rate": 411.1, "required_rate": 680.0,
  "available_wd": 12, "completion_day_n": 19, "slack_wd": -7,
  "planned_exfactory": "2026-10-29", "projected_exfactory": "2026-11-07", "slip_days": 9,
  "risk_score": 76, "band": "Critical", "on_time_probability": 0.02,
  "value_at_risk_usd": 158400.00, "air_freight_exposure_usd": 38016.00,
  "drivers": [
    {"label": "Linking throughput", "detail": "411 vs 680 pcs/day required", "impact_days": 9, "weight": 50},
    {"label": "Yarn in-house late", "detail": "8 days late", "impact_days": "prior", "weight": 12},
    {"label": "Factory OTD", "detail": "GRL 68.1% last 12m", "impact_days": "prior", "weight": 12}
  ]
}
```

---

### 3.6 `get_po_whatif`

- **Purpose:** re-run the engine for one PO with overridden inputs (same engine as the screen's what-if).
- **Grain:** PO.
- **Calls:** `services.prediction.whatif(po_no, linking_machines, overtime_days, user)` — the **same**
  `project()` the `po_whatif_partial` view calls; read-only, writes no snapshot.

```json
{
  "name": "get_po_whatif",
  "description": "Simulate a PO with more linking machines and/or Friday overtime days. Returns projected ex-factory, slip, probability, and air cost. Does not change any data.",
  "parameters": {
    "type": "object",
    "properties": {
      "po_no":           {"type": "string"},
      "linking_machines":{"type": "integer", "description": "New total linking machines for this PO."},
      "overtime_days":   {"type": "integer", "description": "Number of Friday overtime days to add.", "default": 0}
    },
    "required": ["po_no"], "additionalProperties": false
  }
}
```

Returns (`data`): `{"linking_pcs_day", "required_rate", "available_wd", "completion_day_n", "projected_exfactory", "slip_days", "on_time", "on_time_probability", "air_cost_usd", "air_avoided_usd", "donor_po"}`.
Hero `+6 machines (→19) + 2 Friday OT`: `{"linking_pcs_day":600.8,"required_rate":566.7,"available_wd":14,"completion_day_n":14,"projected_exfactory":"2026-10-29","slip_days":0,"on_time":true,"air_avoided_usd":38016.00,"donor_po":"71009573"}`.

---

### 3.7 `get_factory_scorecard`

- **Purpose:** one factory's scorecard.
- **Grain:** factory.
- **Calls:** `services.metrics.factory_scorecard(code, user)` — the same function behind
  `factory_table_partial`/`factory_detail`.

```json
{
  "name": "get_factory_scorecard",
  "description": "One factory's scorecard: machines by gauge, knit load, OTD, AQL, reporting status, open POs/pcs, exposure, value at risk.",
  "parameters": {
    "type": "object",
    "properties": {"code": {"type": "string", "description": "Factory code, e.g. GRL."}},
    "required": ["code"], "additionalProperties": false
  }
}
```

Returns (`data`), GRL example: `{"code":"GRL","name":"Greyloom Knitwear Ltd.","location":"Konabari, Gazipur","machines_by_gauge":{"5":..,"7":..,"12":..},"knit_load_pct":..,"otd_pct":68.1,"aql_pass_pct":95.0,"reporting_compliance_pct":..,"reported_today":{"status":"reported","at":".."},"open_pos":52,"open_pcs":..,"exposure_usd":..,"value_at_risk_usd":774059.00,"status":"At risk"}`.

---

### 3.8 `list_factories_missing_report`

- **Purpose:** which factories are quiet today (freshness / "No update").
- **Grain:** department (across the factory base).
- **Calls:** `services.metrics.reporting_status(user)` — the same function behind `reporting_status_partial`.

```json
{
  "name": "list_factories_missing_report",
  "description": "Factories that have not reported for the latest expected working day (the 'No update' flag), with their last report date.",
  "parameters": {"type": "object", "properties": {}, "additionalProperties": false}
}
```

Returns (`data`): `{"reported": 18, "expected": 22, "missing": [{"code":"SLM","name":"Silkmoor Sweaters","last_report_date":"2026-10-12","missed_wd":2},{"code":"OKH","last_report_date":"2026-10-11"},{"code":"HMR","last_report_date":".."},{"code":"PBB","last_report_date":".."}]}`.

---

### 3.9 `get_shipment_outlook`

- **Purpose:** the N-week shipment forecast (POs, pcs, FOB, on-time %, at-risk USD per period).
- **Grain:** portfolio.
- **Calls:** `services.metrics.shipment_outlook(weeks, user)` — the same function behind `outlook_json` and
  the Shipment forecast report.

```json
{
  "name": "get_shipment_outlook",
  "description": "Week-by-week shipment outlook: for each upcoming week, POs, pieces, FOB USD, on-time %, and at-risk USD.",
  "parameters": {
    "type": "object",
    "properties": {"weeks": {"type": "integer", "default": 8, "minimum": 1, "maximum": 12}},
    "additionalProperties": false
  }
}
```

Returns (`data`): `{"weeks": [{"week_start","label","pos","pcs","fob_usd","on_time_pct","at_risk_usd","bands":{"on_track_pcs","watch_pcs","at_risk_pcs","critical_pcs","late_pcs"}}]}`.

---

### 3.10 `search_documents`

- **Purpose:** retrieve unstructured knowledge (quality manual, T&A standards, factory profiles, audit
  notes, PO comments) from ChromaDB. **Returns text chunks + citations only — never numbers that a screen
  shows.**
- **Grain:** n/a (knowledge); may be filtered to a factory or PO.
- **Calls:** `services.kb.search(query, filters, k, user)`.

```json
{
  "name": "search_documents",
  "description": "Search the knowledge base (quality manual, T&A standards, factory profiles, audit notes, PO comments) for policy, procedure, and qualitative context. Returns text passages with citations. Do NOT use it for KPIs or predictions.",
  "parameters": {
    "type": "object",
    "properties": {
      "query":       {"type": "string"},
      "collection":  {"type": "string", "enum": ["quality_manual","ta_standards","factory_profiles","audit_notes","po_comments"]},
      "factory_code":{"type": "string"},
      "po_no":       {"type": "string"},
      "k":           {"type": "integer", "default": 6, "maximum": 12}
    },
    "required": ["query"], "additionalProperties": false
  }
}
```

Returns (`data`): `{"chunks": [{"text":"…","citation":"Quality Manual §3.2","source":"quality_manual","section":"3.2 AQL sampling","factory_code":null,"po_no":null,"as_of":"2026-10-14","score":0.81}]}`.

---

### 3.11 `get_po_comments`

- **Purpose:** the human commentary on a PO (merchandiser/QA notes).
- **Grain:** PO.
- **Calls:** `services.metrics.po_comments(po_no, user)` (reads `orders.Comment` where `purchase_order=po`).

```json
{
  "name": "get_po_comments",
  "description": "The comment thread on a PO: who said what, when.",
  "parameters": {
    "type": "object",
    "properties": {"po_no": {"type": "string"}, "limit": {"type": "integer", "default": 20}},
    "required": ["po_no"], "additionalProperties": false
  }
}
```

Returns (`data`): `{"po_no":"71010305","comments":[{"author":"...","role":"Merchandiser","at":"2026-10-14T16:20:00+06:00","text":"..."}]}`. These comments are also indexed into the `po_comments` ChromaDB collection (§5) so `search_documents` can cite them; this tool returns the authoritative thread for a known PO.

---

### 3.12 Tool → service → grain summary

| Tool | Grain | `services/` function | Numeric envelope? |
|---|---|---|---|
| `get_portfolio_kpis` | portfolio | `metrics.portfolio_kpis` | yes |
| `get_october_ontime` | portfolio | `metrics.october_on_time` | yes |
| `get_value_at_risk` | portfolio→factory | `metrics.value_at_risk` | yes |
| `list_at_risk_pos` | PO | `metrics.list_pos` | yes |
| `get_po_prediction` | PO | `prediction.get_snapshot` | yes |
| `get_po_whatif` | PO | `prediction.whatif` | yes |
| `get_factory_scorecard` | factory | `metrics.factory_scorecard` | yes |
| `list_factories_missing_report` | department | `metrics.reporting_status` | yes |
| `get_shipment_outlook` | portfolio | `metrics.shipment_outlook` | yes |
| `search_documents` | knowledge | `kb.search` | no (citations) |
| `get_po_comments` | PO | `metrics.po_comments` | no (text + `as_of`) |

---

## 4. Orchestration loop

The async `assistant_stream` view (`POST /assistant/stream/`, SSE) runs a bounded tool loop. The request
carries `thread_id`, `message`, and `context{route, entity_id}` (e.g. the PO the user is viewing).

### 4.1 System prompt outline

```
You are the Karbar Pulse assistant for Karbar Sourcing Bangladesh, a single-brand sweater sourcing office.
Today is {DEMO_TODAY} ({as_of} Asia/Dhaka). The latest expected factory report is {last_expected_report}.

RULES
- Every number you state MUST come from a tool result. Never compute, estimate, or recall a figure.
  If no tool returns it, say "I don't have that."
- Quote each number with its as_of and source as given by the tool.
- Use search_documents only for policy/procedure/qualitative context, never for KPIs or predictions.
- The user is {user.name}, group {user.group}. All users read the full book. Do not expose write actions.
- Prefer the smallest set of tools that answers the question. Portfolio questions → get_portfolio_kpis /
  get_value_at_risk / get_october_ontime; a specific PO → get_po_prediction (+ get_po_whatif for fixes);
  a factory → get_factory_scorecard; "who is quiet" → list_factories_missing_report.
- When the user's screen context names a PO/factory, default to that entity unless they say otherwise.
- Be concise and specific. Offer a chart or table when it clarifies. Surface sources at the end.

CONTEXT: route={route}, entity_id={entity_id}.
```

### 4.2 Loop (pseudocode)

```python
async def run_turn(thread, message, context, user):
    emit("step", id="plan", label="Understanding the question", status="running")
    msgs = build_messages(system_prompt(user, context), thread.history(), message)
    rounds = 0
    while rounds < MAX_TOOL_ROUNDS:
        resp = await openai.chat(model=ENV.CHAT_MODEL, messages=msgs,
                                 tools=TOOL_SCHEMAS, temperature=ENV.TEMPERATURE, stream=True)
        if resp.tool_calls:
            for call in resp.tool_calls[:MAX_TOOLS_PER_ROUND]:     # may run in parallel
                emit("step", id=call.id, label=human_label(call), status="running")
                try:
                    result = await asyncio.wait_for(
                        dispatch(call.name, call.args, user),      # <-- injects user for scope
                        timeout=ENV.TOOL_TIMEOUT_S)
                    emit("step", id=call.id, status="done", ms=elapsed)
                except (ToolError, TimeoutError) as e:
                    result = {"error": str(e)}                     # model will say "I don't have that"
                    emit("step", id=call.id, status="failed", ms=elapsed)
                msgs.append(tool_message(call, result))
                collect_sources(result)                            # as_of + source
                maybe_emit_artifact(call, result)                  # chart / table
            rounds += 1
            continue
        # no more tool calls -> final answer
        async for token in resp.stream_text():
            emit("delta", text=token)
        break
    else:
        emit("delta", text="I can only go so far on that in one step — here is what I found.")
    emit("sources", collected_sources)
    emit("followups", suggest_followups(context))
    persist(thread, message, assistant_text, tool_calls, artifacts, sources, token_usage)
    emit("done")
```

### 4.3 How tool calls are chosen and composed

- **Choice** is the model's, constrained by the schemas and the system-prompt routing hints. The model
  may issue several tool calls in one round (e.g. `get_october_ontime` + `get_value_at_risk` for demo
  question 3). The loop is capped at `ASSISTANT_MAX_TOOL_ROUNDS`.
- **Composition:** tool results return to the model as `tool` messages; the model writes prose that cites
  the returned numbers verbatim. The server independently renders **charts/tables** from the structured
  tool data (not from the model's text) so artifacts are always exactly the service numbers.
- **Determinism for the demo:** because every number originates in the seed `PredictionRun`, the same
  question yields the same numbers regardless of the prose; the eval suite (§8) asserts the numbers, not
  the wording.

### 4.4 Role scope injection

- The authenticated `user` (and their Django group) is passed to **every** `dispatch(...)` call; service
  functions apply the same queryset scoping the views use (`tech/security.md`). Phase 0: **all four groups
  read the full book**, so reads are unscoped by data but still pass `user` for audit.
- **Write/visibility scope** is enforced in the tool layer, not the prompt: in Phase 0 the assistant
  exposes **read tools only**; any future write tool (comment, acknowledge) would filter to the user's
  owned POs/factories inside the service function and refuse otherwise. The prompt is told the user's group
  for tone, but the prompt is never the security boundary.
- Each turn writes an `AuditLog` row (`action="chat"`) and a `TokenUsage` row; messages persist to
  `ChatMessage` with `tool_calls`, `artifacts`, and `sources`.

---

## 5. ChromaDB design (documents only)

ChromaDB runs in **server mode** and holds **only unstructured text** for citations. No number a screen
displays ever comes from ChromaDB. Because `sample_data/` has no documents (PRD A-08), `seed_demo`
fabricates clearly-fictional English documents so citations work.

### 5.1 Collections

| Collection | Content | Typical citation |
|---|---|---|
| `quality_manual` | Sweater quality manual: AQL, defect classes, measurement tolerance, pack-out. | `[Quality Manual §3.2]` |
| `ta_standards` | T&A standards: the 11-milestone calendar, offsets, responsibilities. | `[T&A Standards §2]` |
| `factory_profiles` | One profile per factory (22): capability, gauges, washing, history prose. | `[Factory Profile · GRL]` |
| `audit_notes` | Social/compliance and quality audit notes (fictional). | `[Audit Note · GRL · 2026-08]` |
| `po_comments` | Merchandiser/QA comments on POs (mirrors `orders.Comment`). | `[PO 71010305 · comment · 14 Oct]` |

### 5.2 Chunking strategy

- **Size:** ~800 tokens per chunk; **overlap:** ~120 tokens (≈15%), split on headings/paragraphs first,
  then by size. Manuals and standards split on their numbered sections so a `section` label is natural.
- **Embeddings:** `text-embedding-3-small`, one vector per chunk.
- **One chunk never mixes two sources**; a short document is a single chunk.

### 5.3 Metadata per chunk

```json
{
  "source": "quality_manual",        // collection / document kind
  "doc_id": "quality_manual",        // stable id of the source document
  "section": "3.2 AQL sampling",     // heading/section label (for citation)
  "factory_code": "GRL",             // present on factory_profiles / audit_notes / some po_comments, else null
  "po_no": "71010305",               // present on po_comments, else null
  "citation": "Quality Manual §3.2", // pre-rendered citation label
  "as_of": "2026-10-14",             // document version / last-updated date
  "chunk_index": 4
}
```

Retrieval (`services.kb.search`) embeds the query, filters by `collection`/`factory_code`/`po_no` when
given, returns top-`KB_TOP_K` chunks with their metadata and similarity score.

### 5.4 Re-indexing — `reindex_kb` (django-q2)

`reindex_kb(scope)` is a django-q2 task (`tech/architecture.md §4`): it (re)reads the source documents for
`scope` (`all` or a collection name), re-chunks, re-embeds with `text-embedding-3-small`, and upserts into
ChromaDB keyed by `doc_id:chunk_index` (idempotent). It runs from `seed_demo` and whenever PO comments
change (so `po_comments` stays current). It is **not** on the prediction path.

### 5.5 Citation format shown to the user

- In prose, citations appear as bracketed labels, e.g. **"AQL is inspected at II / 2.5 / 4.0 [Quality
  Manual §3.2]."**
- The UI renders each bracket as a **hover chip** showing the full `source` + `section` + **`as_of`**
  (e.g. *Quality Manual · §3.2 AQL sampling · as of 14 Oct 2026*). The same labels appear in the `sources`
  SSE event: `[{"name":"Quality Manual §3.2","as_of":"2026-10-14"}]`.
- Document citations and numeric sources coexist in the `sources` list; numeric sources read e.g.
  `{"name":"Prediction run (seed)","as_of":"2026-10-15T09:40:00+06:00"}`.

---

## 6. Streaming (async Django SSE)

`POST /assistant/stream/` is an **async view served over ASGI/uvicorn** returning
`text/event-stream`. The event contract matches the design handoff.

### 6.1 Event types

| Event | Payload | Meaning |
|---|---|---|
| `step` | `{id, label, status: running\|done\|failed, ms}` | A plan/tool step; render before text, collapse after `done`. |
| `delta` | `{text}` | A streamed chunk of the answer prose. |
| `chart` | `{option}` | An **ECharts `option` JSON** the client drops into an ECharts instance. |
| `table` | `{columns, rows}` | `columns: [{key,label,align?,format?}]`, `rows: [[…]]`. Exportable to Excel. |
| `sources` | `[{name, as_of}]` | Numeric sources + document citations. |
| `followups` | `[string]` | Suggested next questions / nav hints. |
| `error` | `{message, recoverable}` | A turn-level error (after which `done` still fires). |
| `done` | `{message_id}` | Turn complete; persists `ChatMessage`. |

> The handoff names the artifact event `artifact{type: table\|chart}`. Per `tech/urls-and-views.md` we
> split it into **`chart`** and **`table`** events with the shapes above; this is a naming reconciliation
> only. `chart` always carries an ECharts `option` (not Recharts), per the Django/ECharts stack.

### 6.2 Charts and tables

- **`chart`** carries a complete ECharts `option` built **server-side from the tool's structured data**
  (never from model text), themed from the same CSS variables the screens use. Chart kinds reuse the
  dashboard set: stacked bar (outlook / factory breakdown), line (trend), heatmap.
- **`table`** carries `columns` + `rows`. Any table the assistant emits is **exportable to Excel** via
  `POST /assistant/export.xlsx` → `services.export.table_to_xlsx(columns, rows)` (same exporter the PO and
  report screens use). The client keeps the last table spec and posts it to the export endpoint.

### 6.3 Example event sequence — demo question 1

User: *"Which factories will miss October ex-factory and by how much?"*

```
event: step   data: {"id":"plan","label":"Understanding the question","status":"running"}
event: step   data: {"id":"t1","label":"Reading at-risk October POs (412 → filtered)","status":"running"}
event: step   data: {"id":"t1","label":"Reading at-risk October POs","status":"done","ms":180}
event: step   data: {"id":"t2","label":"Grouping value at risk by factory","status":"running"}
event: step   data: {"id":"t2","label":"Grouping value at risk by factory","status":"done","ms":90}
event: delta  data: {"text":"Three factories concentrate the October slip. "}
event: delta  data: {"text":"GRL carries USD 774,059 at risk, IRB USD 477,578, SLM USD 428,400 — 70% of the USD 2.4M total."}
event: chart  data: {"option": { "xAxis": {"type":"category","data":["GRL","IRB","SLM","…"]},
                                  "yAxis": {"type":"value","name":"USD at risk"},
                                  "series": [{"type":"bar","data":[774059,477578,428400, "…"]}] }}
event: table  data: {"columns":[{"key":"code","label":"Factory"},{"key":"pos","label":"At-risk POs"},
                                 {"key":"slip","label":"Worst slip (days)"},{"key":"var","label":"Value at risk USD","format":"usd"}],
                     "rows":[["GRL",7,9,774059],["IRB",6,"…",477578],["SLM",5,"…",428400]]}
event: sources data: [{"name":"Prediction run (seed)","as_of":"2026-10-15T09:40:00+06:00"}]
event: followups data: ["Why is GRL's PO 71010305 late?","What fixes PO 71010305?"]
event: done   data: {"message_id":"…"}
```

---

## 7. Answer rules

1. **Every number carries `as_of` + source.** The prose states the number; the `sources` event (and hover
   chips) carry the `as_of` and source label from the tool envelope. No bare numbers.
2. **"I don't have that."** When a tool errors, times out, returns empty, or the entity does not exist
   (unknown PO/factory), the assistant says so plainly and, where possible, offers the nearest thing it can
   answer. It never fabricates.
3. **No invented numbers, ever.** The model composes prose; it does not compute. Charts/tables are rendered
   from tool data, not from text. Arithmetic (shares, totals) is done inside the service, not the model.
4. **Documents are context, not data.** Policy/procedure answers cite `search_documents` chunks; a KPI or
   prediction never comes from a document.
5. **Role scope.** Reads are full-book (Phase 0); the user is passed to every tool for scope + audit; the
   assistant exposes no write actions in Phase 0.
6. **Freshness honesty.** Where a factory has not reported, say so (surface `list_factories_missing_report`)
   rather than presenting a stale number as current.

---

## 8. Evaluation — 30 golden questions (pytest)

`tests/assistant/test_golden_questions.py` drives the orchestration loop against the seed `PredictionRun`
and asserts, per question: (a) the expected **tool(s)** were called at the expected **grain**, and (b) the
returned **numbers** match the answer key within rounding. Prose wording is not asserted. The **3 demo
questions must be exact** (M2). Answers marked *"matches services output"* are asserted against the live
service result (they cannot be pinned by hand here but are fixed by the seed).

Legend: **P** portfolio · **D** department · **F** factory · **PO** purchase order · **S** style.

| # | Question | Grain | Tool(s) | Expected answer |
|---|---|---|---|---|
| **1 (DEMO)** | Which factories will miss October ex-factory and by how much? | P→F | `list_at_risk_pos` (exf_month=2026-10) + `get_value_at_risk` | GRL, IRB, SLM lead; VaR GRL 774,059 / IRB 477,578 / SLM 428,400 = 70% of USD 2,400,006; 48 POs at risk. |
| **2 (DEMO)** | Why is PO 71010305 late and what's the fastest way to make it on time? | PO | `get_po_prediction` + `get_po_whatif` | Yarn in-house 8 days late; linking 411 vs 680 pcs/day required; +6 linking machines + 2 Friday overtime days → on time 29 Oct, avoids USD 38,016 air; donor PO 71009573. |
| **3 (DEMO)** | What's our October on-time %, and where is the USD 2.4M at risk concentrated? | P→F | `get_october_ontime` + `get_value_at_risk` | 86.25%; GRL 774,059 / IRB 477,578 / SLM 428,400 = 70% of USD 2,400,006. |
| 4 | How many open POs do we have and what's the total FOB? | P | `get_portfolio_kpis` | 412 open POs; USD 18,601,449 FOB (≈USD 18.6M); 1,900,020 pcs. |
| 5 | How many open pieces are in the book? | P | `get_portfolio_kpis` | 1,900,020 pcs (≈1.9M). |
| 6 | What is our air-freight exposure? | P | `get_portfolio_kpis` | USD 539,720. |
| 7 | How many POs are at risk right now? | P | `get_portfolio_kpis` / `get_value_at_risk` | 48 (At risk 28 + Critical 13 + Late 7). |
| 8 | Give me the band breakdown of the book. | P | `get_portfolio_kpis` | On track 354, Watch 10, At risk 28, Critical 13, Late 7 (=412). |
| 9 | How many critical POs are there? | P | `get_portfolio_kpis` / `list_at_risk_pos`(band=Critical) | 13. |
| 10 | How many POs are already late? | P | `get_portfolio_kpis` / `list_at_risk_pos`(band=Late) | 7. |
| 11 | Which factories haven't reported today? | D | `list_factories_missing_report` | SLM, OKH, HMR, PBB (18 of 22 reported). |
| 12 | How many factories reported today? | D | `list_factories_missing_report` | 18 of 22. |
| 13 | When did SLM last report? | F | `list_factories_missing_report` | 12 Oct 2026. |
| 14 | What's GRL's OTD and value at risk? | F | `get_factory_scorecard`(GRL) | OTD 68.1%; value at risk USD 774,059; AQL 95%; 52 open POs. |
| 15 | How many open POs does GRL have? | F | `get_factory_scorecard`(GRL) | 52. |
| 16 | What's GRL's AQL pass rate? | F | `get_factory_scorecard`(GRL) | 95%. |
| 17 | What's the predicted ex-factory for PO 71010305? | PO | `get_po_prediction` | 7 Nov 2026 (slip 9 days). |
| 18 | What band and risk score is PO 71010305? | PO | `get_po_prediction` | Critical; score 76. |
| 19 | What's the on-time probability for PO 71010305? | PO | `get_po_prediction` | 2%. |
| 20 | What's the bottleneck on PO 71010305 and the required rate? | PO | `get_po_prediction` | Linking at 411.1 pcs/day; required 680 pcs/day. |
| 21 | What air-freight cost would PO 71010305 incur if it slips? | PO | `get_po_prediction` | USD 38,016. |
| 22 | If I add 6 linking machines to PO 71010305, does it make it? | PO | `get_po_whatif`(linking_machines=19) | Projected 1 Nov, slip 3 — still late. |
| 23 | If I only add 2 Friday overtime days to PO 71010305? | PO | `get_po_whatif`(overtime_days=2) | Projected 4 Nov, slip 6 — still late. |
| 24 | What's the donor PO for the GRL machine reallocation? | PO | `get_po_whatif` / `get_po_prediction` | PO 71009573 (stays 5 days early after giving 6 machines). |
| 25 | Show me the at-risk POs at GRL. | PO/F | `list_at_risk_pos`(factory=GRL) | Matches services output; includes 71010305 (Critical). |
| 26 | List critical POs due in October. | PO | `list_at_risk_pos`(band=Critical, exf_month=2026-10) | Matches services output. |
| 27 | What's the shipment outlook for the next 8 weeks? | P | `get_shipment_outlook`(weeks=8) | Matches services output (per-week POs/pcs/FOB/on-time%/at-risk USD; matches answer-key Weekly Outlook). |
| 28 | What AQL standard do we inspect sweaters at? | KB | `search_documents`(quality_manual) | II / 2.5 / 4.0, cited `[Quality Manual §3.x]` (matches seeded manual). |
| 29 | Summarise the latest comments on PO 71010305. | PO | `get_po_comments` | Matches seeded comments (text + author + `as_of`); cited. |
| 30 | What's our revenue / margin this quarter? | P | — (no tool) | "I don't have that" — Pulse tracks delivery risk (FOB, on-time, exposure), not revenue/margin. |

Each test asserts the `sources` event is non-empty for every numeric answer, and that question 30 produces
**no fabricated number** and the honest-decline string.

---

## 9. Fallback for demo day

If the OpenAI API is slow or unavailable, the three demo questions must still answer instantly and
correctly (PRD M5). Pre-stored answers live in `services/assistant/fallback.py` (fixtures), each holding
the **exact text, chart/table specs, and sources** keyed to the seed run.

### 9.1 What is stored

For each demo question (matched by a normalised question signature):

```json
{
  "signature": "factories_miss_october",
  "delta": "Three factories concentrate the October slip. GRL carries USD 774,059 at risk, IRB USD 477,578, SLM USD 428,400 — 70% of the USD 2.4M total, across 48 POs.",
  "chart": { "xAxis": {"type":"category","data":["GRL","IRB","SLM"]},
             "yAxis": {"type":"value","name":"USD at risk"},
             "series": [{"type":"bar","data":[774059,477578,428400]}] },
  "table": { "columns":[{"key":"code","label":"Factory"},{"key":"var","label":"Value at risk USD","format":"usd"}],
             "rows":[["GRL",774059],["IRB",477578],["SLM",428400]] },
  "sources": [{"name":"Prediction run (seed)","as_of":"2026-10-15T09:40:00+06:00"}]
}
```

The other two signatures: `hero_po_fix` (PO 71010305: yarn 8 days late, linking 411 vs 680, +6 machines +
2 Fridays → on time 29 Oct, avoids USD 38,016 air, donor 71009573) and `on_time_and_var` (86.25%; GRL
774,059 / IRB 477,578 / SLM 428,400 = 70% of USD 2,400,006). Because these come from the seed run, the
fallback numbers are **identical** to the live-tool numbers.

### 9.2 How it's toggled

- **Setting:** `ASSISTANT_FALLBACK_MODE` ∈ `auto` (default) / `always` / `off`.
  - `auto` — try OpenAI; on timeout, connection error, or missing `OPENAI_API_KEY`, serve the stored
    answer for a recognised demo signature; for any other question, emit an honest `error` + "I don't have
    that right now."
  - `always` — serve stored answers for the three demo signatures without calling OpenAI (guaranteed
    offline demo path); other questions decline.
  - `off` — no fallback (CI / pilot).
- The fallback replays the **same SSE event sequence** (`step` → `delta` → `chart`/`table` → `sources` →
  `done`) so the UI is indistinguishable from a live answer, and still persists a `ChatMessage` (with a
  `fallback: true` flag in `artifacts`) but writes **no** `TokenUsage` row (no OpenAI call occurred).
