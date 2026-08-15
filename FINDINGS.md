# FINDINGS

**What this is.** `PLAN.md` says what to build. This says what we **learned while
building it** — every blocker, every decision made under uncertainty, every gap
between what a checkbox claims and what is actually verified, and everything
that only a human can close.

Read it before picking up any part. A tick in `PLAN.md` means the code exists;
a line here tells you what it does *not* cover.

**Last updated:** 2026-08-12, after PART 1.5.
**Repo state at that point:** 278 tests green · ruff/format/mypy/import-linter
clean · `alembic check` clean at revision `0008` · frontend tsc/prettier/vitest
clean, builds.

**Legend** — `🚫 BLOCKED` cannot proceed · `👤 HUMAN` no code can close it ·
`⚠️ GAP` shipped but incompletely verified · `🧭 DECISION` settled, do not
relitigate without a reason · `🐛 FOUND` a real defect caught and fixed.

---

## 1. Blockers — nothing downstream moves until these clear

### 🚫 B1 · Self-hosted Nominatim is not running, and cannot be on this machine
*Blocks: 1.3 live behaviour · all six Part 1 exit criteria · any real 1.5 site*

No Docker Desktop and no WSL distribution are installed. Free disk is **3.8 GB
on C:, 17 GB on D:**, against an India import needing the ~1.5 GB PBF plus a
**40–80 GB** database. Starting it would fail hours in, and the partial database
is not resumable.

Consequence today: every address becomes an unlocated lead. L3–L5 are complete
and tested against mock transports but have **never spoken to a live provider**.

*Unblocked by:* the import running on the VPS with `NOMINATIM_URL` pointed at
it, or ~80 GB free plus Docker here. Compose profile and disk warning are in
`docker-compose.yml`.

### 🚫 B2 · The 200 KL+TN addresses do not exist
*Blocks: all six Part 1 exit criteria, independently of B1*

No CPO source is authorised, so there is no list to draw from. It has to be
assembled by hand or from a public directory.

*Note:* the harness is built and is one command —
`uv run python -m scripts.cascade_batch addresses.csv --out verify.csv --write`.
It runs the cascade **and** 1.4, prints four of six criteria PASS/FAIL, enqueues
misses into L6, measures cost per address from `api_usage_events` rather than
assuming it, and writes an empty `correct_y_n` column for the hand check.

### 🚫 B3 · No authorised polling source
*Blocks: 0.1 producing any data · C.4 measured uptime · 2.3 competitor occupancy*

The poller is complete and its dead-man's switch is live, but every source ships
`authorised=False`. Two locks are required by design (registry + endpoint), and
only a human can flip the first. Endpoint discovery is also human work (~hours
per app, mitmproxy or devtools).

### 🚫 B4 · Urban/rural layer not loaded
*Blocks: `sites.urban_rural` (1.5) · any urban/rural split downstream*

The one part of 1.2 still open. District-level SHRUG gives an urban *share*;
1.5 needs a **per-point** flag, which wants the Census 2011 town / built-up
layer. Adding it is one more `LayerSpec` in `app/domain/resolution/reference.py`.

---

## 2. 👤 Human-only actions

### Security — outstanding, and the oldest items here

| | Action | Why it matters |
|---|---|---|
| S1 | **Rotate the OpenAI key** found in the old `.env` | It was live, and it belonged to an unrelated Flask project. Removed from the project `.env`; removal is not rotation. |
| S2 | **Rotate the Google API key** from the same file | Same. Live, unrelated project, still valid until rotated. |
| S3 | **Rotate the Neon database password** | It sat in a plaintext file inside a OneDrive-synced folder, i.e. it has been through a third party's storage. |

These are unchanged since they were first raised. Nothing in the codebase can
close them.

### Data and commercial

- **0.2 SERC tariff PDFs** — Kerala, Tamil Nadu, Karnataka, Maharashtra, Delhi,
  Gujarat. EV charging order **and** the general HT/LT schedule, **including
  superseded orders** (a report dated last year must regenerate with last year's
  tariff). One state per evening.
