# Chargeworthy Data: specification

Status: Parts 0–3 complete; Part 4 implementation complete with live indicators pending sources; Part 5 working draft unpublished; Part 6 content implementation complete; Part 7 implementation complete with owner-confirmed affiliation and ownership disclosure. Part 8 social exports implemented; public origin and deployed WhatsApp check pending. Reviewed 2026-10-01.
Implementation brief: `chargeworthy-data-roadmap.md`.
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

1. **Affiliation and ownership clarified by the owner.** The owner confirms
   Chargeworthy currently has no CPO affiliation, owns no charging stations and
   does not plan to own them. This supersedes the earlier OVERVIEW section 6.3
   affiliation statement for analytics copy. The fee model is site assessments
   and operator matching; current versus planned income is not asserted.
   Existing unrelated OVERVIEW edits are preserved.

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
   Publicly available data without a stated licence may be published with
   attribution under the publication rule in `DATA_SOURCES_TODO.md` (owner
   decision, 2026-10-03).

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

## Part 4 checkpoint — 2026-09-30

- Added validated build-time atlas and TopoJSON delta/reversed-arc decoding, five-step SVG choropleth, hatching for missing values, dotted wide-range estimates, tap/hover details, keyboard district list, sortable table and selected/all CSVs. Source licences, dates and version stamps accompany the map.
- District documents render static key figures, class/month registration charts, known opening records, integer-paise tariffs, locator and shared-edge neighbours when sources exist. Twelve-month totals need explicit complete class/month coverage; absent inventory is unknown, not zero. No-indicator districts remain noindex.
- Acceptance: 185 frontend tests passed including five new district tests; typecheck and production build passed with 795 documents. Browser checks passed development-fixture hatching, keyboard selection, observed counts, three widths, static empty district pages with JavaScript on/off, production demo exclusion and the existing 17-route shell. Build refusal/fixture scan passed. Changed-file formatting passed.
- Live boundaries, monthly registrations, curated charger inventory and tariffs remain pending in DATA_SOURCES_TODO.md. Production renders honest absence and archived district names, not invented geography or coverage. Real source-dependent figures and wide-range estimates are not claimed as live verification. Next: Part 5 offline engine, gated on reviewed private inputs and public inventory.

## Part 6 checkpoint — 2026-10-01

Implemented reviewed Markdown insight and weekly formats with strict front matter, safe body rendering, dataset-backed Chart components, publication/update dates and insight changelogs. Weekly posts have exactly one chart, at most 150 explanation words and captions under 300 characters. Indices sort newest first and retain vertical filters in URLs. Published posts join search, static routes, metadata, recent insights, the latest weekly chart and the landing topic list.

The initial insight and weekly post use the verified archived district reference only. Their charts derive counts from the source records and disclose the historical coverage. They do not infer current district boundaries or EV indicators. No fixtures, owner records or unverified usage estimates are published. Part 5's implementation remains an unpublished working draft; real fitting and usage publication still require reviewed inputs and validation.

Validation: isolated public build and strict TypeScript checks; content schema/source/length/date tests; component, search and prerender checks; production artifact privacy scan; browser checks with JavaScript enabled and disabled at 375, 768 and 1440 pixels, including chart tables, CSV download and vertical filters. Authoring and review rules are in `WRITING.md`.

ESLint could not run: the repository does not provide an `eslint.config.*` file. Strict TypeScript, scoped Prettier and the checks above passed.


## Part 7 checkpoint — 2026-10-01

Implemented plain-language methodology with a separately labelled technical draft, exact privacy rules and volunteer-bias limitations. Real validation remains pending: the build reads only an approved aggregate summary, never a private LOO report. The review export extracts saved run metrics and versions, refusing demos and incomplete runs. Sources are generated from validated metadata with reporting periods, dates, licences, attribution, downloads and published article chart links.

