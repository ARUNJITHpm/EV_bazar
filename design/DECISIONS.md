# DECISIONS — the three calls IMPLEMENT.md required, argued from this repo

Written after reading AGENTS.md, OVERVIEW.md, STACK.md, FINDINGS.md,
INTEGRATION.md, the brand folder, and both reference builds. Each answer
cites what is already shipped, not what the design assumed. Where the design
and the repo disagree, the repo's shipped decision wins and the deviation is
recorded here rather than silently applied.

---

## (a) The point-estimate violation — resolved by splitting the two claims

The designed result screen shows **"2.1% effective return"**. That number is
the output of a demand prediction (a return presumes a utilisation), and
AGENTS.md constraint 6 forbids the point estimate while rule 5 requires any
model run to write a `predictions` row. The public flow deliberately runs
**no model** — that is what lets it exist before the poller has data, and why
`teaser.py`'s docstring says it writes no predictions row.

So the fix is not "put a band around 2.1%". It is to recognise the design
conflated two different claims:

1. **What the site must do** — breakeven utilisation. Pure arithmetic over
   the state's typed tariff (`compute_teaser`), already live, already the
   result of `POST /api/internal/assess`. A threshold, not an estimate;
   constraint 6 does not touch it. **This is the free result screen's hero
   number.**
2. **What the site will do** — projected utilisation and therefore return.
   A model output, banded P10–P90, written to `predictions`, stamped with
   versions. This exists only in the report pipeline (synthetic v0 → stored
   JSONB payload) and stays there. **The report is where the band lives**,
   and the demo report already renders it (HeroNumber's P10–P90 bar against
   the breakeven tick — the same pattern as the reference's section 08).

What can the roi_engine actually supply? Nothing banded on its own: it is
pure arithmetic over a supplied kWh ramp. Bands come from `domain/demand/`
(synthetic v0 widens with missing inputs). Lifting the band onto the free
screen would mean running the demand model per public pin — predictions-row
writes for every anonymous click, version stamps, and the free product
becoming the paid one. Rejected.

The fixed-deposit comparison survives, but **in the report** (its return
figure is banded there; the FD rate genuinely is a point value). On the free
result screen the FD line is dropped, because there is no return figure to
set beside it without a model.

The result screen therefore ends on: the breakeven figure, the tap echoes
(what moved, what did not, what was skipped), the data-tier line, and the
report as the next step. That is the shipped teaser, re-dressed in the new
flow — not a redesign of the product.

## (b) Verdict versus tier — the business call was already made, in code

INTEGRATION.md §6 says this needs a business decision. It was made on
2026-08-20 when `POST /api/internal/assess` shipped **open, BY DECISION**
(it is in `tests/test_console_auth.py` PUBLIC_PATHS with a comment): the
public flow returns **tier + teaser + waitlist**, and the verdict —
BUILD / DON'T BUILD with the band — is the report's, a separate stored
artifact (`GET /api/internal/reports/{id}`, demo KL-TVM-DEMO-001 live).

So: the designed result screen is redesigned around tier + teaser (per (a)),
`AssessOut` needs **no ROI outputs added**, and the full verdict stays
gated behind the report. The flow's closing CTA points at the demo report —
"read a real one end to end" — which is also the launch checklist's own
highest-priority asset.

The reference's "blocker" (Task 3: *every assessment route is behind console
session auth — stop*) is stale: the assess endpoint is already public.
What genuinely does not exist yet is **rate limiting** on it. The write
amplification is bounded (same 5-dp pin upserts one row and bumps a
counter), but distinct random pins create rows. Logged here as the one piece
of backend work the public launch still wants; not silently built now.

## (c) Mapbox versus Leaflet — Leaflet, and the repo makes it a short argument

Keep Leaflet. Three repo reasons, one of them structural:

1. **Rule 10 cannot be satisfied from a browser.** Every metered external
   call must write an `api_usage_events` row; Mapbox GL sessions and
   geocoder calls bill from the client, where no meter exists. Constraint 7
   (hard cap + client-side counter before any paid call) has no
   implementation path for a public visitor's browser. Leaflet + OSM tiles
   has no meter because it has no bill.
2. **The bundle already paid for Leaflet** (lazy-loaded per FINDINGS D11).
   Mapbox GL JS is ~250 KB gzipped on top, for the same pin-drop.
3. **The geocoder buys nothing.** The repo has its own cascade for records,
   and the /assess search box is navigation-only Nominatim by documented
   decision (nothing from search is trusted; the pin is the sole input).

The published Mapbox dark style is kept as a **colour specification**: the
flow's background map is OSM tiles dimmed into the `--cw-ground` dark
surface (low opacity over the page ground, exactly the reference's
`BackgroundMap` treatment), and the locate map stays full-colour because
there the map is the interface.

