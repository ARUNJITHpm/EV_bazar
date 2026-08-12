# STACK.md — FastAPI JSON backend + Vite/React SPA

> Companion to `OVERVIEW.md` (architecture) and `PLAN.md` (sequencing).
> This file fixes the technology choices so the agent stops re-litigating them.

---

## 1. The decision

**One FastAPI application serving JSON. One React single-page app. One database.**

FastAPI renders no HTML. Every page — landing, pin drop, report, operations
console — is a React route in `frontend/`, talking to `app/api/`.

### Why the backend is still a monolith

The three-layer split in `OVERVIEW.md` is a **logical** boundary, not a network
boundary. Demand model → ROI engine is a Python function call. Making it an HTTP
call would add latency, failure modes, and a serialisation format to maintain,
and would buy nothing — they deploy together, scale together, version together.

The one thing that genuinely wants separate deployment is the **status poller**,
because it must run every 5 minutes forever regardless of whether the web app is
up. Separate process, same repo, same models, different entrypoint.

### Why a SPA

The product has grown a second, very different surface. The customer report is a
document. The **operations console** (`PLAN.md` Part C) is not — it is a
data-dense internal tool: sortable spend tables, filterable CPO terms, live
poller heartbeats, token-usage charts. That is where a component framework and a
real UI kit pay for themselves, and it is the majority of the interface surface
by screen count.

One frontend, not two. A React console plus a Jinja report would mean two
styling systems, two build stories, and two places every number is formatted.

### What this costs, stated plainly

Server rendering was carrying three requirements. Each now needs an explicit
replacement, and **these are load-bearing — do not treat them as boilerplate**:

| Was free with Jinja | Now requires |
|---|---|
| Byte-identical regeneration (Rule 1) | Archived PDF artifact + pinned `renderer_version` — see §6 |
| PDF export | Playwright headless Chromium — see §6 |
| SEO on public pages | Prerendered landing/marketing routes at build time |

If you are about to add a dependency that makes any row of that table harder,
that is the tradeoff to weigh, not bundle size.

---

## 2. Repo structure

