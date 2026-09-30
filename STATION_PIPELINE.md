# Station inventory pipeline

Run the refresh to collect station locations, identify the operating CPO, and
resolve state/district from the project's LGD district polygons. This is station
inventory, not charger status (status scraping is a deferred later stage).

```powershell
uv run python -m scripts.refresh_stations
uv run python -m scripts.refresh_stations --states kerala tamilnadu karnataka
uv run python -m scripts.refresh_stations --sources goec zeon
```

Default: Kerala, Tamil Nadu, Karnataka, Maharashtra, Gujarat, **Delhi UT**.
The overview says Delhi-NCR but the repo has no agreed NCR district boundary.
Do not silently include all Haryana and Uttar Pradesh or claim Delhi is all NCR.
OCM requires the existing free `OPEN_CHARGE_MAP__API_KEY`; GoEC and Zeon do not.
PostgreSQL/PostGIS and loaded district polygons are required for resolution and
exports. No paid API is called. The default only reads the database.

Use `--write` to update the existing `competitor_stations` inventory cache after
reviewing the exports. No event table, site, prediction, or tariff is changed.
The full six-target refresh was explicitly requested and committed on
2026-09-30; details and gaps are recorded below.
Each refresh is a separate process; it need not run in the web request lifecycle.
The HF deployment now has `workers.data_refresh`, a separate worker which runs
the three reliable feeds **weekly, Sunday 03:00 IST**, with `--write`. It checks
the current due week on boot and every minute, so a restart/late wake-up catches
up once. Postgres advisory locks prevent concurrent runs; durable outcomes
prevent a successful week being scraped again after a restart. Failed runs retry
after an hour, at most three attempts per period.

`data_refresh_events` (migration 0019) retains append-only start/end outcomes and
the complete compressed ZIP of each attempt's raw responses, exports, manifest
and log. These survive HF's temporary disk being cleared. Local temporary files
are removed only after the archive is committed. No new paid provider is used.

The prepared `.github/workflows/wake-data-refresh.yml` wakes the existing HF Space weekly with
its public health endpoint. This is needed because CPU Basic sleeps when idle;
a timer inside a sleeping container cannot run. GitHub's scheduled workflow may
run late; the durable due-week check handles that. An HTTP 200 means the app is
awake, not that the scrape succeeded: check `data_refresh_events` for outcomes.

Set `STATION_REFRESH_ENABLED=false` on the Space to disable the worker. Keep
`OPEN_CHARGE_MAP__API_KEY` as a Space secret; never put it in the workflow YAML.
Turning off this weekly inventory worker is separate from `SCRAPER_ENABLED`,
which gates five-minute live availability polling.

The wake-up workflow is saved locally but is not yet published: GitHub rejected
the workflow push because the current OAuth login lacks `workflow` scope. Until
that access is restored, due jobs run whenever the Space is awake, but a weekly
wake-up is not guaranteed.

### VAHAN on the server

The Docker image installs the locked `scrape` extra. Set `VAHAN_HEADLESS=true`
for browserless operation; on Linux it reuses the report renderer's pinned
Playwright Chromium and detects its major version for the matching driver.
Driver binaries are downloaded by the existing browser library, requiring
outbound HTTPS. Test after Chromium/library upgrades; the driver itself is not
an archived report renderer and is not used for financial arithmetic.

`VAHAN_SERVER_SMOKE=true` runs a one-RTO, 2025-year test and archives its CSV/log;
it does not ingest smoke data. Zero/marker-only output is a failure. Automatic
monthly ingest stays off unless `VAHAN_SERVER_ENABLED=true`, **and** the server
has a successful smoke result. Monthly due time is day 1, 04:00 IST; if the Space
is asleep it catches up next time it wakes. The existing RTO seed only covers
Kerala/Tamil Nadu, not all six station targets. VAHAN is browser-driven and much
longer than the JSON station refresh. A CAPTCHA/site block needs human review;
no successful smoke or monthly scrape is claimed until a real positive CSV
exists. Monthly runs are capped at four hours and retain their archive on error.