Every analytics page retains the original-content CC BY 4.0 footer. Source and chart CSVs carry a reserved licence comment; third-party licences remain distinct. Checksums cover the actual download bytes, the parser preserves row diagnostics and BOM handling, and export/content renderer versions are advanced to v2. Chart captions and citations support source attribution. The corrections registry validates dates, unique IDs and published chart references; affected charts link to their entry and entries link back. No correction history was invented.

Checks: production build and strict TypeScript, frontend tests, public-summary export tests, scoped Prettier/Ruff, fixture/build-refusal scan, and browser checks with JavaScript enabled and disabled at mobile/tablet/desktop widths. Source links, correction anchors and licensed/checksummed downloads passed. Existing ESLint configuration remains absent.

The owner confirmed no current CPO affiliation, no station ownership and no
plans to own stations. The disclosure states those facts and describes the
site-assessment/operator-matching fee model without asserting when income began.
Part 7 implementation and acceptance checks are complete. No real validation
run, private data export, production migration or deployment occurred.
Workflow details are in METHODOLOGY.md.

## Part 8 checkpoint - 2026-10-01

- Added a shared token-based SVG template for browser PNG downloads and build-time
  social export, with portrait, square and Open Graph formats. The current
  reviewed weekly post gets all three images, sourced from the archived reference.
- The Save image control exports the displayed selection, loads pinned local
  fonts and reports recoverable failures. PNG iTXt metadata preserves source
  licences, public rows and all six stamps; missing values stay missing.
- Weekly HTML includes OG image dimensions and alt text. SPA navigation updates
  and removes image metadata. Build-time minimum-font and wrapping checks refuse
  unreadable exports; a 300px gallery was inspected visually.
- Build, 123 frontend tests, browser PNG downloads/checksums/provenance, pinned
  font glyph bounds, responsive and JS-off OG checks, existing article checks,
  and the production privacy/fixture scan passed. ESLint remains unconfigured;
  existing large-chunk warnings remain for Part 9.
- The public HTTPS origin is awaiting user confirmation. Local builds currently
  emit explicitly labelled preview images; a deployed WhatsApp preview has not
  been claimed. Part 7 disclosure is confirmed and published separately. Part 8
  remains uncommitted and unpublished pending the public origin. See `SOCIAL_IMAGES.md` for configuration and remaining checks.

## Expansion source register (Part 11) - 2026-10-01

These are acquisition contracts, not active datasets. Source discovery and
publication are separate gates. The acquisition checklist, exact URLs and
remaining rights/vintage checks are in [DATA_SOURCES_TODO.md](DATA_SOURCES_TODO.md).
Reuse the existing validated `data/public/<id>/` layer and reviewed backend
lookups in Part 12; do not introduce another loader or a runtime scraper.

| Dataset | Report | Owner | Data section | Main page / assessment |
| --- | --- | --- | --- | --- |
| `discom_performance` | Dated utility AT&C loss and ACS-ARR gap context | Area/verified-provider context | Electricity and district grid context | Source labels and sourced-check coverage; no site loss claim |
| `supply_hours` | Published area-average supply, with interval and rural/urban coverage | Area comparison, separate from private outage log | Electricity and district context only at the published geography | Source labels / area context; never a site uptime assertion |
| `state_ev_policies` | Dated applicable policy context, separate from ROI inputs | Charging-policy context with eligibility caveats | Electricity, vehicle-policy notes and district/state context | District policy context and source labels |
| `nhai_wayside_amenities` | Dated announced amenities; charging only when explicitly listed | No new Part 14 card planned | Corridors, historical/current status separately labelled | Announced-site source labels and Corridors link |
| `osm_power` | Nearest mapped equipment, clearly unverified for capacity/access | No new Part 14 card planned | Sources register; no extra power-equipment map promised | Transformer-distance source label and truthful sourced/unverified count |
| `toll_plaza_traffic` | Conditional measured traffic context only after licence/unit gates | No consumer planned | Conditional future Corridors analysis, not required for Part 15 | Conditional traffic source label only when actual count evidence exists |

