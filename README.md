# Karbar Pulse

Sweater-sourcing intelligence for **Karbar Sourcing Bangladesh** — one screen every morning that says
what will ship on time, where the money is at risk, and the cheapest way to fix a late PO. Built on the
daily Excel reports the 22 factories already send.

Phase 0 (demo + pilot). Server-rendered Django, deterministic prediction engine, offline-capable AI
assistant. Full specs are in [`docs/`](docs/) (start with [docs/PRD.md](docs/PRD.md)); the delivery plan is
[docs/plan/roadmap.md](docs/plan/roadmap.md) and the CEO click-path is
[docs/plan/demo-script.md](docs/plan/demo-script.md).

## Stack
Django 5.2 · Python 3.12 · PostgreSQL 16 (psycopg 3) · Django templates + Tailwind (standalone CLI) +
HTMX + Alpine.js + Apache ECharts · django-q2 (Postgres ORM broker) · OpenAI SDK + ChromaDB (documents
only) · ASGI/uvicorn · WhiteNoise · pandas + openpyxl · pytest-django, factory-boy, ruff.

> **Dev vs prod database.** Production runs PostgreSQL 16 (via Docker Compose). Local development/tests
> fall back to **SQLite** automatically when `DATABASE_URL` is unset, so the suite runs with no DB server.

## Quick start (local, SQLite)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt    # Windows; use .venv/bin/python on POSIX
cp .env.example .env                                                # adjust if needed
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py seed_demo                        # loads the deterministic demo dataset + runs the engine
.venv/Scripts/python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

### Demo logins (password `demo12345`)
| Username | Role | Sees |
|---|---|---|
| `ceo` | Management | the whole book (the demo login) |
| `headmerch` | Management | the whole book |
| `admin` | Admin (superuser) | everything + `/admin/` |
| `qahead` | QA | reads all; QA write actions |
| merchandiser logins (e.g. `farhana.rahman`) | Merchandiser | reads all; writes scoped to their POs |

## The 3-minute demo
Follow [docs/plan/demo-script.md](docs/plan/demo-script.md). In short: Overview (86.25% on time, USD 2.4M
at risk, 3 factories = 70%, 4 not reporting) → open PO **71010305** (predicted 7 Nov, 9 days late) → open
the what-if, set linking machines to **19** and tick the **16 & 23 Oct** overtime Fridays → it snaps to
**29 Oct, on time, USD 38,016 air freight avoided** → press **⌘K** and ask a question → factory scorecard →
Daily Updates upload.

## Tests & lint
```bash
.venv/Scripts/python.exe -m pytest          # 55 tests
.venv/Scripts/ruff.exe check apps services scripts tests
```
The engine is gated on answer-key parity: `tests/test_engine.py` reproduces every one of the 412 open-PO
predictions, the hero what-if, and all headline KPIs from `sample_data/00_Answer_Key.xlsx`. A standalone
check: `.venv/Scripts/python.exe scripts/engine_parity.py`.

## Production (Docker Compose)
```bash
# On the VPS, with a real .env (DATABASE_URL=postgres://…, SECRET_KEY, OPENAI_API_KEY, SITE_ADDRESS):
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo     # demo DB only
```
Services: `web` (uvicorn ASGI), `worker` (django-q2 qcluster), `postgres`, `chroma`, `caddy` (HTTPS).
See [docs/tech/deployment.md](docs/tech/deployment.md), including the demo-day freeze runbook.

## Notes
- **AI assistant runs offline.** Numbers come only from the `services/` layer (never the model), so chat and
  screens can't disagree. With no `OPENAI_API_KEY`, the deterministic router answers the demo and golden
  questions — the demo needs no network. An OpenAI key enables LLM phrasing over the same tools.
- **Architecture:** business logic lives in `services/` (pure engine in `services/prediction/`); views and
  assistant tools both call it. Pages read stored `PredictionSnapshot`s and never recompute. See
  [docs/tech/architecture.md](docs/tech/architecture.md).
