# AI Pulse — AI Assistant (module PRD)

**App:** `assistant` · **FR prefix:** `FR-AI` · **Tier:** Must for 15 Oct
**As of:** 3 Oct 2026 · **Depends on:** `PRD.md`, `data/data-model.md`, `tech/urls-and-views.md`, `ai/prediction-engine.md`

> This is the **product / UX PRD** for the Assistant screen. The **technical spec** (tool catalogue, tool
> schemas, ChromaDB indexing, prompt / system design, model wiring) lives separately in
> **`ai/assistant.md`** — cross-referenced throughout and authoritative for implementation detail. This PRD
> defines what the user experiences and the product rules the implementation must honour.
>
> Canon: `sample_data/` + `00_Answer_Key.xlsx` win on every number; `design/` wins on layout and interaction.
> The core promise: **the dashboard and the chat never disagree**, because every number comes from the same
> `services/` layer the screens use (`PRD.md §2 Vision, §G3`).

---

## 1. Purpose & design screen(s)

The Assistant lets anyone in the office ask the book a plain-English question and watch the answer get
built: the steps it took, then the words, then a chart or table, then the sources with their "as of" time.
It is the same numbers as the screens, answerable without knowing where a figure lives. It is available as a
full page and as a ⌘K slide-over from anywhere in the app.

Design screens (from `design/Karbar Pulse Handoff.dc.html` › "AI Assistant · page + slide-over"):

- **Assistant page** — full conversation view with thread history.
- **Slide-over (⌘K)** — a Sheet opened by ⌘K from any screen, carrying the current route + entity as context
  (e.g. open it on PO `71010305` and ask about "this PO").
- Both stream **steps first, then the answer**; steps **collapse after `done`**.

---

## 2. User stories

- **FR-AI-010 — Page + slide-over.** As any user, I want an assistant page and a ⌘K slide-over that stream
  the steps taken and then the answer, so that I can ask from anywhere and trust how the answer was built.
- **FR-AI-020 — SSE streaming UX.** As a user, I want to see `step`, `delta`, `chart`, `table`, `sources`,
  `followups`, `done` and `error` events render in order, with steps collapsing after `done`, so that the
  answer feels live and auditable.
- **FR-AI-030 — Numbers from tools over services/.** As the business, I want every number the assistant
  states to come from a tool that calls `services/`, so that chat and screens never disagree.
- **FR-AI-040 — Source, as-of, and honesty.** As a user, I want every number to show its source and "as of"
  time, and the assistant to say "I don't have that" instead of guessing, within my role scope.
- **FR-AI-050 — ChromaDB citations.** As a user asking about unstructured knowledge (manual, factory
  profiles, audit notes, PO comments), I want cited passages, so that qualitative answers are grounded.
- **FR-AI-060 — Excel export of a table.** As a user, I want to export any table the assistant returns to
  Excel, so that I can share it.
- **FR-AI-070 — Conversations + token usage stored.** As the office, I want conversations and token usage
  persisted, so that history is available and cost is visible.
- **FR-AI-080 — Role scope honored per user.** As the business, I want answers scoped to the asking user's
  role, so that the assistant respects the same access rules as the screens.
- **FR-AI-090 — Golden-question eval.** As the team, I want 30 golden questions (including the 3 demo
  questions) evaluated, so that answer quality is measured and regressions caught.
- **FR-AI-100 — Offline fallback.** As the presenter, I want pre-stored answers for the 3 demo questions, so
  that the demo runs even if the model is slow or offline.

---

## 3. Acceptance criteria (Given / When / Then)

### FR-AI-010 Page + slide-over
- **Given** any screen, **when** the user presses ⌘K and chooses "Ask the assistant", **then** the slide-over
  opens with `context {route, entity_id}` from the current page (`urls-and-views.md`: `/assistant/panel/`).
- **Given** the slide-over open on PO `71010305`, **when** the user asks "why is this PO late?", **then** the
  entity context resolves to PO `71010305` and the answer concerns that PO.
- **Given** the full page `/assistant/`, **when** it loads, **then** it shows the conversation and the user's
  thread list; asking a question streams steps first, then the answer.

### FR-AI-020 SSE streaming UX
- **Given** a question, **when** `POST /assistant/stream/` runs, **then** the client renders SSE events in
  order: `step {id, label, status, ms}` (status running → done / failed), `delta {text}`, `chart {ECharts
  option}`, `table {columns, rows}`, `sources [{name, as_of}]`, `followups []`, then `done`
  (`urls-and-views.md`; design "Streaming" build note).