District, state and DISCOM averages are never presented as facts about one site.
No planned source upgrades a check from Unverified merely because a lookup exists.
All five required expansion datasets remain pending acquisition; toll traffic
is conditional and does not block Part 12's five-dataset contract.

### Decisions and corrections for Parts 12-16

- **Utility identity:** maintain stable DISCOM IDs, historical aliases, dates and
  reviewed service-area/billing evidence. A state-to-utility list cannot assign
  a provider to a site. Districts can have several providers; show possible
  providers or withhold assignment when the jurisdiction is unverified.
- **Supply periods:** retain the actual month, fiscal year, calendar year or
  other interval and rural/urban/all coverage. Never manufacture monthly or
  district observations from a state annual average. Do not calculate site
  outages as 24 minus area supply. Keep the source's units and definition.
- **WSA evidence:** the reviewed NHAI PDF contains a March 2021 bidding schedule;
  its publication date is unverified. Current planned/awarded claims need dated
  current evidence. Keep status as printed and charging flags true/false/unknown:
  silence means unknown. Require both coordinates or neither; never geocode
  chainage. Announced amenities never count as operational chargers.
- **Owner privacy:** normal edits supersede private grid revisions. Before an
  Alembic migration, define and test verified-owner consent withdrawal/erasure
  across all revisions, derived private caches and any retained audit records.
  Do not UPDATE/DELETE `charger_status_events`, `predictions`, `tariffs` or
  `sites`. Unverified phone login alone is not verified ownership. Private grid
  details stay out of public exports, other customers' reports and the current
  demand model; model changes require separate validation.
- **Corridor gaps:** measure along connected NH routes with distances on
  geography, EPSG:4326, reviewed charger access and inventory coverage. Straight
  line proximity and missing mapped stations do not establish a measured gap.
  Planned amenities cannot close a fast-charger gap.
- **Policy versus economics:** a notification is dated context, not an approved
  subsidy or entitlement. Unknown expiry does not mean currently valid. Preserve
  amendment/supersession and eligibility. The comparison with `subsidy_rules`
  is an offline human-review diff that writes to neither register nor rules.
  Only verified economics inputs reach the pure ROI engine; no LLM writes a
  tariff or financial prediction. LLM proposals carry model/prompt_version and
  an explicit human verification record before acceptance.
- **Actual counts:** inspect the current assembler and `PROMISED_SITE_FACTS` in
  `app/domain/report/coverage.py` before changing counts. Do not blindly add two
  to an old count. Pin the real 12-section report structure and verify coverage
  and the ReportBuild test together. Pending sources remain Unverified.
- **Shared provenance:** preserve edition, table/page, source URL, checksum,
  represented period, retrieval date, licence and transformations. Carry all
  six version stamps on outputs. Stored report JSON and archived PDF bytes stay
  immutable; new context must not rewrite old reports. Generate API types from
  OpenAPI when fields are added. New context needs null-handling tests.

The roadmap's raw schemas need identity and methodology refinements before
implementation: DISCOM identifiers/jurisdiction evidence; supply definition and
area type in the natural key; policy amendment/eligibility and verification;
OSM point-derivation provenance; WSA unknown document dates and paired nullable
coordinates. Geographic joins must allow missing/unresolved LGD codes rather
than guessing. Monetary observations are sourced integer paise, never model
outputs; predictive user-facing values retain P10/P50/P90 or labelled scenarios.
These refinements resolve the roadmap/AGENTS constraints without relaxing them.

### Part 11 checkpoint

Completed six source checklists and the four-surface consumer matrix. Verified
primary source entry points, CEA's annual supply table, policy notification
evidence and the NHAI PDF checksum. NFMS public export/reuse, PFC downloads,
current WSA status, policy amendments and several licences remain acquisition
gates. No openly licensed per-plaza vehicle-count resource was verified.
Only SPEC.md and DATA_SOURCES_TODO.md are published for this part. No datasets,
application code, database, predictions or deployment were changed. Part 12
can proceed with validation/templates and independently verified acquisitions;
pending sources must not be activated as live data.