```
evsite/
├── AGENTS.md
├── OVERVIEW.md
├── PLAN.md
├── STACK.md
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── docker-compose.yml
│
├── alembic/
│   └── versions/
│
├── app/                        # ◀── FastAPI. JSON ONLY. Renders no HTML.
│   ├── main.py                 # app factory, router mounting, CORS
│   ├── config.py               # pydantic-settings, all env vars, quota caps
│   ├── db.py                   # engine, session dependency
│   │
│   ├── models/                 # SQLAlchemy — ONE module per table group
│   │   ├── sites.py
│   │   ├── districts.py
│   │   ├── charger_status.py   # append-only
│   │   ├── tariffs.py          # time-bounded rows
│   │   ├── cpo_terms.py
│   │   ├── predictions.py
│   │   ├── attribution.py
│   │   ├── api_usage.py        # PART C.1 — append-only spend meter
│   │   └── price_cards.py      # PART C.1 — effective-dated, like tariffs.py
│   │
│   ├── metering/               # ◀── PART C.1. Wraps every paid client.
│   │   ├── meter.py            # write event -> then return response
│   │   ├── counter.py          # month-to-date sum; refuses at cap
│   │   └── pricing.py          # cost from the effective-dated price card
│   │
│   ├── domain/                 # ◀── THE MONOLITH'S REAL BOUNDARIES
│   │   ├── resolution/         # PART 1 — pin → LGD code
│   │   │   ├── normalise.py
│   │   │   ├── cascade.py      # nominatim → ola → mappls → google → manual
│   │   │   ├── providers/
│   │   │   └── spatial.py      # point-in-polygon, fallbacks
│   │   │
│   │   ├── context/            # PART 2 — feature vector
│   │   │   ├── roads.py
│   │   │   ├── poi.py
│   │   │   ├── competitors.py  # dedupe across sources
│   │   │   ├── grid.py
│   │   │   └── archetypes.py
│   │   │
│   │   ├── tariffs/            # PART 3a
│   │   │   ├── schedule.py     # effective-dated lookup
│   │   │   └── parse/          # per-SERC parsers
│   │   │
│   │   ├── roi/                # PART 3b — ⚠️ PURE. NO IMPORTS FROM ANYWHERE ELSE.
│   │   │   ├── __init__.py
│   │   │   ├── inputs.py       # frozen dataclasses
│   │   │   ├── engine.py       # the pure function
│   │   │   └── outputs.py
│   │   │
│   │   ├── demand/             # PART 4 — the ONLY uncertain thing
│   │   │   ├── interface.py    # ABC: predict() -> P10/P50/P90
│   │   │   ├── heuristic_v0.py
│   │   │   ├── lgbm_v1.py      # PART 8, drops in behind interface.py
│   │   │   └── coefficients/   # versioned YAML, never hardcoded
│   │   │
│   │   ├── polling/            # PART 0.1 — availability sources
│   │   │   ├── sources.py      # registry; refuses unauthorised sources
│   │   │   ├── normalise.py    # payload -> observations. PURE.
│   │   │   ├── adapters.py     # OCPI fetch
│   │   │   ├── ingest.py       # append-only write + poll-run ledger
│   │   │   └── health.py       # dead-man's switch
│   │   │
│   │   ├── vahan/              # PART 4a
│   │   ├── cpo/                # PART 6 — runs roi engine once per operator
│   │   ├── report/             # PART 5 — assembles the 7-section payload
│   │   └── attribution/        # PART 7
│   │
│   ├── api/
│   │   ├── v1/                 # ◀── CPO PARTNERS. Stable. Contractual.
│   │   │                       #     Breaking it means a partner integration breaks.
│   │   └── internal/           # ◀── OUR OWN FRONTEND. Free to change.
│   │       ├── assess.py       # POST /assess
│   │       ├── reports.py      # GET /reports/{id} -> stored JSONB payload
│   │       ├── console_spend.py
│   │       ├── console_cpo.py
│   │       ├── console_data.py
│   │       └── auth.py         # session cookie, console login
│   │
│   └── pdf/
│       └── render.py           # Playwright -> print route -> archived PDF bytes
│
├── frontend/                   # ◀── Vite + React + TypeScript
│   ├── package.json
│   ├── package-lock.json       # COMMITTED. Rule 1 depends on it.
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── components.json         # shadcn/ui config
│   ├── index.html
│   │
│   ├── src/
│   │   ├── main.tsx
│   │   ├── routes.tsx
│   │   │
│   │   ├── api/
│   │   │   ├── schema.d.ts     # GENERATED from FastAPI OpenAPI. Never hand-edited.
│   │   │   └── client.ts       # openapi-fetch, typed end to end
│   │   │
│   │   ├── components/
│   │   │   └── ui/             # shadcn/ui — copied in, owned by us, not a dependency
│   │   │
│   │   ├── lib/
│   │   │   ├── money.ts        # paise -> ₹ . THE ONLY PLACE THIS HAPPENS.
│   │   │   └── units.ts        # kWh / kW / kVA formatting, never interchangeable
│   │   │
│   │   ├── features/
│   │   │   ├── landing/
│   │   │   ├── assess/         # Leaflet pin drop + the five taps
│   │   │   ├── waitlist/       # tier 2/3 capture
│   │   │   │
│   │   │   ├── report/         # ◀── ONE COMPONENT PER SECTION. 1:1 with §7 anatomy.
│   │   │   │   ├── Report.tsx
│   │   │   │   ├── Verdict.tsx
│   │   │   │   ├── HeroNumber.tsx      # the signature element — see §7
│   │   │   │   ├── SiteProfile.tsx
│   │   │   │   ├── Financials.tsx
│   │   │   │   ├── CpoTable.tsx
│   │   │   │   ├── Ledger.tsx          # assumption ledger, ⚠️ rows
│   │   │   │   └── Provenance.tsx
│   │   │   │
│   │   │   └── console/        # ◀── PART C
│   │   │       ├── ConsoleLayout.tsx   # left sidebar
│   │   │       ├── Overview.tsx
│   │   │       ├── Cpo.tsx
│   │   │       ├── Data.tsx
│   │   │       ├── Geocoding.tsx
│   │   │       ├── SpendMaps.tsx
│   │   │       ├── SpendLlm.tsx
│   │   │       └── Reports.tsx
│   │   │
│   │   └── styles/
│   │       ├── tokens.css      # design tokens as CSS custom properties
│   │       └── print.css       # @page rules — first-class, see §6
│   │
│   └── dist/                   # build output; archived per release
│
├── workers/                    # separate entrypoints, same models
│   ├── poller.py               # ⚡ PART 0.1 — runs forever, independent
│   ├── vahan_ingest.py         # monthly
│   └── tariff_watch.py
│
├── scripts/
│   ├── load_lgd.py
│   ├── load_districts.py
│   └── build_crosswalk.py
│
└── tests/
    ├── test_roi_engine.py      # 30+ tests, 100% branch coverage
    ├── test_cascade.py
    ├── test_metering.py        # cap refuses the call; every call writes an event
    ├── fixtures/addresses_200.json
    └── test_report_regeneration.py
```

