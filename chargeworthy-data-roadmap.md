# Chargeworthy Data: consolidated implementation roadmap

Reviewed 2026-10-01. This is the single roadmap for the public Data section and
its expansion into site reports, owner pages and the assessment flow. It combines
the two earlier implementation briefs, preserves Parts 0-17 and their acceptance
checks, and incorporates the current implementation status and agreed corrections.

Read `AGENTS.md`, `OVERVIEW.md`, `STACK.md`, `PLAN.md`, `FINDINGS.md` and
`docs/analytics/SPEC.md` before implementing a part. The original product roadmap
in `PLAN.md` uses different numbering. The analytics specification and its dated
checkpoints are the detailed authority; this document provides execution order.
Completed prompts below are reference requirements, not instructions to rebuild
or overwrite the existing implementation.

## Current status and remaining work

| Part | Status | What remains |
| --- | --- | --- |
| 0 | Complete | Preserve the existing specification and decisions. |
| 1 | Complete | Public routes, navigation and prerendered shell exist. |
| 2 | Data layer complete; acquisition pending | Only the archived district reference is live: 783 entries, historical 2024 coverage, retrieved 2026-08-12. Obtain and review RTO mapping, monthly EV registrations, public chargers, tariff orders, boundaries and highways. |
| 3 | Complete | Reuse chart/table controls, URL filters, CSVs, citations and missing-data handling. |
| 4 | Implementation complete; live indicators pending | Acquire verified datasets and geometry. Empty district pages stay honest and noindex until an indicator is published. |
| 5 | Working draft, unpublished | Finish review, tests, documentation, dependency/migration integration and publication adapters. Obtain reviewed station/inventory matches and eligible bills before a real run. No fitted public estimates or real validation metrics are published. |
| 6 | Complete for available sources | Existing articles explain the historical district reference. Add EV/network/electricity articles only when their sources are live. |
| 7 | Complete and pushed | Published commit `fe51a91`. Owner confirmed no current CPO affiliation, no station ownership and no plans to own stations. Fee model is assessments/operator matching; current versus planned income is not asserted. |
| 8 | Implemented locally; not committed or pushed | Confirm the public HTTPS origin, configure image URLs and deployment build environment, publish scoped changes, then verify a deployed WhatsApp preview. Local checks passed: build, 123 frontend tests, three PNG formats, provenance, font/bounds checks, responsive controls and OG metadata. |
| 9 | Open | Performance, accessibility, SEO, complete privacy/build checks, required tests and launch gaps. Run a baseline before expansion; run full final acceptance again after Part 16. |
| 10 | Source-dependent backlog | Publish only questions supported by verified public data. |
| 11 | Complete and pushed | Source register, consumer mapping and constraints published in `5aab63b`. Live source acquisition remains gated. |
| 12 | Infrastructure complete; acquisition partially complete | OSM power is active: 7,726 regional observations, unresolved district joins. Three PFC editions, CEA supply table, three policy PDFs and NHAI evidence are archived. Four expansion datasets await permission, methodology or human verification. See `docs/analytics/PART12_SOURCE_REVIEW.md`. |
| 13 | Not started | Report context and provenance; preserve old stored payloads and archived PDFs. |
| 14 | Not started | Owner area context and private grid details, with verified erasure behavior. |
| 15 | Not started | Electricity/Corridors content and district grid/policy blocks. |
| 16 | Not started | Truthful source labels, counts and district context in landing/assessment screens. |
| 17 | Source-dependent backlog | Add public-data questions after the relevant datasets are published. |

## What to do next, in order

1. **Complete live acquisition for Part 12.** Part 11 is published and the shared
   data infrastructure is implemented. Use the source register to resolve reuse,
   download, methodology and current-status gates; activate only reviewed inputs.
2. **Finish Part 8 separately while sources are researched.** Ask for the actual
   public HTTPS origin. Set `VITE_ANALYTICS_SITE_ORIGIN`, with no trailing slash
   or path, and pass it into the deployed frontend build. Existing localhost
   preview images do not prove that WhatsApp previews work. See
   `docs/analytics/SOCIAL_IMAGES.md` for checks. Publish only Part 8 changes;
   preserve the unpublished Part 5 work and unrelated edits.
3. **Acquire Part 12 sources in reviewable stages.** Start with DISCOM performance and
   notified EV policies, subject to actual acquisition and reuse permissions.
   Add OSM power, supply hours and current wayside-amenity evidence as their
   sources become usable. Toll traffic is optional and conditional. Missing
   sources stay pending; fixtures never count as live acquisition.
4. **Acquire the original Part 2 dependencies alongside Part 12.** Monthly
   VAHAN observations, reviewed RTO jurisdictions, a deduplicated public charger
   inventory and verified tariff orders are still required for district EV
   ratios, growth and owner tariff context. Boundary/highway geometry is needed
   for maps and corridor gaps. Expansion sources cannot substitute for these.
5. **Integrate Parts 13, 14, 15 and 16 in order** after their respective source
   gates pass. Do not claim that a source is available merely because a lookup
   or empty-state component exists.
6. **Keep Part 5 on a separate completion track.** Complete the offline engine
   safely with tests, then run it only on reviewed real inputs. Do not delay
   public-source content while waiting for owner-derived estimates. Do not put
   new owner grid fields into the current model without a separately validated
   model change.
7. **Run full Part 9 after Part 16.** Extend privacy checks to the new owner grid
   tables. Resolve the missing ESLint configuration, measure performance and
   accessibility, verify report/PDF compatibility and record deployment-only
   checks explicitly. Large-chunk warnings and unpinned deployment/toolchain
   gaps remain launch work, not evidence of completion.
8. **Use Parts 10 and 17 as the editorial queue.** Publication follows evidence,
   not the order of attractive article titles.

## Corrections and decisions that apply to every prompt below