## Part 12 checkpoint - 2026-10-01

Implemented the five expansion schemas, pending public templates and clearly
marked development fixtures using the existing loader. Validation enforces
allowlisted fields, ranges, signed integer paise, dates/reporting intervals,
natural keys, nulls, state/LGD joins, ODbL and reviewed source provenance.
The expanded public schema is `public_analytics_v2`; all six stamps remain.

The offline export uses this same validator. Backend `PublicReference` lookups
verify a release-pinned snapshot digest against the exact CSV/metadata bytes,
refuse fixtures/stale activations/path escapes and return explicit pending or
no-match results. District lookups preserve wider context at its published
scope and never assign a serving utility. The subsidy comparison is an offline
human-review diff with no database writes or monetary text parsing.

Checks: production build and TypeScript; 150 frontend tests in the publication
checkout before the final export-path test, followed by the 51 scoped loader/
expansion tests; 19 backend tests; Ruff, strict mypy and scoped Prettier. Actual
npm builds refused a bad row in each of the five expansion datasets and the
reference dataset; fixture/artifact scan passed. Existing large-chunk warnings
and missing ESLint configuration remain recorded launch work.

Implementation is ready, but live acquisition is not complete. The Part 11
source/reuse gates remain open and all five expansion datasets stay pending;
fixtures do not satisfy acquisition. Toll traffic remains conditional. Only
owned Part 12 files are published; unfinished Parts 5/8 and unrelated work are
preserved. No API/report payload, database, model run or deployment changed.
See [PUBLIC_REFERENCE.md](PUBLIC_REFERENCE.md) for export, release pins, lookup
semantics and acceptance commands. Source-backed Parts 13-16 still need the
respective acquisition gates to pass.

## Part 12 source acquisition checkpoint — 2026-10-01

Activated 7,726 OSM power observations from the checksum-verified Geofabrik
Southern Zone snapshot (2026-09-30T20:22:42Z), retaining ODbL attribution,
unverified voltage tags and unresolved district joins. Nodes retain mapped
positions; ways use their first perimeter vertex. Seven relations are excluded.
The reproducible offline extractor has isolated osmium regression tests.

Archived three genuine PFC editions, CEA supply data, three state policy PDFs,
the historical NHAI directory and dated current tender evidence. Four expansion
datasets remain pending: PFC requires written commercial reuse permission;
CEA methodology/reuse and NHAI reuse/status require confirmation; policy
proposals require notified-order/amendment and human verification. No policy,
subsidy, ROI input, production database, report payload or archived PDF changed.
See PART12_SOURCE_REVIEW.md and PART12_SOURCE_INDEX.json for evidence and owner
actions. Full Part 12 acquisition and source-dependent Parts 13–16 remain open.

## Part 13 available-source checkpoint — 2026-10-01

OSM power proximity now enriches newly assembled reports through the shared
release-pinned reference, using PostGIS geography within 2 km. Mapped distance
and raw voltage remain unverified; first-way-vertex and regional coverage limits
are explicit. Written DISCOM spare-capacity confirmation uses the existing
advised kVA; demand and ROI inputs are unchanged. Optional public context,
ledger carry-through, source digests/dates and ODbL attribution are persisted.
Enriched reports carry schema stamp 0013_public_context_v1. Old stored JSON is
served without filling new defaults; no archived PDF is regenerated.

Parts 12 and 13 source-dependent work is deferred at the owner's request.
See PART13_REPORT_CONTEXT.md for each gate and remaining task. The unpublished
twelve-section report rebuild is preserved: local section 08 carries the grid
condition; published legacy reports carry it inside the verdict section until the
rebuild is separately published. Production reference configuration/deployment
is still required; this checkpoint does not claim deployment completion.


## Part 14 available-source checkpoint ? 2026-10-02

