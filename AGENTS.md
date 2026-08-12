# AGENTS.md — rules for AI agents working in this repo

Read `OVERVIEW.md` for architecture, `STACK.md` for structure, and `PLAN.md` for sequencing. This file is the short list of things that will break the project if you get them wrong.

## Stack — settled, do not propose alternatives

- **FastAPI monolith, JSON only.** One backend, one database. It renders no HTML. The three-layer split is a logical boundary, not a network boundary.
- **One React SPA: Vite + React + TypeScript**, in `frontend/`. Public site, report and operations console are all routes in the same app — not two frontends.
- **shadcn/ui + Tailwind.** shadcn components are copied into `components/ui/` and owned by us, not treated as a dependency. Design tokens stay CSS custom properties in `src/styles/tokens.css`, wired into the Tailwind theme — no raw hex in a component.
- **`app/api/v1/` is for CPO partners; `app/api/internal/` is for our own frontend.** Do not collapse them. `v1` is a contract with an outside party — breaking it breaks a partner integration. `internal` may be reshaped whenever the UI needs it.
- **The typed client is generated, never hand-written.** `frontend/src/api/schema.d.ts` comes from FastAPI's OpenAPI output; CI fails if the committed copy is stale. A renamed backend field must surface as a TypeScript error, not as `undefined` where a rupee figure should be.
- **No Node process in production.** The frontend is a build artifact: Caddy serves `dist/`, uvicorn serves `/api`.
- **`workers/poller.py` is a separate process.** It shares models but not the request lifecycle, and it runs at a higher reliability tier than the web app.
- **The operations console is a route group in the same SPA** (`features/console/`), behind session auth, backed by `api/internal/console_*.py`. Not a second application.
- If you think the project needs Redis, Celery, a message queue, or a global state library, first point at the specific query, job, or piece of state that requires it.

## Hard constraints — violating these is a revert, not a discussion

1. **No model may output a financial number.** Models predict `kwh_per_connector_day` and nothing else. Payback, IRR, NPV and revenue come only from `roi_engine.py`, which is a pure function.
2. **`roi_engine.py` must stay dependency-free.** No DB session, no HTTP client, no `datetime.now()`, no config import, no globals. Inputs in, dict out. If you need a value, add it to the input dataclass.
3. **Event tables are append-only.** Never write `UPDATE` or `DELETE` against `charger_status_events`, `predictions`, `tariffs`, or `sites`. Supersede with a new row and date bounds.
4. **Every output carries version stamps:** `model_version`, `economics_version`, `schema_version`, `archetype_version`, `tariff_effective_date`, `renderer_version`.
5. **Every prediction is written to `predictions` with `actual_kwh = NULL`.** No exceptions, including test and demo runs (flag them, don't skip them).
6. **No point estimates in any user-facing output.** P10/P50/P90 or a labelled scenario band.
7. **No paid API call without a hard quota cap already configured** in the provider console *and* a client-side counter.

8. **`api/` route handlers stay thin.** Parse request → call one `domain/` function → return a model. Longer than ~25 lines means the logic is in the wrong layer.
9. **The report payload is persisted as JSONB and served from storage.** `GET /api/internal/reports/{id}` returns the stored payload verbatim; it never re-runs the pipeline against today's data. **The rendered PDF is archived as immutable bytes at generation time** — because a browser render is not reproducible across Chromium versions, the archived artifact is what answers "this is not what your report said", not a re-render.
10. **Every metered external call writes an `api_usage_events` row before its response is used** — including retries, errors, and cache hits. A paid client with no meter is a revert. The row is what makes constraint 7's client-side counter real; without it the cap in `config.py` is decoration.
11. **LLMs are extraction and operations tooling only.** They may read a tariff PDF and propose structured values. They may never write a tariff row, produce a financial number, or sit anywhere in the prediction path — that remains `domain/demand/` predicting `kwh_per_connector_day`, and `domain/roi/` doing arithmetic. An LLM-proposed value reaches the ROI engine only after a human verification row exists. Stamp `model` and `prompt_version` on anything an LLM touched, and surface them in report provenance.

## Conventions

- Python 3.11+, `uv` for deps, `ruff` + `mypy --strict` on `app/domain/roi/`
- Frontend: TypeScript `strict`, `eslint` + `prettier`. No `any` at the API boundary — that is what the generated schema is for.
- Layer discipline is enforced in CI by import-linter — `app.domain.roi` may not import `app.db`, `app.models`, `app.api`, `app.config`, `httpx`, or `sqlalchemy`. Do not weaken the contract to make a change compile.
- Report components mirror the 7 sections one-to-one, so "the ledger is wrong" points at exactly one file.
- `src/styles/print.css` and the Playwright PDF path are first-class deliverables, not an afterthought. The PDF is exercised on every build so print styles cannot rot unnoticed.
- Migrations: Alembic only. Never `CREATE TABLE` outside a migration.
- All geometry `EPSG:4326`. Distances computed on `::geography`, not `::geometry`.
- **Money in paise as integers** — backend and frontend both. `lib/money.ts` is the only place paise become ₹.
- Energy in kWh, power in kW, **sanctioned load in kVA** — never conflate the last two. `lib/units.ts` keeps them apart.
- Timestamps `timestamptz`, stored UTC, rendered IST.
- Pin the toolchain: `uv.lock` and `package-lock.json` committed, Docker images by digest, Chromium revision fixed. Rule 1 now depends on this rather than on a template in git.

## Testing

- `roi_engine/` requires 30+ unit tests and must stay at 100% branch coverage.
- Geocoding cascade has a fixture set of 200 real addresses; regressions on the 100%-correct district assertion block merge.
- Any new feature in the context layer needs a null-handling test — real sites will be missing data.
- Metering: a test must prove that hitting a configured cap **refuses** the call rather than logging and proceeding.
- Frontend: `vitest` for `lib/money.ts` and `lib/units.ts` (rupee and kVA formatting are where silent corruption enters), Playwright for the report render and the PDF path.
- CI regenerates `frontend/src/api/schema.d.ts` and fails if it differs from the committed copy.

## When you are unsure

Prefer the boring, explicit, auditable version. This product's value is that a wrong number is traceable to a bad PDF or a bad geocode within minutes. Cleverness that obscures provenance is a net negative here.