- **Stack and model boundary:** one FastAPI JSON monolith and one Vite React
  TypeScript SPA; Node runs only at build time. Models predict only
  `kwh_per_connector_day`. Derive monthly station/district totals using physical
  connector exposure and calendar days; never equate station, device and
  connector. ROI stays pure and dependency-free. Public source observations,
  including monetary rates, are not model-produced financial outputs.
- **Prediction and provenance:** persist every prediction, including test/demo
  runs, with `actual_kwh = NULL` before use. Keep all six version stamps on
  outputs. Real validation summaries must pass the reviewed public allowlist;
  never load private LOO reports into the frontend. The current mixed-model
  draft uses at least 1,000 fitted-parameter Gaussian predictive simulations,
  conditional on fitted variance components; do not call this a refit bootstrap.
- **Shared data access:** extend the Part 2 loader and validation pattern. Backend
  lookups use the same reviewed, versioned files or a controlled import of them,
  not independently acquired copies. Define how validation/version identity is
  verified on the backend. Regenerate OpenAPI client types for new API fields.
- **DISCOM identity and geography:** define stable utility identifiers, aliases,
  historical changes and reviewed service areas/jurisdictions. A state list of
  DISCOMs does not establish the serving DISCOM for a point or district. Use
  verified billing/jurisdiction evidence; otherwise label possible providers or
  withhold the site-specific assignment. Do not guess from the state name.
- **Supply-hour coverage:** preserve the actual published period, including
  annual/fiscal or other intervals; never fabricate monthly observations. State,
  DISCOM or district averages are context, not feeder/site facts. Supply hours
  are not automatically outage hours; do not infer site outages as 24 minus an
  area supply figure. The original source's definition and coverage must appear.
- **Wayside amenities:** the supplied NHAI directory contains a March 2021
  bidding schedule. It is historical evidence, not proof of current planned or
  awarded status. Obtain dated current evidence before making a current claim.
  Preserve printed status and document vintage. A WSA becomes an announced
  charging site only with explicit EV-charging evidence; unknown/false charging
  listings are not announced stations. A planned WSA is never an open charger.
- **Corridor distances:** require verified highway geometry, charger coordinates,
  DC/power classification and recorded snapping tolerance. Measure distance
  along the highway, not straight-line distance between points. Do not geocode
  chainage, invent missing coordinates or let planned amenities close a gap.
- **Owner grid records:** normal edits supersede dated private records. Before
  the migration, document erasure and consent withdrawal for all versions,
  derived/private caches and permitted audit records. Test verified owner
  deletion. This does not permit UPDATE/DELETE against the protected event
  tables named in AGENTS.md. Grid fields stay private and do not enter another
  customer's report or the current usage model.
- **Policy and subsidies:** a policy register provides dated context. A null end
  date is not proof of perpetual validity; review amendments and supersession.
  Compare with `subsidy_rules` read-only for human review. Policy labels never
  silently change financials, model features or verdict arithmetic. Financial
  subsidy amounts remain verified ledger inputs to the ROI engine.
- **Report integrity:** new fields are optional and versioned; stored report JSON
  remains authoritative and archived PDFs remain immutable. Include source,
  reporting/retrieval dates and unverified limitations in the ledger/provenance.
  Derive advertised check counts from the actual emitted checks; do not blindly
  change 34 to 36 when the assembler already emits additional checks.
- **Privacy and licences:** distinguish observations from estimates and label
  ranges for estimates. Keep missing/suppressed values null. At least ten
  distinct consented, separate-meter stations and the one-third dominance gate
  apply to every owner-derived group/period. CC BY 4.0 covers original content;
  third-party data keeps its own licence, including OSM ODbL. Public availability
  is not reuse permission. Preserve all unrelated work and existing staging.
- **Disclosure:** state the owner's confirmed current affiliation and station
  ownership facts. Describe the assessment/operator-matching fee model without
  claiming current earnings or perpetual absence of future affiliations.
- **Source availability:** PFC source files/editions and their permissions still
  need acquisition review. The NPP landing page alone does not establish an
  openly exportable supply-hours dataset. Keep supply hours and per-plaza toll
  counts pending until an actual usable source is verified; toll revenue/fees
  are not traffic counts.

