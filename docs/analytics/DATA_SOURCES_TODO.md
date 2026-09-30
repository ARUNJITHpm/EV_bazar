# Public analytics: source acquisition checklist

Part 2 prepares the data contract; it does not manufacture missing observations.
Sources were checked on 2026-09-30. Portal availability can vary. Never record
that date as a dataset's retrieval date unless the actual dataset was retrieved.

## How to add a dataset

1. Keep the original download and a checksum outside `data/public/`. Preserve
   the publisher's reporting period, geography, definitions and reuse terms.
2. Populate `data/public/<dataset_id>/data.csv` (or the geometry filename below)
   using the provided `data.template.csv` header. Empty optional cells mean
   unknown, never zero. No thousands separators in numeric CSV cells.
3. Complete `meta.template.json`, then save it as `meta.json`. Replace every
   placeholder. Required fields: `id`, `title`, `description`, `source_name`,
   `source_url`, `retrieved_on` (YYYY-MM-DD), `licence`, `geography_level`,
   `time_coverage`, `update_frequency`, `notes`, and `columns` with name, type,
   unit and description. Geometry also requires `attribution`; OSM highways
   retain ODbL. Do not set `fixture: true` on real public data.
4. Record gaps and allocation assumptions in `notes`. Keep licences per source;
   do not label third-party data CC BY 4.0 merely because our articles use it.
5. Run `npm run data:validate --prefix frontend`, then the frontend tests/build.
   The build refuses incomplete active datasets, unknown columns/codes,
   malformed types/dates, duplicate observations and fixture markers.
6. Review the diff before publishing. Only validated files are emitted to
   `frontend/dist/analytics-data/`; each has source metadata, checksum, version
   stamps and a licence README. Templates do not enter the production output.

There is no automatic scraper or paid provider in this pipeline. Build-time
validation reads only the public allowlist; the owner database and raw inventory
are never sources for this part. Restart Vite after changing source files so its
validated catalogue reflects the new snapshot.

## District reference — available as an archived snapshot

- [x] Exported 783 LGD-coded district names from the checksum-verified existing
  `data/reference/districts.parquet`. Two records without valid codes were
  omitted. This is a historical reference, not current exhaustive coverage.
- [x] Saved `data/public/district_reference/data.csv` and `meta.json` with the
  original retrieval date, 2026-08-12, and source checksum.