---

## Deviations from the reference flow — each with its reason

- **The question set is the engine's, not the reference's.** The reference
  asks transformer-distance and transformer-capacity (sliders) and land
  *size*; `compute_teaser` reads none of those. Collecting inputs the
  arithmetic cannot use, on a product whose thesis is honesty, is theater —
  and AGENTS.md's sanctioned-load rule (kVA of the *connection*, never the
  transformer's rating) makes "how big is the transformer" actively
  dangerous to conflate. The flow asks what the engine reads: existing
  connection (+ sanctioned kVA slider when yes), transformer on site,
  land owned/leased — plus **intent** (income / fleet / visitors), kept
  from the design because it is echoed honestly ("changes which operators
  suit you — it does not move this arithmetic") and it is the one question
  the CPO-matching half of the positioning needs. `AssessIn` gains the
  optional `intent` field; `api/internal` is free to reshape.
- **The confirmation card uses our own resolver, and logging it is a
  feature.** `GET /api/internal/lookup/point` is console-auth'd; instead
  the locate step's "Is this the spot?" card comes from `POST /assess`
  with no taps — which logs the lead *at the moment the pin is confirmed*,
  so an owner who abandons mid-questions is still a captured lead (the
  shipped "every pin logs a sites row FIRST" doctrine, now worth more).
  The finishing step re-POSTs the same pin with the taps; the same
  normalised key upserts one site and bumps `requests`. Road class stays
  "Not yet determined" on the card — honest; it arrives with the report's
  context scrape.
- **The working screen shows the real request, however short.** The
  reference's staged checklist runs on `setTimeout(900 + random*900)` — the
  padded progress bar its own comment forbids. Our real work is one POST
  (~1–3 s); the screen names the real sources being consulted and completes
  when the response lands. No timers.
- **Numbers the repo does not have render bracketed, per IMPLEMENT.md.**
  "[340] sites assessed", "[38%] advised against", "[XX%]" accuracy,
  "[1,000+]" owners. Partner and hardware names are NOT shipped (no written
  permission — IMPLEMENT.md's own outstanding list); bracketed slots hold
  their place. Un-bracketing any of these is a human step, never an edit.
- **No ambient video** (KlingAI watermark — cut, per assets/NOTE.txt).
  No `hello@chargeworthy.in` contact link until the domain exists.
- **Webfonts are progressive enhancement**: one Google Fonts stylesheet
  (Archivo, IBM Plex Mono), full system fallback stacks in the tokens, the
  same approach as the reference report.

## Task 4 (the report) — recommendation, deliberately not built in this pass

The repo's storage model stands (JSONB served verbatim; the reference's
build-report.mjs is rejected by INTEGRATION.md itself). On the eleven-vs-
seven sections:

- **Adopt now, cheaply**: fold *How this site was judged* (thresholds
  before data) into the Verdict section's opening, and *Disclosure &
  independence* into the report footer — INTEGRATION.md's own suggestion,
  no section-count change, keeps AGENTS.md's 7-component mirror intact.
- **Adopt when the payload next changes shape**: *What would change this
  verdict*. It is the strongest trust device in the reference and it needs
  real threshold data per factor — which arrives with the context layer
  (2.1) and the calibrated model, not from a template.
- **Already have**: Provenance (section 7 today) and the confidence band
  (HeroNumber, promoted rather than demoted — the demo's audience today is
  technical; revisit placement when a lay buyer exists).
- The greyscale rule (sign + word direction markers, nothing meaning-bearing
  by colour alone) and the reference's print CSS details (thead repeat,
  break-inside, provenance on its own page) apply whenever the report is
  next touched; `print.css` already carries most of them.

Restyling the live report onto the paper palette is follow-up work: it must
move in lockstep with a payload regeneration (the demo's hand-set
`data_tier=1` wrinkle gets fixed in the same pass) and it touches all seven
mirrored components. Nothing in the new public surface depends on it.

## What ships in this pass

1. This file.
2. `design/` enters git; the HF mirror strips it (binaries + it is not part
   of the deployed app).
3. Tokens: the `--cw-*` palette appended to `frontend/src/styles/tokens.css`
   (the only raw-hex file), wired into the Tailwind theme.
4. `features/public/` route group: the Chargeworthy landing at `/`.
5. The assessment flow at `/assess/*`: locate → connection (+kVA) →
   transformer → land → intent → working → result, one question per screen,
   no dropdowns, 56 px targets, browser back works, state survives refresh,
   the map continuous behind every step, wired to the real `POST /assess`.
6. Backend: `AssessIn.intent` + its honest tap echo; OpenAPI + schema.d.ts
   regenerated.
