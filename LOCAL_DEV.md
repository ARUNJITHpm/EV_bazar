# Running locally — without Docker

Docker is **optional**. `docker-compose.yml` is kept as a reference for later, but
everything below runs natively on Windows with no containers.

The initial stage has one station data source: what owners upload (a bill photo or
PDF, or monthly units typed in). Nothing below needs a scraper. Status scraping is
a deferred later stage (`OVERVIEW.md`, "Later stage: status scraping") and stays
off unless `SCRAPER_ENABLED=true` — see the last section here.

---

## Run the app (needs Postgres)

To store owners, bills and forecasts you need PostgreSQL. Native install, no Docker:

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

4. **Create the schema** (installs PostGIS, builds the tables):

   ```powershell
   uv run alembic upgrade head
   ```

5. **Run it** — — start the API and the SPA in two terminals:

   ```powershell
   uv run python -m uvicorn app.main:app --reload --port 8000
   ```
   ```powershell
   cd frontend; npm install; npm run dev
   ```

   Then open `http://localhost:5173/owner` for the owner flow (in development the
   sign-in code is `000000`; it is refused in production until a real SMS provider is
   wired), or `http://localhost:5173/console` for the operations console.

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
| **Geocoding** | The cascade funnel, spend per level, and the manual queue. |
| **Overview** | Health and spend. |

Each panel carries a **"Words on this page"** box defining its own jargon, so the
terms are explained where they are used rather than in a document nobody opens.

---

## Status scraping (deferred)

Off by default. With `SCRAPER_ENABLED` unset the poller process exits at start, its
API routes return 404, and the console hides the CPO panel and the poller section.
To work on it locally, set `SCRAPER_ENABLED=true` in `.env`, then:

```powershell
uv run python -m workers.poller --dry-run   # fetch and print counts, no database
uv run python -m workers.poller --once      # one sweep, then exit
```

A source is polled only when **both** locks are open — config alone is never
consent:

1. **Authorised in code** — read the app's Terms of Service, record `terms_url`,
   `terms_note` and a `rate_limit_per_minute`, then set `authorised=True` for that
   entry in `app/domain/polling/sources.py`. That edit is the recorded decision.
2. **Configured in settings** — set its endpoint in `.env` (nested delimiter `__`),
   e.g. `CHARGEZONE__BASE_URL=...`, `CHARGEZONE__RATE_LIMIT_PER_MINUTE=30`.

Sources in the registry: `chargezone`, `statiq`, `kazam`, `chargemod`,
`tata_power_ez`, `ather_grid`, `jio_bp`. A laptop that sleeps leaves a hole in
any record it keeps, so a real run belongs on an always-on host.