- **0.3 CPO conversations** — two, non-negotiable before Part 7. The question
  that decides the attribution schema is *how they attribute inbound leads*;
  record the answer **verbatim**.
- **1.2 crosswalk sign-off** — 40 rows exist, **all with `verified_by` NULL**.
  Two are fuzzy matches needing judgement (`vizag` / `waltair` →
  "Visakhapatanam"). Nothing in the codebase writes `verified_by`, by design,
  and re-running the matcher will not overwrite a signed row.
- **C.1 price cards** — confirm the Ola and Mappls rates (see ⚠️ G3).
- **Part 1 exit criteria** — 100% hand-verification of 200 districts. Deliberately
  not automatable.

---

## 3. ⚠️ Gaps — shipped, but not verified as far as the tick implies

| | Gap | What would close it |
|---|---|---|
| G1 | **L3–L5 have never called a real provider.** Every paid geocoder is tested against `httpx.MockTransport` only. Response shapes were written from published docs, not observed traffic. | One live call per provider, once keys exist. Watch especially Mappls `copResults` (object vs list) and Ola's `status` vocabulary. |
| G2 | **Mappls auth is assumed.** The configured `api_key` is sent as an OAuth bearer token, which is right for a REST key or an out-of-band token. If we adopt their OAuth flow, the refresh belongs in that module and **outside `meter()`** — a token refresh is not a geocode and must not consume a geocode unit. | Signing a Mappls plan. |
| G3 | **Two of three price cards carry placeholder rates.** Ola (25 paise/call overage) and Mappls (20 paise/call, 10k free) are conservative guesses; only Google's ₹0.44/call (\$5/1,000 at ₹88/USD) is real. `scripts/seed_price_cards` warns on every run. | Confirming against an actual bill. Supersede with a **new card**; never edit the old row. |
| G4 | **Google's free tier is seeded low on purpose** — 10,000 (global Essentials), not the 70,000 an India-billed account gets. Understating the free tier overstates our cost, which is the safe direction. | Confirm the Indian billing entity, then add a new card at 70,000. |
| G5 | **`sites` upsert is not in CI.** The table carries a PostGIS geometry, so it cannot be created on SQLite. All judgement (`combine`, `choose_pincode`) is pure and unit-tested; the round-trip, the generated `geom` and its read-only guarantee are covered by `scripts/resolve_site --selftest`, which needs a database. | Run the selftest after every reference reload. A CI Postgres service would close it properly. |
| G6 | **`npm run lint` is broken** — no eslint config exists at all. Pre-existing; CI does not run it, so nothing is currently failing because of it. | Add a flat config, or remove the script so it stops implying coverage. |
| G7 | **C.2 is partly shipped.** Cost per resolved address and the free-share funnel are live. % of cap, burn-rate projection, the Google-escalation list in the console, and tie/disagreement aggregation are not. | Part C.2 proper. |
| G8 | **Occupancy reconstruction is designed, not demonstrated.** ② plus `poll_runs` liveness should reconstruct occupancy exactly without materialising 288 ticks/day. `replay()` is tested; the occupancy query itself does not exist. | First real polling data (B3). |
| G9 | **Row-count sizing is an estimate.** ~1M rows/day for ②, ~30× for every-observation, resting on ~100k public connectors. The **ratio** is the robust part; the absolute numbers are not measured. | Real volume. |

---

## 4. 🧭 Decisions — settled, with the reason, so they are not relitigated

### Storage and capture

- **Raw archive ① then derived events ②, committed separately.** Capture before
  interpretation. A derivation bug then costs a recompute, not a day of history.
- **Never change-detect at ingest.** Only-on-change straight from the network is
  presence-blind *and* irreversible. Detection is a derivation over ①, replayable
  by `scripts/rederive.py`.
- **Disappearance is derived only from a successful fetch.** One HTTP 500 must
  never append a fleet-wide vanishing to an append-only table. This is the single
  most dangerous failure in the poller design and has a test in both directions.