### The rules that keep it clean

```
frontend/  ──▶ app/api/internal/  ──▶ domain/  ──▶ models/
partners   ──▶ app/api/v1/        ──┘

domain/roi/     imports NOTHING from app/
domain/demand/  imports domain/context/ only
app/            renders no HTML
frontend/       talks to api/internal only — never to api/v1
```

`api/` handlers are thin. Parse a request, call one domain function, return a
model. Longer than ~25 lines means the logic belongs in `domain/`.

**`api/v1` and `api/internal` are separated on purpose.** `v1` is a contract
with an outside party; `internal` can be reshaped whenever the UI needs it.
Collapsing them means every console tweak risks a partner's integration.

Enforce the Python side with import-linter in CI:

```toml
[[tool.importlinter.contracts]]
name = "ROI engine is pure"
type = "forbidden"
source_modules = ["app.domain.roi"]
forbidden_modules = ["app.db", "app.models", "app.api", "app.config", "httpx", "sqlalchemy"]
```

That contract is worth more than a hundred code reviews.

---

## 3. Dependencies

### Backend

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "sqlalchemy>=2.0",
  "geoalchemy2",          # PostGIS types
  "alembic",
  "psycopg[binary]",
  "pydantic-settings",
  "httpx",                # geocoder + poller clients
  "shapely",
  "python-multipart",     # tariff PDF upload
  "playwright",           # HTML → PDF, replaces weasyprint
  "itsdangerous",         # signed session cookies (console auth)
  "numpy",
  "pandas",
  "scikit-learn",         # clustering, Part 2
  "lightgbm",             # Part 8 only
  "apscheduler",          # poller scheduling
]
```

Dropped: `jinja2`, `weasyprint`.

### Frontend

```jsonc
{
  "dependencies": {
    "react", "react-dom",
    "react-router-dom",
    "@tanstack/react-query",     // server state, caching, polling
    "@tanstack/react-table",     // the console is mostly tables
    "openapi-fetch",             // typed client, generated from OpenAPI
    "recharts",                  // spend + token charts (console only)
    "leaflet", "react-leaflet",  // pin drop
    "zod",                       // runtime validation at the API boundary
    "clsx", "tailwind-merge",
    "lucide-react",
    "@radix-ui/*"                // via shadcn/ui
  },
  "devDependencies": {
    "vite", "@vitejs/plugin-react",
    "typescript",
    "tailwindcss", "postcss", "autoprefixer",
    "openapi-typescript",        // regenerates src/api/schema.d.ts
    "vitest", "@testing-library/react",
    "playwright",                // e2e + the PDF path
    "eslint", "prettier"
  }
}
```

**Not included, deliberately:** Redis (Postgres is enough at this scale), Celery
(APScheduler + a table), a state-management library (TanStack Query covers
server state; `useState` covers the rest), a charting library on the *report*
(the hero number is hand-drawn SVG — see §7), any CDN-loaded script.

Add Redis only when you can point at the query that needs it.

### The typed boundary

`src/api/schema.d.ts` is **generated** from FastAPI's OpenAPI output:

```bash
uv run python -m app.export_openapi > openapi.json
npx openapi-typescript openapi.json -o frontend/src/api/schema.d.ts
```

CI regenerates it and fails if the committed copy differs. A backend field
rename becomes a TypeScript error instead of an undefined at render time —
which matters more here than usual, because the things crossing that boundary
are money and utilisation figures.

---

## 4. Request flow — pin to report

```
POST /api/internal/assess     (JSON: lat, lng, + 5 optional taps)
  │
  ├─▶ domain.resolution.cascade.resolve()        → sites row
  ├─▶ domain.resolution.spatial.to_district()    → lgd_district_code
  │      (every paid geocoder call writes an api_usage_events row first)
  │
  ├─  IF tier > 1 ─▶ return {status: "waitlist"}, log the site anyway, DONE
  │
  ├─▶ domain.context.build_features()            → feature vector
  ├─▶ domain.demand.predict()                    → P10/P50/P90   ◀ only uncertain step
  ├─▶ domain.tariffs.lookup(state, date)         → tariff row
  ├─▶ domain.roi.engine.compute()                → breakeven + financials
  ├─▶ domain.cpo.rank()                          → roi.engine × N operators
  ├─▶ domain.report.assemble()                   → ReportPayload + version stamps
  ├─▶ persist report_payload JSONB + predictions(actual=NULL)
  │
  └─▶ 201 {report_id}   → frontend routes to /report/{id}
