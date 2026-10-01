# Public analytics: source acquisition checklist

Part 2 prepares the data contract; it does not manufacture missing observations.
Sources were checked on 2026-09-30, with acquisition on 2026-10-01 recorded in
[PART12_SOURCE_REVIEW.md](PART12_SOURCE_REVIEW.md). Portal availability can vary. Never record
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

## Expansion acquisition gates (Part 11)

Source-register review date: **2026-10-01**. This date is not a dataset retrieval
date or publication date. All expansion datasets remain inactive. Checkboxes
below track acquisition, not merely discovery of a website.

For each accepted source, archive original bytes outside the public tree under
`local_scratch/source_review/<id>/`, compute SHA256, and record actual retrieval,
publisher date (unknown if absent), represented period, edition, table/page,
units, definitions, licence evidence and human reviewer. Publish only reviewed
allowlisted observations in `data/public/<id>/data.csv` with `meta.json` through
the existing validator. Preserve the upstream licence; Chargeworthy's CC BY 4.0
text licence does not relicense third-party data. Public accessibility alone is
not commercial reuse permission. Reject HTML/error/login pages saved as PDFs.
Never use demo/sandbox records as live observations. Missing means null, not zero.

## DISCOM performance - PFC acquisition pending

Publisher: [PFC](https://www.pfcindia.co.in/). Target the latest three report
editions; the following 2024-25, 2023-24 and 2022-23 candidates were identified.
Recheck the publisher index for newer editions at acquisition; direct download
verification remains blocked (2024-25 returned HTML; 2022-23 fetch failed).

- [2024-25 report candidate](https://www.pfcindia.co.in/ensite/DocumentRepository/ckfinder/files/Operations/Performance_Reports_of_State_Power_Utilities/Report%20on%20Performance%20of%20Power%20Utilities%202024-25.pdf)
- [2023-24 report candidate](https://www.pfcindia.co.in/ensite/DocumentRepository/ckfinder/files/Operations/Performance_Reports_of_State_Power_Utilities/Report_on_Performance_of_Power_Utilities_2023-24.pdf)
- [2022-23 database candidate, updated through April 2024](https://pfcindia.com/ensite/DocumentRepository/ckfinder/files/Operations/Performance_Reports_of_State_Power_Utilities/Report%20Database%202022-23%20-%20updated%20up%20to%20April%202024EntityApr.pdf)

- [ ] Obtain genuine publisher PDFs for the newest three editions, archive and
  checksum them; record printed release dates and each represented fiscal year.
- [ ] Verify rights for publishing extracted observations; licence is pending,
  not assumed GODL, CC0 or Chargeworthy CC BY 4.0.
- [ ] Extract state, stable discom_id, published utility name, fiscal_year,
  atc_loss_pct, acs_arr_gap_paise_per_kwh (nullable integer), source_edition,
  source_table_ref and notes. Preserve cash/accrual and subsidy treatment,
  utility cohort and any restatement; do not splice incompatible series.
- [ ] Human-check every value against its table/page, and verify aliases and
  service-area evidence separately. Key: utility + year + definition/edition;
  select reviewed canonical observations without hiding revisions.
- [ ] Save `data/public/discom_performance/data.csv` and `meta.json`; validate
  AT&C 0-100, signed gap, integer paise and unresolved geography handling.

Do not infer site voltage, transformer capacity, outages, tariff, or charging
profitability from utility losses/gaps. Do not unweight-average utility metrics
into a state figure. A utility in a state is not proof it serves a selected pin.

## Supply hours - public annual candidate; NFMS export pending

Official entry points: [National Power Portal](https://npp.gov.in/),
[NPP sitemap](https://npp.gov.in/sitemap),
[NFMS](https://nfms.powermin.gov.in/) and
[CEA Distribution Monitoring](https://cea.nic.in/distribution-monitoring-division/?lang=en).
The NPP landing page's NFMS link handler explicitly targets the NFMS URL above;
the NFMS page was reachable, but a human-exportable public aggregate and its
reuse terms were not verified. Do not use authenticated endpoints or invent an
export URL. [NPP policy](https://npp.gov.in/help_policy) excludes third-party
material from its reproduction provision; it does not establish NFMS rights.

Public candidate: [CEA state-wise daily average supply for FY 2018-19 through
2023-24, attributed to NPP](https://cea.nic.in/wp-content/uploads/dm/2025/09/State_wise_Average_hours_of_Supply_in_a_day_HHhh_for_FY_2018_19_to_FY_2023_2024_as_per_NPP_Portal.pdf).
This one-page table distinguishes rural/urban 11 kV feeders and labels units
HH.hh, with values whose fractional part exceeds 59. Do not interpret them as
minutes; verify decimal-hour methodology before accepting conversions. The
2025/09 upload path is not the coverage date or a verified publication date.

- [ ] Archive/checksum the CEA file; visually check headers, blank cells and
  column alignment. Confirm units and how averages were calculated.
- [ ] Verify CEA/NPP reuse, including third-party rights, against
  [CEA policies](https://cea.nic.in/website-policies/?lang=en); licence pending.
- [ ] Inspect NFMS/NPP manually for publicly exportable aggregate tables. Record
  the exact export URL, definition, represented interval and reuse evidence if
  found; otherwise keep that acquisition pending without bypassing login.
- [ ] Preserve state, nullable discom_id and lgd_code, period_type, period_start,
  period_end, published_period_label, area_type, avg_supply_hours_per_day,
  supply_definition, source_name, source_url, retrieved_on and notes. Key includes
  actual geography, interval, area type and definition. Accept 0-24 hours/day.
- [ ] Save `data/public/supply_hours/data.csv` and `meta.json` after review.

Never downscale annual state data into months/districts or treat area averages
as feeder/site uptime. Do not infer outages as 24 minus published area supply.

## State EV policies - notifications identified, applicability pending

Starting sources:

- Kerala: [government order hosted by the National Single Window System](https://www.nsws.gov.in/s3fs/2022-12/pdf_Electric-Vehicle-policy_2%20%284%29_0.pdf),
  GO(Ms) No.24/2019/Trans, 10 March 2019. Distinguish approval from the 2018
  draft mentioned in [Invest Kerala's overview](https://invest.kerala.gov.in/doing-business-in-kerala/investment-avenue/electric-vehicles/).
- Tamil Nadu: [Guidance Tamil Nadu policy entry, 2023](https://investingintamilnadu.com/business-in-tamil-nadu/policy-notifications?policy=tn-electric-vehicles-policy-2023&tab=state-policies).
  Follow its original notification/download. Check subsequent orders against
  the [official 2025 Gazette index](https://www.stationeryprinting.tn.gov.in/extra_ordinary_lists.php?id=MjAyNQ%3D%3D),
  including the 29 December 2025 entry for GO Ms No.674, Home (Transport-I),
  notification II(2)/HO/1344(d)/2025; inspect the actual gazette before asserting
  any current tax benefit.
- Karnataka: [Clean Mobility Policy 2025-30](https://investkarnataka.co.in/wp-content/uploads/2025/12/Clean-mobility-policy.pdf),
  GO CI 117 SPI 2024(e), 11 February 2025. The order's date, not the upload
  folder, controls notification provenance; its five-year/new-policy condition
  requires checking supersession.
- Central: [MoRTH](https://morth.gov.in/), [official eGazette](https://egazette.gov.in/),
  [MHI PM E-DRIVE](https://pmedrive.heavyindustries.gov.in/) and its
  [press releases](https://pmedrive.heavyindustries.gov.in/press_release).
  Check operational/component guidelines and amendments, including the August
  2025 extension; an old homepage end date is not current eligibility evidence.

- [ ] Download original notified orders, amendments and applicable component
  guidelines; record page, checksum, issuing authority and notification date.
- [ ] Verify current validity, eligibility, geography, vehicle/charging scope,
  supersession and any budget/application conditions; unknown expiry is unknown.
- [ ] Verify reuse of notification text/extracts. No blanket licence confirmed.
- [ ] Preserve state (or central), policy_name, notification_ref, notified_on,
  valid_from, nullable valid_to, incentive_type, vehicle_scope, amount_text,
  source_url, recorded_on and notes; retain amendment and review provenance.
  Key: notification + clause/incentive + scope + validity, not state alone.
- [ ] Save `data/public/state_ev_policies/data.csv` and `meta.json`.
- [ ] Add the offline read-only comparison with `subsidy_rules` in Part 12;
  differences go to human review, never automatic writes or ROI inputs.

Do not call a draft notified policy, manufacturing/purchase incentives charging
grants, or a policy promise a customer's entitlement. LLM extraction proposals
need model/prompt_version stamps and human verification before acceptance.

## NHAI wayside amenities - historical directory reviewed

Sources: [NHAI WSA entry](https://nhai.gov.in/nhai/taxonomy/term/553) and
[NHAI WSA site directory](https://nhai.gov.in/nhai/sites/default/files/mix_file/NHAI_WSA_Site_Directory.pdf).
Downloaded into memory for verification on 2026-10-01: 3,946,448 bytes,
SHA256 `835b770c5f2fc3bf4a1b1aaa32c86838210093d8a8692def2f48761963592e0a`.
The PDF is 21 pages and contains a March 2021 bidding schedule. Printed
publication date was not verified: record unknown, not the download date.
No raw file or extracted dataset has been published in Part 11.

- [ ] Archive the actual PDF and recompute checksum; retain this reviewed digest
  as a comparison, not a guarantee that the mutable URL stays unchanged.
- [ ] Verify reuse permission for the directory; licence remains pending.
- [ ] Obtain dated current award/planning evidence before current-status claims.
- [ ] Human-transcribe wsa_id, nh_ref, state, nullable lgd_code and chainage_km,
  paired nullable lat/lon, status as printed, ev_charging_listed
  (true/false/unknown), nullable source_doc_date, source_page and notes.
  Preserve document checksum/source URL in metadata and per-status provenance.
- [ ] Review each row and charging flag; absence of a charging mention is unknown,
  not false. Key: site ID + source/status effective evidence, preserving history.
- [ ] Save `data/public/nhai_wayside_amenities/data.csv` and `meta.json`.

Do not geocode chainage, invent coordinates, imply every amenity has charging,
or treat planned/awarded sites as operational stations or gap-closing evidence.

## OSM power - active regional snapshot, district joins unresolved

Source: [Geofabrik India extracts](https://download.geofabrik.de/asia/india.html)
or the existing Overpass client in `app/domain/context/poi.py`. Licence:
[ODbL / OpenStreetMap attribution](https://www.openstreetmap.org/copyright).

- [x] Select a bounded extract/query; archive checksum, exact extract timestamp,
  query and transformation versions. Do not call today's date the extract date.
- [x] Extract `power=substation` and `power=transformer`; preserve osm_id with
  object type, kind, voltage as tagged (nullable), lat/lon, nullable lgd_code,
  extract_date and point_derivation. A representative point from a way/relation
  is derived geometry, not a surveyed equipment location.
- [ ] Review state/LGD joins against a dated reference, retaining unresolved
  joins. Key: OSM object type/ID + extract. Coordinates are EPSG:4326.
- [x] Save `data/public/osm_power/data.csv` and `meta.json`; attribute
  OpenStreetMap contributors and satisfy applicable derived-database obligations.
  Exclude usernames, user IDs and changeset metadata from public observations.
- [x] Document missing/uneven mapping coverage and query limits. Any metered
  provider still needs the existing quota and usage-event guarantees.

Mapped proximity proves neither available load, equipment health, voltage,
connection feasibility, ownership nor utility permission. Missing mapping is
not proof no transformer exists. Do not ship raw PBF files to the frontend.

## Toll plaza traffic - conditional, no licensed vehicle count verified

Review result on 2026-10-01: **no openly licensed per-plaza vehicle-count
resource verified in this review**. This is not a claim that none exists.
[NHAI plaza 417](https://tis.nhai.gov.in/TollInformation?TollPlazaID=417) and
[plaza 4588](https://tis.nhai.gov.in/TollInformation?TollPlazaID=4588) expose
dated Traffic (PCU/day), not raw vehicle counts; reuse was not confirmed.
The [OGD catalogue](https://data.gov.in/catalogs) did not yield a verified live
licensed per-plaza count in the review, and displayed a sandbox/demo warning.
Do not ingest those example records.

- [ ] Find a genuine live NHAI/OGD per-plaza resource; record exact dataset/export
  URL, plaza identifiers, method, observation date/interval and counting units.
- [ ] Verify the individual resource's licence, against
  [OGD terms](https://www.data.gov.in/terms-of-use) and
  [GODL](https://ap.data.gov.in/godl) where actually applicable. GODL does not
  automatically cover every NHAI webpage. Licence and acquisition stay pending.
- [ ] If accepted, define a separate reviewed schema for plaza_id, location,
  period bounds, traffic_value, traffic_unit, vehicle_class, method, source_url
  and notes; natural key includes period, class, unit and method.
- [ ] Only then save `data/public/toll_plaza_traffic/data.csv` and `meta.json`
  and activate validation/consumers. Otherwise keep the dataset absent/inactive.

Fees, toll revenue, FASTag transaction counts and PCU/day are not interchangeable
with vehicles/day. Do not relabel PCU as vehicles or ADT as AADT without the
published method. Historical observations and future target traffic are never
current measured counts. Toll traffic is optional; the other five contracts
can progress independently.