- **A vanished connector records `unknown`, not `offline`.** We stopped being
  told; we did not learn it went offline.
- **Rejected: the optional hourly heartbeat snapshot.** 2.4M rows/day at 100k
  connectors against a ~1M/day target, for information ②+liveness already carries.
- **Zero events is healthy.** ② is a change log. The console highlights *pages
  archived* and *connectors seen* instead, because those are the numbers that
  must be non-zero on a live source.

### Resolution

- **`ST_Contains`, not `ST_Intersects`.** A point on a shared edge would match two
  districts and trip the overlap refusal; with Contains it matches zero, falls to
  nearest at 0.0 m, and lands in the branch built for it.
- **Boundary ambiguity is "another district within 500 m"**, not "within 500 m of
  any line". A coastline is not a tariff boundary. Cheaper, index-friendly, and it
  hands the report the neighbour's name and state.
- **Overlapping polygons are refused, not arbitrated.** Whichever district were
  chosen would be wrong for half the sites in the overlap.
- **Confidence is `high|medium|low` plus a `reasons` tuple, never a number.** A
  `0.83` implies a calibration nobody has done. One downgrade per doubt, never
  recovers, and a test asserts every downgrade carries a reason.
- **`ogr2ogr` dropped.** The source is GeoParquet, so the loader reads WKB
  directly — one fewer system dependency on the VPS.
- **The cascade stops at the first confident hit.** Calling every level produces
  identical output and a 4× bill, and makes "≥90% without Google" unmeasurable.
- **Escalation triggers on doubt, not on failure alone.** Consequence of the
  above: with strict stop-at-first, two geocoders never both answer, so the >2 km
  rule could never fire. Doubt = the matched PIN contradicts the supplied one, or
  the provider flags a partial match. "No PIN to check against" is deliberately
  **not** doubt — escalating on it would send nearly every address to a paid level.
- **At most two opinions (`MAX_OPINIONS`).** A third costs money to break a tie we
  have already decided goes to a human rather than to a vote.
- **A site records one confidence: the weaker of the cascade's and 1.4's.** They
  are different claims. A Google hit whose PIN matches (high) that lands 3 km
  outside every polygon and resolves by nearest-fallback (low) is a **low**
  confidence site.
- **`sites.geom` is a generated column.** `GENERATED ALWAYS AS ... STORED` from
  lat/lng, so it cannot drift. Postgres refuses direct writes to it — verified.
- **An unresolved address is still a site.** PLAN 1.6's "log the site anyway",
  applied a step earlier. It is a lead, and it is the row L6's answer lands in.
- **One site row per distinct place, with a `requests` counter.** Two customers
  pasting the same address are one site asked about twice; Part 2's context
  features are expensive. The counter is the expansion-roadmap signal.
- **PIN preference is a decision, not a coalesce.** Customer's PIN → the polygon
  at the point *only if exactly one* → the geocoder's own postcode last. Several
  overlapping PIN polygons is India Post's delivery rounds showing through, and
  picking one invents a fact.

### Money and access

- **Three locks before a paid call.** (1) cap-before-boot in `config.py`,
  (2) client-side counter that *refuses* rather than warns, (3) a price card —
  `build_cascade` will not assemble a paid level that cannot be priced.
- **Metering is structural, not remembered.** `build_cascade` is the only place a
  paid geocoder is constructed, and it constructs them wrapped. An unmetered
  provider is not one that skips its row; it is one the cascade cannot reach.
- **A cap writes its own `capped` row.** Otherwise a self-inflicted refusal is
  indistinguishable from a provider outage.
- **Cache hits are priced at the cost they avoided.** That is how "median cascade
  cost per address = ₹0" is evidenced rather than asserted.
- **Guard at the router, not per-endpoint.** A test walks the live OpenAPI schema
  and asserts every non-public `/api/internal` path returns 401, so a panel added
  next month is covered without anyone remembering.