## What a run leaves

`data/station_inventory/<UTC timestamp>-<run id>/` contains:

- `raw/`: response bytes, SHA-256, timestamp, source, URL without query strings,
  HTTP status and version stamps. Captured before parsers use a response. Failed
  requests retain their attempt record. Headers/keys are not saved in metadata.
- `stations.json` and `stations.csv`: source IDs, raw/canonical CPO names,
  latitude/longitude, state/district names, LGD codes, boundary vintage,
  resolution, source timestamp, fetch timestamp, and freshness.
- `by_state/` and `by_cpo/`: separate CSVs for each observed state and canonical
  CPO; unresolved operators and geography get their own review files.
- `manifest.json`: source failures, request count, database outcome and a
  state-by-CPO coverage matrix for every canonical CPO in `identity.py`.

The capture folders are ignored by git. Retain/back up them to preserve history;
the database cache alone does not preserve earlier inventory versions. Response
bodies may contain provider-supplied information; review before sharing externally.
No export is sent to a CPO automatically.

`fetched_at` means we read a source, not that anyone recently verified a charger.
Unknown source dates stay `unknown`; older than `--stale-days` (default 30) is
`stale`. A recent source status update is not proof of fresh coordinates or of
live operation. Source timestamps in the future are flagged. Missing entries
never mean a station is closed. Retain failed/closed listings as evidence.

Bounding boxes discover candidates; district polygons decide state membership.
Out-of-state candidates are excluded. Unplaced and multiply-contained points
remain in the export with NULL geography for review and are excluded from writes.
Each source's station identity is retained. CSV counts and the coverage matrix
are **source records**, not cross-source deduplicated physical station counts;
existing CPO presence logic folds overlap separately.

The default request budget is 100, with at least one second between calls.
`--max-requests` caps all attempts, including redirects. No automatic retries.
If an OCM tile returns 500 records, that entire source refresh is refused instead
of claiming complete coverage. Rerun with `--grid 5 --max-requests 200` if needed;
use a smaller state batch to stay within the provider's acceptable rate.
Exit 2 means a source is blocked/failed or resolution/storage failed. Other
successful sources can still produce exports. Check the manifest rather than
treating any CSV as proof of complete coverage. The manifest currently identifies
failure types; consult archived HTTP status/body for diagnosis.

## Occasional CPO exports

An export shared by your former CPO team can be ingested without treating it as
current. Supply a CSV in this format (all other metadata is optional):

```csv
source_id,latitude,longitude,operator,name,source_last_status_update
station-123,9.9312,76.2673,chargeMOD,Kochi hub,2026-08-01T00:00:00+05:30
```

```powershell
uv run python -m scripts.refresh_stations --sources --csv chargemod data/chargemod.csv
```

Use the source's stable ID, not a spreadsheet row number. Dates must include
timezone. Omit dates if unknown. Keep coordinates in EPSG:4326 decimal degrees.
Input bytes are archived before parsing. Invalid coordinates, missing IDs and
timezone-less dates refuse that input. Provider state/district text remains in
the raw CSV; it is not authoritative geography. Unknown operator names remain
unresolved for review. Do not rename an aggregator's roaming stations to the
aggregator: the CPO is whoever operates that station.

## Source research — checked 2026-09-30

Recommended evidence order is a project decision: verified first-party station
records first; government and open datasets widen coverage; aggregators provide
additional independent sightings. Compare source dates/conflicts rather than
letting a newly downloaded old list overwrite evidence of closure.