```

**Persist the assembled payload as JSONB, then render from it.** The frontend
`GET /api/internal/reports/{id}` returns that stored payload verbatim. It does
not re-run the pipeline against today's data. This is unchanged from the
server-rendered design and remains the foundation of Rule 1.

Slow path: if context building exceeds ~3s, return `{status: "pending"}` and let
TanStack Query poll the report endpoint with a refetch interval. Don't reach for
a task queue before you've measured.

---

## 5. Frontend structure

Report components map **one-to-one** onto the 7 sections in `OVERVIEW.md` §8.
That mapping is the point: "the ledger is wrong" points at exactly one file,
`features/report/Ledger.tsx`.

Two formatting rules that exist because getting them wrong corrupts every
number on the page:

- **`lib/money.ts` is the only place paise become ₹.** Money is integer paise
  everywhere else, backend and frontend both.
- **`lib/units.ts` keeps kW and kVA apart.** They are not interchangeable and a
  60 kW charger needs ~67 kVA sanctioned. A shared formatter is how that error
  gets made once and repeated everywhere.

State: TanStack Query for anything from the server. `useState` for the rest.
No global store — there is very little client state that isn't server state.

---

## 6. Rule 1, print, and PDF — the part that got harder

> Rule 1: *reports must be byte-regenerable in three years.*

A Jinja template in git satisfied this trivially. A browser render does not:
Chromium's font rasterisation and layout change between versions. **Pretending
otherwise is the failure mode here.** So the guarantee is restructured:

1. **The stored JSONB payload is the data of record.** Immutable, append-only,
   versioned. Every number a customer saw is recoverable from it forever. This
   is the guarantee that actually matters in a dispute.
2. **The rendered PDF is archived at generation time** as immutable bytes
   alongside the payload. This is the artifact you hand to a customer who says
   "this is not what your report told me." You do not re-render it to answer
   that question — you retrieve it.
3. **`renderer_version` joins the version stamps** — the Vite build hash from
   the manifest, plus the pinned Chromium revision. Recorded on every report.
4. **Pin everything:** `package-lock.json` committed, Docker images referenced
   by digest, Playwright's Chromium version pinned in `pyproject.toml`, the
   built `dist/` archived per release.

The regeneration test in `tests/test_report_regeneration.py` becomes: render a
30-day-old payload with its recorded `renderer_version` and assert the PDF is
byte-identical to the archived artifact. It will pass while the pinned
toolchain is intact and fail loudly when someone bumps Chromium — which is
exactly the signal you want.

**Print CSS remains a first-class deliverable, not an afterthought.** Page
breaks between the 7 sections, `@page` margins, provenance block in the footer
of every page. It lives in `src/styles/print.css` and is exercised by the PDF
path on every build, so it cannot rot unnoticed.

```python
# app/pdf/render.py
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto(f"{BASE_URL}/report/{report_id}?print=1")
    await page.wait_for_selector("[data-report-ready]")  # never race the render
    pdf = await page.pdf(format="A4", print_background=True)