- **Unconfigured means 503, never 200.** "We have not chosen a password" must not
  mean "anyone may read CPO terms".

---

## 5. 🐛 Defects found and fixed — worth remembering, they recur

| | Defect | Root cause |
|---|---|---|
| D1 | Cache-wipe: `update_connector_state(seen=…)` set every seen-but-unchanged connector to `unknown` each cycle | A design error of mine, caught while writing the test. Fixed by deleting `last_seen_at` entirely — which also removed ~100k upserts per cycle. |
| D2 | Flaky security test, ~1 run in 8: `test_a_tampered_session_is_rejected` | **Not** the first diagnosis (that the appended char matched). Base64's final character carries padding bits, so several different characters decode to identical bytes — the "tampered" token was frequently byte-identical, meaning the test asserted a *valid* session was rejected. Replaced with 5 deterministic mutations. A security test that cries wolf gets ignored. |
| D3 | FastAPI returned 422 on every guarded request in tests | The `get_settings` override had `**kwargs`, which FastAPI introspected as query parameters. |
| D4 | Login cookie silently dropped by TestClient | `secure=` was set for `env="test"` over plain http. Now `secure = (env == "prod")`, with an explicit prod-Secure test. |
| D5 | `ST_MakeValid` returned a GeometryCollection, rejected by the MULTIPOLYGON column | Fixed with `ST_Multi(ST_CollectionExtract(…, 3))`. **13 of 819 district features were published invalid** — the repair is now counted, not swallowed. |
| D6 | Pincode parquet carried India Post circle/region/division, not state/district | Columns renamed to `postal_*` so nobody joins a postal circle to a state. |
| D7 | `app/models/__init__.py` was missing a model import | The file's own docstring warns: a model not imported there is a migration that silently does not get written. |
| D8 | `alembic check` was permanently red | Every monthly partition child looks like a table with no model, so autogenerate proposed dropping all 21 — and it would worsen every month until nobody read it. Filtered in `env.py`. |
| D9 | `choose_pincode` reached into `raw["address"]["postcode"]` | Nominatim's shape; would silently return nothing for Ola/Mappls/Google. `GeocodeOutcome` now carries `postcode`, filled by each parser. |
| D10 | A selftest check passed vacuously | With Nominatim down nothing had coordinates, so "geom matches lat/lng" verified nothing. It now places a known point first and fails when there is nothing to check. |
| D11 | Leaflet added 160 kB to the main bundle | The public report would have carried a mapping library so one operator could place pins. Lazy-loaded. |
| D12 | The Lookup panel's step 1 named the **overriding** district, not the one the containment query returned | A trace reconstructed from `Resolution` could not see what a `pin_override` had replaced, so it described a query returning a district that query never saw. `Resolution` now carries `overridden_district`; a test asserts step 1 names Ernakulam while the answer says Thrissur. Exactly the drift the module docstring warns about. |
| D13 | Two console-auth tests passed only while `.env` had no console password | `Settings()` reads `.env` from disk, so "unconfigured console returns 503" was asserting against the developer's machine. Both now pass `_env_file=None`. Found by configuring a console locally — i.e. by the first person to use the feature. |

---

## 6. Findings by plan part

### PART 0 — Poller
Built and tested; **produces nothing** until B3. Three commits per cycle (run
row → raw pages → derived transitions). A fetch failure is `FAILED` with nothing
derived; a derivation failure is `PARTIAL` with the archive intact. Append-only
enforced by DB `RULES` on `api_usage_events`, `charger_status_events` and
`poll_raw_payloads` — ⚠️ **`TRUNCATE` bypasses rules.** `poll_runs` and
`connector_state` are a ledger and a cache, updated in place deliberately.
*Still open:* VPS deploy, endpoint discovery, rate-limit tuning, 0.2, 0.3.