| Source | Useful evidence and access | Implementation / limits |
|---|---|---|
| GoEC | [Official network map](https://www.goecworld.com/network); existing public JSON feed | Live refresh succeeded 2026-09-30. Adapter wired. Connector rows grouped into stations. No source verification timestamp or live status assumed. |
| Zeon | [Official app/network](https://zeoncharging.com/mobile_app); existing public JSON feed | Live refresh succeeded 2026-09-30. Adapter wired. Station IDs and connectors. No live status assumed. |
| Open Charge Map | [Official API](https://openchargemap.org/site/develop/api), free application key; [official export repository](https://github.com/openchargemap/ocm-export) | Adapter wired, broader CPO inventory. Provider licenses vary: keep attribution and inspect `DataProvider` licensing; do not assume one uniform license. No proof of exhaustive coverage or live status. |
| BEE / EV Yatra | [Official station-list page](https://beeindia.gov.in/show_content.php?lang=1&level=2&lid=67&ls_id=345) lists data through 26 October 2025 | Good baseline and missing-CPO discovery, explicitly old vintage. No bulk parser or public API verified here. CPO-supplied registry data can lag. |
| PlugShare | [Commercial data API](https://help.plugshare.com/hc/en-us/articles/4418950880659-PlugShare-Charging-Stations-API-Documentation-Access), [business data](https://company.plugshare.com/business.html) | Commercial license required. Not wired; no unofficial endpoint replay. Your experience of occasional CPO uploads reinforces retaining provider vintages rather than assuming freshness. |
| OpenStreetMap | [`amenity=charging_station`](https://wiki.openstreetmap.org/wiki/Charging_station), tagged operator/network and coordinates | Optional adapter now wired (`--sources osm`). Nodes, ways and relations retain their source IDs; feature overlap is not physical-station dedupe. ODbL attribution preserved; edit dates are not treated as verification. Primary live fetch returned HTTP 406; public Private.coffee probe timed out. No OSM stations committed in this run. |
| Delhi OpenEV | [Official documentation](https://openev.delhitransport.in/documentation/) | Useful Delhi lead. Search indexed documentation; direct page fetch failed in this check. Endpoint/auth/live response not verified; not wired. |
| e-AMRIT / NITI | [Public JSON station feed](https://e-amrit.niti.gov.in/getChargingStation) | Newly found public JSON, with `stationid`, `lattitude` (source spelling), `longitude`. Source dates absent and some names/addresses/coordinates contradict each other. Review-only candidate; not enabled as authoritative inventory. |
| Pulse Energy | [Official charging API offering](https://pulseenergy.io/ev-charging-api), [charging map](https://fleet.pulseenergy.io/charging-network-map) | Promising multi-CPO integration; request API access. Landing page is not a public bulk API contract. Not wired. |
| Electromaps | [Official service](https://www.electromaps.com/) | Additional aggregator candidate. India coverage and reusable bulk access still need verification; not wired. |

### Per-CPO route register

For every CPO below, OCM/BEE can supply baseline listings where they exist, and
the saved CSV route works now. Those routes do **not** imply coverage of all
stations. A website describing an app does not establish an open bulk API.

| CPO | First-party candidate | Direct automation state |
|---|---|---|
| chargeMOD | [Official website/app](https://www.chargemod.com/), [new web presence](https://web.chargemod.com/) | Saved export supported. Status polling is deferred; no endpoint is configured or authorised. Ownership/ongoing access must not be inferred from the historical repo affiliation. |
| Tata Power | [EZ Charge map](https://ezcharge.tatapower.com/evselfcare/) | Existing status adapter, previously captured, not newly verified. Registry remains disabled. No embedded app credential extracted/replayed. |
| Statiq | [Official app](https://www.statiq.in/) | Website describes live status in-app; public bulk access unverified. Saved export/authorised endpoint needed. |
| ChargeZone | [Official app](https://chargezone.co.in/app-download) | App discovery confirmed by official site; bulk feed unverified. |
| Kazam | [Official platform](https://kazam.energy/) | CMS/platform can serve many operators. Preserve actual CPO identity; request partner access. |
| Ather Grid | [Official locator](https://www.atherenergy.com/charging), [published station list](https://assets.atherenergy.com/grid_charging_stations.pdf) | PDF/address inventory candidate. Coordinates/date still need extraction/validation; do not confuse scooter charging with CCS car charging. |
| Jio-bp | [Official locator](https://www.jiobp.com/locate-fuel-station), [pulse app](https://www.jiobp.com/products-and-services/EV-charging) | Locator includes fuel/CNG as well; only explicit EV stations qualify. Bulk JSON not verified. |
| Relux | [Official website](https://reluxelectric.com/) | Saved export or verified locator feed needed. Announced future stations are not installed stations. |
| Bolt.Earth | [Official charger map](https://bolt.earth/ev-charger-near-me) | JavaScript map confirmed; bulk access/response unverified. Preserve private/shared-access flags. |
| Glida | [Official locations](https://www.glida.in/locations/) | First-party source candidate; direct parser not built. Existing Fortum aliases map to Glida. |
| Shell Recharge | [Official India charging page](https://www.shell.in/shell-recharge.html) | India-only station feed remains unverified; do not use global Shell data as India coverage. |
| ElectricPe | [Official app](https://www.electricpe.com/app) | Aggregator candidate; do not attribute every roaming charger to ElectricPe. |
| GO EC, Zeon | Direct public feeds above | Wired and live refreshed. |
| Pulse Energy | Partner API above | Access/coverage validation pending. |
| EESL | [Government locator](https://e-amrit.niti.gov.in/charging-map) | JSON lead above, but conflicting labels and unknown source dates require review. |
| Rebolt | [Official network/app](https://www.reboltnetwork.com/) | App discovery documented; no reusable bulk endpoint verified. |
| Adani | [Official EV business announcement](https://www.adanigas.com/newsroom/media-release/ATGL-forays-into-electric-mobility-infrastructure-sector) | Existence confirmed; first-party station feed still unverified. |
| Charge_iN | [Mahindra locator](https://charginghub.mahindra.com/ChargingStations/), [2026 network update](https://www.mahindra.com/news-room/press-release/en/charge-in-by-mahindra-expands-to-50-charging-stations) | Existing aggregator listings must distinguish Mahindra-operated sites from other networks. No bulk adapter verified. |
| Wheels Drive | [Official site terms](https://wheelsdrive.com/terms-conditions/) | Charging business reference found, current station feed/ownership needs review. |
| Hydra Charging | [Official FAQ/app](https://hydracharging.in/faq.html) | App/PlugShare discovery documented. No bulk endpoint verified. |
| Midgard Electric | [Government startup profile](https://dst.gov.in/sites/default/files/75-Promising-Startups-NIDHI-Seed-Support-Program.pdf) | Historical existence only; current first-party source remains unresolved. OCM/CSV evidence kept. |

Commercial sources remain unimplemented until credentials, storage rights and
the project's provider-console quota + client metering are configured. The
existing polling authorisation registry is not modified by inventory work.

### Delhi-NCR extension

`--states delhincr` is available only when the official boundary service returns
all four valid subregion geometries. It preserves each station's real state and
district and labels its target region `delhi-ncr`. The default remains Delhi UT.
The [NCRPB constituent list](https://ncrpb.nic.in/ncrconstituent.html) confirms
that NCR extends beyond Delhi. The [government GIS service](https://bharatnetprogress.nic.in/nicclouddb/rest/services/NCR/NCR_Geo_Portal_23_01_2025/MapServer)
timed out from this machine, so the extension was not enabled in the saved run.
The code refuses an NCR run when its official polygon is unavailable; it never
substitutes all Haryana/UP/Rajasthan or guesses changed district boundaries.

For an OSM-only attempt on the documented public mirror:

```powershell
uv run python -m scripts.refresh_stations --sources osm --osm-server private-coffee --write
```

See [public Overpass instances](https://wiki.openstreetmap.org/wiki/Overpass_API)
for server policies. The established three feeds remain the reliable default;
an optional source failure is recorded and never fabricated as coverage.

## Verification

Pipeline tests cover refusal at the request cap, raw capture on HTTP and
transport errors, secret-safe error summaries, CSV coordinate/timestamp checks,
source isolation, ambiguous geography, selected-state filtering, and stale/NULL
source dates. Existing OCM/GoEC/Zeon parser tests are run with them.

```powershell
uv run pytest tests/test_station_pipeline.py tests/test_competitors.py tests/test_competitors_inventory.py
uv run ruff check app/domain/context/station_pipeline.py scripts/refresh_stations.py tests/test_station_pipeline.py
```

Keep the old import command for compatibility. Prefer this refresh when you need
source captures, explicit state filtering, and a per-CPO coverage audit.

### Live read-only run results — 2026-09-30

Both runs succeeded; database writes were disabled. OCM parsed 2,591 candidates
from discovery boxes, then excluded resolved stations outside selected states.
GoEC parsed 251 stations and Zeon 494 before the same geographic filtering.

| Resolved state | OCM source records | GoEC + Zeon source records |
|---|---:|---:|
| Kerala | 601 | 314 |
| Tamil Nadu | 230 | 259 |
| Karnataka | 386 | 93 |
| Maharashtra | 88 | 24 |
| Gujarat | 71 | 0 |
| Delhi UT | 34 | 1 |
| Unplaced / needs review | 1 | 1 |
| Total exported | 1,411 | 692 |

The 2,103 combined records overlap across sources and are not a unique station
count. The zero for GoEC/Zeon in Gujarat says what these captures observed, not
that Gujarat lacks stations. Archives:

- `data/station_inventory/20260930T093913Z-b99c5531/`
- `data/station_inventory/20260930T094040Z-7c65a568/`

### Full configured-target refresh saved — 2026-09-30

Command executed:

```powershell
uv run python -m scripts.refresh_stations --states kerala tamilnadu karnataka maharashtra gujarat delhi --sources ocm goec zeon osm --write
```

Run archive: `data/station_inventory/20260930T095820Z-07fbc1ad/`.
All OCM/GoEC/Zeon captures succeeded. **2,101 resolved source records were
upserted into `competitor_stations` in one transaction**; all 2,103 records were
exported, including two geography review records. No missing station was deleted.
OSM failed with HTTP 406 and was excluded; the manifest reports the source failure
even though successful sources were committed. The public mirror probe then
timed out. There is no claim of exhaustive physical-station or per-CPO coverage.

| Configured target | Resolved source records saved |
|---|---:|
| Kerala | 915 |
| Tamil Nadu | 489 |
| Karnataka | 479 |
| Maharashtra | 112 |
| Gujarat | 71 |
| Delhi UT | 35 |

The strategy is this document, linked from `CPO_SOURCES.md`. Raw archives and
exports live under `data/station_inventory/`; the inventory cache is in the
database. Individual CPO direct-feed gaps remain in the route register above.

### HF execution verified — 2026-09-30



HF CPU Basic ran the weekly worker in 68 seconds. OCM/GoEC/Zeon all succeeded;

2,101 resolved source records were committed, two held for geography review.

The 1,238,851-byte ZIP is persisted in `data_refresh_events` and downloaded to

`data/server_refresh/2-stations_weekly.zip`; its SHA256 was verified.



The first VAHAN test started Chromium but timed out navigating the government

dashboard after 120 seconds, before extracting any rows. Its failure archive is

`data/server_refresh/4-vahan_smoke.zip`. The adapter now waits for the initial DOM

rather than all page assets, bounds navigation at 60 seconds, and closes the

browser if startup fails. `VAHAN_SERVER_SMOKE_REVISION` permits an explicit

retest of a changed adapter within the same month. Full ingest remains disabled.

