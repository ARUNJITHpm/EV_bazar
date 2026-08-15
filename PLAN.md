# PLAN.md — EV Site Intelligence Platform

> Read `OVERVIEW.md` first.
> Work **one Part at a time**. A Part is not done until its **Exit Criteria** pass.
> Do not start a Part whose dependencies are unmet. Do not skip Part 7.
>
> **Then read `FINDINGS.md`** — the blockers, the decisions already settled, the
> gaps between what a tick here claims and what is actually verified, and the
> things only a human can close. A `[x]` below means the code exists; `FINDINGS.md`
> says what it does not cover.

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · `⚡` time-critical · `⚠️` common failure point

---

## PART 0 — Start Immediately, In Parallel

> These three have **zero dependencies** and must not wait for the repo to exist.

### 0.1 ⚡ Status Poller — START TODAY

The one asset that cannot be retroactively acquired. Every day not polling is permanently lost.

- [x] Enumerate availability sources: PlugShare, OCPI feeds, individual CPO apps/APIs, ChargeZone / Statiq / Kazam / chargeMOD / Tata Power EZ / Jio-bp / Ather Grid endpoints — all nine registered in `sources.py`; research notes per network in `CPO_SOURCES.md`. Enumerated, not yet captured (next bullet).

**Source strategy — decided: scrape first, OCPI when partnered.**

> Charging apps are thin shells over JSON APIs — the map screen is calling something like `GET /api/stations?...` and getting connector status back as JSON. No HTML scraping, no browser automation: find the endpoint once, then it is a polite HTTP loop.

- [~] **Generic scrape path wired.** All CPO apps (ChargeZone, Statiq, Kazam, chargeMOD, Tata Power EZ, Ather Grid, Jio-bp) share **one** `ScrapeAdapter` + one tolerant normaliser (`from_scraped_stations` / `SCRAPE_STATUS_MAP`) + the `python -m workers.poller` entrypoint. They differ only in endpoint and status words. chargeMOD is just one of these — treated no differently from the rest. Tests green.
- [ ] **Discover each app's endpoint once** (~hours per app): watch the app's traffic with mitmproxy on a phone, or devtools on their web map. Record endpoint, auth shape, and response schema per source. Validate the mapping with **no database**: `uv run python -m workers.poller --dry-run` prints per-source station/connector/status counts.
- [x] ⚠️ **Two locks, both required.** A source polls only when it is authorised in `app/domain/polling/sources.py` (its ToS read, terms + rate limit recorded, `authorised` flipped by a human) **and** given an endpoint in settings. Config alone is never consent; the registry refuses otherwise.
- [ ] Poll at the gentlest rate that still gives 5-min resolution; back off on errors. ⚠️ A blocked IP loses data days, and data days cannot be bought back.
- [ ] ⚠️ **Networks overlap — keep the duplicates.** Many chargers roam across these apps over OCPI, so the same physical unit appears under several sources with different station ids. That overlap is signal (it maps the roaming graph and cross-checks occupancy) and is kept per-source, deduped downstream at analysis time on distance + operator + connector fingerprint (Part 2.3) — never at poll time.
- [ ] **OCPI is the upgrade path, not the prerequisite:** ask every CPO for OCPI credentials during the 0.3 conversations. When a partner token lands, switch that source from scraped endpoint to official feed — provenance (`source`) already records which rows came from which. Scraped history stays; official data takes over from that date.
- [ ] Expect endpoint churn: apps change their APIs every few months. The dead-man's switch catches it; budget the occasional hour to re-discover. This maintenance attention — not compute — is the real ongoing cost.
- [x] **Local run is Docker-free** — see `LOCAL_DEV.md`. Dry-run needs only Python; recording needs a native Postgres. Console CPO panel (`/console/cpo`) shows every source's governance + measured status.
- [x] Write poller: **5-minute interval, nationwide, append-only** — `workers/poller.py`; `max_instances=1` so a slow cycle cannot stack crawls on a struggling partner.

**Storage design — decided: raw archive + derived events.**

> Capture and storage are separated on purpose. The capture is irreplaceable and must be lossless; the queryable layer must be cheap. Doing lossy compression at ingest — the one irreproducible moment — based on diff logic you will tweak for months is the wrong place to be clever. So ingest keeps everything; the derived table is where the ~30× win lives, and any bug in it costs a recompute, not data.