### PART 1.1–1.2 — Infrastructure and reference layers
Complete except B4. 783 district polygons across all 36 states/UTs (Telangana
and Ladakh included), 19,312 PIN polygons. District polygons carry **LGD codes
natively**, which removed name-matching from the critical path. Provenance per
layer (URL, SHA-256, licence, feature count, fetch time) feeds C.5's data-vintage
row. The overlap audit found **one pair at 1.06 m²** — a shared-edge digitisation
sliver, below the 1000 m² material threshold, reported but not a failure.

### PART 1.3 — Geocoding cascade
All seven levels built. L0–L2 free, L3–L5 metered, L6 queue with a Leaflet panel.
Blocked live by B1; see G1, G2, G3, G4 for what is unverified.
⚠️ Tiles come from `tile.openstreetmap.org`, so the **viewport of an address
under review leaves the building**. Acceptable for an internal console; point
`TILE_URL` at a self-hosted renderer when one exists.

### PART 1.4 — Point-in-polygon
Complete and verified live. Selftest 9/9. Walayar on NH-544 → Palakkad,
`medium`, neighbour **Coimbatore (Tamil Nadu) at 87 m** — two SERCs, exactly the
case the ambiguity flag exists for. PIN override verified: Kochi coordinates +
PIN 680001 → Thrissur, `low`.

### PART 1.5 — `sites`
Complete except the two deliberate NULLs (`urban_rural` → B4, `data_tier` → 1.6)
and G5. Verified live: Kochi `9.9312, 76.2673` + PIN `682035` → **Ernakulam
(555)**, `contained`, confidence **low** — the point actually sits in PIN 682005,
so 1.4 records the conflict, declines to override (same district either way), and
downgrades; the site inherits the weaker label.

### PART 1.6 — Tier gate — **next**
Not started. What it needs and what it unblocks:

- `data_coverage(lgd_district_code, tier, has_tariff_data, has_competitor_poll,
  has_vahan_data, osm_road_quality)`.
- ⚠️ **Every one of those four evidence columns is currently `false` for every
  district.** No tariffs (0.2), no polling (B3), no VAHAN (4.1), no OSM import
  (2.1). So a tier derived honestly from evidence is Tier 3 everywhere today —
  which is the correct answer and needs to be stated rather than worked around
  by hardcoding "KL+TN = Tier 1".
- It fills `sites.data_tier`, and `tier > 1` → waitlist **while still logging the
  site**. `sites.requests` is already the demand counter that makes the waitlist
  an expansion roadmap.
- Also feeds C.5: *which uncovered district has the most waitlisted pins*.

### PARTS 2–8, G — not started
Their `PLAN.md` ⚠️ markers stand as written and are not duplicated here. The
three most likely to be regretted if skipped:
- **2.1 median access direction** — a site on the wrong side of a divided highway
  loses about half its addressable traffic.
- **4.4 selection-bias hunt** — without ≥20 confirmed failed/closed stations the
  model learns "everywhere is fine", and telling someone their site is bad is the
  entire product.
- **Part 7 attribution** — marked DO NOT DEFER; the honesty firewall ships with
  the first commission, not after.

### PART C — Console
C.0 and C.1 complete. C.2 partly (G7). C.3–C.6 not started.
⚠️ **Panels are read-only today**, so C.0's "writes are attributed to the
operator" rule has not yet been tested by a real write — the manual queue's
resolve/reject endpoints are the first, and they do record `resolved_by`.

---

## 7. Standing rules that keep being load-bearing

1. **Two locks for polling**: authorised in `sources.py` *and* configured. Config
   alone is never consent.
2. **Three locks for spending**: provider-console cap, client-side counter, price
   card.
3. **Never overwrite an effective-dated row** — tariffs, subsidies, price cards.
   Insert a new one and close the old range.
4. **Refuse rather than guess.** The crosswalk, the point-in-polygon resolver and
   the cascade all return "ask a human" as a first-class answer. L6 is what makes
   that affordable.
5. **A test that passes vacuously, or flakes, is worse than no test** — see D2 and
   D10. Both trained a reader to ignore a signal.
