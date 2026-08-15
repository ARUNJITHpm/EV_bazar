# Running locally — without Docker

Docker is **optional**. `docker-compose.yml` is kept as a reference for later, but
everything below runs natively on Windows with no containers.

There are two levels of "run", depending on what you're doing.

---

## Level 1 — Validate a scrape, no database needed

The fastest loop when you've just captured a CPO app's endpoint and want to check
the mapping. **No Postgres, no Docker, nothing but Python.**

1. Put the endpoint in `.env` and authorise the source (see "Enabling a source").
2. Dry-run:

   ```powershell
   uv run python -m workers.poller --dry-run
   ```

   It fetches each configured source and prints, per source, how many stations and
   connectors came back and the status breakdown, e.g.:

   ```
   chargezone: 214 connectors across 88 stations [available=141, charging=52, offline=21]
   ```

   If the counts look wrong (everything `unknown`, or zero stations), correct the
   field names / status words in `app/domain/polling/normalise.py`
   (`from_scraped_stations` / `SCRAPE_STATUS_MAP`) and run it again. Nothing is
   written anywhere, so iterate freely.

---

## Level 2 — Actually record data (needs Postgres)

To store observations you need PostgreSQL. Native install, no Docker:

1. **Install PostgreSQL 16 + PostGIS** (Windows): the EDB installer
   (<https://www.postgresql.org/download/windows/>), then add the **PostGIS**
   bundle via *Stack Builder* (bundled with the installer).

2. **Create the database and user** (in `psql` or pgAdmin):

   ```sql
   CREATE USER evsite WITH PASSWORD 'evsite';
   CREATE DATABASE evsite OWNER evsite;
   ```

3. **Point the app at it** — in `.env`:

   ```
   DATABASE_URL=postgresql+psycopg://evsite:evsite@localhost:5432/evsite
   ```

4. **Create the schema** (installs PostGIS, builds the partitioned tables):

   ```powershell
   uv run alembic upgrade head
   ```

5. **Run the poller:**

   ```powershell
   uv run python -m workers.poller --once   # one sweep, then exit
   uv run python -m workers.poller          # loop forever on the interval
   ```

6. **See it in the console** — start the API and the SPA in two terminals:

   ```powershell
   uv run python -m uvicorn app.main:app --reload --port 8000
   ```
   ```powershell
   cd frontend; npm install; npm run dev
   ```

   Then open `http://localhost:5173/console` and sign in.

> **`uv run <name>` failing with "trampoline failed to canonicalize script
> path"?** The console-script shims in `.venv/Scripts` record the absolute path
> they were installed at, so they break if the project folder is moved. Either
> run the module form — `uv run python -m uvicorn`, `python -m mypy`,
> `python -m pytest` — or rebuild them once with `uv sync --reinstall`.

---

## The console login

Every console endpoint refuses until a password exists — an unconfigured console
returns **503**, never 200, because "we have not chosen a password" must not mean
"anyone may read CPO commercial terms".

```powershell
uv run python -m scripts.console_password
```

Paste the two printed lines (`CONSOLE_SECRET_KEY`, `CONSOLE_PASSWORD_HASH`) into
`.env` and restart the API. The script never writes to `.env` itself — a script
that edits your `.env` is a script that can clobber it.

### Where to start reading

| Panel | What it answers |
|---|---|
| **Lookup** | Put in a coordinate → district, state, LGD code, **and every step that got there**, with the table behind each answer. The example buttons walk through the interesting cases, including two deliberate refusals. |
| **Data** | Every table, how full it is, and what it is *for*. Then the tier per state, derived live from the evidence rather than declared. |
| **CPO** | Every charging network, and whether both locks are open yet. |
| **Geocoding** | The cascade funnel, spend per level, and the manual queue. |
| **Overview** | Health and the poller heartbeat. |

Each panel carries a **"Words on this page"** box defining its own jargon, so the
terms are explained where they are used rather than in a document nobody opens.

> A cheap always-on VPS is where the poller belongs in the end (PLAN 0.1) — never
> your laptop, because a laptop that sleeps is a hole in the record. For local
> development, running it by hand is fine.

---

## Enabling a source (the two locks)

A source is polled only when **both** are true — config alone is never consent:

1. **Authorised in code** — read the app's Terms of Service, record `terms_url`,
   `terms_note` and a `rate_limit_per_minute`, then set `authorised=True` for that
   entry in `app/domain/polling/sources.py`. That edit is the recorded decision.

2. **Configured in settings** — set its endpoint in `.env` (nested delimiter `__`):

   ```
   CHARGEZONE__BASE_URL=https://api.chargezone.example
   CHARGEZONE__STATIONS_PATH=/stations
   CHARGEZONE__API_KEY=            # if the endpoint needs one
   CHARGEZONE__RATE_LIMIT_PER_MINUTE=30
   ```

Scraped sources available: `chargezone`, `statiq`, `kazam`, `chargemod`,
`tata_power_ez`, `ather_grid`, `jio_bp`. They share one generic adapter and one
tolerant normaliser; only the endpoint and status words differ per app.

> **On overlap:** many chargers roam across these networks over OCPI, so the same
> physical unit shows up under several apps. That is kept on purpose — it maps the
> roaming graph and cross-checks occupancy — and is deduped downstream at analysis
> time (PLAN 2.3), never at poll time.