- [x] **① Raw archive — lossless, append-only, the insurance.** Every poll cycle stores its raw payload per source (one blob per source per cycle is fine), unindexed and compressible. This is the asset that cannot be re-acquired; ingest must be bug-proof, and any downstream logic error stays recoverable offline forever. Honors "always keep the raw blob." — `poll_raw_payloads`, one row **per page** (page boundaries are part of what we saw and a merge cannot be undone), committed *before* anything interprets it.
- [x] **② Derived events — presence-aware change log, the working set.** A row is written on **appear / disappear / status-change**, *derived* from ①. ⚠️ A "change" is not just a status transition: a connector that stops appearing in the feed (station delisted, one station's API hiccups) must write an `unknown`/`offline` row — otherwise its last-known status is wrongly credited as "still available." This is where occupancy queries run. — `derive.py`, pure; disappearance records `unknown` (we stopped being told, we did not learn it went offline) and is written **once**, not once per cycle. ⚠️ Disappearance is derived **only from a successful fetch** — one 500 must never append a fleet-wide vanishing.
- [ ] **Occupancy reconstructs exactly** from ②: a connector held status X from t1 until the next transition at t2, *given the poller was alive throughout* — which `poll_runs` proves. No need to materialise 288 identical ticks; the denominator comes from cadence + liveness, not from row count.
- [x] **Liveness = `poll_runs`**, one row per cycle per source — that *is* the heartbeat (source-level). Optional: an hourly full snapshot into ② so reconstruction queries need not join `poll_runs`. — **hourly snapshot deliberately NOT built**: at ~100k connectors it is 2.4M rows/day, more than the ~1M/day the whole design targets. `longest_gap()` reads `poll_runs` for the "no gaps > 15 min" criterion.
- [x] ⚠️ **Do NOT change-detect at ingest.** Writing only-on-change directly from the network, with raw dropped on unchanged polls, is both presence-blind and irreversible — the one approach to avoid. Change-detection is a *derivation* over ①, re-runnable and fixable. — `scripts/rederive.py` replays ① and reports drift against ②; `replay()` is unit-tested to reproduce the live incremental path exactly.
- [ ] Sizing: ② lands near ~1M rows/day nationwide vs ~30M for every-observation (~30× on ~10–20 transitions/connector/day vs 288 polls). ① compresses hard because it is so repetitive. **These counts are estimates** (rest on ~100k public connectors — verify against real volume); the 30× ratio is the robust part. One small always-on VPS (1–2 vCPU) handles the polling either way — compute is trivial, only storage grows.
- [x] Schema — `charger_status_events` **is table ②** (derived transitions), raw lives in ①:
  ```sql
  -- ② derived events (queryable, one row per transition)
  id BIGSERIAL, source TEXT, source_station_id TEXT,
  observed_at TIMESTAMPTZ, connector_id TEXT,
  status TEXT,           -- available|charging|occupied|offline|unknown
  poll_run_id UUID,      -- which cycle observed this transition
  ingested_at TIMESTAMPTZ DEFAULT now()
  -- ① raw archive (lossless, unindexed, compressible)
  -- poll_run_id UUID, source TEXT, observed_at TIMESTAMPTZ, raw_payload JSONB
  ```
- [x] Never UPDATE, never DELETE, on either table. Append only. — DB `RULES` on both; verified against the live database. ⚠️ `TRUNCATE` bypasses rules. `poll_runs` and `connector_state` are ledgers/caches and *are* updated in place, deliberately.
- [ ] Deploy to a cheap always-on VPS (not your laptop)
- [x] Dead-man's-switch alert: if no successful poll in 30 min → notify — `/api/internal/poller/health` returns 503 so an external uptime monitor is a second, independent alarm. Still needs a monitor pointed at it once deployed.
- [x] Partition both tables by month; TimescaleDB compression on ① is optional but well-suited (repetitive rows compress ~50–100×) — both partitioned, `DEFAULT` backstop on each, `scripts/ensure_partitions.py` covers both. Timescale compression not enabled (Neon does not offer it; revisit at VPS deploy).
- [x] ⚠️ **Code migration owed:** `ingest.py` currently writes every observation with `raw_payload` on each row (the every-observation model, which is lossless but ~30× heavier and its "denominator" justification is wrong — the denominator reconstructs fine from ②+liveness). — **done, migration `0004`.** `raw_payload` dropped from ②; the archive holds it. The migration refuses to run if ② has rows, so it can never silently discard captured payloads.
- [x] ⚠️ **The console must not read "0 events" as broken.** ② is a change log, so a healthy quiet cycle writes zero rows. The numbers that must be non-zero on a live source are **pages archived** and **connectors seen**; both are surfaced and highlighted in Overview and CPO.

**Exit:** Poller has run **7 consecutive days** with zero gaps > 15 min.

---

### 0.2 SERC Tariff PDF Collection — one state per evening

- [ ] Kerala (KSERC) · Tamil Nadu (TNERC) · Karnataka (KERC) · Maharashtra (MERC) · Delhi (DERC) · Gujarat (GERC)
- [ ] For each, capture the **EV charging tariff order** and the general HT/LT schedule
- [ ] Store PDF + `state`, `order_number`, `effective_from`, `effective_to`, `source_url`, `downloaded_at`
- [ ] ⚠️ Capture **superseded orders too** — a report dated last year must regenerate with last year's tariff

**Exit:** 6 states × current + 1 prior order, filed and indexed.

---

### 0.3 CPO Conversations

- [ ] Talk to **two** CPOs. Non-negotiable before Part 7.
- [ ] Extract: revenue share %, ₹/kWh fee, fixed platform fee, hardware bundled or BYO, AMC included, minimum guarantee, contract tenure, **and how they attribute inbound leads**
- [ ] The last one determines the attribution schema. Write it down verbatim.

**Exit:** Two written term summaries + one attribution requirements doc.

---

## PART 1 — Foundation & Site Resolution  *(Weeks 1–2)*

**Deps:** none · **Delivers:** pin → trusted `lgd_district_code`

### 1.1 Infrastructure
> Stack is fixed in `STACK.md`: FastAPI JSON backend, Vite + React + TypeScript SPA with shadcn/ui + Tailwind, poller as a separate process. Scaffold the `app/domain/` layout from `STACK.md` §2 now — retrofitting layer boundaries later is the expensive version.

- [x] Scaffold repo per `STACK.md` §2; `uv` + `pyproject.toml`
- [x] FastAPI app factory, `api/v1` (partners) and `api/internal` (our SPA) mounted separately — and an **independence contract** so neither can import the other
- [x] `frontend/` scaffold: Vite + React + TS, Tailwind, shadcn/ui init, router
- [x] OpenAPI → `schema.d.ts` generation wired into CI, fails on drift
- [x] **import-linter contract for `domain/roi` purity, wired into CI on day one** — 4 contracts; the purity one was verified to actually *fail* when broken, since a contract that cannot fail is decoration
- [x] Postgres 16 + PostGIS; `CREATE EXTENSION postgis;` — PostGIS 3.6 on Neon; `/readyz` checks the extension explicitly, because every spatial query fails far from the cause without it
- [x] Alembic migrations from commit one — at `0005`
- [x] `schema_version` table, seeded — one row per migration
- [x] Append-only event tables; no destructive updates anywhere — DB `RULES`, verified against the live database
- [x] `.env` + secrets management; **quota caps set on every paid key before first call** (Rule 5) — enforced in `config.py`: a key without a positive cap **and** `console_cap_confirmed` refuses to boot

### 1.2 Reference layers (download once)

> **The LGD-codes step turned out to be unnecessary as a separate download.** The india-geodata district polygons ship with `dist_lgd` / `state_lgd` on every feature, so the codes and the geometry arrive together and the primary layer needs no name matching at all. The crosswalk is still built — VAHAN, tariff orders and census extracts all speak names — but it is no longer on the path to a working point-in-polygon lookup.
>
> Reproduce with: `uv run python -m scripts.fetch_reference && uv run python -m scripts.load_reference && uv run python -m scripts.build_crosswalk --seed-aliases --report`

- [x] LGD codes — carried on the district/state polygons themselves (`dist_lgd`, `state_lgd`); the separate `ramseraph.github.io/opendata/lgd` archives are 7z behind a date picker and were not needed.
- [x] District polygons — `LGD_Districts.parquet` (GeoParquet, WKB, EPSG:4326). **783 loaded** of 785; the two skipped are the PoK-administered J&K rows, which carry no LGD code because there is no Indian administration to attribute a site to.
- [x] PIN code polygons — `Datagov_Pincode_Boundaries.parquet`, **19,312 loaded**. Chosen over the 270 MB build. ⚠️ It carries India Post's *circle/region/division*, **not** state/district — stored under those names so nobody joins a postal circle to a state.
- [ ] Urban/rural — Census 2011 town layer, or SHRUG (https://www.devdatalab.org/shrug) — **not done.** Deferred deliberately: district-level SHRUG gives an urban *share*, and 1.5 needs a per-point urban/rural flag, which wants the town/built-up layer. Adding it is one more `LayerSpec`; it is the one part of 1.2 still open.
- [x] Load **all ~780 districts**, not just Tier 1 — 783, all 36 states/UTs, Telangana and Ladakh included.
- [x] ⚠️ **Build `district_name_crosswalk` by hand for 6 states.** Shapefile names ≠ LGD names. Telangana, Ladakh, UP/AP/Assam splits. One evening. Getting this wrong misattributes every downstream number silently. — **table + matcher built; the hand-verification is yours.** `app/domain/resolution/crosswalk.py` is pure and refuses rather than guesses:
  - `exact` / `alias` → safe unreviewed (`Match.trustworthy`)
  - `fuzzy` → proposed, **never** trusted
  - `unresolved` → nothing near enough, *or two candidates too close to call* — bare "Bengaluru" does not silently become Bengaluru Urban
  - Matching is scoped by state, because Bilaspur/Hamirpur/Aurangabad/Pratapgarh each exist in more than one.
  - **Nothing in the codebase writes `verified_by`**, and re-running the matcher will not overwrite a row a human has signed.
  ```sql
  source_name, source_state, source_dataset, lgd_district_code,
  match_method,  -- exact|alias|fuzzy|unresolved
  match_score, verified_by, verified_at, note
  ```
- [x] **Provenance per layer** — `reference_layers` records source URL, SHA-256, licence, feature count and fetch time; a re-fetch whose checksum changed is reported, not silently accepted. Feeds the "data vintage per layer" row in C.5 and answers "which boundaries produced last March's report" (Rule 1).
- [x] **Geometry repaired on load** and the repair counted, not swallowed: `ST_Multi(ST_CollectionExtract(ST_MakeValid(...), 3))`. 13 of 819 features were published invalid. Zero invalid geometries after load.
- [x] **Verified end to end**: 7 real coordinates (Kochi, Thiruvananthapuram, Bengaluru, Chennai, Coimbatore, Hyderabad, Leh) each `ST_Contains` to the correct district; a point in the Arabian Sea matches nothing and its nearest district is 242 km away, so 1.4's 5 km rule will reject it.

### 1.3 Geocoding cascade
```
0 normalise → 1 cache → 2 Nominatim → 3 Ola Maps → 4 Mappls → 5 Google → 6 manual queue
```

> **All seven levels built (L0–L6).** Same pure-decision / thin-shell split as 1.4: `app/domain/resolution/geocode.py` holds `classify_geocode` + `doubt_about` (pure) and `geocode` (the I/O shell), with `normalise.py` (L0), `providers/` (L2–L5), `cascade.py` (assembly) and `manual.py` (L6) beside it. **`meter()` now has its first caller** — every paid level is wrapped in `providers/metered.py`, so the Part C exit criterion is claimable.
>
> Spot-check with: `uv run python -m scripts.geocode_address "opp Lulu Mall, MG Rd, Trivandrum 695001" --normalise-only` (no network/DB) · `--selftest` (live Nominatim) · `uv run python -m scripts.cascade_batch addresses.txt` (the Part 1 exit criteria) · `uv run python -m scripts.seed_price_cards`. 69 tests across `test_geocode.py`, `test_geocode_paid.py`, `test_manual_queue.py`.
>
> 🚫 **BLOCKED, not deferred: self-hosted Nominatim is not running, and cannot be stood up on the current machine.** No Docker Desktop and no WSL distribution are installed, and free disk is 3.8 GB on C: / 17 GB on D: against an India import that needs ~80 GB. Every level above L2 is therefore untested against a live gazetteer, and **the Part 1 exit criteria below cannot be run at all** — the harness for them exists and is one command. This needs either disk + Docker here, or the import done on the VPS with `NOMINATIM_URL` pointed at it.

- [x] **L0 Normalise** — `normalise.py`, pure. Extracts the 6-digit PIN **first** (anchored so it is not plucked from a 10-digit phone number), then lowercases, strips diacritics/punctuation, drops proximity words (`near|nr|opp|opposite|beside|behind`), expands `rd→road`/`jn→junction`, and canonicalises spelling (Trivandrum→Thiruvananthapuram, Bangalore→Bengaluru, Calicut→Kozhikode). ⚠️ It **does not** collapse a city onto its district (Kochi↛Ernakulam) — that would send a district name where a city was meant; district aliasing stays the crosswalk's job. `cache_key` includes the PIN so two places sharing a name but differing by PIN never collide.
- [x] **L1 Cache** — `geocode_cache` table (migration `0006`) with every column the plan lists; the **full raw provider JSON** is stored so confidence can be re-derived without re-paying. **Misses are cached too** (lat NULL) so an unfindable address is not re-asked every retry; a manual resolution later upserts the same key. Round-trip tested on SQLite.
- [x] **L2 Nominatim** — `providers/nominatim.py`, fetch/parse split like the poller adapters. `countrycodes=in` (stops "Salem" resolving to Oregon), a supplied PIN passed as the structured `postalcode` filter, and a missing lat/lon parses to `None` rather than a guessed point. ⚠️ **The self-hosted India import is not done** — it takes hours and is the next session's first background task; until it is up, the cascade resolves nothing live (the code and tests are complete via mock transport).
- [x] **Escalation rule** — two geocoders > 2 km apart return a MISS for the manual queue rather than picking one. ⚠️ **This rule needed a design fix to be real at all.** The cascade must *stop at the first confident hit* (or it costs four calls per address and Part 1's "≥90% without Google" is unmeasurable) — but then two geocoders never both answer and the rule can never fire. So escalation now triggers on **doubt**: the matched PIN contradicts the supplied one, or the provider flags a partial match. `doubt_about()` is pure and tested; "no PIN to check against" is deliberately *not* doubt, since escalating on that would send nearly every address to a paid level.
- [x] **Stop-at-first-confident** — `geocode()` walks levels cheapest-first and breaks on the first undoubted answer; a miss falls through quietly, a failure is recorded as a reason and *then* falls through. At most `MAX_OPINIONS = 2` answers are ever held: a third would cost money to break a tie we have already decided goes to a human, not a vote.
- [x] **L3 Ola Maps** — `providers/ola.py`, 500k free/month, India-only. **`meter()`'s first caller.** PIN is folded into the query text (Ola has no structured postcode filter).
- [x] **L4 Mappls** — `providers/mappls.py`. The **eLoc is stored**, in a generic `geocode_cache.provider_place_id` that also holds Google's `place_id`, Ola's, and Nominatim's `osm_id` — two sites with the same handle are provably the same place. `copResults` is an object for one match and a list for several; both shapes are handled, because treating the object as a list silently loses every single-match geocode.
- [x] **L5 Google** — `providers/google.py`, `components=country:IN` (plus `postal_code:` when a PIN is supplied, as a hard filter rather than another token). ⚠️ **Status is not emptiness**: Google returns HTTP 200 for `REQUEST_DENIED` and `OVER_QUERY_LIMIT`, and reading `results` as empty would cache "this address does not exist" for every address asked during a key outage — and the cache does not expire. Only `ZERO_RESULTS` becomes a miss; four other statuses raise, each with a test. `partial_match` is carried through and costs a confidence step.
- [x] **Every paid call is metered** — `providers/metered.py` wraps each paid level, and `build_cascade` is the only place a paid level is constructed, so a provider cannot join the cascade and skip its usage row. Tested for a hit, a miss (a geocoder bills for looking), an error, and a refusal at cap — the last writes a `capped` row so a cap never looks like an outage.
- [x] **A paid level with no price card refuses to build** — `card_for()` raises at *assembly*, before a rupee. Nothing read `provider_price_cards` until now, so this was the third missing lock: a call that cannot be priced is a spend report reading ₹0 while the bill arrives. Seed with `scripts/seed_price_cards.py`; ⚠️ **the Ola and Mappls overage rates are conservative placeholders** and the seed script says so on every run.
- [x] **L6 Manual queue** — `geocode_manual_queue` (migration `0007`) + `app/api/internal/geocoding.py` + a Leaflet panel. One row per normalised address with a `hits` counter, so fifty asks are one job and the queue sorts by what the twenty seconds buy most. Resolving **writes the point back into `geocode_cache`** with `source='manual'` — without that the next lookup misses again and the queue refills with work already done. "Cannot place" is a first-class button: a human who could not find it must not be nudged into guessing a point.
- [x] **Leaflet is lazy-loaded** — it added 160 kB to the main bundle, and the public report must not carry a mapping library so one operator can place pins. Main chunk is unchanged at 366 kB; the map is a separate 162 kB chunk.

### 1.4 Point-in-polygon

> `app/domain/resolution/geography.py`. Split so every *decision* is a pure function of query results (`classify`) and the PostGIS work is a thin shell (`resolve`) — the subtle mistakes are in what we decide when the SQL comes back ambiguous, not in the SQL.
>
> Spot-check with: `uv run python -m scripts.resolve_point 9.9312 76.2673 [--pincode 680001]` · `--selftest` · `--audit`

- [x] `districts` table with `GIST` index on `geom` — from 1.2
- [x] ~~`ogr2ogr`~~ — **not used.** The source is GeoParquet, so `scripts/load_reference.py` reads WKB directly and never needs GDAL installed. One fewer system dependency on the VPS.
- [x] `ST_Contains` lookup — deliberately **not** `ST_Intersects`: a point exactly on a shared edge would match two districts. With Contains it matches zero, falls to the nearest path at 0.0 m, and lands in the branch built to handle it.
- [x] Handle **zero rows** → nearest-within-5km fallback via `<->` operator; reject beyond 5 km — `<->` orders by *planar* degrees, so the top 5 are re-sorted by true geodesic distance before choosing. Confidence is `medium` within 500 m (a coastline rounding artefact) and `low` beyond it (a geocode nobody should build a report on).
- [x] Flag `boundary_ambiguous` if within 500 m of a district line (two tariff regimes — say so in the report) — implemented as *"another district within 500 m"* rather than "within 500 m of any line": a coastline is not a tariff boundary, and this version also hands the report the **neighbour's name and state**. Verified live at Walayar on NH-544 → Palakkad, `medium`, neighbour Coimbatore (Tamil Nadu) at **87 m**.
- [x] Handle **multiple rows** → fix the source shapefile, don't paper over — `Method.OVERLAPPING`, district `None`, both codes named in the reason. `--audit` sweeps all 783 polygons for overlapping pairs; **1 found, 1.06 m²** — a shared-edge digitisation sliver, reported but below the 1000 m² "material" threshold, so not a failure.
- [x] Handle **PIN disagrees with polygon** → trust PIN, downgrade `geocode_confidence` — the supplied PIN's polygons are unioned and the district holding the **largest overlap area** wins, since a PIN can straddle a district line. Verified live: Kochi coordinates + PIN 680001 → overrides to Thrissur, confidence `low`, reason stated.
- [x] **Confidence is a label, not a number** — `high | medium | low` plus a `reasons` tuple that feeds the report's assumption ledger. A `0.83` would imply a calibration nobody has done. One downgrade per doubt and it never recovers; a test asserts every downgrade carries a reason.
- [ ] ⚠️ **`urban_rural` cannot be filled by 1.5 yet** — the built-up/town layer from 1.2 is still unloaded, so that column will be NULL until it lands.

### 1.5 `sites` table
`site_id, raw_input, lat, lng, geom, lgd_state_code, lgd_district_code, pincode, urban_rural, geocode_source, geocode_confidence, data_tier, boundary_ambiguous, resolved_at`

> `app/models/site.py` + `app/domain/resolution/sites.py` (migration `0008`). Same split again: `combine()` is pure and decides what the row *claims*; `resolve_site()` runs 1.3 then 1.4 then upserts. 20 tests.
>
> Spot-check with: `uv run python -m scripts.resolve_site "MG Road, Kochi 682035"` (dry-run by default) · `--selftest` · `--write`

- [x] **Every column in the spec exists**, plus three the spec implies but does not name: `normalised_input` (the identity, and the join to `geocode_cache` / the manual queue), `district_method`, and `reasons`.
- [x] **`geom` is a generated column** — `GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED`. Nothing writes it, so it cannot drift from the coordinates beside it; a separately-written geometry is one UPDATE from disagreeing, and a spatial join against a stale point returns the wrong neighbourhood rather than an error. Verified live: the database **refuses** a direct write to it.
- [x] **One confidence, and it is the weaker of the two** — 1.3 says how sure it is of the *point*, 1.4 how sure it is of the *district*, and those are different claims. A Google hit whose PIN matches (high) that lands 3 km outside every polygon and resolves by nearest-fallback (low) is a **low**-confidence site. Reporting the geocoder's number is the tempting shortcut and it is the one that is usually higher. Both reason trails concatenate, cascade-first.
- [x] **`district_method` is kept next to it** — ⚠️ `pin_override` means the coordinates and the district disagree *on purpose*: Part 2 will compute road and POI features at a point that is **not inside** the district Part 3 charges it against. Right call, and it has to stay visible rather than being flattened into a confidence label.
- [x] **An address nobody could place is still a site** — PLAN 1.6's "log the site anyway", applied one step earlier. `lat`/`lng`/district are all nullable; `resolved` (has a district) and `located` (has a point) are derived, not asserted. It is also the row the manual queue's answer lands in.
- [x] **One row per distinct place, with a `requests` counter** — two customers pasting the same address are one site asked about twice, not two sites; Part 2's context features are expensive and there is nothing to recompute. The counter is what makes demand in a district we do not serve yet visible, which is the expansion roadmap.
- [x] **Which PIN the site records is a decision, not a coalesce** — the customer's PIN first (a human who knows the place), then the polygon at the point *only if there is exactly one* (several is India Post's delivery rounds showing through, and picking one invents a fact), then the geocoder's own postcode last (that is the geocoder agreeing with itself). ⚠️ `GeocodeOutcome` gained a `postcode` field for this, so nothing reaches into a provider-specific raw blob.
- [x] **Verified live** against loaded reference geography: Kochi `9.9312, 76.2673` + PIN `682035` → **Ernakulam (555)**, `contained`, confidence **low** — the point actually sits in PIN 682005, so 1.4 records the conflict, declines to override (same district), and downgrades; the site inherits the weaker label. Repeat request → 1 row, `requests=2`.
- [ ] ⚠️ **`urban_rural` is NULL** — the built-up/town layer from 1.2 is still unloaded. Guessing it from district type would be wrong for exactly the peri-urban sites where the distinction changes the answer.
- [ ] ⚠️ **`data_tier` is NULL** — it is 1.6's `data_coverage` to fill. A tier is a claim about what data we hold for a district, and which districts we sell into; that is a business decision and not this table's to invent.
- [ ] ⚠️ **The upsert is verified against live Postgres, not in CI** — `sites` carries a PostGIS geometry so the table cannot be created on SQLite. All the judgement is in `combine`/`choose_pincode`, both pure and unit-tested; the round-trip, the generated column and the read-only-geom guarantee are covered by `resolve_site --selftest`, which needs a database. Run it after every reference reload.

### 1.6 Tier gate
- [ ] `data_coverage(lgd_district_code, tier, has_tariff_data, has_competitor_poll, has_vahan_data, osm_road_quality)`
- [ ] `tier > 1` → waitlist response, **but log the site anyway** (lead capture + expansion roadmap)

### Exit Criteria — Part 1

> 🚫 **All six are blocked on the same thing: Nominatim is not running** (see 1.3). Nothing here can be measured against a cascade whose free workhorse is absent — running it now would report a 0% resolve rate and a Google bill, which is a measurement of the outage, not of the cascade.
>
> The harness is built and is one command: `uv run python -m scripts.cascade_batch addresses.csv --out verify.csv --write`. It runs each address through the cascade *and* through 1.4's `resolve()`, prints four of the six criteria with PASS/FAIL, enqueues every miss into L6, measures cost per address from `api_usage_events` (rather than assuming it), and writes a CSV with an empty `correct_y_n` column for the hand check.
>
> ⚠️ **The 200 addresses do not exist yet either.** No authorised CPO source is enabled, so there is no list to draw from — it has to be assembled by hand or from a public directory before this can run.

- [ ] 200 real charging-station addresses (KL + TN) run through the cascade
- [ ] **≥95%** resolve to a district code
- [ ] **≥90%** resolve without touching Google
- [ ] **100%** of resolved districts correct — verify all 200 by hand (only cheap ground truth you'll ever get). ⚠️ Deliberately **not** automated: the script writes the column and refuses to fill it. A script that grades its own homework throws the ground truth away.
- [ ] Median cascade cost per address = **₹0**
- [ ] Every Google-escalated case reviewed → normalisation backlog written — the harness lists them by name at the end of the run

---

## PART 2 — Context Layer  *(Weeks 3–5)*

**Deps:** Part 1 · **Delivers:** feature vector per site

### 2.1 Roads
- [ ] Import OSM India extract into PostGIS (osm2pgsql)
- [ ] Nearest NH/SH segment + distance in metres (`highway=trunk|primary`)
- [ ] ⚠️ **Median access direction** — a site on the wrong side of a divided highway loses ~half its addressable traffic. This is a real feature, not a nicety.
- [ ] Junction count within 500 m
- [ ] Detour cost: seconds off-route from nearest arterial

### 2.2 POI gravity (500 m / 1 km / 3 km rings)
- [ ] Counts: F&B, retail, hotels, hospitals, offices, malls
- [ ] **Dwell-anchor score** — does anything hold a driver 30–45 min? A DC fast charger next to nothing is a charger nobody waits at.

### 2.3 Competitors
- [ ] Ingest from PlugShare + OCPI + CPO apps
- [ ] ⚠️ **Dedupe across sources** — same physical charger appears 3×. Match on distance + operator + connector fingerprint.
- [ ] Counts within 1 / 3 / 5 km, connector types, rated kW
- [ ] **Join to poller data → observed occupancy.** This is the piece nobody else has.

### 2.4 Grid
- [ ] Distance to nearest 11 kV feeder / DISCOM substation (where data exists)
- [ ] Placeholders for the customer-supplied taps (sanctioned load, transformer)

### 2.5 Archetypes
- [ ] Cluster the feature space (k-means / HDBSCAN). **No labels needed.**
- [ ] Name the clusters by hand: `highway_dhaba`, `mall_basement`, `urban_fleet_depot`, `residential_ac`, …
- [ ] ⚠️ **Cover 2W/3W archetypes, not just 4W DC fast.** Indian EV volume is overwhelmingly two- and three-wheelers; AC / swap / low-ticket charging is a different economics archetype. 4W-DC-only archetypes miss most of the actual demand in Tier 1 states.
- [ ] Ship "comparable sites" — nearest neighbours in feature space
- [ ] Store `archetype_version`

### Exit Criteria — Part 2
- [ ] Any resolved site returns a complete, non-null feature vector in < 2s
- [ ] Competitor dedupe verified by hand on 50 sites
- [ ] Archetypes are human-nameable; if a cluster can't be named, re-cluster

---

## PART 3 — Tariff DB + ROI Engine  *(Weeks 5–7)*

**Deps:** 0.2 · **Delivers: the first sellable product**

### 3.1 Tariff database
- [ ] Structured schema: state, consumer category, EV-specific slab, ₹/kWh energy charge, ₹/kVA/month demand charge, ToD slabs, fixed charges, duty/cess, `effective_from`, `effective_to`, `source_pdf`, `order_number`
- [ ] ⚠️ **Time-bounded rows.** Never overwrite a tariff — insert a new row with new dates.
- [ ] Cross-check every state against one real electricity bill
- [ ] **Subsidy ledger** — sibling table, same effective-dating discipline: PM E-DRIVE capital subsidy per charger class, state EV-policy subsidies, accelerated depreciation, GST treatment. `state, scheme, charger_class, amount_or_rate, conditions, effective_from, effective_to, source_url`. These change amortised capex enough to flip verdicts.

### 3.2 ROI engine — **pure function, zero dependencies**
- [ ] No DB access, no network, no globals. Inputs in, dict out.
- [ ] **30+ unit tests.** Include: zero utilisation, 100% utilisation, negative margin, ToD split, missing transformer, revenue-share vs ₹/kWh CPO models
- [ ] Capex: hardware, civil, transformer/load augmentation, DISCOM connection, signage/canopy — **net of the subsidy ledger (3.1)**
- [ ] Opex: **demand charges (`sanctioned_kVA × ₹/kVA/mo × 12`)**, energy, O&M/AMC 5–8% of hardware capex, rent/revenue share, network fee, gateway ~1.5–2%, GST treatment
- [ ] **Fleet anchor scenarios** — *with/without* a minimum-guarantee offtake, as first-class scenarios. The single biggest de-risker in Indian charging economics; an anchor alone can flip Don't → Build.
- [ ] **Utilisation as a ramp curve**, never a flat rate — the engine consumes `kwh_by_year[]`, not one number. Payback at "P50 in year 1" vs "P50 in year 3" is a different verdict.
- [ ] **Sanctioned load as an output** — recommend the kVA (battery-buffered / managed-peak options), don't just accept it. Cutting ₹2–4 lakh/yr of demand charges is advice worth paying for.
- [ ] **Solar co-location scenario** — canopy/rooftop solar shifts `margin_per_kWh` enough to flip verdicts
- [ ] **Selling-price sensitivity** — price is a decision constrained by nearby competitor pricing (the poller observes it); output breakeven at ±₹2/kWh around the assumed price
- [ ] **Optional financing block** — debt/equity split, interest rate → levered IRR. Lenders are the deepest-pocketed buyer and unlevered IRR is incomplete for a credit committee.
- [ ] Outputs: `margin_per_kWh`, `annual_fixed`, **`breakeven_kWh_year`**, **`breakeven_utilisation`**, NPV, IRR, payback, 10-yr cashflow
- [ ] `economics_version` stamped on every result

### 3.3 Validation
- [ ] Reconcile against **one operator's one month of real P&L**. Must match within 5%. If it doesn't, the tariff parse is wrong — fix it before proceeding.

### 🎯 Exit Criteria — Part 3 — **SHIP THIS**
- [ ] **Tariff Audit + breakeven number is sellable with no demand model at all.**
- [ ] 30+ tests green
- [ ] Real-P&L reconciliation within 5%
- [ ] **Sell the Tariff Audit to three operators. Do this before Part 4.** The audit is the door-opener (OVERVIEW §6.1): the customer feels the pain today, can verify the number against their own bill, and every audit customer is a warm prospect for an expansion assessment. If three operators won't pay for found money, that is market feedback the demand model cannot fix.

---

## PART 4 — Demand Layer + Heuristic v0  *(Weeks 7–10)*

**Deps:** Parts 2, 3 · **Delivers:** the quarantined uncertain number

### 4.1 VAHAN ingestion
- [ ] Monthly batch from https://vahan.parivahan.gov.in/vahan4dashboard/
- [ ] District-level, split 2W / 3W / 4W / bus, plus fleet/commercial share
- [ ] ⚠️ **Weight the 12-month growth rate above absolute count.** Absolute count tells you where EVs are; growth tells you where they're going.
- [ ] Store as time series, never overwrite

### 4.2 Heuristic v0
```
score = w1·traffic + w2·poi_dwell + w3·(−competition)
      + w4·vahan_growth + w5·grid_ease + w6·access_penalty
```
- [ ] Coefficients in a **config file**, versioned — never hardcoded
- [ ] Map `score` → kWh via **archetype-specific anchors calibrated on polled stations**
- [ ] Output **P10 / P50 / P90**, never a point estimate
- [ ] **Output a ramp curve** (year 1 → steady state), even a crude one — the ROI engine consumes `kwh_by_year[]` (3.2). A flat rate makes good sites look bad and bad sites look survivable.
- [ ] `model_version` stamped

### 4.3 Prediction log — Rule 2
- [ ] `predictions(site_id, model_version, economics_version, predicted_p10, p50, p90, predicted_at, actual_kwh NULL, actual_observed_at NULL)`
- [ ] Write to it from the very first prediction

### 4.4 ⚠️ Selection bias hunt — Rule 3
- [ ] Actively find **failed and closed stations**: PlugShare "permanently closed", stations that vanished from feeds, news reports, ask CPOs directly
- [ ] Store with the same feature vector as live sites
- [ ] Without these, the model learns "everywhere is fine" — and the product's whole value is telling someone their site is bad

### Exit Criteria — Part 4
- [ ] Heuristic beats "district mean kWh" baseline on held-out polled stations
- [ ] ≥ 20 confirmed failed/closed sites in the dataset
- [ ] Every prediction logged with a null actual

---

## PART 5 — Reports  *(Weeks 10–12)*

**Deps:** Parts 1–4

- [ ] Seven React components in `features/report/`, one per section of the `OVERVIEW.md` anatomy
- [ ] Hero: breakeven utilisation vs P10–P90 band vs margin of safety — hand-drawn SVG, not a chart library
- [ ] Verdict logic driven by **P10** — Build / Conditional / Don't
- [ ] 3 scenarios: conservative / base / upside
- [ ] **Assumption ledger** — every default listed, ⚠️ on unverified
- [ ] Each ⚠️ links to a resolve-this action (re-engagement hook)
- [ ] **Provenance block:** `model_version`, `economics_version`, `schema_version`, `archetype_version`, `tariff_effective_date`, `renderer_version`, `generated_at`
- [ ] `print.css` with `@page` rules and page breaks between sections
- [ ] **Playwright PDF path**, waiting on `[data-report-ready]` — never race the render
- [ ] **Archive the rendered PDF bytes** alongside the payload at generation time (Rule 1 — see `STACK.md` §6)
- [ ] **Regeneration test:** re-render a 30-day-old payload at its recorded `renderer_version` → byte-identical to the archived PDF
- [ ] Five customer taps in the UI: connection? sanctioned load? transformer? land? budget?
- [ ] Waitlist route for Tier 2/3

### Exit Criteria — Part 5
- [ ] Report regenerates identically from stored payload + recorded `renderer_version`
- [ ] Archived PDF retrievable for any report ever generated
- [ ] A stranger can read it without explanation
- [ ] At least one "Don't build" verdict shipped to a real customer

---

## PART 6 — CPO Comparison

**Deps:** Parts 0.3, 3

- [ ] `cpo_terms` table: revenue share %, ₹/kWh fee, fixed platform fee, hardware bundled/BYO, AMC, minimum guarantee, tenure
- [ ] **Run the ROI engine once per CPO** — each changes `margin_per_kWh`, `annual_fixed`, and capex
- [ ] Rank on net IRR
- [ ] Separate qualitative score: district app user base (from poller), OCPI roaming, **measured uptime on their existing stations** (from poller), regional fleet contracts
- [ ] ⚠️ **Never blend financial and qualitative into one number.** Display side by side.
- [ ] ⚠️ **Our own affiliated network is listed and scored by the same public rules as everyone else's** — no special-casing, in either direction. The operator-affiliation decision (OVERVIEW §6.3) must be resolved before this table is shown to any external customer.

### Exit Criteria — Part 6
- [ ] Same site, 3 CPOs, 3 different IRRs, all explainable line-by-line

---

## PART 7 — Attribution  ⚠️ DO NOT DEFER

**Deps:** Part 0.3

> "If you can't prove the lead was yours, nobody pays." Build this **before** you think you need it. This is why the plan ends at Part 7 and not Part 5.

- [ ] Attribution chain logging every touchpoint the CPO conversations said matters
- [ ] `report_id` → `lead_id` → `cpo_handoff` → `installation`, immutable and timestamped
- [ ] UTM / referral / signed-token handoff to CPO partners
- [ ] Reconciliation export in whatever format the CPO's finance team will accept
- [ ] Dispute-resistant: append-only, cryptographically timestamped if feasible
- [ ] ⚠️ **The honesty firewall (OVERVIEW §6.2) ships with the first commission**, not after:
  - Report priced separately from the lead — a *Don't build* verdict still earns
  - Verdict distribution (Build / Conditional / Don't) published publicly
  - Verdict logic stays in the pure ROI engine — no commission can touch a number

### Exit Criteria — Part 7
- [ ] A CPO can independently verify one lead end-to-end from your export
- [ ] You can answer "prove it" without opening a spreadsheet by hand
- [ ] The verdict distribution is public before the first commissioned lead is handed off

---

## PART 8 — Supervised Model  *(Month 3+)*

**Deps:** ⚡ **90 days of poller data.** Cannot start earlier. This is why Part 0.1 was day one.

- [ ] Target: `log(kwh / connector / day)`
- [ ] **LightGBM with quantile objectives** → P10 / P50 / P90 directly
- [ ] **Leave-One-District-Out CV** — prevents the model memorising Bengaluru and claiming it understands Kochi
- [ ] Compare against heuristic v0 on the same holdout. **If it doesn't beat the heuristic, keep the heuristic.**
- [ ] Swap in behind the same interface — nothing downstream changes
- [ ] Then: hierarchical CPO effects with **partial pooling**, so small operators borrow strength from the group average instead of overfitting to three stations
- [ ] Backfill `actual_kwh` into `predictions` → your first real calibration curve

### Exit Criteria — Part 8
- [ ] Beats heuristic on LODO-CV
- [ ] P10/P90 band is **calibrated** — ~10% of actuals fall below P10, ~10% above P90
- [ ] Reports still regenerate under old `model_version`

---

## PART G — Revenue & Distribution  ⟲ *continuous, like Part C*

**Deps:** G.0 none · G.1 needs Part 3 · **Delivers:** paying customers, in the order they actually pay

> The retail report is **marketing, not the business** (OVERVIEW §6.1). Ladder: audits (cash now) → institutional subscriptions (the business) → attribution commissions (upside, firewalled). Individual site owners are low-LTV, high-CAC — they feed the funnel, they are not the revenue.

### G.0 The operator-affiliation decision — *before the first external sale*
- [ ] Decide: internal expansion weapon **or** neutral brand (OVERVIEW §6.3). **The middle is where trust dies.**
- [ ] If neutral: our own network scored by the same public rules as every other CPO (Part 6)
- [ ] Either way: our own session data becomes demand-model ground truth — wire it into 4.2 calibration

### G.1 Tariff Audit as door-opener  *(pairs with Part 3)*
- [ ] Productise the audit: bill in → found-money number out, one page
- [ ] Target list: existing operators in KL/TN/KA — start with operators the CPO conversations (0.3) already opened
- [ ] Three paid audits = Part 3 exit criterion
- [ ] Every audit customer flagged as warm prospect for an expansion assessment

### G.2 Free instant breakeven teaser
- [ ] Public web tool: drop a pin → breakeven utilisation in 30 seconds. **Pure arithmetic — needs Part 3 only, no demand model.**
- [ ] Every teaser run logged as a lead with its district (feeds the waitlist expansion signal, OVERVIEW §4)
- [ ] Upsell path: teaser → paid report → ⚠️-ledger resolution loop

### G.3 Institutional buyers — where the money is
- [ ] **Lenders / NBFCs:** pitch the P10 margin-of-safety number as an underwriting standard. There is none today. One bank partnership > thousands of retail reports. Needs the financing block (3.2).
- [ ] **CPO expansion teams** (non-competing footprints): annual portfolio-screening subscription / API — "rank these 200 candidate sites" — not per-report pricing
- [ ] **OMC dealer networks & franchise programs:** petrol-pump dealers being pushed to add chargers are concentrated and reachable through an association structure. Same for hotel associations and mall operators.
- [ ] **Fleet operators:** depot/opportunity-charging siting; each one is also a potential **fleet anchor** (3.2) for someone else's site

### G.4 Publish the data  *(pairs with 0.1 — needs ~90 days of polling)*
- [ ] Quarterly *State of EV Charger Utilisation* note (KL/TN/KA) from poller data — the only report of its kind in India
- [ ] Cheap PR, inbound institutional interest, and it advertises the moat itself

### Exit Criteria — Part G
- [ ] Affiliation decision written down and reflected in Part 6 display rules
- [ ] 3 paid tariff audits (G.1)
- [ ] 1 institutional conversation advanced to a pilot (lender, CPO, OMC program, or fleet)
- [ ] First quarterly utilisation note published within one quarter of Part 8's data threshold

---

## PART C — Operations Console  ⟲ *continuous, built in parallel*

**Deps:** none to start · **Delivers:** one internal place to see what the system knows, what it is spending, and what it is missing

> **Not on the numbered critical path**, and deliberately not a "Part 9". The console grows **one panel per Part** rather than arriving at the end — a panel ships when the data behind it ships.
>
> Build **C.0 and C.1 first**. They are the only panels whose absence actively costs money: right now `config.py` declares a `monthly_cap` and nothing on earth counts against it. Constraint 7 asks for two locks and we currently have one.

Internal only. A route group in the same SPA — `frontend/src/features/console/` — backed by `app/api/internal/console_*.py`. Not a second application, and not `api/v1` (that namespace is contractual, for partners).

Unlike the report, the console **may look like a normal admin tool**: use the shadcn table, dialog and form primitives as-is. Nobody is being persuaded by it.

### C.0 Shell + access control

- [x] `ConsoleLayout.tsx` with the left sidebar; nested routes under `/console`
- [x] ⚠️ **Auth lands before the first panel renders.** This console exposes CPO commercial terms and our own spend. It is the most sensitive surface in the product. — landed late (panels shipped first); closed now, before C.4 puts CPO terms on screen.
- [x] Single operator account, httpOnly server-side session cookie, one `require_operator` FastAPI dependency guarding every `console_*` endpoint. No SSO, no roles table until there is a second operator. — `scrypt` from the stdlib, no new dependency; 12-hour sessions; `ENV=prod` **refuses to boot** without a password, same shape as the quota-cap rule.
- [x] ⚠️ **Guard on the server, not in the router.** A hidden React route is not access control — the endpoints are what must refuse. — the guard is a **router-level** dependency, so a new panel is protected by being added there. A test walks the live OpenAPI schema and asserts every non-public `/api/internal` path returns 401, so an endpoint added later is covered without anyone remembering.
- [x] ⚠️ **Unconfigured must not mean unprotected.** No password set → every console endpoint returns **503**, never 200.
- [x] Unauthenticated `/api/internal/poller/alive` for an external uptime monitor: a status code and `{alive, never_run}`, nothing about which networks we poll.
- [ ] Panels are **read-only by default**. Writes are explicit, append-only, and attributed to the operator. — all panels are currently read-only; the attribution rule bites when C.4 gains its first write.
- [x] `/console/*` excluded from prerendering, `sitemap`, and `robots` — SPA has no prerender; `frontend/public/robots.txt` disallows `/console` and `/api/internal`.

```
OVERVIEW        health · today's spend · poller heartbeat · what's stale
CPO             partners · terms · attribution requirements · measured uptime
DATA            sources · coverage · freshness · dedupe · failed-station hunt
GEOCODING       cascade funnel · manual queue · cost per address
SPEND ▸ MAPS    calls · quota burn · ₹ · projection to month end
SPEND ▸ LLM     tokens · models · ₹ · by purpose
REPORTS         generated reports · verdicts · leads · attribution chain
```

### C.1 ⚡ Metering foundation — *the second lock*

Every metered external call writes one append-only row **before** the response is used. No exceptions, including retries, errors, and cache hits.

- [x] `api_usage_events` — append-only (every column below exists; `NOT NULL` on `price_card_version` so an unpriced row cannot be written):
  ```sql
  id BIGSERIAL, provider TEXT,        -- google_maps|ola_maps|mappls|nominatim|openai|anthropic
  operation TEXT,                     -- geocode|places_nearby|tariff_extract|...
  model TEXT,                         -- LLM only, NULL otherwise
  units_in INT, units_out INT,        -- calls, or input/output tokens
  cost_paise BIGINT,                  -- money in paise, integers (AGENTS.md)
  price_card_version TEXT,            -- which card priced this
  billing_month DATE,                 -- the quota window this counts against
  status TEXT,                        -- ok|error|rate_limited|cache_hit
  caused_by TEXT, site_id UUID,       -- what triggered the spend
  latency_ms INT, raw JSONB, occurred_at TIMESTAMPTZ
  ```
- [x] `provider_price_card` — **effective-dated rows, exactly like the SERC tariff table.** Never overwrite a price; insert a new row with new dates. A cost computed last March must still recompute to last March's price.
- [x] **Enforcing counter:** before a paid call, sum this month's units for that provider. At cap → refuse the call and fall through to the next cascade level. Do not warn-and-proceed.
- [x] ⚠️ **Log `cache_hit` rows with the cost you avoided.** Part 1's exit criterion is *median cascade cost per address = ₹0* — this is how you evidence it rather than assert it.
- [x] Alert at 80% of cap; hard stop at 100% — `QuotaState.should_alert` / `QuotaExceededError`; the refusal itself writes a `capped` row, so a blocked call is still accounted for.
- [x] **`meter()` has its first callers** — the three paid geocoders (1.3 L3–L5), each wrapped in `providers/metered.py`. "No paid call can execute without writing a usage event" is now structural rather than a convention: `build_cascade` is the only constructor of a paid level and it constructs them wrapped, so an unmetered provider is one the cascade cannot reach.
- [x] **Effective-dated cards are actually read** — `app/metering/cards.py`. The table existed since `0002` but nothing looked anything up in it; `card_for()` closes that, model-specific card beating the all-models card, and **raising rather than defaulting to free**. ⚠️ Two of the three shipped rates are unverified placeholders (Ola and Mappls overage) — `scripts/seed_price_cards` warns on every run, and the spend report will not reconcile against those two bills until someone confirms them.

### C.2 Spend ▸ Maps & geocoding APIs

> Partly shipped alongside 1.3 L6, since the funnel and the manual queue are the same screen: `/api/internal/geocoding/funnel` + the console **Geocoding** panel.

- [ ] Per provider per month: calls, ₹, % of cap, burn-rate projection to month end — *calls and ₹ per provider are live; % of cap and burn-rate are not*
- [x] Cost per **resolved address**, and the cascade funnel — resolved/unresolved per level, month-to-date spend per provider, and the **share resolved without a paid call**, flagged when it falls under the 90% Part 1 wants
- [ ] Every Google escalation listed with its input, so the normalisation backlog (Part 1 exit criteria) writes itself — *`scripts/cascade_batch` prints them for a batch run; the console does not list them yet*
- [ ] Which provider is winning ties, and where two geocoders disagreed > 2 km — *the disagreement reason is stored on the queue row; nothing aggregates it*

### C.3 Spend ▸ LLM

> ⚠️ **LLMs are extraction and ops tooling. They are not in the prediction path and never in the financial path.** The demand model remains the only learned thing that touches a report number. See the new constraint 10 in `AGENTS.md`.

- [ ] Model registry + effective-dated price card (input/output priced separately)
- [ ] Tokens in / out, ₹, **grouped by purpose** — `tariff_extract`, `pdf_classify`, etc.
- [ ] ⚠️ **Retry and failure cost shown separately.** A retry loop is the quiet way to lose a budget; averaged into a total it is invisible.
- [ ] Cost per successfully parsed tariff PDF — the number that tells you whether extraction is worth automating at all
- [ ] `model` + `prompt_version` stamped on every artefact an LLM touched, and surfaced in report provenance
- [ ] Queue of LLM-extracted tariff values **pending human verification**, with a diff against the source PDF

### C.4 CPO panel  *(pairs with 0.3 and Part 6)*

- [ ] `cpo_terms` rows: revenue share %, ₹/kWh fee, platform fee, hardware bundled/BYO, AMC, minimum guarantee, tenure — with effective dates
- [ ] Contacts and the **verbatim attribution requirements** from 0.3
- [ ] **Measured uptime** per operator, computed from poller data — not their claim, our observation
- [ ] District-level app footprint from the poller

### C.5 Data panel  *(pairs with Parts 0.1 and 2)*

- [ ] Per source: rows ingested, last successful poll, gap history, ToS/rate-limit notes
- [x] ⚡ **Poller heartbeat with the dead-man's switch state front and centre.** Silence is the failure mode and silence is invisible unless something watches for it.
- [ ] Coverage by district against the tier table; **which uncovered district has the most waitlisted pins** — this is the expansion roadmap from `OVERVIEW.md` §4
- [ ] Competitor dedupe stats — candidates merged, matches rejected, the 50 hand-verified sites
- [ ] ⚠️ **Failed/closed station hunt tracker** (Rule 3). Count against the ≥20 target, with source per confirmation.
- [ ] Data vintage per layer: LGD, polygons, OSM extract, VAHAN month, tariff effective dates

### C.6 Reports & leads panel  *(pairs with Parts 5 and 7)*

- [ ] Reports generated, verdict split (Build / Conditional / Don't), waitlisted pins
- [ ] Unresolved ⚠️ assumptions per report — the re-engagement queue
- [ ] Attribution chain view: `report_id → lead_id → cpo_handoff → installation`
- [ ] Prediction log with its NULL `actual` column, and calibration once backfill starts (Part 8)

### Exit Criteria — Part C

- [ ] **No paid call anywhere in the codebase can execute without writing a usage event** — verified by grepping every provider client, not by assertion
- [ ] Hitting a configured cap **provably refuses** the call in a test, rather than logging and proceeding
- [ ] Month-to-date ₹ in the console reconciles against the provider's own billing dashboard within 5%
- [ ] Poller silence is visible from the Overview panel within one refresh
- [ ] A tariff value extracted by an LLM cannot reach the ROI engine without a human verification row

---

## Standing Checklist — verify before every merge

- [ ] Did anything predict a financial number directly? → **revert**
- [ ] Is every new output stamped with its versions?
- [ ] Is every new prediction logged with a null actual?
- [ ] Are all new numbers ranges, not points?
- [ ] Does any new API key lack a hard quota cap?
- [ ] **Does every new paid or metered call write an `api_usage_events` row before its response is used?**
- [ ] **Did an LLM output reach a tariff row or a financial number without human verification?** → **revert**
- [ ] Did we UPDATE or DELETE an event row anywhere?
- [ ] Is the poller still running?

---

## Dependency graph

```
0.1 Poller ────────────────────────────────────────────▶ PART 8 (needs 90d)
0.2 Tariff PDFs ──────▶ PART 3 ──┬──▶ PART 5 ──▶ PART 7
0.3 CPO talks ────────┬──────────┘                  ▲
                      └──▶ PART 6 ──────────────────┘
PART 1 ──▶ PART 2 ──▶ PART 4 ──▶ PART 5

PART G ⟲ runs alongside everything from Part 3 onward.
  G.0 affiliation call ──── before the first external sale
  G.1 audits            ──── needs Part 3 · three paid audits
  G.2 free teaser       ──── needs Part 3 only (arithmetic, no model)
  G.3 institutions      ──── lenders need 3.2 financing block
  G.4 publish data      ──── needs ~90 days of 0.1 polling

PART C ⟲ runs alongside all of the above.
  C.0 shell + auth   ─┐
  C.1 metering       ─┴─▶ start now, before the first paid call
  C.2 maps spend      ──── needs Part 1.3
  C.3 llm spend       ──── needs Part 0.2 / 3.1
  C.4 cpo             ──── needs Part 0.3
  C.5 data            ──── needs Part 0.1
  C.6 reports/leads   ──── needs Parts 5, 7
```

**Critical path is Part 0.1.** Everything else can slip. That cannot.

**C.1 is the one exception to "console can wait":** every paid call made before the meter exists is spend you can never account for retroactively — the same shape of problem as the poller, at a smaller scale.