The station page now includes ?Your area? with six explicit missing/source states,
plus optional private grid details (kVA versus kW), transformer ownership/rating
and a separate approximate monthly outage log. Reviewed statewide supply rows
can be displayed from the pinned Part 12 reference with period, rural/urban
scope, definition and provenance. Current CEA acquisition is still pending.

Private writes append revisions with optimistic conflict checks and station
locking. Explicit private consent records carry the manual ownership-review
reference. Collection defaults to blocked: deployment staff must verify station
ownership evidence and configure the ID-to-evidence register; phone/password
login alone is not ownership verification. Withdrawal deletes every private
revision/consent while retaining bills; account/inactivity erasure includes them.
Browser cache clearing and public build privacy refusal are tested. Grid values
remain outside public analytics, prediction inputs and reports.

The clean migration chain adds 0022 after published 0020; existing unrelated
local migration drafts are preserved. The migration has not been applied to
production. Live database migration/trigger acceptance, ownership-review release
setup and backup-erasure operations remain release tasks. See
[PART14_OWNER_PRIVACY.md](PART14_OWNER_PRIVACY.md).

Parts 12/13 remaining acquisition is deferred as requested. Part 14 live
registrations/growth/charger ratios, reviewed serving-utility tariff/ToD and
human-verified policy consumers remain deferred until source gates pass. This
checkpoint completes the available-data UI and private storage infrastructure;
it does not claim those live metrics or source-dependent consumers are complete.


## Part 15 available-source checkpoint — 2026-10-02

Public Electricity now consumes reviewed AT&C observations with a same-edition,
year and metric-basis national reference and per-state trends; all charts retain
the outage/voltage warning. Supply hours retain separate geography, definitions
and rural/urban coverage. Policy tables retain notifications, validity, expired
and superseded states; registration charts include sourced policy date markers
and a causation warning. Metadata-driven source links and methodology explain
these limits, including CSV context and all six version stamps.

District pages add Grid and policy without inferring a serving utility. Fleet-
to-charger ratios remain unavailable rather than substituting new registrations.
Corridors separately display eligible dated planned/awarded EV amenities with
hollow symbols; they never establish or shorten a gap. Corridor gap computation
and its map still require verified operating DC-fast records, connected NH
geometry and reviewed snap metadata, and remain unimplemented.

The four relevant acquisition sources are still pending under Part 12, so current
production sections show explicit missing states. Source acquisition, serving-
DISCOM crosswalks, compatible fleet/inventory counts, real-data acceptance and
final Part 9 launch checks remain. See [PART15_PUBLIC_CONTEXT.md](PART15_PUBLIC_CONTEXT.md).
No private data, demand/ROI inputs, persisted reports or production database changed.


## Part 16 available-source checkpoint — 2026-10-02

The 34-question checklist now labels each source or missing evidence. Example
walkthrough values are explicit and fixed verification counts are removed;
report coverage counts only stored facts. Working and result share a sourced
LGD-linked district block, preserve pacing and omit unmatched older responses.
Electricity/corridor promotion is gated on eligible reviewed observations.
Fleet ratios, serving-DISCOM joins, source activation and complete 34-check
report emission remain pending. See [PART16_PUBLIC_FLOW.md](PART16_PUBLIC_FLOW.md).


## Part 9 launch acceptance checkpoint ? 2026-10-02

Implemented progressive loading, local licensed fonts, viewport-only geometry,
accessibility fixes, unique SEO metadata, source-licensed Dataset JSON-LD and
origin-gated sitemap/canonicals. A pinned axe browser/SEO/PDF acceptance template and
expanded all-artifact owner/grid scan are included. Workflow activation requires
GitHub workflow scope. Frontend 178 and backend
713 tests passed. Production URL, real Android/deployed-host acceptance,
populated production-record comparison, container execution and source-dependent
publication remain open. See [PART9_LAUNCH_ACCEPTANCE.md](PART9_LAUNCH_ACCEPTANCE.md).
