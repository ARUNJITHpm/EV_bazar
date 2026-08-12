# CPO Data Sources — how to get availability from each network

Research notes for PLAN 0.1. **Verify every endpoint against a live capture before
wiring it** — app APIs are private and change without notice. Nothing here is a
committed integration; it is the map for the reverse-engineering evening.

> **Governance reminder.** This matches `app/domain/polling/sources.py`: a source is
> polled only after its terms are read, recorded, and `authorised` is flipped by a
> human, *and* an endpoint is configured. Prefer the legitimate paths below —
> scraping a consumer app is the last resort, not the first.

---

## Starting-stage strategy — DECIDED: scrape everything first, including chargeMOD

The dataset cannot be backfilled, so the starting stage optimises for **one uniform
mechanism we can stand up today**, not for the cleanest long-term integration. That
means: **scrape every network first — chargeMOD included — and treat OCPI/UEI as a
later upgrade phase**, switched in per source as partnerships land.

Why scrape-first now (even for our own network): one code path (`ScrapeAdapter`),
zero waiting on anyone's credentials or conversations, and every day of polling is a
day that can never be re-acquired. chargeMOD is scraped like the rest at this stage
purely so the whole fleet comes up together on the same mechanism; we swap it to a
direct internal feed later, when the OCPI phase begins.

There are **four ways** to get availability. We use #4 now for everything; #1–#3 are
the later upgrade, not the starting point:

| Path | What it is | Phase |
|---|---|---|
| **4. App scrape** *(NOW)* | Capture the app's JSON endpoint; generic `ScrapeAdapter` | **Starting stage — all sources, incl. chargeMOD** |
| **2. OCPI partner tokens** | Each CPO issues a token; `GET /locations` gives EVSE status | Later upgrade, per source |
| **1. UEI / Unified Bharat e-Charge** | National Beckn layer; one gateway to all onboarded CPOs | Later upgrade |
| **3. Public / commercial APIs** | Open Charge Map (free), TomTom (paid), gov open-data | Later / supplementary |

When we upgrade a source from scrape to OCPI, the `source` column already records
which rows came from which, so scraped history stays and the official feed simply
takes over from that date. Nothing is lost in the switch.

> **The later upgrade is real, just not now.** OCPI/UEI are worth it eventually —
> Kazam runs an OCPI platform and courts integrators, UEI already has ~5,386 points
> (Pulse Energy, Kazam, ChargeZone onboarded), and chargeMOD is ours to feed directly.
> All of that is a Phase-2 conversation; it does not gate starting to collect.

---

## Per-network notes

### chargeMOD *(ours)*
- **Starting stage:** scrape the app like every other source, so the whole fleet comes
  up on one mechanism. Being our own network, there is no ToS question — authorise it
  and go.
- App id: `com.bpm.chargemod`. Supports OCPP + OCPI; roams with Tata, Shell, Kazam.
- **Later upgrade:** swap to the direct internal API / DB (and/or OCPI) when Phase 2
  begins. Our sessions data is also demand-model ground truth.

### Kazam
- **Best path:** ask for OCPI / developer API — they run an OCPI platform and court
  integrators. Fastest legitimate yes.
- App id: `com.kazam.ev`. Real-time status. On UEI.
- **Action:** request OCPI credentials (path 2) or join their integration programme.

### ChargeZone
- **Best path:** OCPI (ask) or UEI (already onboarded).
- App id: `com.chargezone`. App shows real-time availability + reservations.
- **Fallback:** capture app JSON. Note it also surfaces inside aggregator apps (below).

### Statiq
- **Best path:** ask (contact `support@statiq.in`); runs a CSMS with real-time uptime.
  No public API docs found.
- App id: `com.statiq`. 10,000+ stations, real-time status, 7-day reservations.
- **Fallback:** capture app JSON, or read via an aggregator.

