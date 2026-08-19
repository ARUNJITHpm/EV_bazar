# Brief for Fable — the EV_Bazar customer-facing report & acquisition site

_Paste this whole file into a fresh Fable session opened in `D:\EV_Bazar`. It tells you what
already exists, what I want built, and the hard rules you may not break. Read the referenced
docs before proposing anything._

---

## 0. Before you write a line of code — read these, in this order

1. `OVERVIEW.md` — the product vision, the breakeven math, the report anatomy, the revenue model.
2. `PLAN.md` — Parts **2** (Context/Location layer), **4** (Demand), **5** (Report UI), **G** (Revenue).
3. `AGENTS.md` — the hard constraints. Line 19 is the one that governs everything you build.
4. `STACK.md` §5 — the frontend structure and the planned `features/report/` components.
5. `FINDINGS.md` — the honest gap list, so you don't design around data that isn't there.
6. `CPO_SOURCES.md` — where live-occupancy data will eventually come from (and why it's not here yet).

**I do not want you to reinvent the vision. It already exists and I like it. I want you to design and
build the customer-facing experience on top of it, and fill three specific gaps.** If anything below
contradicts `OVERVIEW.md`/`PLAN.md`, flag it — don't silently diverge.

**Give me the idea first.** Before building, come back with a concept: the report layout, the
public funnel, the visual direction, and how you'll handle the three gaps in §3. I want to react to
the idea before you write the UI.

---

## 1. What EV_Bazar is (one paragraph)

A customer drops a pin on a candidate location for an EV charging station. EV_Bazar returns a
production-grade **site-assessment report** that answers three questions: *what utilisation will
this site realistically get, what utilisation does it need to break even, and which charge-point
operator (CPO) makes the economics work.* The hero number is **breakeven utilisation** and the
margin of safety against it. The retail report is the top of a funnel; the business is selling
portfolio screening and underwriting signals to CPOs, lenders/NBFCs, OMC dealer programs and
fleets (`OVERVIEW.md` revenue ladder, `PLAN.md` Part G).

---

## 2. The job

Design and build the **customer-facing surface** that does not exist yet:

1. **The site-assessment report** — the 7-section report described in `OVERVIEW.md` §8 (Report
   anatomy). Today `frontend/src/features/report/` is empty and `/console/reports` is a placeholder.
   Build it for real, wired to the **actual** ROI engine (`app/domain/roi/engine.py`, already built
   and tested).
2. **The public acquisition funnel** — `PLAN.md` G.2: a public "drop a pin → breakeven utilisation
   in 30 seconds" teaser. This is customer acquisition. It must feel top-tier, but honest (see §4).
3. **Fill the three gaps in §3** so the whole thing is demonstrable end-to-end **today**, on the
   real data we have plus honest stand-ins for what we don't.

Make it production-grade in look and feel. This is what a CPO expansion lead, a bank's underwriter,
or a site owner sees first.

---

## 3. The three gaps you are filling

| Gap | State today | What to do |
|---|---|---|
| **A. Occupancy / usage** | Zero rows — no CPO source is authorised yet (blocker B3). This is the "moat" data and it isn't here. | Build a **clearly-labeled synthetic usage stopgap** (see §5). It demonstrates the pipeline. It is never shown to a customer as a real prediction. |
| **B. Location / traffic layer** | Spec only. `PLAN.md` §2.1–2.3 and §4.2 define the formula and road/POI features; none of it is built. No traffic-count data exists anywhere. | Build the location layer from **free** data sources (see §6) and feed it into the heuristic in `PLAN.md` §4.2. |
| **C. Report + funnel UI** | Doesn't exist. | Build it (§2). |

You may **defer live-occupancy scraping** (Tata Power / Statiq / chargeMOD app capture). It's
gated on a human authorisation decision (`CPO_SOURCES.md`, `app/domain/polling/sources.py`) and is
not blocking the customer-facing work. Design the report so that when real occupancy *does* arrive,
it drops into the same slot the synthetic stopgap occupies now.

---

## 4. Non-negotiable constraints — the honesty firewall

These come from `AGENTS.md` and `OVERVIEW.md`. Breaking them breaks the product's whole premise.

- **No model — including you — ever outputs a financial number.** Payback, IRR, NPV, revenue and
  breakeven come **only** from `app/domain/roi/engine.py`, a pure function. The UI *renders* those
  numbers; it never invents or "estimates" them. (`AGENTS.md:19`, `OVERVIEW.md:34`)
- **Every prediction is a distribution: P10 / P50 / P90, never a point estimate.** The verdict is
  driven by **P10** (the conservative case), never P50. (`OVERVIEW.md:63`)
- **Synthetic usage is labeled synthetic** — it appears in the assumption ledger with a ⚠️, marked
  as a placeholder, and is visually distinct from measured data. A customer must never mistake it
  for a real reading. (This is how §5 stays inside the firewall.)
- **"Telling someone their site is bad *is* the product."** (`OVERVIEW.md:63`) Don't design a
  hype tool that always says "Build." A "Don't build" verdict, well-argued, is a feature.
- **Provenance everywhere.** Every number carries its source, version, and data vintage
  (`OVERVIEW.md` §8 sections 6–7: Assumption Ledger + Provenance).

---

## 5. The synthetic usage stopgap — how to do it without lying

Goal: let the ROI engine and report run end-to-end before real occupancy exists, without
fabricating a "reading."

- Make it a **deterministic, seeded function** — not random noise — of signals we actually have:
  site **archetype** (highway / mall / urban fleet / residential), **VAHAN EV-registration density**
  in the catchment (real), and **competitor density/specs** nearby (real, 1,788 stations on hand).
  Same inputs → same output, so reports are reproducible.
- Output it as a **utilisation distribution (P10/P50/P90)**, matching the real demand-model
  interface, so swapping in real poller data later is a data-source change, not a UI change.
- **Stamp it** `source = "synthetic_v0"` with a version, surface it in the assumption ledger with a
  ⚠️, and render it in a visually distinct "modelled, not measured" style in the report.
- Put it behind the same interface the real demand model (`PLAN.md` §4.3, `app/domain/demand/`,
  currently empty) will implement, so it's a drop-in placeholder, not a fork.

Deliver this as a small pure module (mirroring how `roi/engine.py` is structured) with tests.

---

## 6. Location & traffic — the free-data strategy (this answers "is there a free traffic API?")

Short answer: **road-proximity and catchment are fully free; live congestion is free at low volume;
raw vehicle counts (AADT) have no free API for India and must be proxied.** Build the location
layer (`PLAN.md` §2) on this:

| Question the report needs to answer | Free source | Notes |
|---|---|---|
| Is the plot on a main road? Distance to nearest NH/SH? Which side of a divided highway? | **OpenStreetMap via Overpass API** (no key, no cap) | Query `highway=motorway\|trunk\|primary\|secondary` near the pin; compute distance + **median access direction** (`PLAN.md:223` — a site on the wrong side of a divided highway loses ~half its traffic; this is a real feature, not a nicety). |
| How many EVs / people are within a 5–10 min drive? (catchment / demand-in-reach) | **OpenRouteService isochrone API** (free 500/day) | Draw the drive-time polygon, then overlay **VAHAN EV-registration density** (real data we have) and **POI counts** inside it. This is the demand signal that's actually defensible. |
| How busy is this road / corridor? | **TomTom Traffic Flow API** (free ~2,500 req/day) or **HERE** / **Mapbox** free tiers | Gives typical speed & congestion, *not* vehicle counts. A "high-congestion arterial" flag is a fine proxy for "high exposure." |
| POI gravity / dwell anchors (does anything hold a driver 30–45 min?) | **OSM/Overpass** POI tags | `PLAN.md:229` — count F&B, retail, hotels, malls, offices in 500m/1km/3km rings; a DC fast charger next to nothing is a charger nobody waits at. |
| Raw traffic volume (AADT) | **No free real-time API for India.** data.gov.in has patchy static sets; real counts are sold by vendors. | **Proxy it**, don't buy it: OSM road class × POI density × population (WorldPop/Census) × VAHAN EV density. Be explicit in the ledger that traffic is *modelled from proxies*, not measured. |

Wire the outputs into the existing heuristic (`PLAN.md:304`):
`score = w1·traffic + w2·poi_dwell + w3·(−competition) + w4·vahan_growth + w5·grid_ease + w6·access_penalty`
— coefficients in a **versioned config file, never hardcoded**, and the score maps to a kWh/
utilisation **distribution**, not a point value (`PLAN.md:307-310`).

Respect each source's terms: OSM/ORS/TomTom free tiers are fine to store; **Google Places
availability may not be cached into a time series** (`CPO_SOURCES.md`). Meter any keyed API through
the existing spend ledger (`api_usage_events`).

---

## 7. What data you actually have (real, today)

- **Geography:** 783 district polygons + 19,312 pincode polygons + state outlines (LGD-coded, PostGIS).
  Districts are the join key of the whole product.
- **Demand:** `vahan_ev_registrations` — EV registrations for Kerala + Tamil Nadu, per calendar year
  2023–2026, by vehicle class, as a time series of snapshots (growth is computable, not just level).
- **Competitors:** 1,788 charging stations (Open Charge Map + GoEC + Zeon) with specs, connectors,
  power — **inventory, not occupancy**.
- **Tariffs:** electricity tariff rows for KL + TN (gazette-exact for KL), plus subsidy rules.
- **ROI engine:** `app/domain/roi/engine.py` — built, pure, 43 tests, `economics_version 0.1.0`.
- **What's missing:** occupancy (gap A), the location layer (gap B), the report/funnel UI (gap C).

---

## 8. The report to design (7 sections — `OVERVIEW.md` §8)

1. **VERDICT** — Build / Conditional / Don't (driven by P10).
2. **THE NUMBER** — Breakeven utilisation, predicted P10–P90 band, margin of safety (with ⚠️ when negative).
3. **SITE PROFILE** — archetype, comparables, competitor occupancy, **road/access/catchment** (your new §6 layer).
4. **FINANCIALS** — 3 scenarios · NPV · IRR · payback · 10-yr cashflow — **all from the ROI engine**.
5. **CPO COMPARISON** — ranked table, IRR recomputed per operator.
6. **ASSUMPTION LEDGER** — every default, ⚠️ on anything unverified or synthetic.
7. **PROVENANCE** — version stamps + data vintages for every input.

It must be **print-clean** (there's a `print.css`; a PDF export path is planned) and **regenerable**
(`STACK.md` Rule-1: same inputs + versions → same report).

---

## 9. UX / design direction

- **Two audiences, two front doors.** (a) A public, high-polish **acquisition funnel** — drop a pin,
  get the breakeven number in ~30 seconds, then a call-to-action. (b) The full **report** for a
  serious buyer. The existing landing page (`features/landing/`) is deliberately austere and reads
  like a technical document; the *customer* funnel should be warmer and more confident, but never
  dishonest.
- **Lead with the verdict and the one number.** Don't bury it under charts.
- **Distributions, visually.** P10–P90 bands, not single bars. Make uncertainty legible, not hidden.
- **Modelled vs measured** must be visually distinct everywhere (ties to §4 and §5).
- **A map is central** to the site profile — but the public report must stay lightweight; the mapping
  library is already lazy-loaded elsewhere (`Geocoding.tsx`) for exactly this reason.
- Trustworthy, data-dense, calm. Think "underwriting memo a bank would act on," not "growth-hack SaaS."

---

## 10. Tech you must build within (`STACK.md`, `frontend/package.json`)

- **Frontend:** Vite 7 + React 19 + TypeScript 5.7, Tailwind 4, TanStack Query + Table, react-router 7,
  **Leaflet + react-leaflet**, **recharts**, lucide-react, zod. API types are generated from
  `openapi.json` into `src/api/schema.d.ts` (CI fails on drift — regenerate, don't hand-edit).
- **Backend:** FastAPI JSON API. Money is integer paise end-to-end; `lib/money.ts` is the only place
  paise become ₹; `lib/units.ts` keeps kW and kVA apart. Reuse them.
- Follow the domain layout under `app/domain/` (a `context/`, `demand/`, `roi/` split already exists).
  New location code belongs in `app/domain/context/` (`roads.py`, `poi.py` are named-but-unbuilt in
  `STACK.md` §2).

---

## 11. Deliverables & acceptance

- The **concept first** (§0): report layout + funnel + visual direction + how you'll handle gaps A–C.
- Then: a working report route rendering all 7 sections for a real pinned KL/TN location, with real
  VAHAN + competitor + tariff data, the free location layer, and the synthetic-usage stopgap —
  every financial number coming from the ROI engine, every synthetic input labeled.
- The public "drop a pin → breakeven in 30s" funnel.
- New backend modules (location layer, synthetic demand) as pure, tested functions.
- No honesty-firewall violation anywhere (§4). If you can't answer something honestly, say so in the
  ledger — a visible "unknown" beats an invented number.

**Start by reading the docs in §0, then reply with the concept. Don't build until I've reacted to the idea.**
