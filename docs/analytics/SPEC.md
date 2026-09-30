# Chargeworthy Data: specification

Status: Parts 0, 1, 2 and 3 complete. Reviewed 2026-09-30.
Implementation brief: `chargeworthy-data-section-antigravity.md`.
Read this file before every subsequent analytics part, alongside `AGENTS.md`,
`OVERVIEW.md`, `STACK.md`, `PLAN.md` and `FINDINGS.md`.

## Purpose

A public section of the Chargeworthy site that explains EV charging in India
through data. It builds trust in Chargeworthy's judgment and supplies weekly
marketing content. It never shows private data.

## Reference

Modelled on the structure and principles described in the brief for
[Data For India](https://www.dataforindia.com):

- Content organised into a small number of verticals.
- Every chart can switch to a table view and download its data as CSV.
- Clear, transparent sources and methodology on every chart.
- Articles are living documents, updated as new data arrives, with dates.
- Original content published under Creative Commons Attribution 4.0 (CC BY 4.0).
- A short weekly format answering one question with one chart.

Do not copy its design, code, text, charts, logo or name. This review covers the
local repository; the reference website has not been audited.

## Name and routes

Section name: **Chargeworthy Data**. Base route: `/data`.
Use the existing React Router configuration in `frontend/src/routes.tsx`.
Bracketed route parameters in the brief become React Router colon parameters.

| Route | Purpose |
| --- | --- |
| `/data` | Landing page and public content search |
| `/data/:vertical` | One page per vertical below |
| `/data/district/:slug` | District document |
| `/data/insights` and `/data/insights/:slug` | Insight index and articles |
| `/data/weekly` and `/data/weekly/:slug` | Weekly index and posts |
| `/data/methodology` | Methodology and corrections |
| `/data/sources` | Dataset sources and licences |

Use explicit index and information routes alongside the dynamic vertical route;
validate slugs against a public registry and render an honest not-found page for
unknown values. Do not derive public pages from private owner records.

## Verticals

1. **Vehicles** (`vehicles`): EV registrations by district, month and vehicle class.
2. **Charging network** (`charging-network`): public chargers, chargers per 1,000 EVs,
   AC versus DC.
3. **Electricity** (`electricity`): EV tariffs by state, demand charges and
   time-of-day rules.
4. **Usage** (`usage`): estimated monthly kWh per charger from privacy-safe owner
   aggregates; publish only after Part 5's gates pass.
5. **Corridors** (`corridors`): highway stretches without a fast charger.
6. **Method** (`method`): sources, models, sample sizes and corrections; link to
   the dedicated methodology and sources pages.

## Non-negotiable rules

- No private data on any public page, in any bundle, source map, public CSV,
  social image or log. Owner data appears only as aggregates produced by the
  offline estimation engine in Part 5 under its privacy rules.
- No figures by named charge point operator. Public charger inventories must
  omit operator fields and must not become operator comparisons. Public source
  identifiers are distinct from private owner and station identifiers.
- Every chart shows source, last updated date and, for estimated values, a
  labelled P10/P50/P90 range. Missing or suppressed data is not zero.
- Never fabricate data. Obviously fake placeholders live only in test fixtures;
  they never render or ship in production builds. A development fixture mode
  requires both a development build and a visible "Test data" banner.
- Data pages never promote a CPO, charger brand or paid service beyond one quiet
  link to the home page. Shared navigation must respect this restriction.
- Independence and ownership claims require the factual conflict below to be
  resolved before they appear in new public copy.
- Models never produce financial numbers. Financial calculations remain in the
  dependency-free ROI engine. Tariff values are sourced observations, represented
  internally as integer paise and displayed only through `lib/money.ts`.
- Preserve all six required version stamps on generated analytical outputs:
  `model_version`, `economics_version`, `schema_version`, `archetype_version`,
  `tariff_effective_date`, `renderer_version`. Use explicit documented
  not-applicable values where needed, never invented vintages or omitted fields.
- Every prediction, including demo and test runs, is persisted in `predictions`
  with `actual_kwh = NULL` and appropriate run flags. Design Part 5's prediction
  adapter before fitting or running models.
- No new paid external call without provider-console caps, a client-side refusal
  counter and metering before its response is used. Public analytics must not
  enable the deferred status poller or put LLMs in a prediction path.

## Visual system

Data pages are documents and use the light Chargeworthy report palette. Site
header and footer retain existing site styling, subject to the content rules.
Colours belong only in `frontend/src/styles/tokens.css`, with Tailwind mappings
in `frontend/src/styles/index.css`; never put raw colours into components.

| Role | Colour | Existing token |
| --- | --- | --- |
| Paper | #FAF8F4 | `--cw-paper` |
| Ink | #12171A | `--cw-ink` |
| Slate | #1C3A4F | `--cw-paper-slate` |
| Rule | #D6D2C8 | `--cw-rule` |
| Muted | #5C5852 | `--cw-paper-muted` |
| Band | #B9C6CC | `--c-band` / Tailwind `cw-band` |
| Caution | #A65B1F | `--cw-caution` |
| Caution tint | #F5E6D3 | `--cw-caution-tint` |
| Chart highlight | #B5651D | Add an analytics-scoped token in Part 1 |

Use restrained slate, ink and muted series, with one copper highlight for the
series being discussed. Each series must also differ by marker or line style,
never colour alone. Check text contrast at least 4.5:1 and usable non-text
contrast; light range bands need an adequately contrasted boundary.

Use Source Serif 4 for headings and prose (`--cw-serif`) and IBM Plex Mono for
every number (`--cw-mono`, tabular figures). Both are already declared and loaded
by `frontend/index.html`, with system fallbacks. Body text is at least 17px with
1.6 line-height and no weight below 400. Use Indian number formatting (`en-IN`,
lakh and crore), and `lib/units.ts` for energy, power and sanctioned load.
Keep kWh, kW and kVA distinct.

No animation beyond chart transitions shorter than 200ms. Respect
`prefers-reduced-motion`; scope analytics motion so existing landing-page reveal
animations cannot hide prerendered content without JavaScript.

## Privacy rules for owner-derived figures

- Only stations whose owners gave analysis consent.
- Stations with shared or unknown meters excluded.
- A published group must contain at least 10 distinct eligible stations.
- No single station may make up more than one third of a group's total.
- Groups failing either rule show **"Not enough data yet"**, never a number.

Count distinct stations, not uploads, readings or connectors. Select the latest
confirmed correction for each station and billed month before aggregation.
Apply the gates for each published group and period. Part 5 adds connector-type
coverage and bias checks; it cannot relax these minimum rules. Public outputs
are an explicit aggregate-field allowlist, not private records with fields
removed. Check downloadable selections and overlapping groups for disclosure
risk before publication. Do not expose intermediate predictions or private
validation reports through the frontend.

## Repository review and implementation locations

| Concern | Observed implementation and intended integration |
| --- | --- |
| Framework | One FastAPI JSON backend, one Vite 7 / React 19 / strict TypeScript SPA. No second frontend and no Node server in production. |
| Routing | React Router 7 `createBrowserRouter` in `frontend/src/routes.tsx`; entry point `frontend/src/main.tsx` uses `createRoot` and `RouterProvider`. Feature chunks use `lazy` and `Suspense`. Add analytics under `frontend/src/features/analytics/`. |
| Styling | Tailwind 4 through `@tailwindcss/vite`; CSS custom properties in `src/styles/tokens.css`, `@theme inline` in `src/styles/index.css`; copied UI primitives under `src/components/ui/`. |
| Home and navigation | `src/features/public/Landing.tsx` defines its own `Header` and footer. `Landing` renders Hero, HowItWorks, WhatWeCheck, WhoRunsIt, Cards, ReportShowcase and Close. The footer is inside Close; insert the quiet Data section immediately before that footer and add only the requested Data navigation link. |
| Typed API | `src/api/client.ts` uses the generated `src/api/schema.d.ts`. Any new JSON endpoint belongs under `app/api/internal/`, with thin handlers and domain logic, not the partner API. Regenerate the schema rather than editing it. |
| Public data | Proposed repo-root `data/public/<dataset_id>/data.csv` and `meta.json`, `data/fixtures/` for tests, and `data/published/` for approved aggregates. Geometry uses its own TopoJSON/line artifact instead of CSV. Only validated allowlisted artifacts may be copied to the frontend build. |
| Backend analytics | Proposed `app/domain/analytics/` for validation, offline aggregation and publication; model fitting remains behind a `app/domain/demand/` interface. Use Alembic for any required schema changes. |
| Documentation | This file, then `docs/analytics/DATA_SOURCES_TODO.md` in Part 2 and `docs/analytics/WRITING.md` in Part 6. |
| Frontend checks | `npm run typecheck`, `format:check`, `test`, `build` in `frontend/`. Vitest 4 with jsdom and Testing Library; money, units, flow and report tests already exist. An ESLint script exists but its working configuration still needs verification. |
| Backend checks | CI runs uv, Ruff lint/format, import-linter, mypy and pytest; regenerates OpenAPI types and fails on drift. Preserve ROI purity and 100% branch-coverage requirement. |
| Build | `frontend/package.json`: `tsc -b && vite build`; Vite outputs `dist/`, build manifest and source maps. No prerender plugin or script is configured. |
| Deployment | Docker builds the frontend with Node and runs Caddy plus uvicorn. `deploy/Caddyfile` serves `/srv/frontend/dist`, proxies `/api/*`, and falls back to `/index.html`. GitHub `sync-to-hf.yml` publishes main to the Hugging Face Space; CI separately validates backend and frontend. |
| PDF | `app/pdf/render.py`, `scripts/archive_report_pdf.py`, `tests/test_pdf_render.py` and `src/styles/print.css` exist. Preserve archived report artifacts and renderer stamps. Analytics social images are separate build artifacts. |

## Conflicts, resolutions and dependencies

1. **Independence is factually inconsistent.** `OVERVIEW.md` section 6.3 says we
   are affiliated with an operating CPO; `PLAN.md` G.0 leaves the decision open.
   `Landing.tsx` and `report/Disclosure.tsx` say Chargeworthy is not a CPO and
   owns no stakes. The brief repeats the latter as required public copy.
   Ask the owner which statement is current. Until clarified, record this as
   unresolved and do not add absolute independence or ownership claims. Do not
   edit existing disclosures in Part 0.

2. **No-JavaScript pages require work absent from today's SPA.** The current
   entry point mounts into an empty root; a successful Vite build does not meet
   the brief's static HTML requirement. In Part 1 implement build-time
   prerendering for public analytics routes using the same React components,
   with hydration/progressive enhancement and static text and tables. Keep
   FastAPI JSON-only and Node build-only. Verify nested-path HTML resolution
   with Caddy and Vite preview. Extend the renderer for district/content routes
   in Parts 4 and 6. Never prerender owner or console pages, reports or private
   data; do not postpone this prerequisite to Part 9.

3. **No weekly dataset or publication date is established.** Part 1 must show
   an explicit preparation state in the home preview, latest chart and recent
   insights areas. Do not invent a chart, article, number or launch date. State
   the release dependency: content appears after sourced datasets are validated
   and a post is published. Search only registered public content; district
   discovery waits for the validated reference registry in Part 2.

4. **Existing inventory is not publication-ready.** `FINDINGS.md` documents
   source overlaps and incomplete coverage in scraped station inventory.
   Part 2 specifies a manually maintained public list. Do not silently export
   raw caches, per-CPO CSVs or owner stations. Curate licensed public records,
   deduplicate physical stations and define station/charger/connector counting
   before calculating ratios. Attribution and limitations remain visible.

5. **Existing VAHAN ingestion is annual, the brief asks for monthly data.**
   `FINDINGS.md` describes calendar-year and cumulative snapshots, not monthly
   registration series. Do not divide annual totals into fabricated months or
   claim rolling 12-month growth from inadequate periods. Obtain an appropriate
   public monthly source or label the available annual series; record human
   acquisition work in Part 2's source checklist. Keep LGD as the district key
   and disclose multi-district RTO allocation limitations.

6. **Part 5's model units conflict with AGENTS.md.** The brief proposes learning
   log monthly kWh per charger, while models here predict only
   `kwh_per_connector_day`. Fit behind the existing demand boundary using
   connector-days as the normalisation basis; derive monthly station/district
   totals arithmetically, with uncertainty. Never equate a station, charger and
   connector. Before Part 5, define exposure for partial bill periods, physical
   inventory matching, missing features and the prediction persistence adapter.
   No model run may bypass the prediction log or produce financial outputs.

7. **Existing owner peers do not satisfy public publication gates.**
   `FINDINGS.md` notes a state-level peer cohort despite district consent text,
   and an assumption-based `owner_peer_v0`, not a fitted model. Part 5 must use
   confirmed, consented, separate-meter station records and a reviewed district
   resolution; current `OwnerStationRecord` carries district/state names, not
   an LGD key. Resolve pins via the existing geography pipeline with provenance
   rather than joining names blindly. Define private out-of-sample validation
   before publishing; never reuse the placeholder curve as real public data.

8. **Licences differ by source.** CC BY 4.0 covers original Chargeworthy content
   and eligible original outputs. Third-party material retains its licence,
   including OSM's ODbL obligations. Do not blanket-relicense all source CSVs;
   document reuse permissions per dataset and with each download in Parts 2/7.

9. **Token and build descriptions contain older assumptions.** Actual Tailwind
   configuration is CSS-first v4, not a new `tailwind.config.ts`. Reuse the
   existing report tokens and add only the scoped chart highlight. Docker image
   references currently use tags, despite the repo's digest-pinning requirement;
   do not claim that toolchain acceptance already passes. Record the launch
   gap for Part 9 without changing Docker or deployment in this part.

## Ordered delivery and acceptance

Implement one part per checkpoint in the brief's order. Finish its acceptance
checks, report issues and ask questions if needed; otherwise report readiness
for the next part. The user's instruction authorises implementation; routine
reversible edits do not need repeated plan approvals.

After each completed part, pull and integrate remote changes, commit only that
part's work, and push to the shared remote. The user requested this workflow on
2026-09-30. Preserve unrelated local edits and existing staged changes.

| Part | Deliverable and completion check |
| --- | --- |
| 0 | This spec and repo review. Only this file is added; pre-existing edits remain intact. |
| 1 | Routes, navigation, page shell and initial prerendering. Every route renders; only the requested home additions change; text works with JavaScript disabled. |
| 2 | Public schemas, loaders, metadata, LGD reference and source checklist. Broken data fails with file/row/column; fixtures cannot enter production. |
| 3 | SVG chart component, tables, URL filters, CSVs and citations. Selected/all downloads match the displayed data and filters survive reload. Recharts is installed; evaluate existing capability before adding any chart dependency. |
| 4 | District map/pages. No-data districts use hatching and honest empty documents, never zero, and remain noindex. |
| 5 | Private offline fitting, validation and safe aggregate publication. Nine-station groups are suppressed; privacy allowlist tests pass; private LOO report and prediction ledger exist. |
| 6 | Insights and weekly content with writing guidance. Real sourced charts, update dates and changelogs render; fixtures cannot satisfy live-content acceptance. |
| 7 | Methodology, generated sources, licences, corrections and verified disclosure. Source-specific licences accompany every download. |
| 8 | Shared social export template in three formats. Minimum-size checks pass and each published weekly post has generated images; real WhatsApp preview needs an accessible deployed URL. |
| 9 | Performance, accessibility, SEO, privacy/build scans and required tests. Record measured evidence and remaining human/deployment checks; do not claim them from a build alone. |
| 10 | Source-dependent launch content backlog from the brief; publish only questions supported by validated public data. |

Part 0 acceptance is file existence and change scope. No application tests are
needed for this documentation-only part; later parts run checks appropriate to
their application changes. This analytics numbering is separate from the older
product roadmap numbering in `PLAN.md`.

## Part 1 checkpoint — 2026-09-30

- Added `frontend/src/features/analytics/`: public route shell, six verticals,
  preparation pages, public topic search, privacy/method/source notes and the
  quiet home section. Existing home content is retained; only its Data
  navigation link and section were added.
- `npm run build` now prerenders 12 public documents and an unpublished-page
  fallback with `frontend/scripts/prerender-analytics.mjs`. React hydrates
  matching documents; unpublished nested district/article/post paths receive
  their section's honest preparation document before JavaScript enhances it.
  No district names or article records were invented to fill the registry.
- Vite preview and Caddy resolve the generated HTML. Only public analytics is
  prerendered; no backend data, API calls, paid providers or models are involved.
- Acceptance: build/typecheck passed; all 138 frontend tests passed; 16 routes
  passed with JavaScript enabled and disabled through both Vite preview and
  Caddy. Search, reload/back navigation, home integration, metadata restoration,
  hydration, keyboard skip link and 375/768/1440px layouts were exercised.
- Repeat browser acceptance with `python scripts/check_analytics_shell.py --url
  http://127.0.0.1:4188` against a running built preview (or a Caddy URL).
  `--screenshots <directory>` optionally saves rendered layout evidence.
- Changed frontend files pass Prettier; the acceptance script passes Ruff.
  The full frontend format check still flags pre-existing formatting in
  `ConsoleLayout.tsx`, `Cpo.tsx`, `Data.tsx` and `Overview.tsx`. These were left
  untouched. Vite also reports the existing large-chunk warning; performance
  work remains Part 9.
- Next: Part 2, public datasets, schemas, validation and the verified LGD
  district registry. District search, weekly previews and recent articles
  intentionally remain preparation states until real sources/content exist.
  Independence copy remains omitted pending the factual clarification above.

## Part 2 checkpoint — 2026-09-30

- Added strict CSV and geometry schemas, metadata validation, LGD joins,
  typed browser loaders and a Vite public-data plugin. Approved files are
  emitted with SHA-256 hashes, source-specific licence notes and version
  stamps. Tariff money uses integer paise; unknown charges remain null.
- The build reads only the allowlisted public dataset tree. Missing sources
  stay pending; active datasets must have complete metadata. Invalid records
  fail with file, row and column. External symlinks, duplicate identifiers,
  unknown LGD codes and production fixtures are rejected.
- Exported 783 valid district records from the existing, hash-verified LGD
  reference archive. Its historical coverage and retrieval date are visible;
  this is not represented as a complete current district registry. District
  search and source notes use this reference; empty district pages remain
  noindex. The build now prerenders 795 public documents.
- Added clearly fake development fixtures for all seven datasets. They are
  accessible only in development with `?fixtures=1`; the production plugin
  never reads the fixture tree. Docker copies only `data/public` into the
  frontend build stage.
- Six datasets remain pending: RTO mapping, monthly registrations, curated
  public chargers, verified tariffs, district boundaries and highways.
  `docs/analytics/DATA_SOURCES_TODO.md` records exact acquisition sources,
  required fields, licensing and verification work. No figures were invented
  and no private inventory was exported.
- Acceptance: production build and TypeScript checks passed; all 163 frontend
  tests passed. `npm run data:check-build` proved a broken real CSV makes
  `npm run build` fail, then restored its original bytes and scanned generated
  assets for fixture leakage. Browser acceptance passed on 17 routes with
  JavaScript enabled and disabled, including district discovery and the
  development/production fixture gate. Changed files pass Prettier and Ruff.
- Repeat validation with `npm run data:validate` in `frontend/`; repeat the
  fixture and build-refusal check with `npm run data:check-build` after a clean
  build, with no concurrent build. Browser acceptance accepts `--dev-url` to
  exercise fixture isolation alongside a production preview.
- No backend API, model, paid call or deployment was added. The existing
  formatting and bundle-size limitations recorded in Part 1 remain.
- Next: Part 3, the shared SVG chart component, table view, URL filters,
  source citations and matching CSV downloads. Live chart publication still
  requires validated source data.

## Part 3 checkpoint — 2026-09-30

- Added shared deterministic SVG charts: line, vertical/horizontal bars, dot/range and small multiples with a common numeric scale. Explicit missing rows break paths; estimates require ordered P10/P50/P90; suppressed rows refuse values and sample sizes. Shapes and line styles distinguish up to three series; larger comparisons use small multiples.
- Added sortable semantic tables, en-IN numeric formatting, chart-specific URL filters/view, selected/all CSVs carrying raw values, ranges, source licences and all versions, and citation copying with a manual fallback. Browser controls use the latest URL to preserve successive filters during concurrent router renders. Static HTML includes the SVG and a full noscript table.
- Development demo requires both development mode and fixtures=1, visibly labels invented data and covers every chart family. Production excludes its module and fixture strings, including source maps. Save image is visibly deferred to Part 8. Integration guidance is in CHARTS.md. No source-dependent live chart or model prediction was created.
- Acceptance: all 180 working-workspace frontend tests passed (17 new chart tests), strict typecheck, production build and 795 prerendered documents passed, changed-file Prettier and browser-script Ruff passed. Actual browser checks passed real selected/all downloads, filter reload/back, keyboard controls and 375/768/1440px layouts; production demo exclusion passed with JavaScript on/off. Existing shell acceptance passed 17 routes with JavaScript on/off. Inspected the rendered line chart. The broken-CSV build refusal and production fixture scan passed.
- Fixed two existing CSV acceptance mutations to match both LF and CRLF, so Windows checkouts exercise the intended invalid values. Existing large-chunk warning remains a Part 9 item. No new data acquisition or publication blockers were introduced in this component part.
