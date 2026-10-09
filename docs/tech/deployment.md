# Karbar Pulse — Deployment

**Target host:** a single Ubuntu 24.04 LTS VPS. **Runtime:** Docker Compose, five services —
`web` (uvicorn ASGI), `worker` (django-q2 `qcluster`), `postgres` (PostgreSQL 16), `chroma`
(ChromaDB server mode), `caddy` (HTTPS reverse proxy + static). Settings read from the environment
via django-environ. This document is operational only; no application code lives here. See
`tech/architecture.md` for the container/service map and `tech/security.md` for secrets and transport.

---

## 1. Compose stack

One `docker-compose.yml` on the host. `web` and `worker` are built from the **same image** (the app
image, which also runs the Tailwind standalone CLI at build time — no Node runtime at runtime);
`postgres`, `chroma` and `caddy` are stock images. Only `caddy` publishes ports; everything else talks
over the internal compose network.

```yaml
# docker-compose.yml (representative outline)
services:
  web:
    build: .                       # app image; Tailwind CLI runs in the build stage
    image: karbar-pulse:latest
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput &&
             uvicorn karbar_pulse.asgi:application --host 0.0.0.0 --port 8000"
    env_file: [.env]
    depends_on:
      postgres: {condition: service_healthy}
      chroma:   {condition: service_started}
    volumes:
      - static:/app/staticfiles     # collectstatic output, served by WhiteNoise
      - uploads:/app/media          # uploaded Excel, outside the web root
    expose: ["8000"]                # not published; reached via caddy only
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz/')"]
      interval: 30s
      timeout: 5s
      retries: 3
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "5"}

  worker:
    image: karbar-pulse:latest       # same image as web
    command: python manage.py qcluster
    env_file: [.env]
    depends_on:
      postgres: {condition: service_healthy}
      chroma:   {condition: service_started}
    volumes:
      - uploads:/app/media           # worker reads the uploaded file to ingest it
    restart: unless-stopped
    logging:
      driver: json-file
      options: {max-size: "10m", max-file: "5"}

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: karbar_pulse
      POSTGRES_USER: karbar
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backups:/backups           # pg_dump target (see §5)
    expose: ["5432"]
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U karbar -d karbar_pulse"]
      interval: 10s
      timeout: 5s
      retries: 5

  chroma:
    image: chromadb/chroma:latest
    volumes:
      - chromadata:/chroma/chroma    # persistent vector store
    expose: ["8000"]                 # internal only; web/worker connect by service name
    restart: unless-stopped

  caddy:
    image: caddy:2
    depends_on: [web]
    ports: ["80:80", "443:443"]      # the only published ports
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data             # ACME certs + keys (must persist)
      - caddy_config:/config
      - static:/srv/static:ro        # optional: Caddy can serve collected static directly
    restart: unless-stopped

volumes:
  pgdata:        # PostgreSQL data (+ django-q2 broker tables live in this DB)
  chromadata:    # ChromaDB documents/embeddings
  static:        # collectstatic output shared web <-> caddy
  uploads:       # uploaded Excel files (media)
  caddy_data:
  caddy_config:
```

Notes:
- The django-q2 broker is the **Postgres ORM broker** — there is no Redis service; the broker tables
  live inside the same `postgres` database and volume.
- `chroma` runs in **server mode** and holds documents only (manual, factory profiles, notes, PO
  comments); all numbers come from Postgres via `services/`.

---

## 2. Caddy — HTTPS + reverse proxy