### Tata Power EZ Charge
- **Best path:** OCPI roaming (confirmed reachable via chargeMOD's OCPI links).
- App ids: `com.tatapower.evapp` (driver), `com.tatapower.ez_charge_partner` (partner).
  Real-time monitoring in-app.
- **Fallback:** capture app JSON.

### Ather Grid
- **Best path:** Ather **partnered with Google Maps** to publish live availability —
  so status is visible via Google Maps/Places for Ather sites (mind Google ToS).
- App id: `com.atherenergy.aegridapp`. Live status, 80+ cities (mostly 2-wheeler DC).
- **Fallback:** capture app JSON.

### Jio-bp pulse
- **Best path:** OCPI (ask) or aggregator. 5,000+ points, ~95% fast DC.
- App/site: jiobp.com; real-time availability in-app. Appears in aggregator apps.
- **Fallback:** capture app JSON.

### Aggregators — one capture, many networks
- **1C / "Massive Charging"** (`in.one.charging`) displays live chargers from
  ChargeZone, Statiq, Tata Power EZ and Jio-bp Pulse **together**. Capturing one
  aggregator can yield several networks at once — efficient, but check *its* ToS, and
  note it may not label which CPO each charger belongs to.
- **Electromaps**, **Statiq's public map** (lists chargeMOD etc.) — web maps with
  station lists; lighter on live status.

### PlugShare
- **No free path.** Commercial license only (`api.plugshare.com`); personal/scraping
  use is not permitted. Request via developer.plugshare.com if the budget justifies it.
  Third-party scrapers (Apify) exist but sit against PlugShare's ToS — avoid.

---

## Public / commercial APIs (documented, no scraping)

- **Open Charge Map** — free, documented REST: `GET /api/v3/poi?output=json&latitude=..&longitude=..&distance=..&maxresults=..` with a free key (openchargemap.org → My Apps → Register an Application). Crowd-sourced; strong on **locations**, weak on live status. Good for backfilling the station master list and cross-checking dedupe.
- **TomTom EV Charging Stations Availability API** — commercial, aggregated **real-time** availability. A paid but clean real-time source if the metering budget allows (goes through the paid-provider cap machinery in `config.py`).
- **Delhi OpenEV API** (`ev.delhi.gov.in/openev/documentation`) — government open data for Delhi EV stations. Worth checking for other states' open-data portals too.

---

## How to capture an app's endpoint (path 4)

Only after the source is authorised in `sources.py`. One evening per app.

1. **Proxy:** install mitmproxy (mitmproxy.org). Start it; set your phone's Wi-Fi proxy
   to your PC's IP:8080; install the mitm cert from `http://mitm.it`.
2. **Drive the app:** open the map / a station. Watch the flow list for a
   `GET …/stations?...` (or `/locations`, `/chargers`, `/map`) returning JSON with
   status fields.
3. **Record:** endpoint URL, auth header shape, and the JSON structure (station key,
   connector list key, status field + its vocabulary).
4. **Wire it:** set `<NAME>__BASE_URL`/path in settings; extend
   `from_scraped_stations` / `SCRAPE_STATUS_MAP` in `normalise.py` if the shape/words
   differ. Validate with `uv run python -m workers.poller --dry-run` (no DB).
5. **Tools:** `mitmproxy2swagger` can turn a capture into an OpenAPI sketch to speed
   step 3. Some apps use TLS pinning — then this is harder; prefer the OCPI ask instead.

⚠️ Cert-pinned apps, and any app whose ToS forbids automated access, are a signal to
switch to path 1/2/3 rather than fight the client.

---

## Recommended order of attack

**Starting stage — scrape, in this order (all path 4):**
1. **chargeMOD** (ours) — scrape it first; no ToS question, fastest to first data.
2. **An aggregator** (1C / "Massive Charging") — one capture yields ChargeZone, Statiq,
   Tata, Jio-bp together. Biggest coverage per evening (check its ToS; it may not label
   which CPO each charger belongs to — reconcile downstream).
3. **The remaining apps individually** — Kazam, and any network the aggregator misses —
   each under a recorded decision (read ToS → record → authorise).
4. **Open Charge Map** (free API) for the station master list + dedupe cross-check.

**Phase 2 — the OCPI/UEI upgrade (later, does not gate the above):**
5. Ask Kazam / ChargeZone for OCPI tokens; register as a UEI / Beckn BAP. Swap each
   source from scrape to official feed as credentials land — `source` provenance keeps
   the history continuous.

Sources: [Open Charge Map API](https://openchargemap.org/site/develop/api) ·
[OCPI locations module](https://github.com/ocpi/ocpi/blob/master/mod_locations.asciidoc) ·
[Unified Energy Interface explainer (EVreporter)](https://evreporter.com/an-explainer-on-uei-for-electric-vehicle-charging/) ·
[Unified Bharat e-Charge (Bolt.Earth)](https://bolt.earth/blog/unified-bharat-e-charge-ubc-explained-indias-ev-charging-interoperability-framework) ·
[Kazam integration programme](https://emobilityplus.com/2026/07/13/kazam-launches-free-integration-programme-to-expand-interoperable-ev-charging-through-unified-bharat-e-charge/) ·
[chargeMOD on OCPI](https://chargemod.com/blog/understanding-ocpi-ev-charging-standard1729858163zoG) ·
[TomTom EV Availability API](https://developer.tomtom.com/ev-charging-stations-availability-api/documentation/ev-charging-stations-availability-api/ev-charging-stations-availability) ·
[PlugShare Developer Center](https://developer.plugshare.com/) ·
[mitmproxy](https://mitmproxy.org/)