```

---

## 7. Design system

Tailwind, with **design tokens as CSS custom properties** in
`src/styles/tokens.css`, wired into `tailwind.config.ts` as the theme. Tokens
stay the single source of colour and size; Tailwind classes reference them.
No raw hex in a component.

shadcn/ui components are **copied into `components/ui/` and owned by us** —
they are source files, not a dependency. Restyle them to the tokens rather than
accepting their defaults.

### The two surfaces look different on purpose

**The report is an instrument panel, not a dashboard.** This product's whole
claim is that its numbers are auditable, so the visual language reads like a
survey report or a technical certificate — dense, tabular, precise,
unglamorous. `font-variant-numeric: tabular-nums` everywhere a number appears.
Hairline rules to separate, not cards and shadows. A single accent reserved
**exclusively** for the ⚠️ unverified-assumption state, so unresolved
assumptions are the loudest thing on the page after the verdict.

Resist the pull toward a generic SaaS dashboard — gradient hero, rounded cards,
three-colour status chips. That aesthetic signals "we made this number up in a
design tool." The competitive claim is the opposite one. **shadcn's defaults
will pull you exactly that way; override them.**

**The console may be a normal admin tool.** It is internal, it is dense, and
nobody is being persuaded by it. Use the shadcn table, dialog and form
primitives as-is there.

### The hero number

`HeroNumber.tsx` is the signature element and gets the design effort. Breakeven
utilisation, the P10–P90 band, and the margin of safety in one composed unit at
the top: a horizontal scale with the breakeven threshold as a hard vertical rule
and the prediction band drawn against it.

Hand-drawn SVG, not a chart library — it is one bespoke figure, and a charting
dependency would fight the styling on every axis. Whether the band clears the
rule **is** the verdict, and it must be legible in one second without reading a
word.

Keep everything below it quiet.

---

## 8. Running it

```yaml
# docker-compose.yml
services:
  db:        postgis/postgis:16-3.4
  nominatim: mediagis/nominatim:4.4       # India extract, self-hosted, profile-gated
  api:       uvicorn app.main:app
  frontend:  npm run dev                  # vite dev server, proxies /api -> api
  poller:    python -m workers.poller     # ⚡ separate, always up
```

Dev: Vite dev server on :5173 proxying `/api` to uvicorn on :8000. One command.

Production: `npm run build` emits static assets; **Caddy serves `dist/` and
reverse-proxies `/api` to uvicorn.** No Node process in production — the
frontend is a build artifact, not a running service. That keeps the SPA's
production footprint close to what server rendering had.

The poller runs as its own container with `restart: always` and its own
dead-man's-switch alert.

The web app can go down for an hour without lasting harm. **The poller cannot.**
Treat them as different reliability tiers from day one.

---

## 9. Where the Parts land

| Part | Backend | Frontend |
|---|---|---|
| 0.1 Poller | `workers/poller.py`, `domain/polling/`, `models/charger_status.py` | console Overview |
| 0.2 Tariff PDFs | `domain/tariffs/parse/` | — |
| 1 Resolution | `domain/resolution/` + `scripts/load_*.py` | `features/assess/` |
| 2 Context | `domain/context/` | — |
| 3 Tariffs + ROI | `domain/tariffs/`, `domain/roi/` | — |
| 4 Demand | `domain/demand/` + `workers/vahan_ingest.py` | — |
| 5 Reports | `domain/report/`, `app/pdf/` | `features/report/` (7 components) |
| 6 CPO | `domain/cpo/` | `features/report/CpoTable.tsx` |
| 7 Attribution | `domain/attribution/` + `api/v1/` | `features/console/Reports.tsx` |
| 8 Supervised | `domain/demand/lgbm_v1.py` | — |
| **C Console** | `app/metering/`, `api/internal/console_*.py` | `features/console/` |

Part 8 replaces one file and nothing else changes. That is still the payoff for
the whole architecture, and moving the frontend does not affect it — the
demand model never reaches the UI directly, only through a report payload.