- [ ] Refresh and reconcile names/splits against the official
  [LGD district directory](https://lgdirectory.gov.in/) or
  [LGD districts on data.gov.in](https://data.gov.in/resource/local-government-directory-lgd-districts).
- [ ] Review former names; store verified aliases as a JSON array in the
  `former_names` CSV cell. Do not infer aliases or silently map split districts.

Fields: `lgd_code`, `district_name`, `state_name`, `slug`, `former_names`.
Keep LGD codes stable; existing slugs use the district name plus code to avoid
duplicate names. Data-source state labels must match the reference exactly.
On refresh, retain an existing slug for the same LGD code; record a renamed
district in its name and verified aliases rather than breaking published URLs.

Original snapshot:
[LGD release file](https://github.com/yashveeeeeeer/india-geodata/releases/download/admin/districts/LGD_Districts.parquet).
The publisher identifies release files as CC0 in its
[district README](https://github.com/yashveeeeeeer/india-geodata/blob/main/data/administrative/districts/README.md).
`scripts/export_public_districts.py` reproduces the export from the archived
source and refuses to overwrite an existing public reference.

## RTO-to-district mapping — pending human jurisdiction review

- [ ] Consult the official state transport department's RTO jurisdiction list,
  using the RTO names/codes shown by the
  [MoRTH VAHAN dashboard](https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml).
- [ ] Record the exact official jurisdiction document URL and its vintage in
  metadata. An office's coordinates establish where the office is, not the
  districts covered by that office.
- [ ] Save `data/public/rto_to_district/data.csv` and `meta.json`.

Fields: `state`, `rto_code` (normalised, for example KL01), `lgd_code`,
`covers_multiple_districts` (literal true/false), `allocation_note`.
Multiple rows may map an RTO to different districts, but all must flag the
overlap. A flagged RTO requires a note. Do not copy its whole registration count
to every district. Obtain district-resolved counts or document a defensible
allocation; if neither exists, withhold district registration totals.

## EV registrations — monthly observations pending

- [ ] Download/export month-by-month electric registrations from the official
  [VAHAN report dashboard](https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml).
  The [MoRTH public analytics dashboard](https://www.analytics.parivahan.gov.in/analytics/publicdashboard/vahan?lang=en)
  is an alternative official entry point; verify the export's available axes.
- [ ] Confirm reuse terms, reporting coverage and whether the selected RTOs
  supply actual monthly counts. Do not divide annual or cumulative totals into
  imaginary months. Existing `data/vahan/` yearly files cannot fill this contract.
- [ ] Review a mutually exclusive class mapping: 2W, 3W, 4W, bus, goods. Record
  how commercial three-wheelers are assigned so they are not counted twice.
- [ ] Resolve RTO jurisdictions using the mapping above.
- [ ] Save `data/public/ev_registrations/data.csv` and `meta.json`.

Fields: `month` (YYYY-MM), `state`, `rto_code`, `lgd_code`, `vehicle_class`,
`fuel` (ELECTRIC(BOV) or PURE EV), `count` (non-negative integer).
Do not treat missing RTO/month/class records as verified zero registrations.
One row per month/state/RTO/district/class/fuel; duplicates fail validation.
For multi-district RTOs, metadata must explain allocation and its uncertainty.

## Public chargers — curated list pending

- [ ] Start from BEE's published listings on its
  [electric mobility page](https://www.beeindia.gov.in/show_content.php?lang=1&level=2&lid=67&ls_id=345)
  and the [EV Yatra portal](https://evyatra.beeindia.gov.in/).
  Confirm the exact list's vintage and reuse permission before transcription.
- [ ] Curate public-access chargers manually; cite the specific published list
  supporting each row. No app scraping or operator-wise statistics.
- [ ] Verify coordinates, connector specifications and opening month; leave
  unknown opening months blank. Review physical duplicates across lists.
- [ ] Define one `charger_id` per physical charging device. Multiple connectors
  do not automatically mean multiple devices. Record the counting definition
  in metadata before publishing station/charger/connector ratios.
- [ ] Save `data/public/public_chargers/data.csv` and `meta.json`.

Fields: `charger_id`, `name`, `lat`, `lon`, `lgd_code`, `road_class`,
`connector_type`, `power_kw`, `ac_or_dc`, `opened_month`, `source_name`,
`source_url`, `recorded_on`. Coordinates are EPSG:4326 longitude/latitude.
`road_class`: national_highway, state_highway, urban, rural or unknown.
Do not export scraped `competitor_stations`, per-CPO inventory CSVs or owner
station IDs. This public source ID is independent of private owner identifiers.

## EV tariffs — primary orders pending verification

- [ ] Retrieve orders from the relevant state regulator. First sources:
  [KSERC](https://erckerala.org/) and
  [TNERC](https://www.tnerc.tn.gov.in/).
- [ ] For Kerala, the repo's existing source points to this
  [KSERC schedule](https://dev.erckerala.org/api/storage/orders/vnp1XnN5z47r0dCh18rj3s2e1q2utii3T8AtwUMm.pdf).
  Check effective dates and subsequent orders before transcribing public rates.
- [ ] For Tamil Nadu, obtain the actual order, not the news article used in the
  older seed. Check charge basis and all time-band edges against the order.
- [ ] Record DISCOM, category, effective date, order reference and whether the
  figure includes duty, surcharge or tax. No current-rate claim from an old order.
- [ ] Save `data/public/ev_tariffs/data.csv` and `meta.json`.

Fields: `state`, `discom`, `tariff_order_ref`, `effective_from`, `category`,
`energy_charge_paise_per_kwh`, `demand_or_fixed_charge_paise`, `unit`,
`tod_rules`, `notes`. Money stays in integer paise; this deliberately adapts the
brief's unspecified currency columns to AGENTS.md. Convert only for display
with `lib/money.ts`.

`unit`: per_kva_month, per_kw_month, per_connection_month, none or unknown.
Verified nil fixed charge: amount 0, unit none. Missing charge: blank amount,
unit unknown; do not replace it with 0. Keep kW and kVA distinct.
Source-derived values stay observations; no model computes a tariff or saving.

## District boundaries — TopoJSON pending

- [ ] Fetch the openly licensed gbOpen India ADM2 record from the
  [geoBoundaries API](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/).
  Its [API documentation](https://www.geoboundaries.org/api.html) explains the
  download and source-licence fields. Save the actual returned licence,
  attribution, represented year and source details.
- [ ] Download its TopoJSON via the record's `tjDownloadURL`, simplify for web
  display if needed, and record the simplification tolerance. Do not use a
  non-commercial gbAuthoritative release by accident.
- [ ] Build and review an explicit boundary-to-LGD crosswalk; names and years
  may differ from the district reference. No fuzzy join without verification.
- [ ] Save `data/public/district_boundaries/data.topojson` and `meta.json`.

Contract: Topology; `objects.districts` is a GeometryCollection of Polygon or
MultiPolygon; each feature has only `properties.lgd_code` (integer). Topology
arcs may be unquantized EPSG:4326 coordinates or quantized integer deltas with
`transform`. Metadata columns: lgd_code (integer), geometry (json, EPSG:4326).
Validation checks coordinate bounds, ring connections/closure, arc references,
duplicate district codes and the LGD join. Review full geographic correctness
and disputed-boundary presentation separately before Part 4 publishes a map.

## Highways — OSM linework pending

- [ ] Obtain an extract from
  [Geofabrik's India download page](https://download.geofabrik.de/asia/india.html).
  Choose a manageable regional extract or process the national PBF offline;
  do not ship the raw PBF to the browser.
- [ ] Extract verified national highway ways and preserve their NH reference.
  A motorway classification alone does not prove a national-highway designation.
- [ ] Save `data/public/highways/data.geojson` and `meta.json`.

Contract: FeatureCollection; LineString or MultiLineString in EPSG:4326.
Allowlisted properties: osm_id (string), ref (NH followed by its number),
road_class (national_highway). Metadata also describes geometry (json).
Omit OSM user IDs, usernames and changeset metadata.

- [ ] Preserve attribution to OpenStreetMap contributors, licence ODbL-1.0,
  extract vintage and any derived-database obligations. See
  [OpenStreetMap's copyright and licence page](https://www.openstreetmap.org/copyright).
- [ ] Review completeness, divided carriageways and station access before
  asserting corridor gaps. Linework is inventory, not measured traffic.

## Fixtures and development preview

All seven schemas have deliberately invented files under `data/fixtures/`.
Their metadata declares `fixture: true`, station/district names begin with Test,
and source URLs use example.invalid. They are test inputs, never public data.

Run Vite development mode and open `/data?fixtures=1` to see a visible **Test
data** banner and the fixture station. Production builds neither read nor emit
the fixture tree; the same query cannot enable it in production. The fixture
gate is independent of other development flags. Do not copy these fixtures into
`frontend/public/`.

`node frontend/scripts/scaffold-public-data.ts` can recreate missing templates
and fixtures without overwriting existing files. Leave template retrieval dates,
source URLs and licences unset until actual acquisition; partial templates never
satisfy the active-dataset validation contract.

After a clean frontend build, run `npm run data:check-build --prefix frontend`
with no concurrent build. It temporarily breaks one reference CSV cell, proves
the actual build refuses it, restores the original bytes in a finally block,
and scans production artifacts for the fixture observations.