- **Given** demo question 1 ("Which factories will miss October ex-factory and by how much?"), **when** it
  streams, **then** steps show the funnel the design describes (e.g. 412 open → filtered to October → grouped
  by factory), followed by a bar chart and a table, then sources stamped "as of" the run time (09:40 Dhaka in
  the demo).
- **Given** streaming has completed, **when** `done` arrives, **then** the step list **collapses** to a
  summary the user can expand (design: "collapse steps after done").
- **Given** a tool or model failure mid-stream, **when** it occurs, **then** an `error` event renders a
  readable message and partial content is not presented as a complete answer.

### FR-AI-030 Numbers from tools over services/
- **Given** any numeric claim in an answer, **when** it is produced, **then** it came from a tool that reads
  `services/` (the same layer the screens use) — the model does not do arithmetic on raw rows itself
  (`ai/assistant.md` tool catalogue; `PRD.md §G3`).
- **Given** demo question 3 ("What's our October on-time %, and where is the USD 2.4M at risk
  concentrated?"), **when** answered, **then** it returns October on-time **86.25%** and value at risk **USD
  2,400,006** — the exact answer-key figures the Overview shows (`PRD.md` glossary) — because both read the
  same `services.metrics`.
- **Given** demo question 2 ("Why is PO 71010305 late and what's the fastest way to make it on time?"),
  **when** answered, **then** the drivers and the fix match the snapshot and what-if: predicted 7 Nov, slip
  9, band Critical; fastest on-time fix = **+6 linking machines (13→19) and 2 Friday overtime days (16 & 23
  Oct)** → ex-factory 29 Oct, on time, avoiding **USD 38,016** air freight (`prediction-engine.md §10` Hero
  What-if).

### FR-AI-040 Source, as-of, and honesty
- **Given** any answer with numbers, **when** it renders, **then** it ends with `sources [{name, as_of}]` and
  each number is attributable to a source with an "as of" time (M4 freshness honesty).
- **Given** a question the tools / knowledge base cannot answer, **when** it is asked, **then** the assistant
  says it does not have that information rather than fabricating a number or a citation.
- **Given** a user whose role scope excludes some data, **when** they ask, **then** the answer is limited to
  what their role may read (see FR-AI-080) and says so where relevant.

### FR-AI-050 ChromaDB citations
- **Given** a question about unstructured knowledge, **when** it is answered, **then** passages are retrieved
  from ChromaDB over the seeded corpus — the sweater quality manual, T&A standards, the 22 factory profiles,
  audit notes, and PO comments — and cited as sources (ASSUMPTION A-08; `ai/assistant.md`).
- **Given** PO comments, **when** they are created (`/pos/<po_no>/comments/`), **then** they are indexed into
  ChromaDB so the assistant can cite them (`data-model.md › Comment`).
- **Given** ChromaDB supplies a citation, **when** a number is involved, **then** the number still comes from
  a `services/` tool, not from the retrieved text (citations are for qualitative grounding only;
  `urls-and-views.md`: "ChromaDB supplies citations only").

### FR-AI-060 Excel export of a table
- **Given** an answer that returned a `table`, **when** the user exports it (`POST /assistant/export.xlsx`),
  **then** an `.xlsx` of that table downloads, matching the rows shown, and an `export` `AuditLog` row is
  written (`FR-ACCT-050`).

### FR-AI-070 Conversations + token usage stored
- **Given** a conversation, **when** messages are exchanged, **then** `Conversation` and `ChatMessage` rows
  persist (role user / assistant / tool, content, `tool_calls`, `artifacts`, `sources`), and each model call
  writes a `TokenUsage` row (`model`, prompt / completion / total tokens) (`data-model.md`).
- **Given** a completed assistant turn, **when** it finishes, **then** a `chat` `AuditLog` row is written for
  the user (`FR-ACCT-050`).

### FR-AI-080 Role scope honored per user
- **Given** `/assistant/stream/`, **when** a user asks, **then** scope is enforced per user (`urls-and-views.md`:
  "read: all; scope enforced per user"): all four groups read the whole book, and any write-shaped request is
  refused — the assistant does not create comments, acknowledge alerts, upload, or change parameters.
- **Given** thread history, **when** a user lists threads (`/assistant/threads/`), **then** they see **only
  their own** threads (read: own threads).

### FR-AI-090 Golden-question eval
- **Given** the eval suite, **when** it runs, **then** **30/30** golden questions return the expected answer
  and the **3/3** demo questions match exactly (success metric M2; `prediction-engine.md`-aligned figures).
- **Given** a change to the engine, services, or prompts, **when** the eval re-runs, **then** a regression in
  any golden question fails the suite.

### FR-AI-100 Offline fallback
- **Given** the 3 demo questions, **when** the model is slow or offline, **then** pre-stored answers are
  served so the 3-minute demo path still runs (success metric M5; ASSUMPTION A-09):
  1. "Which factories will miss October ex-factory and by how much?"
  2. "Why is PO 71010305 late and what's the fastest way to make it on time?"
  3. "What's our October on-time %, and where is the USD 2.4M at risk concentrated?"
- **Given** the fallback answer, **when** it renders, **then** its numbers equal the live answer-key figures
  (e.g. 86.25% on-time, USD 2,400,006 at risk, hero fix avoiding USD 38,016) so the fallback and the live
  answer agree.

---

## 4. Design components

- **Assistant page** — conversation transcript, thread list, composer.
- **Slide-over (Sheet)** — ⌘K-opened panel carrying route + entity context.
- **Streamed step list** — steps with status and elapsed ms, collapsing after `done`.
- **Answer blocks** — markdown text (`delta`), **chart** (ECharts option), **table** (columns / rows),
  **sources** list (name + as_of), **followups** (suggested next questions / nav hints).
- **Export** button on any returned table.
- Design component mapping: Sheet (slide-over), Command / Dialog (⌘K entry), Table, chart via the Overview's
  ECharts conventions.

---

## 5. Data read / write + URLs / partials

**Models (`data-model.md`):** `Conversation`, `ChatMessage` (`tool_calls`, `artifacts`, `sources`),
`TokenUsage`; `Comment` (indexed to ChromaDB); numbers come from `PredictionSnapshot` / `FactoryStat` /
`services.metrics` / `services.prediction` via tools (never recomputed in the assistant). `AuditLog` for
`chat` and `export`.

**URLs / views (`urls-and-views.md`):**
- `GET /assistant/` → `assistant_page` → `assistant/page.html` (read: all).
- `GET /assistant/panel/` → `assistant_panel` → `partials/assistant/slideover.html` (read: all).
- `POST /assistant/stream/` → `assistant_stream` (async SSE; read: all, scope per user).
- `GET /assistant/threads/` → `threads_list` → `partials/assistant/threads.html` (read: own threads).
- `GET /assistant/threads/<id>/` → `thread_detail` → `partials/assistant/messages.html` (read: own thread).
- `POST /assistant/export.xlsx` → `assistant_export` (read: all).
- Full tool catalogue and schemas: **`ai/assistant.md`**.

---

## 6. Empty / error / stale-data states

- **No input:** an empty question is not submitted.
- **No data / out of scope:** "I don't have that" instead of guessing (FR-AI-040); no fabricated numbers or
  citations.
- **Tool / model error:** an `error` SSE event renders a readable message; partial output is not labelled as
  a complete answer.
- **Model slow or offline:** the 3 demo questions fall back to pre-stored answers (FR-AI-100); other questions
  show a clear "the assistant is unavailable" state.
- **Stale run:** sources carry the latest run's `as_of`; if the run is old the assistant shows that `as_of`
  honestly rather than implying today's data (M4).
- **No threads yet:** the thread list shows an empty state; a new question starts a thread.
- **Export with no table:** export is offered only when the last answer returned a table.

---

## 7. Permissions

| Capability | Admin | Management | Merchandiser | QA |
|---|---|---|---|---|
| Use assistant (page + slide-over) | ✓ | ✓ | ✓ | ✓ |
| Read answers over the whole book | ✓ | ✓ | ✓ | ✓ |
| See own threads | ✓ | ✓ | ✓ | ✓ |
| Export a returned table | ✓ | ✓ | ✓ | ✓ |
| Have the assistant perform writes | – | – | – | – |

All four groups may use the assistant and read the whole book (ASSUMPTION A-05); scope is enforced per user
in `/assistant/stream/` (FR-AI-080). Thread history is private to its owner. The assistant is **read-only**:
it never performs a write action (comments, alert actions, uploads, parameter changes); those remain in the
owning modules under their own permissions. Assistant use and table exports are audited (`FR-ACCT-050`).
