# Chargeworthy Data — Implementation Prompts for Antigravity

A new public analytics section for the existing Chargeworthy site, reached from the home page. Modelled on how **Data For India** (https://www.dataforindia.com) works: public, sourced, non-partisan data explained in plain language, with every chart downloadable.

## How to use this file

1. Open the existing project in Antigravity.
2. Paste **Part 0** first. It writes a spec file into the repo that every later part reads, so later prompts stay short.
3. Paste one part at a time, in order. Use planning mode and approve each plan before it edits files.
4. Run the acceptance checks at the end of each part before moving on.

| Part | What it builds |
|---|---|
| 0 | Repo review and the spec file |
| 1 | Route, navigation from home page, page shell |
| 2 | Public data layer (sources, schemas, loaders) |
| 3 | Chart component (chart/table toggle, CSV, citation) |
| 4 | District map and district pages |
| 5 | Estimation engine for owner data (privacy-safe aggregates) |
| 6 | Insights articles and the weekly one-chart format |
| 7 | Methodology, sources, licence, corrections |
| 8 | Social image export for Instagram and WhatsApp |
| 9 | Performance, accessibility, SEO and final checks |
| 10 | Launch content backlog |

---

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
- Independence: Chargeworthy is not a charge point operator. Data pages
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
- Outcome: log of monthly kWh per charger
- Features known for every charger, uploaded or not: AC/DC and power
  class, months since opening (spline or log), road class, distance to
  national highway, district EV registrations (log)
- Hierarchical (mixed) model with random intercepts for district and
  state, so small districts borrow strength from their state and
  region. Use statsmodels MixedLM or PyMC; keep the model behind a
  single interface so it can be replaced by the cluster model later.
- Predict every non-uploading charger in public_chargers from its
  features.
- District total for a month = sum of observed kWh for uploading
  chargers + sum of predicted kWh for the rest.
- Uncertainty: simulate from the fitted model (parametric bootstrap or
  posterior draws, at least 1,000) to produce P10, P50, P90 for each
  district total and per-charger average.
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
     validation results (pulled automatically from the latest run's
     summary: LOO error, interval coverage, number of stations)
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
5. Independence statement: Chargeworthy is not a charge point
   operator, holds no stake in any station, does not publish figures
   by operator, and earns fees from site assessments and operator
   matching. Keep it short and factual.
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