Caddy terminates TLS with **automatic certificates** (Let's Encrypt / ZeroSSL via ACME) and reverse-
proxies to `web` on the internal network. `caddy_data` must persist so certs are not re-issued on every
restart (and to stay within ACME rate limits).

```caddyfile
# Caddyfile
pulse.karbar.example {
    encode zstd gzip

    # App: everything proxied to uvicorn (ASGI, incl. the assistant SSE stream)
    reverse_proxy web:8000 {
        flush_interval -1          # don't buffer Server-Sent Events (assistant stream)
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    log {
        output file /var/log/caddy/access.log
    }
}
```

**Why WhiteNoise is still used even with Caddy in front.** Static files are served by **WhiteNoise from
inside the `web` (ASGI) process** — hashed filenames, far-future cache headers, compression. This keeps
one deploy artifact (static ships inside the image / `static` volume via `collectstatic`), works
identically in dev and prod, and means the app is correct even if Caddy's static mount is absent.
Caddy's role is TLS, HTTP/2, compression and proxying; it may optionally front `/static` from the shared
`static` volume for a small edge win, but WhiteNoise remains the source of truth for static delivery.

---

## 3. Settings via django-environ — `.env` keys

All settings are read with django-environ from a single `.env` file on the host (never baked into the
image). Representative keys:

```dotenv
# Django core
DJANGO_SETTINGS_MODULE=karbar_pulse.settings
SECRET_KEY=<50+ random chars>
DEBUG=False
ALLOWED_HOSTS=pulse.karbar.example
CSRF_TRUSTED_ORIGINS=https://pulse.karbar.example
TIME_ZONE=Asia/Dhaka

# Database (psycopg 3) — one URL
DATABASE_URL=postgres://karbar:<password>@postgres:5432/karbar_pulse
POSTGRES_PASSWORD=<password>            # consumed by the postgres service

# OpenAI (model name is config, not hard-coded)
OPENAI_API_KEY=sk-<redacted>
OPENAI_MODEL=gpt-4o-mini               # chat/tool-calling model
OPENAI_EMBED_MODEL=text-embedding-3-small

# ChromaDB (server mode)
CHROMA_HOST=chroma
CHROMA_PORT=8000

# django-q2 (Postgres ORM broker)
Q2_WORKERS=4
Q2_TIMEOUT=600                         # seconds; must exceed the longest ingest/predict task
Q2_RETRY=900                           # must be > Q2_TIMEOUT so tasks are not retried early
Q2_MAX_ATTEMPTS=1

# Demo / app behaviour
DEMO_TODAY=2026-10-15                  # the fixed "today" the seeded demo runs against

# Cookies / transport hardening (prod)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https   # Caddy sets X-Forwarded-Proto
```

**Secrets handling:**
- Secrets live only in `.env` on the host — **not** in the image, not in `docker-compose.yml`, not in
  git. `.env` is in `.gitignore`.
- The file is owned by the deploy user and `chmod 600` (`-rw-------`).
- `SECRET_KEY`, `DATABASE_URL`/`POSTGRES_PASSWORD` and `OPENAI_API_KEY` are rotated by editing `.env`
  and recreating the affected containers; no secret is ever logged.

---

## 4. Startup sequence

Order is enforced by compose `depends_on` + healthchecks and by each service's command:

1. **postgres** starts; healthcheck (`pg_isready`) must pass before dependents start.
2. **chroma** starts (server mode) on the persistent `chromadata` volume.
3. **web** starts and, in its command, runs `migrate --noinput` then `collectstatic --noinput`
   (WhiteNoise hashes), then launches `uvicorn karbar_pulse.asgi:application`.
   - Migrations also create/maintain the django-q2 broker tables.
4. **worker** starts `python manage.py qcluster` — the django-q2 cluster that runs `ingest_file`,
   `run_predictions`, `evaluate_alerts`, `reindex_kb`.
5. **caddy** starts, obtains/loads certs, and begins proxying to `web`.

**Scheduled jobs** are registered as django-q2 `Schedule` rows (idempotently, e.g. in a one-off
`register_schedules` management command or on first boot). The two nightly schedules:
- `run_predictions('nightly')` — recomputes `FactoryStat` + all open-PO snapshots into a new
  `PredictionRun`, then enqueues `evaluate_alerts`.
- nightly `pg_dump` (see §5).

**Chroma init / seeding.** On first bring-up, run the seed and knowledge-base build once:
`python manage.py seed_demo` (writes master data, orders, the 15 Oct snapshots, and the fabricated
fictional KB documents) and `python manage.py reindex_kb all` (chunks + embeds documents into Chroma).
`reindex_kb` is also a django-q2 task that can be re-run any time.

---

## 5. Backups and restore

### Database (authoritative state)
Nightly logical backup via `pg_dump` in custom format. Either a host cron entry or a django-q2
`Schedule` is acceptable; cron shown here because it is independent of the app being healthy:

```cron
# /etc/cron.d/karbar-pulse-backup  (host crontab; runs 02:30 Asia/Dhaka)
30 2 * * *  deploy  docker compose -f /opt/karbar-pulse/docker-compose.yml exec -T postgres \
  pg_dump -U karbar -Fc karbar_pulse > /opt/karbar-pulse/backups/pulse_$(date +\%F).dump 2>>/var/log/pulse-backup.log

# Retention: delete dumps older than 14 days
15 3 * * *  deploy  find /opt/karbar-pulse/backups -name 'pulse_*.dump' -mtime +14 -delete
```

**Retention:** keep 14 daily dumps on the host; copy the latest off-box (object storage / another host)
if available. Before the demo, also keep a dated "freeze" snapshot indefinitely (see §7).

**Restore (exact steps):**

```bash
# 1. Stop the app so nothing writes during restore
docker compose stop web worker

# 2. Drop and recreate the database (custom-format dump + pg_restore --clean also works;
#    a clean createdb is the most predictable)
docker compose exec -T postgres psql -U karbar -d postgres -c "DROP DATABASE karbar_pulse;"
docker compose exec -T postgres psql -U karbar -d postgres -c "CREATE DATABASE karbar_pulse OWNER karbar;"

# 3. Restore the dump (custom format -> pg_restore)
docker compose exec -T postgres pg_restore -U karbar -d karbar_pulse --no-owner \
  < /opt/karbar-pulse/backups/pulse_2026-10-14.dump

# 4. Bring the app back
docker compose start web worker
```

(For a plain-SQL dump, replace step 3 with `psql -U karbar -d karbar_pulse < dump.sql`.)

### ChromaDB (rebuildable)
Chroma persists to the `chromadata` volume, so a normal restart loses nothing. Chroma is **derived
state** — its documents are produced by `seed_demo` (fabricated fictional KB) or re-chunked from
Postgres rows (PO comments). If the volume is lost or corrupted, rebuild rather than restore:

```bash
docker compose run --rm worker python manage.py reindex_kb all
```

This re-chunks and re-embeds all documents. No separate Chroma backup is required for Phase 0;
Postgres is the only authoritative store.

---

## 6. Ops

- **Log rotation:** every long-running container uses the Docker `json-file` driver with
  `max-size: 10m` / `max-file: 5` (shown in §1), capping per-container logs at ~50 MB. Caddy's access
  log file is rotated by host `logrotate` (or Caddy's own `roll` directive). No unbounded logs.
- **Health checks:** `/healthz/` is a public JSON view (`{status, as_of}`) used by the compose
  `healthcheck` on `web` and by any external uptime monitor. `postgres` uses `pg_isready`. An unhealthy
  `web` is restarted by `restart: unless-stopped`.
- **Resource notes:** sized for 22 factories / ~1,287 POs (412 open). A 2 vCPU / 4 GB VPS is adequate:
  Postgres is the heaviest resident, uvicorn is light, the single `qcluster` worker (`Q2_WORKERS=4`)
  handles ingest + nightly predictions well within the window. Chroma's footprint is small (documents
  only). Keep swap enabled; watch disk for `pgdata` + `backups` + Docker logs.
- **Deploys:** build the new image, `docker compose up -d` (web runs migrate + collectstatic on start),
  verify `/healthz/`. Roll back by re-deploying the previous image tag.

---

## 7. Demo-day freeze runbook — 15 Oct 2026

The demo runs on seeded data as of `DEMO_TODAY=2026-10-15` and must reproduce the answer-key numbers
exactly. The goal of the freeze is **zero change on the day**.

1. **T-1 evening (14 Oct): cut a labelled snapshot.** Take a `pg_dump` and keep it indefinitely,
   clearly named, e.g. `backups/pulse_DEMO_FREEZE_2026-10-14.dump`. This is the rollback point.
2. **Confirm the seed is the live state.** If anything was poked during rehearsal, restore seeded state
   with `docker compose run --rm web python manage.py reset_demo` (restores the seeded 15 Oct state:
   master data, orders, snapshots, KB), then re-run `reindex_kb all` if KB was touched.
3. **Freeze deploys.** No image builds, no `up -d`, no migrations, no master-data/parameter edits on
   15 Oct. Announce the freeze; the only running processes are the five services already up.
4. **Pre-demo smoke check (morning of 15 Oct), in order:**
   a. **Seed parity** — spot-check headline KPIs against the answer key: October on-time **86.25%**,
      value at risk **USD 2,400,006**, air-freight exposure **USD 539,720**, open-PO count **412**,
      and the hero PO **71010305** shows slip **9 days**, band **Critical**, score **76**.
   b. **Assistant fallback available** — confirm the three demo questions return (A-09): (1) factories
      that will miss October ex-factory; (2) why PO 71010305 is late and the fastest fix; (3) October
      on-time % and where the USD 2.4M is concentrated. Verify the **pre-stored fallback answers** are
      present so the path runs even if the OpenAI call is slow/unavailable.
   c. **Theme toggle** — flip dark/light; confirm it persists.
   d. **One upload** — drop a known-good daily Excel into `/uploads/`, watch the HTMX status poll go
      `queued → running → done`, then **immediately restore the freeze snapshot** (step 1) so the demo
      data is pristine again, OR run the smoke upload against a scratch copy before the freeze. Do not
      leave ingested test data in the demo DB.
5. **Rollback (if anything drifts during the demo window):** `docker compose stop web worker`, restore
   `pulse_DEMO_FREEZE_2026-10-14.dump` via the §5 restore steps, `docker compose start web worker`,
   re-verify step 4a. The freeze snapshot always returns the exact demo state.
6. **After the demo:** lift the freeze; resume normal nightly schedules and deploys.