Source checks from the preceding review: [NHAI WSA directory](https://nhai.gov.in/nhai/sites/default/files/mix_file/NHAI_WSA_Site_Directory.pdf)
(2021 bidding schedule visible) and [National Power Portal](https://npp.gov.in/)
(entry page, not a verified supply-hours export). Record source-file dates,
checksums, reuse terms and reporting definitions during Part 11 acquisition.

## Working method

Implement one requested part at a time. Read the specification first, inspect
existing work and reuse completed components. Make routine reversible changes
within the user's authorised scope; ask focused questions when required facts
or choices are missing. The user has already authorised implementation and
requested git pull and scoped commit/push after each completed part. No blanket
plan-approval step is required. Do not commit unrelated work or mix unpublished
Part 5/8 changes into another part. Finish acceptance checks, report remaining
issues honestly and state readiness for the next part.

The detailed prompts and source schemas follow. Their numbering is retained so
existing checkpoints, tests and future requests remain understandable.

## Foundation requirements: Parts 0-10

## Part 0 — Review the repo and write the spec

```
Read this repository before changing anything. Identify: framework and
router, how pages and routes are defined, styling approach, where design
tokens live, how the home page and header navigation are built, test
setup, and how the site is built and deployed. Report this back to me.

Then create docs/analytics/SPEC.md with the content below, adapting file
paths and naming to this repo's conventions. Do not change any other
file in this part.

--- SPEC.md content ---

# Chargeworthy Data: specification

## Purpose
A public section of the Chargeworthy site that explains EV charging in
India through data. It builds trust in Chargeworthy's judgment and
supplies weekly marketing content. It never shows private data.

## Reference
Modelled on how Data For India (dataforindia.com) works:
- Content organised into a small number of verticals
- Every chart can switch to a table view and download its data as CSV
- Clear, transparent sources and methodology on every chart
- Articles are living documents, updated as new data arrives, with dates
- Content published under Creative Commons Attribution 4.0 (CC BY 4.0)
- A short weekly format answering one question with one chart
Use it as a model for structure and principles only. Do not copy its
design, code, text, charts, logo or name.

## Name and route
Section name: "Chargeworthy Data". Base route: /data.

## Verticals
1. Vehicles: EV registrations by district, month and vehicle class
2. Charging network: public chargers, chargers per 1,000 EVs, AC vs DC
3. Electricity: EV tariffs by state, demand charges, time-of-day rules
4. Usage: estimated monthly kWh per charger (from owner uploads)
5. Corridors: highway stretches without a fast charger
6. Method: sources, models, sample sizes, corrections

## Non-negotiable rules
- No private data on any public page, in any bundle, or in any CSV.
  Owner data appears only as aggregates produced by the estimation
  engine (Part 5) under its privacy rules.
- No figures by named charge point operator.
- Every chart shows: source, last updated date, and a note if values
  are estimates, with their range.
- Never fabricate data. Placeholder fixtures must be obviously fake,
  live only in test fixtures, and never render in production builds.
- Disclosure: Chargeworthy currently has no CPO affiliation. Data pages
  never promote a CPO, charger brand or Chargeworthy's paid services
  beyond one quiet link to the home page.

## Visual system
Data pages are documents, so they use the Chargeworthy report palette
(light): paper #FAF8F4, ink #12171A, slate #1C3A4F, rule #D6D2C8,
muted #5C5852, band #B9C6CC, caution #A65B1F, caution-tint #F5E6D3.
Site header and footer keep the existing site styling.
Chart series colours: a restrained set built from slate, ink, muted and
one copper highlight (#B5651D) for the single series being discussed.
Every series must also differ by marker shape or line style, never
colour alone.
Typography: serif (Source Serif 4) for headings and prose; tabular
monospace (JetBrains Mono or IBM Plex Mono) for every number. Body at
least 17px at 1.6 line-height, no weight below 400.
Indian number formatting (en-IN, lakh and crore).
No animation beyond chart transitions under 200ms; respect
prefers-reduced-motion.

## Privacy rules for owner-derived figures
- Only stations whose owners gave analysis consent
- Stations with shared or unknown meters excluded
- A published group must contain at least 10 stations
- No single station may make up more than one third of a group's total
- Groups failing either rule show "Not enough data yet", never a number

--- end SPEC.md ---

Finish by listing any conflict between this spec and the existing repo
(for example a different routing pattern or token system) and how you
propose to resolve it.
```

**Check:** `docs/analytics/SPEC.md` exists and nothing else changed.

---

## Part 1 — Route, navigation and page shell

```
Read docs/analytics/SPEC.md first and follow it.

Build the Chargeworthy Data section shell.

Routes (adapt to the repo's router):
  /data                     landing page
  /data/[vertical]          one page per vertical from the spec
  /data/district/[slug]     district page (content filled in Part 4)
  /data/insights/[slug]     articles (Part 6)
  /data/weekly/[slug]       one-chart weekly posts (Part 6)
  /data/methodology         (Part 7)
  /data/sources             (Part 7)

Home page integration:
- Add "Data" to the main header navigation, linking to /data.
- Add one quiet home page section near the end, before the footer:
  heading "Chargeworthy Data", one sentence explaining it is free,
  public data on EV charging in India, the latest weekly chart as a
  static preview image, and a link "Explore the data". Do not change
  any other home page section.

/data landing page, top to bottom:
1. Title and a two-sentence description of what the section is and
   that everything is free to use under CC BY 4.0.
2. Latest weekly chart, shown large.
3. The six verticals as a simple list with one line each.
4. Recent insights (title, date, one-line summary).
5. A district search field that jumps to /data/district/[slug].
6. Footer note: sources and methodology links, licence, and
   "Chargeworthy is not a charge point operator."

Vertical and district pages: create them now with their headings,
a "coming soon" state that says which data is being prepared, and
breadcrumbs back to /data. Empty states must say what will appear and
when, never a blank area.

Add a search box on /data that searches titles of insights, weekly
charts, verticals and districts (client-side index is fine).

Use static generation where the framework supports it. Data pages must
work with JavaScript disabled for text and tables; charts may enhance.
```

**Check:** Home page shows the Data link and section; every route renders; nothing else on the home page changed.

---

## Part 2 — Public data layer

```
Read docs/analytics/SPEC.md first and follow it.

Build the data layer for PUBLIC datasets only. Owner data is Part 5.

Structure:
  data/public/<dataset_id>/data.csv
  data/public/<dataset_id>/meta.json
  data/fixtures/<dataset_id>/data.csv   (fake values, tests only)

meta.json fields: id, title, description, source_name, source_url,
retrieved_on (ISO date), licence, geography_level, time_coverage,
update_frequency, notes, columns (name, type, unit, description).

Use LGD district codes as the join key for districts so renamed or
split districts stay consistent. Keep a district reference table:
lgd_code, district_name, state_name, slug, and any former names.

Create schemas, loaders and validation for these datasets:
1. ev_registrations: month, state, rto_code, lgd_code, vehicle_class
   (2W, 3W, 4W, bus, goods), fuel (electric only), count.
   Source: VAHAN dashboard, which reports by RTO. Include an
   rto_to_district mapping table and flag RTOs covering more than one
   district.
2. public_chargers: charger_id, name, lat, lon, lgd_code, road_class,
   connector_type, power_kw, ac_or_dc, opened_month (nullable),
   source_name, source_url, recorded_on. Compiled by hand from
   government and published lists, one source per row. This is a
   manually maintained list, not scraping.
3. ev_tariffs: state, discom, tariff_order_ref, effective_from,
   category, energy_charge_per_kwh, demand_or_fixed_charge, unit,
   tod_rules (text), notes. Source: state regulatory commission
   tariff orders.
4. district_boundaries: simplified TopoJSON of Indian districts from
   an openly licensed source; record the licence in meta.json.
5. highways: national highway lines from OpenStreetMap (ODbL) for the
   corridors vertical; record attribution.

Validation on build: required columns present, types correct, lgd_code
exists in the reference table, no negative counts, dates parse, every
dataset has meta.json with source_url and retrieved_on. Fail the build
with a clear message naming the file, row and column.

Do NOT invent real figures. Create fake fixtures only, clearly named
(e.g. station names "Test Station 01"), used only by tests and a
?fixtures=1 development mode that shows a visible "Test data" banner.

Write docs/analytics/DATA_SOURCES_TODO.md: a checklist for a human to
download or enter each dataset, with the exact source to use, the
fields needed and where to save the file.
```

**Check:** Build fails on a deliberately broken CSV with a clear message; fixtures never load in a production build.

---

## Part 3 — Chart component

```
Read docs/analytics/SPEC.md first and follow it.

Build one reusable Chart component used by every page in the section.

Types: line, bar (vertical and horizontal), dot/range (estimate with
P10 to P90), and small multiples. Choropleth maps are Part 4.
Render as SVG. Use a small library only if the repo already has one;
otherwise hand-built SVG with a shared scale/axis helper.

Every chart has, in this order:
- Title as a question or plain statement
- One-line subtitle saying what is measured and in what unit
- The chart
- Source line and "Last updated" date
- Notes, including an estimate note with range when relevant
- Controls at the bottom right:
    Chart / Table toggle
    Download CSV (current selection)
    Download CSV (all data behind this chart)
    Copy citation, e.g. "Chargeworthy Data, <title>, <url>,
    accessed <date>. CC BY 4.0."
    Save image (hooked up in Part 8)

Filters where the data supports them: region (state/district search),
time period, indicator. Filter state lives in the URL query string so
any view can be shared.

Table view: real <table> with headers, numbers right-aligned in
tabular monospace, en-IN formatting, sortable columns.

Accessibility: role="img" with a meaningful aria-label summarising the
main finding, keyboard-operable controls, visible focus, series
distinguished by marker/line style as well as colour, contrast at
least 4.5:1 for text.

Estimates: render the P10 to P90 range as a band or whisker and label
the value as an estimate. Groups with insufficient data render a
labelled gap, never zero.

Write component tests and a development-only demo page showing every
chart type with fixture data.
```

**Check:** Table view and both CSV downloads match the chart; filters survive a page reload via the URL.

---

## Part 4 — District map and district pages

```
Read docs/analytics/SPEC.md first and follow it.

1. Choropleth map component using the district TopoJSON from Part 2.
   - Colour scale in 5 steps from the report palette; legend with
     numeric breaks in monospace.
   - Districts with no data or insufficient data: diagonal hatching
     plus a legend entry "Not enough data yet". Never a colour.
   - Low-confidence estimates (range wider than a set threshold):
     lighter fill with dotted outline, legend entry "Wide range".
   - Hover/tap shows district name, value, range and sample size.
   - Keyboard: districts reachable via a searchable list beside the
     map; selecting one highlights it.
   - Fallback: a sortable table of the same values.
   Indicators to support: EV registrations (latest 12 months), public
   chargers, chargers per 1,000 EVs, estimated kWh per charger.

2. /data/district/[slug] pages, generated for every district:
   - District name, state, and a small locator map
   - Key figures: EVs registered (12 months and growth), public
     chargers (AC and DC), chargers per 1,000 EVs, estimated monthly
     kWh per charger (when published), each with source and date
   - Charts: registrations by month and vehicle class; chargers over
     time where opened_month is known; tariff summary for the state
   - Comparison with the state average and neighbouring districts
   - "What we don't know yet" box listing missing data honestly
   - Links to relevant insights

Pages must be static and fast. District pages with no data still
render, show what is missing, and are marked noindex until they have
at least one published indicator.
```

**Check:** A district with no data shows hatching on the map and an honest empty page, never a zero.

---

## Part 5 — Estimation engine for owner data

```
Read docs/analytics/SPEC.md first and follow it.

Build an offline estimation engine that turns private owner bill data
into public district aggregates. It runs as a script or scheduled job,
never in the browser. Raw owner data must never enter the website
bundle, public CSVs or logs.

Inputs:
- Owner bill records (from the existing owner pages): station, month,
  kWh, meter type, consent flag, install month, connectors
- public_chargers list from Part 2 (all known chargers, with features)
- ev_registrations from Part 2

Eligibility: consented stations with a separate meter only.

Model (version 1):
- Outcome: log(1 + kWh per physical connector per day). Monthly
  station/district totals are derived arithmetic, not model outputs.
- Features known for every charger, uploaded or not: AC/DC and power
  class, months since opening (spline or log), road class, distance to
  national highway, district EV registrations (log)
- Hierarchical (mixed) model with random intercepts for district and
  state, so small districts borrow strength from their state and
  region. Use the existing statsmodels MixedLM draft; keep the model behind a
  single interface so it can be replaced by the cluster model later.
- Build a reviewed physical-station/device/connector crosswalk from the
  public inventory. Predict daily connector-normalised energy for every
  non-uploading physical station, then derive its monthly kWh.
- District total for a month = sum of observed kWh for uploading
  stations + sum of derived monthly kWh for the remaining stations.
- Uncertainty: at least 1,000 fitted-parameter Gaussian predictive
  simulations, conditional on fitted variance components, produce
  P10/P50/P90 district totals and monthly physical-station averages.
  These are not a refit bootstrap; document this limitation.
- Where opened_month is unknown, impute from the state distribution
  and widen the range accordingly; record the share imputed.

Validation, written to a private report each run:
- Leave-one-out: predict each uploading station from the others;
  report median absolute % error overall and by charger type.
- Interval coverage: share of held-out stations falling inside their
  P10 to P90 range (target near 80%).
- Volunteer bias check: compare features of uploading vs non-uploading
  chargers per district (share DC, median age, share on highways) and
  flag districts where they differ by more than a set threshold.
- Out-of-sample log: store the prediction for every charger before its
  owner first uploads, then compare when the bill arrives.

Publication gate (all must pass for a district to be published):
- At least 10 eligible uploading stations in the district
- No single station above one third of the observed group total
- Uploading stations cover the charger types that make up at least
  70% of the district's connectors
- No bias-check flag, or the flag is disclosed in the district note
Failing districts publish "Not enough data yet" and nothing else.

Output: data/published/usage_estimates.csv plus meta.json, containing
only: lgd_code, month, stations_known, stations_with_data,
kwh_per_charger_p10/p50/p90, district_total_p10/p50/p90, note.
Define these legacy per-charger fields as monthly kWh per physical
station; do not silently switch their denominator to devices/connectors.
Preserve all six stamps in the published artifact and metadata.
Add a test proving no station id, owner field or individual kWh value
can appear in any published output.
```

**Check:** Published CSV contains only aggregates; a district with 9 stations publishes nothing; LOO report is produced.

---

## Part 6 — Insights and the weekly one-chart format

```
Read docs/analytics/SPEC.md first and follow it.

Build two content formats using Markdown/MDX (or the repo's content
system) with embedded Chart components by dataset id.

1. Insights (/data/insights/[slug]): longer articles answering one
   big question with several charts.
   Front matter: title, question, summary, vertical, authors,
   published_on, updated_on, datasets used, changelog entries.
   Show "Updated on" prominently and a changelog at the end, because
   insights are living documents.

2. Weekly (/data/weekly/[slug]): one question, one chart, at most 150
   words of explanation, source line. Designed to be shared.
   Front matter: title (a question), published_on, dataset, chart
   config, social_caption (for Instagram/WhatsApp, under 300 chars).

Index pages: /data/insights and /data/weekly, newest first, filterable
by vertical. A topic list at the bottom of /data linking every
vertical, insight and weekly post.

Writing rules to put in docs/analytics/WRITING.md:
- Plain language; explain every technical term the first time
- Every claim cites a chart or source on the page
- Estimates always given with their range
- No hype words, no exclamation marks, no promotion of any operator
- Indian number formatting; units always stated
```

**Check:** An insight and a weekly post render with live charts; updated_on and changelog appear.

---

## Part 7 — Methodology, sources, licence and corrections

```
Read docs/analytics/SPEC.md first and follow it.

1. /data/methodology in plain language:
   - What data we use and why
   - How district usage is estimated, explained without equations
     first, then a technical section with the model, features,
     validation results (from the latest approved real aggregate
     summary only: LOO error, interval coverage, number of stations)
   - Privacy rules for owner data, stated exactly as in the spec
   - Known limitations, including volunteer bias
2. /data/sources: generated from every meta.json; name, link,
   retrieved date, licence and which charts use it.
3. Licence: all Chargeworthy Data content and CSVs under CC BY 4.0,
   stated on every page footer and in every CSV download (a header
   comment or accompanying README in a zip).
   Third-party data keeps its own licence (e.g. OSM under ODbL);
   show attribution where required.
4. Corrections log at /data/methodology#corrections: date, what
   changed, why. Linked from any chart affected.
5. Disclosure: Chargeworthy currently has no CPO affiliation, owns no
   charging stations and does not plan to own them. The business model
   is based on site-assessment and operator-matching fees; do not assert
   current income versus planned income. No figures by named operator.
   Keep it short and factual.
```

**Check:** Sources page lists every dataset automatically; licence appears on each page and CSV.

---

## Part 8 — Social image export

```
Read docs/analytics/SPEC.md first and follow it.

Add image export to the Chart component's "Save image" control and a
build step that pre-renders images for each weekly post.

Formats:
- 1080x1350 (Instagram portrait)
- 1080x1080 (square)
- 1200x630 (Open Graph, used as the page's og:image and for WhatsApp
  link previews)

Each image contains: the chart title as a question, the chart, the key
number in large monospace, source line, "Chargeworthy Data" wordmark
text, and the page URL. Report palette, generous margins.

Legibility test: every image must remain readable when shown 300px
wide. Enforce minimum font sizes per format and fail the build if a
label would render below them.

Generate images server-side at build time (e.g. a headless renderer or
SVG-to-PNG); client-side "Save image" uses the same template.
```

**Check:** Each weekly post has three images; OG preview works when the URL is pasted into WhatsApp.

---

## Part 9 — Performance, accessibility, SEO and final checks

```
Read docs/analytics/SPEC.md first and follow it.

Performance: /data and district pages under 2s on a mid-range Android
over 4G. Lazy-load the map and TopoJSON only when in view. Pre-render
all pages. Keep chart JavaScript out of pages that have no charts.

Accessibility: run axe (or the repo's tool) on /data, a vertical, a
district, an insight and a weekly page; fix all serious issues.

SEO: unique titles and descriptions per page; Dataset structured data
(schema.org/Dataset) for each downloadable dataset with licence and
source; sitemap entries for published pages only; noindex on
districts without data.

Final acceptance checks, run and report:
- Header "Data" link and home page section work
- No private owner data anywhere in the build output: search the built
  files for station ids and owner fields from the private store
- Every chart shows source, updated date, and a working table view and
  CSV download
- Districts failing the publication gate show "Not enough data yet"
- Fixture data never appears in a production build
- All tests pass

Summarise every file created or changed.
```

---

## Part 10 — Launch content backlog

Not a prompt. The first ten weekly posts, all possible with **public data only**, before owner uploads build up:

1. Which Kerala districts registered the most EVs in the last 12 months?
2. How fast are electric 3-wheelers growing compared with electric cars in South India?
3. How many EVs share each public charger, district by district?
4. What does EV charging electricity cost in each South Indian state?
5. Where on NH-66 in Kerala is the longest stretch without a fast charger?
6. What share of public chargers in each state are DC fast chargers?
7. Which districts have many EVs but few public chargers?
8. How do time-of-day rules change charging costs across states?
9. How has the number of public chargers in Tamil Nadu changed by year?
10. Electric 2-wheelers: which districts lead, and how fast are they catching up?

Once the estimation engine publishes its first districts, add usage posts: how long new stations take to reach typical usage, AC vs DC usage per district, and seasonal patterns such as monsoon and festival months.

## Expansion requirements: Parts 11-17

## Expansion scope — source-dependent gaps to fill

### Site report, section 04 "The site" (`app/domain/report/assemble.py`)

The landing page promises 34 checks in five groups. Today several of them are
printed as `not assessed` or come from an archetype default. These are the gaps
the new sources can close:

| Group | Check | Today | New source | After |
|---|---|---|---|---|
| Access | AADT traffic count | not assessed | NHAI toll plaza data, only if an open per-plaza count exists | "Nearest toll plaza, X km, plaza-level count", sourced; otherwise stays not assessed |
| Access | Dominant flow direction, Peak hour timing | not assessed | none open | Unchanged — survey item |
| Demand | EV registrations, Vehicle mix | VAHAN district snapshot | VAHAN monthly (Part 2 contract) | Add 12-month growth |
| Demand | *(new)* EVs per public charger, district | — | VAHAN + `public_chargers` | New check, with state comparison |
| Power | Transformer distance | not assessed | OSM `power=transformer` / `power=substation` | "Nearest mapped: X m", ODbL, survey confirms |
| Power | Transformer spare capacity | not assessed | not public | Unchanged — DISCOM feasibility request; owner can supply (Part 14) |
| Power | Grid outage hours | not assessed | NFMS / National Power Portal supply hours | District or DISCOM average, labelled "not this feeder" |
| Power | *(new)* DISCOM performance | — | PFC AT&C loss report | Context line: serving DISCOM and its AT&C loss |
| Power | State subsidy applicability | archetype default | State EV policy register, cross-checked with `subsidy_rules` | Policy in force named, with validity dates |
| Competition | Announced stations | inventory only | NHAI wayside amenity directory | Planned/awarded WSA sites within 10 km, labelled planned |

Section 08 (what would change the verdict), 10 (assumptions ledger) and 11
(provenance) must pick these up too: each filled check names its source and date,
and anything still not assessed stays in the ledger.

### Owner pages (`frontend/src/features/owner/`)

Station page shows: last month, next-month forecast, comparison with similar
stations, demand, power factor, time of day, forecast track record. It shows
**nothing about the station's district or grid**, and asks the owner nothing about
their connection beyond the bill.

### Chargeworthy Data (`/data`)

Shell, charts, district pages, insights, methodology and sources are built. Most
datasets are still pending acquisition. The Electricity and Corridors verticals have
the least planned content.

### Main page and assessment flow (`features/public/`, `features/animation/data.ts`)

The landing page lists the 34 checks grouped by source. The working screen walks
through them. The result screen has no district context.

---

## Ground rules for these sources (from AGENTS.md and SPEC.md)

- Primary publishers only: government portals, regulators, PFC, NHAI, OSM. No
  blogs, videos, social posts or news as a cited source.
- Human-exported, versioned files; no scraping behind logins or CAPTCHAs; no paid
  traffic APIs (hard constraint 7).
- District or DISCOM figures are never presented as a fact about one site.
- New report checks are display context. They do not enter `roi_engine` or the
  demand model unless a later, validated model change says so.
- Owner-supplied grid facts are private, like bills.

---

## Part 11 — Source register (documentation only)

```
Read AGENTS.md, docs/analytics/SPEC.md and docs/analytics/DATA_SOURCES_TODO.md
first. Change only SPEC.md and DATA_SOURCES_TODO.md in this part.

1. SPEC.md: add these datasets with the surfaces that read each one
   (report / owner / data / main page):
     discom_performance      AT&C loss %, ACS-ARR gap, by DISCOM and year
     supply_hours            published supply hours by state/DISCOM/district
     state_ev_policies       notified EV policies and incentive types
     nhai_wayside_amenities  planned/awarded WSA sites on national highways
     osm_power               OSM power=substation and power=transformer points
     toll_plaza_traffic      ONLY if an open per-plaza count is found
   State the rule: district or DISCOM figures are never shown as a fact
   about a single site.

2. DATA_SOURCES_TODO.md: one checklist section per dataset in the existing
   style (exact source, fields, where to save, licence and vintage, what
   not to infer):
   - PFC "Report on Performance of Power Utilities", latest three editions.
     Record edition, fiscal year and table/page per value.
   - National Feeder Monitoring System and National Power Portal
     (https://npp.gov.in/). Find the official URLs and reuse terms. Only
     aggregates a human can export; no login-only data.
   - NHAI Wayside Amenities: https://nhai.gov.in/nhai/taxonomy/term/553 and
     https://nhai.gov.in/nhai/sites/default/files/mix_file/NHAI_WSA_Site_Directory.pdf
     Record the PDF date and checksum.
   - State EV policies: gazette notification or the state department page,
     starting with Kerala, Tamil Nadu, Karnataka. Central schemes from MoRTH
     (https://morth.gov.in/) and the Ministry of Heavy Industries.
   - OSM power features: Geofabrik extract or the existing Overpass client;
     ODbL attribution; note that coverage is incomplete.
   - Toll plaza traffic: check NHAI and data.gov.in for an openly licensed
     per-plaza traffic count. Record the answer and URL either way. Fees or
     toll collection are not traffic; do not substitute them.

3. Record the decisions in the corrections section of this roadmap:
   verified DISCOM identity/service-area mapping, real supply periods,
   dated WSA evidence and explicit charging flags, owner-record erasure,
   corridor route distances, policy/subsidy separation and actual check
   counts. Report remaining conflicts with SPEC.md or AGENTS.md.
```

**Check:** only the two docs changed; every dataset lists the surfaces that read it.

---

## Part 12 — Shared datasets: build them once

```
Read docs/analytics/SPEC.md first and follow it. Reuse the Part 2 data
layer exactly: data/public/<id>/ with templates and meta.json, fixtures in
data/fixtures/<id>/ (obviously fake, example.invalid), build validation,
fixture gate. No new loader pattern.

Datasets and columns:

discom_performance:
  state, discom, fiscal_year (2024-25), atc_loss_pct (decimal as
  published), acs_arr_gap_paise_per_kwh (integer paise, nullable),
  source_edition, source_table_ref, notes

supply_hours:
  state, discom (nullable), lgd_code (nullable), period_type
  (month/fiscal_year/calendar_year/other), period_start, period_end,
  published_period_label,
  area_type (rural/urban/all), avg_supply_hours_per_day,
  source_name, source_url, retrieved_on, notes
  Geography level and reporting interval are whatever was published;
  never downscale a state figure to a district or an annual figure to
  fabricated months. Validate 0-24 hours/day and preserve definitions.

state_ev_policies:
  state (or "central"), policy_name, notification_ref, notified_on,
  valid_from, valid_to (nullable), incentive_type (purchase_subsidy,
  road_tax_waiver, registration_fee_waiver, charging_capex_subsidy,
  concessional_ev_tariff, land_or_permit, other), vehicle_scope (2W, 3W,
  4W, bus, goods, charging, all), amount_text (verbatim, nullable),
  source_url, recorded_on, notes

nhai_wayside_amenities:
  wsa_id, nh_ref, state, lgd_code (nullable), chainage_km (nullable),
  lat, lon (nullable), status (as printed), ev_charging_listed
  (true/false/unknown), source_doc_date, source_page, notes
  Human-transcribed from the PDF. If an LLM proposes rows, write them to a
  review file stamped with model and prompt_version; only human-checked
  rows enter data.csv (AGENTS.md rule 11). Never geocode a chainage.

osm_power:
  osm_id, kind (substation/transformer), voltage (nullable, as tagged),
  lat, lon, lgd_code, extract_date. ODbL attribution in meta.

Validation: types, ranges (0-100 for %), one row per natural key, state
and lgd_code exist in the reference, money in integer paise, blank means
unknown never zero. Add a script outside the web build that lists
differences between state_ev_policies and the subsidy_rules table for
human review; it writes to neither.

Backend access: add read-only lookups in app/domain/ (one module per
dataset or one public_reference module) that the report assembler and
owner API can call with an lgd_code, state or point. They read the same
validated files (or a table loaded from them by an Alembic-managed
loader), never a second copy.
```

**Check:** build fails on a bad row in each dataset; the report and owner code can look up all five by district/state without touching the frontend.

---

## Part 13 — Site report: fill section 04 and carry it through

```
Read AGENTS.md, design/brand/report-spec.md, app/domain/report/assemble.py
and app/domain/report/coverage.py first. Logic in app/domain/report/,
handlers stay thin, payload stays the stored authority (rule 9).

Change these checks in section 04, each with source name and date:

Power and tariff
- Transformer distance: nearest OSM power=transformer, else
  power=substation, within 2 km: "nearest mapped: 140 m (substation,
  11 kV)". Note "Mapped by OpenStreetMap; the site survey confirms." Keep
  unverified=True. None within 2 km: "none mapped nearby", not "0" and
  not an error.
- Grid outage hours: from supply_hours at the finest published level
  for the site's district/DISCOM: "avg 22.4 h/day supply, <DISCOM>,
  <period> — area average, not this feeder". unverified=True stays.
  None published: keep "not assessed".
- New check "DISCOM performance": serving DISCOM and latest AT&C loss
  with edition. If several DISCOMs serve the state and the site's DISCOM
  is not verified, say so; do not guess. Direction always "neutral".
- State subsidy applicability: name the policy in force on the report
  date from state_ev_policies, with validity dates. The rupee amount in
  the financials still comes only from subsidy_rules via the ROI engine.
  If the register says the policy expired, direction "against" and the
  ledger lists it.

Demand
- EV registrations: add 12-month growth when monthly VAHAN data exists.
- New check "EVs per public charger, district" with the state figure
  beside it. Computed from our datasets only.

Access
- AADT traffic count: only if toll_plaza_traffic exists and the site is
  on the same NH within a set distance of a plaza; label it plaza-level.
  Otherwise unchanged.

Competition
- Announced stations: add planned/awarded NHAI wayside amenity sites
  within 10 km on the same NH, labelled "planned, not open", but only
  where current dated evidence explicitly lists EV charging. Historical
  directory rows and unknown charging flags are not current stations.

Carry-through:
- Section 08: add the checkable condition "DISCOM confirms transformer
  spare capacity of at least <kVA>" when spare capacity is unverified.
- Section 10: every check still unverified appears in the ledger.
- Section 11: provenance rows for each new dataset's version and
  retrieved_on; ODbL attribution for OSM.
- Bump schema_version for the payload change. Old stored payloads must
  still validate and render (fields optional); coverage.py reports what
  they lack.
- None of these values enter roi_engine or domain/demand.

Tests: null-handling test per new check (AGENTS.md); a payload with no
new data renders exactly as before; a sample fixture in
frontend/src/features/report/fixtures shows the new checks.
```

**Check:** a site with no mapped substation, no supply data and no WSA nearby renders "none mapped / not assessed", not zero; `roi_engine` diff is empty; Playwright PDF path still passes.

---

## Part 14 — Owner pages: district and grid context

```
Read AGENTS.md and frontend/src/features/owner/ first. Owner data is
private; nothing in this part reaches /data except through the Part 5
estimation engine and its gates.

1. New card on the station page, "Your area", read from the Part 12
   lookups by the station's district/state:
   - EV registrations in the district, last 12 months and growth
   - EVs per public charger in the district vs the state
   - Current EV tariff for the station's DISCOM and category, with
     time-of-day bands (from ev_tariffs), and a link to the order
   - Average supply hours for the area, labelled as an area average
   - EV policies in force for charging stations, with validity dates
   Each line shows its source and date. Missing data: "Not available
   yet", never zero. Money through lib/money.ts.

2. Optional grid details the owner can add (private, editable, dated):
   - Sanctioned load (kVA) and connected load (kW) — keep kVA and kW
     separate (lib/units.ts)
   - Transformer: own / shared / unknown, and its kVA rating if known
   - Outage log: month and approximate hours without supply
   Store via Alembic with append-only dated revisions during normal use
   (supersede, never update). Define verified privacy erasure of all
   private grid revisions before implementation, and extend the existing
   consent and "Delete my data" flow. Do not alter the protected event
   tables named in AGENTS.md.

3. Use of the owner grid details:
   - Shown back to the owner beside the area average supply hours.
   - Private owner display only in this part. Any future Part 5 feature
     integration requires a separate validated model change, consent,
     feature-availability/bias review and version bump. Never publish
     individual grid details or silently extend the current model.
   - Not used in any site report for another customer.

Tests: card renders with every source missing; delete removes grid
details; no owner grid field appears in any /data build output (extend
the Part 9 private-data scan).
```

**Check:** the station page shows the area card with sources; deleting the station's data removes the grid details.

---

## Part 15 — Chargeworthy Data: Electricity, Corridors and district pages

```
Read docs/analytics/SPEC.md first and follow it. Use the existing Chart
component, district map and empty states.

Electricity vertical:
- AT&C loss % by DISCOM, latest year, with the national figure from the
  same PFC edition as the reference line; trend over available years as
  small multiples by state. Fixed note: "AT&C loss is electricity that
  is not billed or not paid for, plus technical loss. It is not a
  measure of outages or voltage at any site."
- Supply hours by state/DISCOM where published, as its own chart.
- "Policies in force" table by state with validity and notification
  links; expired policies labelled with their end date.

Vehicles vertical:
- Policy start/end dates shown as markers on each state's registration
  chart, with the note "Dates are context; the chart does not show that
  a policy caused a change."

Corridors vertical:
- Gaps between consecutive verified DC fast chargers along each NH
  (snap tolerance recorded in meta; distance along verified highway
  geometry using geography). Straight-line point distances are not gaps.
- Planned/awarded wayside amenities as hollow markers labelled "planned,
  not a verified charger"; they never shorten a gap.

District pages:
- Add a block "Grid and policy": serving DISCOM(s) with AT&C %, area
  supply hours, policies in force. Each figure with its own source,
  date and coverage. Missing: "Not available yet".
- Add "EVs per public charger" with the state figure, if not already
  shown.

Sources page and methodology pick up the new datasets automatically from
meta.json; add a methodology paragraph on what each new measure does and
does not mean.
```

**Check:** every AT&C chart carries the outage note; a planned WSA site never closes a corridor gap.

---

## Part 16 — Main page and assessment flow

```
Read frontend/src/features/public/Landing.tsx, features/animation/data.ts,
features/public/flow/ and app/domain/report/coverage.py first. The 34
checks and their grouping by source are the owner's decision; do not
regroup them.

1. Landing page check list: update each check's source label to the real
   source it now uses (e.g. Grid outage hours -> "NFMS / NPP area
   average"; Transformer distance -> "OSM, survey confirms"; Announced
   stations -> "inventory + NHAI WSA directory"). Update the
   Measured / Sourced / Unverified counts to match what the report
   assembler actually emits, and keep PROMISED_SITE_FACTS in coverage.py
   in step if the count changes (two new checks were added in Part 13).
   The ReportBuild test must still pin the section list.

2. Assessment flow, working screen: when the site's district is resolved,
   show the district facts as they load (EV registrations and growth,
   EVs per public charger, serving DISCOM, policy in force), each with
   its source. Keep the owner-approved pacing.

3. Result screen: a short "Your district" block with the same four facts
   and a link to /data/district/<slug>. Plain facts, no ranking.

4. Home page "Chargeworthy Data" section: add one line linking the
   Electricity and Corridors verticals once they have live data.

No new claims on the landing page that the report does not print.
```

**Check:** every source label on the landing page matches what a real report prints for that check; counts match `coverage.py`.

---

## Part 17 — Content backlog additions (not a prompt)

Add to the original Part 10 list, all from public data once the datasets are live:

1. Which DISCOMs lose the most electricity to billing and collection gaps, and has it improved in three years?
2. Which states' EV policies are in force today, and which have expired?
3. Electric 3-wheelers vs 2-wheelers: where does each dominate, district by district?
4. How many EVs share each public charger, compared with the state average?
5. NH-66: how many planned wayside amenities sit inside today's longest fast-charger gaps?
6. How many hours a day of supply do rural and urban areas get, state by state?

After Part 16, run the original **Part 9**, extending its private-data scan to the owner grid tables from Part 14.
