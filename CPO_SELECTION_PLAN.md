# The part-wise working plan

**Temporary working file.** It holds two tracks of work in one place until each
is built or folded into `PLAN.md` and `OVERVIEW.md`. Delete it then — it is not
a document the project keeps.

Written 2026-09-06. Everything marked *today* was checked against the code on
that date; everything marked *blocked* names what blocks it.

| Track | What | State |
|---|---|---|
| **A · Parts 0–9** | Operator selection — who runs the station, and why a neighbour counts differently per operator | mostly shipped 2026-09-07 |
| **B · Part R** | The report, rebuilt to `samplereport/` — plainer money, a "what it means" column, real page chrome | **R0–R12 shipped 2026-09-09 — Track B is COMPLETE, and rule 9 is closed: migration applied, demo regenerated, render archived** |

Track B is done. **All twelve sections are rebuilt, the renderer behind rule 9
exists, and the record of it lives in the console** at `/console/report` rather
than in this file. Every decision the plan reserved for the owner has been
made. What is left is not Track B work: backend data the sections are already
shaped to receive, and two writes to the live database that are the owner's.

R11 found that every print measurement taken in this rebuild was **one page
optimistic**: `networkidle` plus `[data-report-ready]` is not enough, fonts
are still loading at that point, and Chromium then lays the document out in
fallback metrics. The three fixtures print **22 / 23 / 23**; the stored demo was 17 and is **26** since the 9 September regeneration filled section 04 out.

R12 found what this file was quietly becoming. The record of Track B had been
appended, part by part, to the `to_close` field of a single milestone in
`progress.py` until it was **37 kB — 494 lines** in a field whose job is to
name the one thing that closes a milestone. It was in the console, and nobody
was ever going to read it.

---

## Part 0 — What is promised, and what is behind it

| Promise | Where | What actually computes it |
|---|---|---|
| "Which CPO partner makes the economics work best?" | `OVERVIEW.md` §1, question 3 | nothing |
| "Match the operator … we rank our partners on charger type, revenue share and how fast they reach you for a fault, then name one" | `Landing.tsx` `STEPS[1]` | nothing |
| "Matched to the right operator, not our own" | `Landing.tsx`, trust card | nothing |
| "06 Operator comparison — ranked table, IRR recomputed per operator" | `OVERVIEW.md` §8, `report/Operators.tsx` | `spec.cpo_options`, hard-coded per report; the section prints its own "terms are placeholders" chip |
| "CPO handoff — where revenue lives" | console `Concept.tsx`, funnel step 3 | nothing |
| `cpo_terms` table, run the engine once per CPO | `PLAN.md` Part 6 | unticked; `app/domain/cpo/__init__.py` is one docstring line and no code |

**The gap is not the terms table.** Part 6 as written is a *terms* comparison:
run the ROI engine once per operator, because each changes `margin_per_kWh`,
`annual_fixed` and capex. That is correct and necessary, and it answers *which
contract pays best*.

It does not answer *which operator will get drivers onto this plug*. And that
question changes the first one, because a fee is only worth paying against the
volume the network behind it delivers. Nothing in the product models it.

---

## Part 1 — The operator factor set

The 34 factors answer **should anything be built here**. Every one of them is a
property of the land, identical whichever operator signs.

Operator fit is a different question with different inputs, and it is
**site-conditional** — the same operator scores differently at two sites 5 km
apart. So it is not a league table of operators. It is 34 site factors × N
operators, and the answer only exists for one pin at a time.

Twelve factors, grouped BY SOURCE, the same discipline `data.ts` holds the 34
to: one group is one real fetch.

### Group 1 — Network reach · source: `competitor_stations`, grouped by operator

| # | Factor | What it does to the answer |
|---|---|---|
| 1 | Stations in this district | The installed base that already has this operator's app on the phone. Their app is a demand channel; a network with no district presence has no channel here. |
| 2 | Stations in this state | Service depth and spares. A network with three stations in the state has no engineer within reach of a fault. |
| 3 | **Same-operator stations within 3 km** | **Cannibalisation.** Their own app routes their own drivers between their own plugs. Nearby stations *of the operator you sign with* split your volume in a way a rival's station does not. |
| 4 | Same-operator stations within 10 km | The same effect, weaker — worth showing because a 4 km station is invisible to factor 3 and still real. |

Factor 3 is the whole idea. **The same nearby station means a different thing
depending on which operator you sign with.** A GoEC charger 1 km away is
competition for everybody. A chargeMOD charger 1 km away is competition for
everybody *plus a demand split for you specifically, if you sign chargeMOD.*
The report today counts nearby stations once, operator-blind, and so cannot say
this.

### Group 2 — Demand channel · source: VAHAN, this district

| # | Factor | What it does to the answer |
|---|---|---|
| 5 | District EV registrations against the operator's district presence | How many drivers exist here, and what share of them this network plausibly reaches. Rising registrations grow every operator's channel; they do not grow it equally. |
| 6 | Connector fit against the district's registration mix | A two-wheeler-heavy district and a 4W DC-only network is a mismatch that no revenue share fixes. `VahanContext.two_wheeler_share` already carries the mix. |

### Group 3 — Measured behaviour · deferred (later stage: status scraping)

Factors 7 and 8 need charger status read from CPO apps, which is not part of the
initial stage (`OVERVIEW.md`, "Later stage: status scraping"). They are not
scored and not shown; the report says so.

| # | Factor | What it does to the answer |
|---|---|---|
| 7 | Measured uptime, per operator | Deferred. Would be our observation, never their claim. |
| 8 | Observed usage at their nearby stations | Deferred. Would turn cannibalisation from an inference into a measurement. |

### Group 4 — Interoperability · source: `sources.py`, OCPI/UEI status

| # | Factor | What it does to the answer |
|---|---|---|
| 9 | Roaming (OCPI / UEI) | A roaming network is reachable from other apps, which widens the channel and partly offsets a small installed base. `CPO_SOURCES.md` already records who roams. |
| 10 | Reservation and in-app routing | Features that actively send a driver to a plug rather than waiting to be found. Research-grade; defer. |

### Group 5 — Commercial terms · source: `cpo_terms`, human-entered, effective-dated

| # | Factor | What it does to the answer |
|---|---|---|
| 11 | Revenue share / ₹ per kWh | Moves `margin_per_kWh`. Already the engine's input. |
| 12 | Platform fee, AMC, hardware bundled or BYO, minimum guarantee, tenure | Moves `annual_fixed` and capex. |

### What can be computed today

| Factors | State | Why |
|---|---|---|
| 1 – 4 | **Today.** No new fetch, no new external source. | `competitor_stations` already carries `operator`, `lgd_state_code`, `lgd_district_code` and a GiST-indexed `geom`. One `GROUP BY` and one `ST_DWithin` away. |
| 5 – 6 | **Today.** | VAHAN is in every report already (`district_vahan`). |
| 7 – 8 | **Deferred** to the later stage (status scraping is off). | Say so; do not estimate uptime. |
| 9 | Mostly known, needs restructuring. | `sources.py` knows roaming per *source*; this needs it per *operator*. |
| 10 | Defer. | |
| 11 – 12 | **Blocked** on `PLAN.md` 0.3 (two CPO conversations) and the `cpo_terms` table. | Numbers here are never invented. |

### The thing most likely to be skipped

`competitor_stations.operator` is **verbatim from the source and not
normalised**. The same network arrives as `Zeon Charging` from Open Charge Map
and `Zeon` from `zeoncharging.com/api/stations`, under two `source` values,
because the schema deliberately keeps duplicates until the Part 2.3 dedupe.

Counting stations per operator on top of that produces confident wrong numbers
— which is worse than no numbers, and exactly the failure this product exists
to avoid. **The alias crosswalk is not a tidy-up task; it is the precondition.**
`(unattributed)` stays its own bucket and is never merged into anything.

---

## Part 2 — Data and backend

> **SHIPPED 2026-09-07: 2.1, 2.2, and the section 06 half of Part 6.** The
> smallest shippable slice from Part 8, built and measured against the real
> inventory. What follows is marked done or open, item by item.

### 2.1 Operator identity — blocks everything else — **DONE**

`app/domain/cpo/identity.py`. Pure, no DB, no network, `crosswalk.py`'s shape
with the **fuzzy tier removed**: nothing reviews an operator name, so a
near-miss would silently merge two networks. Four outcomes — exact, alias,
not-a-network, unresolved — and unresolved reports as unknown, never zero.

Measured against the whole inventory on 2026-09-07: **1,788 rows, 23 distinct
names, coverage 54.5% → 95.2%**, with **zero unresolved names remaining**. The
residual 4.8% is 86 rows the source itself declines to attribute — held apart
in `Coverage.unattributed`, because that is a fact about the feed and has no
fix, while an unresolved name is a missing alias and has exactly one.

The single biggest rule was not a name at all: Open Charge Map suffixes its
titles with the country (`GO EC (IN)`, `Chargezone (India)`), which split every
OCM row from the same operator's own feed — **45% of the inventory**.

No table, no migration. A hand-maintained map in a pure module was the smaller
and more testable half of the two, and nothing here needs a row per operator
until `cpo_terms` does.

### 2.1b What was NOT built here

- The console's operator surface, which is where unresolved names are meant to
  reach a human (Part 3.1). `coverage()` exists and nothing calls it yet.

### 2.2 Presence — `app/domain/cpo/presence.py` — **DONE**

- `operator_presence(session, *, lat, lng, lgd_district_code, lgd_state_code)`
  returns `dict[str, OperatorPresence]`. One SQL — everything in the state plus
  everything within 10 km, so a station across a district edge still counts —
  then a pure `fold_presence`, which is where every tested decision lives.
- **Duplicate rows are folded before counting.** `competitor_stations` is
  upserted by `(source, source_id)`, so one charger seen through OCM and through
  the operator's own feed is two rows by design. Counting rows would double the
  networks we cover best. Records within ~55 m of each other, under the same
  canonical operator, fold to one. It is coarse and it is not the Part 2.3
  dedupe: the residual error always over-counts, so it can make a network look
  more present than it is and never hides a station that argues against it.
- Verified against Neon on 2026-09-07. At the demo site (Kazhakkoottam) it
  returns 10 networks, and the result is the honesty rule of Part 9 working on
  real data: **chargeMOD — our own network — has 8 of its own stations within
  3 km**, the worst split of any operator on that table.

### 2.3 Terms — `cpo_terms` (PLAN 6.1) — open

- Revenue share %, ₹/kWh, platform fee, hardware bundled/BYO, AMC, minimum
  guarantee, tenure, with effective dates. Append-only, superseded not updated.
- A missing row means "no terms on file", which `Operators.tsx` already renders
  honestly. That path stays.

### 2.4 Assembly — `assemble.py` — **DONE**

- `CpoOption` gains `presence`; `CpoRow` gains the presence fields.
- The ROI engine runs once per operator exactly as now. **Presence never enters
  the engine.** Hard constraint 1 (no model output is a financial number) and
  `OVERVIEW.md` §8 (financial rank and qualitative signal side by side, never
  blended) both bite here. Presence sits in a column next to the return; it is
  never multiplied into it.
- **No composite operator score**, for the same reason `data.ts` refuses a "site
  fit score": the payload has no such field, and a single number would hide the
  weighting, which is the site owner's to choose.

### 2.5 Direction markers — **deliberately not shipped**

A `favours / against` marker needs thresholds, and report section 03's rule is
that thresholds are printed *before* the site data. Adding markers therefore
means adding operator thresholds to section 03, and those numbers are not mine
to set. Section 06 ships the counts and the mechanism instead, and lets the
reader weigh them — which is also what "never blended" already requires.

Three-way `favours / neutral / against` from fixed thresholds, the shape `_band`
already uses, printed before the data (report section 03). Proposed starting
values — **these need the owner's signature and are provisional until they
can be checked against owner-uploaded bills**:

| Factor | favours | neutral | against |
|---|---|---|---|
| Same operator within 3 km | 0 | 1 | 2 or more |
| Same operator within 10 km | 0–1 | 2–3 | 4 or more |
| Operator's district stations | 10 or more | 3–9 | under 3 |
| Operator's state stations | 50 or more | 10–49 | under 10 |

---

## Part 3 — Console — **DONE 2026-09-07**

**This is where to pick the work back up.** `/console/operators` carries a
"where operator selection stands" block listing every part below with its state,
and the Progress panel has a `6 (operators)` milestone naming what is built,
what is blocked, and by what. Both point back at this file.

### 3.1 The CPO panel is not an operator panel — **DONE**

`Cpo.tsx` + `GET /api/internal/sources` stay a source registry: *are we allowed
to poll this network* (a deferred later stage; the panel is hidden unless
`SCRAPER_ENABLED=true`).

`/console/operators` is the second surface — `GET /api/internal/operators`,
`app/domain/cpo/inventory.py`. Canonical network, stations (deduped) against raw
rows, DC-fast, districts, states; alias coverage; and **the list of raw names
that defeated the alias table**, which is the queue a human works through.

Measured on 2026-09-07: 1,788 rows, 95.2% named, 0 unresolved names, 86 rows the
source itself would not attribute. The stations/rows gap is feed overlap made
visible — Zeon 543 stations from 612 rows, GO EC 311 from 435.

### 3.2 `Concept.tsx` — the standing record — **DONE**

- New firewall rule: **"Operator fit is shown beside the money, never blended
  into it."**
- New firewall rule: **"A nearby station is counted again, per operator, because
  it means something different to each."**
- Funnel step 3 says the table "ranks operating arrangements". After this it
  ranks arrangements *at this site* — change the wording, or the panel is
  describing the old product again.
- `DATA_STRATEGY` gains a row: operator presence · derived from the competitor
  inventory · live once aliases resolve.

### 3.3 `progress.py` — **DONE**

A `6 (operators)` milestone, PARTIAL: what is built, what is not, and what each
blocker is. It names this file and `/console/operators` as the way back in.

---

## Part 4 — The public site — **DONE 2026-09-07**

`WhoRunsIt` in `Landing.tsx`, between the 34 factors and the trust cards —
because it is the SECOND question, and a site that fails the first never
reaches it. Animation D, the twelve factors with what each does, and a closing
paragraph stating which four are counted today. Operators are unnamed
throughout, per 4.4.

### 4.1 Step 02 over-promised — **narrowed**

It claimed we rank on "how fast they reach you for a fault". Nothing measures
that, and the new section says on the same page that uptime waits on the
poller — so the two contradicted each other. Step 02 now reads "charger type,
commercial terms and how much of their own network already sits around you",
which is what the report will actually show. The same edit was already made to
the explainer PDF, so both customer-facing surfaces now agree.

**Revert this if you disagree** — it is a marketing claim, not a bug fix.

### 4.1b The original options, for the record

It claims we rank on charger type, revenue share, **and how fast they reach you
for a fault**. Fault response is not measured and has no source. Two options:

- **(recommended)** narrow the claim now to what the report will actually show,
  and add response time when status data exists (a later stage); or
- keep the claim, and factor 7 becomes a launch blocker.

Leaving it as it stands is the one outcome that is not honest.

### 4.2 A new landing section, sibling to the 34 — **DONE**

"The same charger nearby can mean two different things." The twelve named, not
scored, each with what it does to the answer — and a closing paragraph naming
which four are counted today, so the section describes the method without
claiming the whole of it is built.

### 4.3 The `[1,000+]` card

It sits beside "the reason our operator comparisons are grounded in what
actually happens after commissioning" — the claim this plan makes computable.
It stays bracketed until it is.

### 4.4 Disclosure

Every operator-facing surface keeps `OVERVIEW.md` §6.3's affiliation line. A
CPO-affiliated platform that ranks CPOs is read as a funnel unless it says
otherwise on the same page.

---

## Part 5 — Animation — **DONE 2026-09-07**

### 5.1 `data.ts` gains `OPERATOR_GROUPS` — **DONE**

Twelve factors grouped 4/2/2/2/2 by source, plus `OPERATOR_CANDIDATES` and
`NEIGHBOURS` for the animation. Every figure through `illustrative()`.

### 5.2 A fourth animation — `OperatorMatched.tsx` — **DONE**

Six neighbours around one plot. They never move; only who you signed with
changes, and with it what each one means — the ones belonging to the focused
operator light up and read "splits". That is the whole argument, and it is the
one part of this a still frame cannot carry.

**The operators are unnamed** — "Network A / B / C". `Landing.tsx` promises
partner operators appear named only with written permission, and an
illustration is not an exception to that. One is flagged "our network", which
is the disclosure the report already makes.

Ends on all three side by side: the widest reach is also the nearest
competition for the same drivers, and no score settles that trade.

### 5.3 Held to the existing rules — **DONE**

No animation library — one step index on `useLoopClock`, every movement inside
a step is CSS. `prefers-reduced-motion: reduce` parks on the summary with
nothing looping. `/animation` gained panel D.

*Also fixed there:* panel B's note still described the factors as "grouped
9 / 7 / 8 / 6 / 4" — the taxonomy replaced by the BY SOURCE 12/4/8/7/3 regroup.

### 5.4 Do not extend `SiteAssessed.tsx`

It walks the 34 and ends on the verdict. The operator question comes *after* the
verdict — a site that fails never reaches it. Merging them would tell the
visitor the two are one decision, which is the misunderstanding this whole
section exists to prevent.

---

## Part 6 — The report

The one-to-one component rule holds: **twelve sections stay twelve.** Nothing
below adds a section.

| Section | Change | State |
|---|---|---|
| 03 · How this site was judged | The operator thresholds are printed here with the site thresholds. That is the section's rule — a standard shown first was not fitted to the conclusion. | open, waits on 2.5 |
| 06 · Operator comparison | **R9 replaced this**: two tables, not one. Money (terms, cash per year, return, margin at downside) and network/service (district / state, own within 3 km, own within 10 km, roaming, repair target, tie-in) never share a grid, because they are never blended into a score. | **DONE — expanded by R9** |
| 07 · Competitors | Unchanged, and deliberately: this stays the operator-blind count. 06 is where a station gets counted a second time. | done by doing nothing |
| 08 · What would change this verdict | An operator opening a station within 3 km is a checkable condition with a threshold — it belongs here. | open, waits on 2.5 |
| 10 · Assumption ledger | Alias-resolution coverage and terms vintage, both flagged unverified while they are. | **DONE** — an "Operator footprint" row, flagged, naming how many arrangements matched |
| 11 · Provenance | The operator crosswalk version, next to the existing competitor fetch stamp. | open |
| 12 · Disclosure | Restated, because 06 now ranks harder than it did. | open |

**Why only one column.** A4 less the 14mm print margins leaves about 688px. A
table wider than that is not scrolled on paper, it is cut off, so the district
and state figures went into the sentence and the table kept its proven 42rem
minimum. Measured uptime lost its column in the same pass — it is one repeated
placeholder while status scraping is deferred, and a column of one repeated string is
furniture. The field is untouched in the payload; the column comes back when
there is an observation to put in it.

**The stored demo report predates these fields.** By Rule 9 it is served
verbatim, not recomputed, so section 06 renders its counts as dashes and hides
the sentence block entirely rather than printing empty rows. Running
`uv run python -m scripts.generate_demo_report --write` fixes it — that is a
write to the live database behind a public page, so it is nobody's call but
the owner's.

---

## Part 7 — The explainer PDF

Done 2026-09-06. A new section **05 · Choosing who runs it** sits between the 34
factors and the twelve report parts; the later sections renumber to 06–09.

It carries the two-fuel-pumps analogy for the split, the six things that decide
the operator, and a caution block naming exactly what is counted today and what
is not. That block was written before any of this was built and is **still
accurate** after 2026-09-07: station counts are now real, uptime and usage
are deferred with status scraping, and terms are still never invented.
`explainer/README.md` carries the same three-line status so it stays honest as
the rest lands.

---

## Part 8 — Sequencing

```
2.1 aliases ──────┬──▶ 2.2 presence ──┬──▶ 6 · report section 06
                  │                   ├──▶ 3.1 console operators surface
                  │                   ├──▶ 5.2 fourth animation
                  │                   └──▶ 4.2 landing section
0.3 conversations ┴──▶ 2.3 cpo_terms ─┴──▶ 6 · report section 06
0.1 poller (deferred) ▶ factors 7, 8 ─────▶ 4.1 fault-response claim
```

**Smallest shippable slice: 2.1 + 2.2 + the presence columns in report section
06.** No new external source, no new key, no conversation, no metering. It uses
data already in the database and turns the report's weakest section into its
sharpest one.

> **Shipped 2026-09-07, and then the rest of the diagram.** Parts 2.1, 2.2,
> 2.4, report section 06, all of Part 3 (console), Part 4 (landing) and Part 5
> (animation). 502 backend tests green, frontend prettier/tsc/vitest green, the
> typed client regenerated, no console errors and no horizontal overflow on `/`
> or `/animation` at 1440/1100/900/640/390.
>
> **What is left, and why:**
>
> | Part | Blocked by |
> |---|---|
> | 2.3 `cpo_terms` | PLAN 0.3 — two CPO conversations. Terms are never invented. |
> | 2.5 thresholds + report 03, 08 | A decision, not code. The numbers need signing off, and section 03 prints them BEFORE the site data. |
> | Factors 7, 8 (uptime, usage) | Deferred — status scraping is a later stage. |
> | Factors 5, 6 (registrations vs presence, connector fit) | Nothing blocks these. Both halves exist; nothing joins them. |
> | Report 11, 12 | Small, unblocked: a provenance stamp and a restated disclosure. |
>
> The stored demo report still predates the payload fields, so `/report/…`
> shows dashes in section 06 until
> `uv run python -m scripts.generate_demo_report --write` is run against the
> live database — deliberately not done here.

---

## Part 9 — What this must never become

1. **No blended operator score.** Money and service quality side by side; the
   weighting is the site owner's.
2. **No model produces a financial number.** Presence is a count, not a
   multiplier on anyone's return.
3. **No operator named publicly without written permission** — bracketed slots
   hold their place until then.
4. **Our own network under the same rules, both directions** — no favouring, and
   no theatrical self-penalty either.
5. **Cannibalisation is reported even when it argues against our own network.**
   That is the test of whether any of this is real.
6. **Nothing is un-bracketed without evidence.** Un-bracketing stays a human step.

---

## Appendix — factor to source to status

| # | Factor | Source in the repo | Today |
|---|---|---|---|
| 1 | Stations in district | `competitor_stations.lgd_district_code` | **live** |
| 2 | Stations in state | `competitor_stations.lgd_state_code` | **live** |
| 3 | Same operator within 3 km | `competitor_stations.geom` + operator | **live**, and in the table |
| 4 | Same operator within 10 km | as above | **live** |
| 5 | Registrations vs presence | `district_vahan` + 2.2 | open — both halves exist, nothing joins them |
| 6 | Connector fit vs mix | `VahanContext.two_wheeler_share` | open — needs connector types per operator, which the inventory carries and the fold discards |
| 7 | Measured uptime | `charger_status_events` | deferred · later stage |
| 8 | Observed usage nearby | `charger_status_events` | deferred · later stage |
| 9 | Roaming | `sources.py`, `CPO_SOURCES.md` | needs per-operator restructure |
| 10 | Reservation / routing | none | defer |
| 11 | Revenue share | `cpo_terms` | blocked · 0.3 |
| 12 | Fees, AMC, tenure | `cpo_terms` | blocked · 0.3 |


---
---

# Track B · Part R — The report, rebuilt to the sample

Source: `samplereport/` — three 10-page A4 PDFs (`build`, `moderate`,
`do-not-build`), read 2026-09-07. They are a **sales demonstration** with
fictional figures, not a spec handed down; where they conflict with what the
engine can honestly say, the note under the part says so.

**The structure is not in question.** The sample carries the same twelve
sections in the same order as `features/report/`, so the one-to-one component
rule (AGENTS.md) survives intact. Only two are renamed in spirit — 03 "The
rules", 09 "Scenario basis" — and twelve sections still fit on ten pages
because it pairs them: 03+04, 06+07, 08+09, 10+11+12.

So this is a **re-skin plus a content upgrade**, not a restructure. Which is
why it splits cleanly into parts that each land in one sitting.

## What the sample does better, in one list

1. **Page chrome.** A running head on every page (wordmark, tagline, hairline),
   a mono section eyebrow — `04 / THE SITE • CHECKS 01-12` — and a footer
   carrying the demonstration banner and `CW-DEMO-001 / 04`. Ours has none of
   this: the demo warning is one chip at the top of a continuous scroll.
2. **A big serif sentence as each section heading.** "The money, in simple
   terms." · "Can drivers get in and out?" · "The operator changes your deal."
   Ours are small uppercase mono labels. This one change does more for the
   document than everything else on this list.
3. **A "WHAT IT MEANS" column on all 34 checks**, with the direction marker
   sitting above a plain-English consequence. Ours shows label / value / source
   / direction and never says *why the reader should care*.
4. **Plain money.** "Cash left / lost each month", "Time to recover setup
   cost", "Customer spending each month". No IRR, no NPV — the sample says
   outright, "This is not an IRR".
5. **Two thresholds, both named**: running-bill breakeven (day-to-day costs
   only) and full-cost breakeven (also recovers setup over ten years). We
   compute one.
6. **A legible threshold chart** — an axis, a labelled vertical line at the
   full-cost point, and a band from cautious to optimistic with a dot at the
   middle. Print-safe and readable at a glance.
7. **Units, not kWh.** "320 units/day … about 11 visits/day at 25 units per
   visit." One unit = one kWh sold, stated once.
8. **A concept plot schematic** — MAIN ROAD → ACCESS LANE → CONCEPT PLOT, two
   bays, one shared 60 kW charger — captioned "Concept only. Not a survey,
   route map or approved layout."
9. **`? UNVERIFIED` as a fourth direction**, in the same column as favours /
   neutral / against rather than a separate chip.
10. **Every table closes with a footnote that takes something back** — "Station
    counts do not prove uptime" · "All vehicles, not all EVs or customers" ·
    "Distance alone does not prove demand".

## The one thing NOT to copy

The sample disclaims itself as "hand-selected demonstration scenarios, not
P10/P50/P90 probabilities, a confidence interval or a trained-model forecast".

**That sentence is true of the sample and would be false of ours.** Our three
cases *are* model percentiles from `domain/demand/`. Pasting that disclaimer
into a generated report would claim less provenance than the number actually
has — dishonesty in the opposite direction, and against the intent of rule 6.

The resolution is R5: keep the percentile provenance, change only the label.

---

## R0 — Three fixture payloads, and a way to look at them — **DONE 2026-09-07**

`frontend/src/features/report/fixtures/samples.ts` and `SampleRoute.tsx`;
`/report/sample/build | moderate | dont`, lazy-loaded and unlinked.

Written as typed TS rather than `.json`: a renamed payload field then breaks
the build here too instead of arriving as `undefined` where a rupee should be.
Every figure is internally consistent with the engine's own definitions —
which is how the first finding fell out, below.

**Three things the fixtures made visible immediately.**

1. **Breakeven is running-bill breakeven, not full-cost.** `engine.py` computes
   `fixed / margin` — annual operating cost over margin per kWh, with the build
   cost nowhere in it. So a site can clear breakeven, earn a BUILD verdict, and
   still be short over ten years: Palm Junction's own downside case prints
   `BUILD` on page 1 and `₹1.94 L short` on page 2. Both are true. The document
   puts them four inches apart and reconciles them nowhere. **This is R5's
   second question, and the fixture answers half of it: the sample's full-cost
   breakeven is not a relabelling of ours, it is a second number.**
2. **The assembler produces 16 site facts, not 34.** Four groups, four facts
   each, and no "Site and amenities" group at all — while `data.ts`, the
   landing page and the explainer all promise 34 grouped 12 / 4 / 8 / 7 / 3.
   The fixtures carry the full 34 so the section can be designed at its real
   length; closing the gap is backend work nobody had written down.
3. The three verdicts tally 26 / 1 / 7, 6 / 12 / 16 and 12 / 15 / 7
   favours / against / neutral. The DON'T BUILD page carries **twelve
   favourable checks** — which is precisely the page to check hardest.

### R0, as originally planned

**Do this first.** It unblocks every part below and needs no database.

- Three `ReportPayload` JSON fixtures — build / moderate / do-not-build —
  mirroring the sample's three sites, in `frontend/src/features/report/fixtures/`.
- A dev-only route (`/report/sample/:which`) rendering `<Report>` from a
  fixture instead of a fetch. Unlinked, same idea as `/animation`.
- Why: the stored demo report is a database write nobody wants to make yet, it
  carries one verdict only, and **the design has to be checked at all three** —
  a DON'T BUILD page that still reads as encouraging is exactly the failure this
  document exists to prevent.
- Every fixture figure stays visibly fictional. The sample's own banner is the
  right treatment.

## R1 — Page chrome — **DONE 2026-09-07**

Running head (wordmark · RIGHT SITE. RIGHT OPERATOR. · hairline) and running
foot (demonstration banner · report id) on **every printed page**, verified by
rendering to PDF and counting: 15/15, 16/16, 16/16.

**`print.css` was never imported.** Not by `index.css`, not by `main.tsx`, not
anywhere. AGENTS.md calls it a first-class deliverable "exercised on every
build so print styles cannot rot unnoticed"; in fact no print rule had ever
reached a page — not the A4 setup, not the section break rules, not
`thead { display: table-header-group }`. One `@import` line fixed it, and the
page count moved the moment it landed, which is how it was caught.

**Then three mechanisms failed before one worked.** All measured on a 12-page
render, not reasoned about:

| Mechanism | Result |
|---|---|
| `@page` margin boxes + `counter(page)` | not implemented in Chromium at all — the old footer had always been decorative |
| `position: fixed` in `@media print` | head on **0** pages, foot on **1** |
| `display: table-header-group` on a plain div | head on page **1** only |
| a real `<thead>` in a real `<table>` | **repeats** — this is what ships |

So the document is wrapped in a one-column `role="presentation"` table. It is
ugly, and it is the only thing that works; `Report.tsx` carries that table of
results in a comment so nobody tidies it away and silently loses the header.

**The page number is still not there.** `counter(page)` resolves only inside an
`@page` margin box, so `{report_id} / {page}` needs Playwright's
`footer_template` — **R11**, with the rest of the PDF path. A hard-coded number
would be wrong on nine pages in ten, so the foot carries the report id alone.

**Also found:** `app/pdf/render.py` does not exist. STACK.md §6 specifies it;
there is no Playwright PDF path in the repo at all. R11 is bigger than "a print
pass" — it is writing that path.

## R2 — The section head, and three shared parts — **DONE 2026-09-07**

All in `parts.tsx`. `Section` now takes a mono eyebrow (`02 / WHAT THIS MEANS
FOR YOUR MONEY`), a **large serif sentence** heading, and an optional
standfirst; all twelve sections were given their sentence in the same pass —
"The money, in simple terms." · "Same rules. Every site." · "The operator
changes your deal." `StatCard`, `StatCards`, `Callout` (neutral / caution) and
`Footnote` are new; `TH` gained the dark ground, and `Table` gained zebra rows
with a `zebra={false}` escape for the short tables where banding is noise.

New tokens: `--cw-paper-head`, `--cw-paper-zebra`, `--cw-paper-tint`.

`print-color-adjust: exact` is now set on `.cw-report-root`, because white mono
on a dark table head is invisible if the ground is dropped — and Chromium drops
backgrounds by default from the browser's own print dialog. The archived PDF
passes `print_background=True`; a customer printing the page themselves does
not.

**Open, for R11:** a section starting at the top of a page puts its own top
rule directly under the running head's hairline. There is 20pt of clearance
between them now, which is legible, but the sample document has no section
rules at all. Whether ours survive is a print-pass decision.

**Built and not yet called.** `StatCard`, `Callout` and `Footnote` render
nowhere — R3 and R6 are their first callers. That is deliberate: twelve
sections stay consistent by construction, not by twelve files agreeing with
each other.

### R2, as originally planned

`parts.tsx` is where all of this belongs, so the twelve sections stay
consistent by construction rather than by discipline.

- **`Section`** gains a mono eyebrow (`02 / WHAT THIS MEANS FOR YOUR MONEY`), a
  **large serif sentence heading**, and an optional muted standfirst.
- **`StatCard`** — tinted box, mono uppercase label, large bold figure. Used in
  pairs: SETUP BUDGET · MIDDLE-CASE CASH / MONTH.
- **`Table`** gains a dark header row (slate ground, white mono uppercase) and
  zebra rows. Everything else stays — `display: table-header-group`, no row
  splits.
- **`Callout`** — left rule plus tint, two variants: neutral ("YOUR NEXT MOVE")
  and caution ("READ THIS BEFORE SIGNING").
- **`Footnote`** — the small muted line that closes a table.

Doing R1 and R2 before any individual section means everything after them is a
content edit rather than a redesign.

## R3 — 01 Verdict — **DONE 2026-09-07**

`Verdict.tsx`, rebuilt: a full-width dark block carrying the word and a plain
subtitle, then the lead sentence in large serif, the plain-language paragraph,
**THE MAIN REASON TO KEEP READING**, and a **YOUR NEXT MOVE** callout — the
first callers of `Callout`, which R2 built and left unused.

**Two decisions are frozen in the file's own comment.**

1. **All three verdicts sit on the same dark ground.** The word used to be set
   in green / amber / red; it no longer is. A BUILD in green reads as an
   endorsement, and a document that has to survive a monochrome photocopy in a
   bank file cannot spend its only colour on the one thing a reader will never
   misread. This is the decision the plan asked for, taken as written.
2. **`conditional` prints as CONDITIONAL, not "BUILD — CONDITIONAL".** At
   48px the old label's first word was the whole glance, and the whole glance
   said BUILD. The sample's answer to the same problem is **MODERATE** —
   adopting that word is a rename across `data.ts`, `Concept.tsx`, `Judged.tsx`
   and the API enum, so **it is parked with R5 as a product decision**, not
   slipped in behind a stylesheet. Dropping the misleading prefix needed no
   rename anywhere.

**THE MAIN REASON TO KEEP READING is derived, not authored per site.** Written
prose would quietly stop being true the moment the data moved. The rule, in
order: on a **NO**, lead with the case FOR the site (`12 of the 34 checks
argued in this site's favour`) — that is the anti-bias promise section 04
exists to keep, and burying it would be the exact failure the section guards
against; otherwise lead with whatever is still open (`2 of the 34 checks are
still unverified — grid outage hours and mobile network coverage`); then the
modelled demand band; then the weight of evidence against. Nothing is
recomputed — the checks are counted, never re-judged.

**Three print bugs surfaced and were fixed here, all of them R3's own making.**

| What broke | Why | Fix |
|---|---|---|
| Page 1 held the title and nothing else | section 01 grew past what `break-inside: avoid` would keep whole, so it jumped to a fresh page | `[data-report-section="verdict"] { break-inside: auto }` — it joins `site`, `ledger` and `financials` in opting out |
| YOUR NEXT MOVE split, label on one page and instruction on the next | `Callout` had no break rule | `[data-callout] { break-inside: avoid }`, and the same for `[data-verdict-block]` |
| The whole callout then pushed to page 2 | ~29pt short on the two longer verdicts | seven trims of 2–11px each, plus `margin-top: 14pt` for section 01 alone — it follows the title block, not another section, so it does not need the gap that separates two sections |

**Measured after:** all three verdicts close page 1 with YOUR NEXT MOVE on it,
with 32–53pt to spare — and that is *with* the demonstration banner, which a
real (`demo: false`) report does not carry, so a customer's page 1 has about
55pt more headroom than the worst fixture. Running head and foot still on
every page: 15/15, 16/16, 16/16.

**Also cut:** each `MEANING` paragraph used to close on "the rest of this
document shows the working, including the factors that argued against it".
THE MAIN REASON now says that four lines below, and says it about *this* site.

### R3, as originally planned

The sample's strongest page.

- Site name **large in serif**, kicker line under it.
- **A full-width dark block** carrying the verdict word (BUILD / MODERATE / DO
  NOT BUILD) and a one-line plain subtitle: "A strong starting point" · "Build
  only after conditions are met" · "Protect your money at this location".
- Then the lead sentence in large serif, a muted qualifier, "THE MAIN REASON TO
  KEEP READING", and a "YOUR NEXT MOVE" callout.
- **Decision:** the verdict block is the one place a colour could carry meaning.
  Keep the existing rule — the word decides, colour only ever agrees — so all
  three verdicts sit on the same dark ground and differ in the word.

## R4 — 04 The site: the "what it means" column — **DONE 2026-09-07**

The biggest content win in the track, and the only part of it that reached
the backend. Section 04 now carries, for every check: **what it is** (numbered
01–34), **what we found** (with its source under it), and **what it means** —
one plain sentence.

**The sentence is the section.** A reader who does not already build charging
stations cannot tell whether "9 m turning radius" is good news, and a table of
readings they cannot interpret is a table they skip — which is how a document
that shows its working gets read as a document that hides it.

**Shipped, in both halves:**

- `SiteFact.means: str | None` on the pydantic model, the TS type, `openapi.json`
  and `schema.d.ts`. Optional on the wire, **required at every `add()` call
  site** in `assemble.py` — a reading with no sentence beside it is a number
  the reader has to take on trust, so the assembler cannot emit one. All 20
  call sites carry one; four sentences are named constants because a check
  assembled two different ways (fetch succeeded / fetch failed) must not
  explain itself two different ways.
- The 34 fixture sentences live **once**, in a `CHECKS` map in `samples.ts`,
  and `facts()` attaches them. That map is also the closed key type the fact
  rows are checked against, so a typo, a rename, or a check missing from one
  of the three sites is now a **build error** rather than a page that quietly
  renders 33. It compiled first time, which proves the three fixtures already
  agreed on all 34 names.
- **Three chapters, five groups.** The groups are how the data is *fetched*
  (one group is one real fetch — the discipline `data.ts` owns); the chapters
  are how the answer is *read*: "Can drivers get in and out?" · "Customers,
  and electricity." · "A place people will choose." Each chapter prints its
  question, a standfirst, one table per group, and a closing footnote that
  takes something back. Both layers are on the page.
- **A fourth state.** `? UNVERIFIED` replaces the direction mark rather than
  sitting beside it as the old chip did, and neutral moved from `·` to `=` to
  match the legend. `Chip` is no longer used here at all.

**The tally changed, and it should have.** Unverified checks used to be
counted as though they had argued: Palm Junction read "26 favourable" while
two of those 26 were unconfirmed. The balance line is now four numbers that
add to the total and each match a mark printed on the page — *25 favourable,
1 against, 6 neutral, 2 still unverified*. `Verdict.tsx`'s "main reason"
sentence counts the same way, because it points the reader straight at this
line.

**Degrading cleanly is tested on a real payload.** The stored demo report was
assembled before the column existed and is served verbatim (rule 9), so it has
16 checks, no `means`, and no "Site and amenities" group. It renders: the mark
without the sentence, chapter 3 holding Competition alone, checks numbered
01–16 and never claiming 34.

**Two things worth knowing for R11.** Section 04 prints **9–11 checks a page**
against the sample's 12, and that gap is structural, not sloppy: we carry a
source line under every value and the sample carries no source column at all.
It costs 4–5 pages for the 34. Getting there needed the table to opt out of
the shared 17px cell — and the first attempt to do that **silently did
nothing**, because two Tailwind utilities of equal specificity are resolved by
their order in the generated stylesheet, not by their order in the class
attribute. `TD` kept winning. The cell class is now spelled out in `Site.tsx`
with that written above it.

### R4, as originally planned

The biggest content win, and the only part here that touches the backend.

- `SiteFact` gains **`means: str`** — one plain sentence per check, written once
  per factor rather than per site. Thirty-four sentences, authored by hand.
- Checks are **numbered 01–34** and split by group across pages, each group
  under its own question: "Can drivers get in and out?" (12) · "Customers and
  electricity." (4 + 8) · "A place people will choose." (7 + 3).
- The direction marker moves into the third column, above the sentence, and
  gains a fourth state `? UNVERIFIED` — replacing the separate chip.
- Each group's table closes with a footnote that qualifies it.
- **The backend half is one field** and can lag: render `means` when present,
  omit the line when absent — the same degrade-cleanly path section 06 already
  uses for the presence sentence.

## R5 — The money vocabulary — **DECIDED 2026-09-07**

The owner answered all three. **R6 is unblocked.**

| Question | Answer | What it costs |
|---|---|---|
| Does IRR survive anywhere? | **Keep it everywhere, as today.** | R6 is now *additive*: section 02 keeps the effective-return-vs-fixed-deposit comparison — the most legible thing in the current document — and **gains** cash left per year and time to recover. Section 05 keeps NPV and gains the ten-year cumulative table. Sections 02 and 05 get longer, which is the page count's problem, not the reader's. |
| Does the engine gain a full-cost breakeven? | **Yes.** | `economics_version` 0.1.0 → **0.2.0**, `RoiResult` gains two fields, `BreakevenPayload` gains three. Shipped in this pass, not deferred to R6. |
| Does `conditional` become MODERATE? | **No — keep CONDITIONAL.** | Nothing. R3 already removed the misleading `BUILD —` prefix, which was the real problem; "conditional" points at section 08, "moderate" points nowhere. |

**So the R5 table below is now half right.** The rows about IRR and NPV are
**overruled** — those numbers stay. The rows about payback, the case labels,
"units", and the two breakevens stand.

### The full-cost breakeven is DISCOUNTED, and the plan's own formula was wrong

This plan specified `full cost = annual bills + setup ÷ 10 years`. It was
implemented, then measured against the three sample payloads before shipping,
and it **contradicted the NPV already printed in the same document on two
cases out of nine** — including the exact case that prompted the question:

```
PALM JUNCTION, downside (P10), 75,581 kWh/yr, ten-year NPV −₹1.94 L
  bills + setup/10   64,445 kWh/yr  →  "ahead"   CONTRADICTS the NPV
  NPV = 0            78,131 kWh/yr  →  "short"   agrees
MARKET LINK, central (P50), 93,347 kWh/yr, ten-year NPV −₹71.6 L
  bills + setup/10   86,957 kWh/yr  →  "ahead"   CONTRADICTS the NPV
  NPV = 0           104,362 kWh/yr  →  "short"   agrees
```

R5 was asked to *remove* a contradiction; the straight-line formula would have
added a third number arguing with the other two. So what shipped is the
steady-state volume at which NPV is exactly zero —
`(annual_fixed + build_cost / annuity) / margin`, the annuity being the
present value of 1 per year over the horizon at the document's own discount
rate. It agrees with NPV by construction, and **a test asserts exactly that**:
hold the site at its full-cost breakeven and NPV comes out zero; a tenth above
it is positive, a tenth below negative. If that test ever fails the report is
printing two numbers that disagree about the same site.

The cost is that the number is no longer checkable on the back of an envelope.
That is the right trade: a reader who cannot re-derive a threshold is worse
off than a reader who finds two of our numbers fighting.

### What shipped with it

- `engine.py`: `full_cost_breakeven_kwh_year` and `..._utilisation`, the
  reasoning in the module docstring where it will not be re-litigated, and a
  new line in `assumptions` so the ledger carries it.
- `payload.py` / `payload.ts` / `openapi.json` / `schema.d.ts`:
  `breakeven.full_cost_{utilisation,kwh_year,kwh_day}`, all optional — a
  payload stored by economics 0.1.0 still validates and simply omits the row.
- **Section 03 gained one row**, and this is a correctness fix rather than
  R8 work done early. The rules table said "Build — downside clears
  breakeven" without saying *which* breakeven; a reader who took that to mean
  the build cost was back had been misled by our own wording, and was exactly
  the reader who then found a negative ten-year figure four pages later. It
  now names both lines and says the verdict is measured against the first.
- The three fixtures carry both numbers, consistent with their own capex and
  margin. Palm Junction reads **4.4% running-bill, 7.4% full-cost** against a
  downside of 7.19% — the R0 finding, now a number instead of an argument.

### R5, as originally planned — the IRR and NPV rows are OVERRULED

Blocks R6. Nothing in R6 should start until this is settled.

| Today | Sample | Note |
|---|---|---|
| IRR, central case | *gone* — "cash left per year", and as a % of setup cost | The sample states "This is not an IRR" |
| NPV | *gone* — a ten-year cumulative cash table instead | |
| Payback period | "Time to recover setup cost" | Same number, plainer name |
| P10 / P50 / P90 | CAUTIOUS / MIDDLE / OPTIMISTIC | **Label only** — keep the percentile provenance in 09 and 10 |
| kWh | "units", defined once as one kWh sold | |
| One breakeven | Running-bill breakeven **and** full-cost breakeven | Full cost = annual bills + setup ÷ 10 years |

Two questions to answer:

1. **Does IRR survive anywhere?** Section 02 is for the owner; 05 and 09 are for
   their accountant and the bank's credit officer (`OVERVIEW.md` §8). Dropping
   IRR everywhere may cost the second reader. Likely answer: plain money in 02
   and 05, IRR kept in 09.
2. **Does the engine gain full-cost breakeven?** It is arithmetic the engine
   already holds every input for, so it is cheap — but it changes what the
   verdict is measured against, which is a product decision, not a refactor.

## R6 — 02 Money and 05 Financial working — **SHIPPED 2026-09-07**

Everything planned landed, plus one thing that was not planned. R5 kept IRR
and NPV, so this was additive throughout: the plain money went in **beside**
the finance, never instead of it.

### What the engine gained

`economics_version` **0.2.0 → 0.3.0**. Three breakdowns, and the rule that
makes them worth printing: **a breakdown always sums exactly to the total it
explains.**

- `capex_lines` → `capex.net_paise`. The subsidy is its own line rather than
  quietly netted off, because a subsidy applied for and refused is the
  commonest way a build budget moves after the report is written.
- `fixed_cost_lines` → `annual_fixed_paise`. Zero lines are omitted, never
  printed as ₹0 rows.
- `unit_economics` → `margin_paise_per_kwh`. Price minus every cut equals what
  is left, **to the paise** — which is what lets section 05 print it as a
  sentence the reader checks in their head.

Each line is rounded on its own, so the residue is absorbed into the largest
line (`_reconcile`). A report that prints "9 + 3 + 3 = 14" has spent more
trust than the fraction of a paise was worth.

`Scenario.plain` carries the money view of each case: what comes in, what goes
out, what is left, monthly and annually, plus the **year-by-year running
total** from year 0 to the horizon. The annual figures are the STEADY year —
the same year `kwh_year` already reported — and the ramp is not hidden by
that choice, it is the cumulative row.

All of it optional, so a payload stored by economics 0.2.0 still validates.

### What the sections do now

- **02** — three stat cards (setup budget · cash left each month · time to
  recover), then the four-row table across the three cases, the footnote
  saying what "cash left" excludes, the deposit comparison kept exactly as R5
  decided, and a **READ THIS BEFORE SIGNING** caution naming the six things
  the budget leaves out: land, the DISCOM security deposit, GST, financing,
  contingency, ramp-up working capital.
- **05** — the one-time budget totalling to the setup cost; the per-unit chain
  as a sentence; the bills that arrive whether or not a unit is sold; a steady
  year across the three cases; then the **ten-year cumulative table**. The
  finance table (NPV, return, payback) moved BELOW them, so the plain-money
  build-up runs uninterrupted and the finance table reads as "the same thing,
  said to your accountant" — which mirrors 02's own shape.

The cumulative table earns its place immediately: on the MODERATE fixture the
downside column falls further behind every year while the central case crosses
into the black at year 8. That is the clearest statement of a *conditional*
verdict anywhere in the document.

### Two departures from this plan, both deliberate

1. **The cases are NOT renamed CAUTIOUS / MIDDLE / OPTIMISTIC.** The table
   above said "label only", but five other sections already say "the downside
   case" in their prose, and a third vocabulary for the same three numbers is
   exactly the drift R2 built the shared module to prevent. "Cautious" also
   describes the forecaster; "downside" describes the outcome. The mapping now
   lives once, in `payload.ts` (`CASE_LABEL`), and `Financials.tsx`'s private
   copy is gone.
2. **The ramp sentence is chosen from the data, not asserted.** The first
   draft's footnote said "demand ramps, so the first years are smaller" — and
   the fixtures are flat, so it printed that over a column of identical
   numbers. `ramps()` decides which sentence to print. The document
   contradicting itself on the same page is the failure this whole rebuild
   exists to remove; it does not get a pass for being a footnote.

### Found and fixed while measuring

- **An orphaned section number.** As 05 grew, the page break landed *inside*
  the section head block: "05 / FINANCIAL WORKING" alone at the foot of page
  11, its heading on page 12. `break-after: avoid` was already there and was
  not enough — the head needed `break-inside: avoid` too. All twelve heads on
  all three documents now travel whole.
- **Two units in one column.** `formatRupeesCompact` switches at one lakh, so
  the bills table printed "₹36.0k" between "₹2.23 L" and "₹2.40 L". The budget
  and the bills now print whole rupees; only the ₹-lakh grids, which declare
  their unit in the head, stay compact.

### The fixtures are derived now, not typed

R6 needed sixty more figures per site. Rather than type them, each fixture
declares one `Econ` — build cost, price, margin, fixed bills — and the rest is
built from it. Those three numbers were **recovered from the fixtures' own
stored NPVs** and reproduce all nine to **zero paise**, so this is not a new
invention layered on an old one. `samples.test.ts` re-derives the NPVs from
them on every run.

### Cost

Page count: 17 / 17 / 18 → **21 / 21 / 22**, and the stored demo 18 → 19. That
is R11's problem and R11 knew it was coming. No table exceeds the 688px
printable width; no horizontal overflow at 1440 / 1100 / 900 / 640 / 390;
running head and foot on every page of every document.

## R7 — 08 and 09: the threshold chart — **SHIPPED 2026-09-07**

Everything planned landed except the price-sensitivity strip, which is
deliberately **not** here — see the departures below.

### What the engine gained

`economics_version` **0.3.0 → 0.4.0**, and it is one field:
`full_cost_build_recovery_paise_year`, the build cost spread over the horizon
at the document's own discount rate.

That field exists because **section 09 prints the division rather than
asserting its answer**, and a sum a reader is invited to check has to show
every term in it. The alternative was the component dividing the build cost by
an annuity factor of its own — a financial number computed outside the engine,
which is the one thing AGENTS.md rule 1 forbids, and the first time the
discount rate moved the page would have quietly disagreed with the threshold
printed beside it.

### What the sections do now

- **08 — the rows are named levers**, a short noun phrase beside the sentence
  carrying the number, with "where it stands" kept as a third column because
  the gap is the thing a reader scans for. Three things are new:
  - **The build-cost line is a lever.** R5 added the second breakeven and R6
    printed ten years of running total against it, and this section still
    asked only whether the site covered its bills. On the BUILD fixture the
    downside case clears the bills line and is ₹1.94 L short over ten years —
    exactly the fact a reader deserves as a checkable condition rather than as
    a surprise in section 05. No verdict is measured against this line, so the
    cell beside it shows the whole band rather than the one case a rule picks.
  - **A contract only counts if it is additional.** The sample gives this a
    lever of its own ("No double counting") and it is the cheapest mistake in
    this document to make: signing a fleet for volume the forecast already
    assumed buys nothing and feels like it bought everything. The contract row
    also now appears on a BUILD whose downside misses the build-cost line —
    a data question, not a verdict question.
  - **A closing callout naming what is still open on THIS site**, which is
    what section 01's YOUR NEXT MOVE promises when it sends the reader here to
    answer the conditions in writing. Derived from the unverified checks, not
    a standing list.
- **09 — two rules, not one.** The bills line is SOLID and heavy because it is
  the rule the verdict is measured against; the build-cost line is DASHED and
  lighter because no verdict is measured against it. Drawing them identically
  would have invented a second rule the engine does not apply. Neither carries
  colour: this page gets photocopied into a bank file.
- **09 — the sum is printed, not asserted.** Both divisions run in full, and
  the sentence that closes them ("one extra term is the whole difference
  between the two rules") is the clearest statement of what the second
  threshold means anywhere in the document. R5 promised this reconciliation
  and never printed it.
- **09 — the standfirst defines utilisation** as energy sold ÷ what the
  chargers could deliver, "not the share of time a bay is occupied", which is
  the sample's own correction and one this document needed.
- The build-cost sentence under the chart is **chosen from the data**, in four
  branches, because no verdict is measured against that line and a sentence
  keyed on the verdict would assert a rule the engine does not apply.

### Two departures from this plan, both deliberate

1. **No price-sensitivity strip in 09.** The sample puts one here; R6 already
   put one at the foot of section 05, in the same units, one section earlier.
   A document that prints the same three numbers twice teaches the reader that
   its sections are not about different things. A clause in 09's provenance
   note points there instead. (The sample's strip shows *annual cash* at three
   prices rather than three breakevens — a genuinely different quantity — but
   the payload does not carry it, and inventing it here would be a financial
   number from a component.)
2. **The chart axis stays utilisation, not units/day.** The sample plots units
   a day. Ours would be the same picture at a different scale, and utilisation
   is the unit section 03's rules are written in. Both thresholds are restated
   in units a day beside the figures and in the formula, so the reader gets
   the checkable daily number without the page changing units mid-argument.

### Found and fixed while measuring

- **Labels printed through the other line.** The first draft let both rules
  span the full height, so the dashed one ran straight through the word
  "bills" in the other label and through "P10 7.2%". Two labels on separate
  rows do not collide with each other; a label still collides with the OTHER
  line. The chart is now laid out in rows nothing crosses — labels at the top,
  rules and band in the middle, axis, then the dimension line — and the band's
  P10/P90 values moved up into the figures, because inside the plot they were
  text in the one row that cannot have any.
- **A dimension label printed through its own end caps.** "+2.8 pp at the
  downside" is wider than a short span, and centred on the same row as the
  caps it ran through both. The label sits below the line now.
- **One axis tick in a different format.** `0.75 × 0.2` is
  0.15000000000000002 in binary floating point, so the tick row read "0% 5%
  10% 15.0% 20%". Rounded before the integer test, not after. This one
  predates R7 and had been printing on every document since R0.
- **"Both lines" printed over one line.** On the stored 0.1.0 demo, which has
  no full-cost threshold, the provenance note still said "Both lines hold the
  price and the fees fixed" under a chart carrying one. Counted from what is
  actually drawn now — the same discipline as R6's `ramps()`.
- **The fixtures' provenance said `economics_version 0.1.0`** while carrying
  R5's second breakeven, R6's three breakdowns and R7's recovery figure. A
  provenance row that contradicts the payload it stamps is worse than none.

### Cost

Page count: 21 / 21 / 22 → **21 / 21 / 23**, and the stored demo 19 → 20. One
page on the DON'T document and one on the demo; nothing on the other two. All
twelve section heads still travel whole with their headings on all four
documents, no table exceeds the 688px printable width, and there is no
horizontal overflow at 1440 / 1100 / 900 / 640 / 390.

## R8 — 03 The rules, and the concept plot — **SHIPPED 2026-09-07**

**The decision was made: keep both.** The schematic goes into 03 and both
Mapbox images stay in 04, because they answer different questions — the
satellite view is the evidence behind the frontage, turning and entry checks,
the ringed catchment is the evidence behind section 07's competitor counts,
and the schematic is the only picture that says what is being costed. The
sample document having no map is a limitation of the sample, not a design.

No engine or payload change: R8 is entirely a section.

### The rules table went from six rows to three

It had grown to two thresholds, three verdicts and a horizon row — and a
table of six rows carrying three different kinds of thing is not a rule, it
is a glossary. R5 put the second breakeven here because nothing else said
which line the verdict meant; R7 then gave that line a chart, a formula and a
lever of its own. So the thresholds moved OUT into the paragraph below, and
the table is the one thing it is for: three answers, and the rule producing
each. The horizon row went entirely — every section that quotes a ten-year
figure already says "10 years" beside it.

**The rule printed is ours, not the sample's.** The sample measures all three
verdicts against its full-cost line; our engine measures them against the
running-bill line and reports the other separately (R5's decision). Copying
the sample's wording would have made section 03 describe a rule the code does
not run, so the paragraph says plainly which line the verdict uses, that a
site can clear it and still be short over ten years, and points at 09.

### The concept plot draws OUR configuration

Inline SVG: no key, never fails to load, prints as vector, claims nothing
about the ground. MAIN ROAD → ACCESS LANE → CONCEPT PLOT, one bay per
connector, each with its own charger, all cabled down to **one grid
connection**.

The sample shows one 60 kW charger shared across two outlets. Ours models one
charger per bay and shares the *connection* instead — `sanctioned_load`
recommends less than the sum of the chargers on the assumption the peak is
managed. Drawing the sample's arrangement would have put a configuration on
the page that no number in the document was computed from. Drawing ours makes
section 05's sanctioned-load lever visible two sections before it is
quantified.

### Found by measuring, and worth more than R8 itself

**Four sections were taller than a printed page while still carrying
`break-inside: avoid`.** That rule is INERT on a block that cannot fit a page
— Chromium drops it and breaks wherever the break lands. What it still does
is push the block to a fresh page *first*, so a section 1.05 pages tall
leaves most of the previous page blank **and** breaks anyway.

`money` grew past a page in R6, `statistical` in R7, `judged` in R8, and
nothing said so, because a silently dropped rule looks exactly like a rule
that is working. All four now break honestly, and what holds them together is
the inner protections that were already there: the section head travels
whole, `thead` repeats, `tr` / `figure` / `[data-callout]` refuse to split.
Both SVG charts are wrapped in a `figure` for that reason.

Two smaller things:

- **The dashed road centre line ran behind the "MAIN ROAD" label.** It starts
  clear of it now; dashes through a label read as a printing fault.
- **The threshold footnote said "Neither line…" on a payload carrying one** —
  the same trap R7 found in section 09's provenance note, found here by
  looking at the stored 0.1.0 demo rather than at the fixtures.

### Cost — negative, for once

Page count: 21 / 21 / 23 → **20 / 19 / 21**, and the stored demo 20 → **17**.
R8 adds a whole new figure and the document still got *shorter than it was
before R7*, because the page-break finding recovered more space than the
schematic costs. Both figures travel whole on one page on all four documents;
all twelve section heads still travel whole with their headings.

## R9 — 06 Operator comparison, expanded — **SHIPPED 2026-09-08**

**The radius decision was made: 3 km and 10 km, both as columns, and no
5 km.** The sample's 5 km is the sample author's choice, not a finding; 3 km
is the ring `domain/demand/synthetic.py` already deducts forecast volume for
and the one section 07's verdict prose quotes, so adopting 5 km would have
left the document carrying two meanings of "near" unless the demand model
were re-derived with it. All three surfaces — the report, `/console/operators`
and the `OperatorMatched` animation — already agreed on 3 km near and 10 km
wide, and still do. Both now have a column of their own: 3 km is the split
you feel, 10 km the one you feel later.

### Two tables, not one

The sample puts fees, cash, rank, station counts, vehicle fit, roaming,
repair target and tie-in in a single grid, and then has to write "There is no
combined score" underneath to undo the impression the grid just made. We say
it structurally instead: **the money in one table, the network and the
service in another.** Never blending them is already our rule (OVERVIEW.md
§8, AGENTS.md constraint 1) and a rule the layout enforces does not need a
footnote to apologise for it.

It is also what keeps the section printable. Nine attributes in one table is
either fourteen columns or operators as columns — and a table that grows a
column per operator is cut off on paper the day a fifth operator appears.
As rows, an operator costs a row and no width. Both tables measure exactly
688px in print media, which is A4 less the 14 mm margins.

- **Cash per year is new, and it is the engine's.** `assemble.py` publishes
  the steady year of each operator's own run — the same figure `_plain` takes
  for section 02 — so the row for the headline operator carries section 02's
  own rupees. A return is comparable but abstract; cash is what the owner
  feels, and it is what makes the revenue share beside it mean something.
- **No rank column.** The sample needs "financial rank only" because its
  operators are columns and columns have no order. Ours are rows, already
  sorted; the order *is* the rank, and one footnote clause says it is
  financial only. A column asserting what the order already carries is a
  column that can disagree with it.
- **Repair target and tie-in still wait on `cpo_terms` (Track A · 2.3).** The
  columns exist, the fixtures exercise them, and the live assembler emits
  `None` for every operator — so both columns disappear rather than printing
  one dash per row. That is the rule `uptime` has lived under since this
  section was written: a column of repeated placeholder is furniture. A test
  pins it, and will start failing the day `cpo_terms` lands, which is the
  point.
- **Vehicle / charger fit was dropped.** The sample prints "60 kW CCS2" three
  times, once per operator, because it is a property of the hardware and not
  of the deal. R8's concept plot already draws it and section 05 prices it.
- **The per-operator sentence survives only where the columns cannot speak.**
  The counts became columns, so repeating them in prose underneath would be
  the duplication R6 removed. A dash is the one cell that cannot explain
  itself, so an unmatched name and self-operation keep their sentence.
  Everything else lost one.

### The fixtures were ranking a 13.6% deal above a free one

Found by adding the cash column: **the hand-typed CPO table contradicted the
terms printed in its own rows.** Operator A returned 28.8% on a 13.6% revenue
share while Self-operate returned 24.1% on nothing at all, and the same
inversion sat in the margin-at-downside column.

The cause is exact. `Econ.margin` deducts the effective tariff and *nothing
else* — `unitEconomics` says so in as many words — so every stored figure on
these sites is the zero-terms case. 28.8% is the P50 scenario's own IRR, and
it had been copied onto the wrong row; Self-operate's numbers were then
invented to sit below it.

So section 06's money is now **derived**, the way R6 derived the plain money
and R7 derived the recovery term. Each site declares only the terms and the
footprint; cash, return and margin at downside come from that site's `Econ`,
and the rows sort themselves with the assembler's own key rather than being
typed in an order. `samples.test.ts` holds the zero-terms row to the P50
scenario's IRR and to the payload's own `margin_of_safety_pp` on all three
sites — which is what proves the derivation right, and what would have caught
this years earlier.

Two consequences worth knowing:

- An 11.4% share on a ₹22 unit is ₹2.51 off a ₹13.50 margin, nearly a fifth
  of it. The operators are **much** dearer than the old table implied: on the
  MODERATE site only the free arrangement returns the build cost at all.
- Self-operate now leads every site, which is true of the model and not of
  the world — so the section says so: *the model prices no operator cut for
  it, and prices none of the work either.*

### Prose counted, not asserted

Four sentences read themselves off the rows: how many arrangements return the
build cost (with "1 of the 4 arrangements **returns**", the verb following
the count); who leaves the most cash; who answers a fault fastest; and, when
those are different operators, the trade between them — named, with both
figures, and left to the owner. That is what section 06 is for, and it is the
one thing the tables are forbidden to resolve.

**Found by looking at the DON'T BUILD document:** "Self-operate leaves the
most cash, −₹2.82 L a year" is a true sentence that reads as good news. Where
every arrangement loses money, the best of them **loses the least**, and the
words now change with the sign. The signed-rupee formatter moved into
`lib/money.ts` at the same time, because sections 02 and 06 both print losses
and a document that signs the same quantity two ways on two pages is the
drift this rebuild removes.

### Three smaller things, all found by looking

- **Roaming disappeared on the stored payload.** Table B was gated on the
  footprint columns, which a 0.1.0 payload does not have — taking a field it
  *does* have down with them. It degrades to a counted sentence now, because
  one yes/no column under a heading promising four is furniture.
- **"our network" wrapped under a half-width operator name** in a six-column
  table and read as a second operator. It is its own line now, deliberately.
- **"1 of the 4 arrangements return"** — the verb follows the count, not the
  set. A counted sentence that reads as a typo undoes the reason for counting.

### Cost

Page count 20 / 19 / 21 and the stored demo 17 → **20 / 20 / 21 and 17**: one
page, on the MODERATE document only. A whole second table and a new money
column for one page. No table exceeds 688px in print media, nothing overflows
at 1440 / 1100 / 900 / 640 / 390px, and all twelve section heads still travel
whole with their headings on all four documents.

## R10 — 10, 11 and 12 — **SHIPPED 2026-09-08**

### There were two assumption ledgers and only one was printed

`engine.py`'s module docstring has said this since it was written:

> Every default that shapes the answer is written into `assumptions` — the
> report's assumption ledger (PLAN 5) consumes it verbatim.

It did not. `RoiResult.assumptions` was built on every run, carried the
discount rate, the O&M share, the gateway cut, what the utilisation ceiling
means, how the ramp continues past its last given year, the ToD shares, the
fleet-anchor terms and the financing — and then went into the database inside
the stored result and never onto a page. What section 10 printed was a
*second* ledger, hand-written in `assemble.py`. Only the hand-written one was
visible, so only the generated one could go stale, and nobody would have
noticed for as long as it stayed that way.

Both are on the page now, and they are not the same thing: the engine's list
is what the **model** chose, `ledger` is where each **input** came from and
whether anyone has confirmed it. `model_assumptions` on the payload carries
the first, verbatim, from the central run.

**`ECONOMICS_VERSION` is 0.5.0** because of it. Until now the wording of
those strings was free to drift — nothing read them. From here they are part
of the deliverable, and two reports stamped the same version have to say the
same thing.

### The three jobs R10 inherited, closed

- **R6 left a full-cost line in the engine that section 10 should carry.** It
  arrives with the rest of the engine's list; no new prose was needed.
- **R7's recovery figure is a ledger row in its own right.** It is now a term
  in the engine's own full-cost sentence — "spreads the 24.00 lakh build cost
  over 10 years at 12%, **which is 4.25 lakh a year**" — computed from the
  same `build_per_year` section 09 prints. One number, one origin, and a test
  that fails if the two ever differ.
- **R9's per-operator cash is a third.** It is an assumption and a strong one:
  every operator is priced at the same volume. That is now a ledger row,
  because it is the reason section 06 must not be read as a forecast of which
  network brings more drivers.

### The document had no date on it

Not on the cover, not in the running chrome, nowhere — while section 11
existed so that an old report could defend itself. `generated_at` is on the
payload now and section 11 opens a **document record**: id, date, how many
checks it actually carries, engine version. It is baked in at assembly, not
read at render time, because the payload is served verbatim and a date filled
in on the way out is the date of the *reading*.

Section 11 also says **what the report was not built from** — no site visit,
no survey, no bill, no lease, no supply quotation, no outage log, no signed
terms. Most of section 04 is measured off a map, and a map cannot see a
transformer with no spare capacity or four hours of power cuts a day. The
sample's version of this block lists where evidence *would* come from; ours
says what is missing, because the reader can already see the sources in the
table directly above and repeating them there was the duplication R6 removed.

### Section 12 is as blunt as the sample

Three things were missing, and each is the kind a reader is entitled to be
told rather than to work out:

- **Describing a conflict does not resolve it.** We are paid more when a site
  is built, and section 06 ranks the operators who would pay us. Fee
  neutrality on the assessment is a real mitigation and it is not
  independence. No independence claim in the document has been verified by
  anyone outside the company, and it now says so.
- **A bracket is easy to miss.** The rejection counts were already bracketed
  per `IMPLEMENT.md`'s rule, but nothing said what the bracket *meant*, so the
  paragraph read as a track record. It is labelled as not one, and forecast
  accuracy is named as not yet measurable at all.
- **What must be disclosed before a real client sees this** is a list now, not
  prose: the fee actually charged and by whom, every referral or success fee
  and who pays it, any relationship with the operators in section 06, and who
  commissioned the report. Prose is where obligations go to be skimmed.

### Two fixture defects, found by printing the second ledger

- **Three rows said "Verified" over a basis of "engine default".** Sanctioned
  load, horizon and discount rate. An engine recommendation nobody has
  confirmed is the opposite of verified, and the page said both things inside
  one row. Sanctioned load is unverified now, and its basis says what is
  missing: not confirmed with the DISCOM.
- **Horizon and discount rate were in both ledgers at once.** They are model
  choices, and printing the engine's list put them on the page twice. They are
  rows no longer — the engine states them, which is where they were always
  stated.

Section 10's table also took the sample's shape: **value and basis share one
cell.** They were separate columns, and the basis is the half that makes a row
worth reading — "₹22.00/kWh" says nothing, "₹22.00/kWh assumed, a decision
variable rather than an observation" says everything. Splitting them gave the
sentence a third of the width and gave the two words "archetype default" a
column of their own.

### Cost, and the number R11 inherits

Page count 20 / 20 / 21 and the stored demo 17 → **21 / 24 / 23 and 17**.
That is expensive, and about two pages of it is content: section 10 grew by
the engine's ledger, and 11 and 12 no longer close the document on one sheet
between them — they take two.

The rest is break waste, and R10 measured it rather than guessing, at the
688px printable width against a 1017px page:

| | content | = pages | printed | wasted |
|---|---|---|---|---|
| build | 16,730px | 16.5 | 21 | **4.5** |
| moderate | 18,186px | 17.9 | 24 | **6.1** |
| dont | 18,202px | 17.9 | 23 | **5.1** |
| stored | 13,286px | 13.1 | 17 | **3.9** |

**The four sections still held whole total only 2.3–3.0 pages of height
between them, and every one of them fits a page, so none is inert** — R8's trap is not what
is happening here. The waste is mostly *inside* the sections that already
break freely: rows that cannot split, figures, callouts, and section heads
travelling whole. That is R11's first job and it now has a measurement to
start from instead of a hunch.

Every table still measures under 688px in print media, nothing overflows at
1440 / 1100 / 900 / 640 / 390px, and all twelve section heads travel whole
with their headings on all four documents.

## R11 — The print pass, and the renderer — **SHIPPED 2026-09-09**

### Every page count in this rebuild was one page optimistic

`networkidle` had fired, `[data-report-ready]` was present, the network was
quiet — and `document.fonts.status` was still `loading`. Chromium prints
whatever it has, so every measurement from R6 to R10 was laid out in
**fallback metrics**: narrower glyphs, fewer wraps, one page fewer than the
truth. Every one of those recorded numbers is low by a page.

Awaiting `document.fonts.ready` fixes it, and the renderer does. The true
counts are **22 / 23 / 23 and 17** — the stored demo became **26** later the
same day, when regenerating it grew section 04 from 16 checks to 39 — and two
independent paths now agree on
them — the measurement scripts and `app/pdf/render.py`, which is the check
that matters, because a renderer that disagrees with the print pass means one
of them is measuring a document nobody receives.

This is not a footnote. It is a small, silent, reproducible way to get a
different document from the same payload, which is precisely the class of
problem rule 9 exists for — and it was found by building the renderer, not by
looking harder at the CSS.

### `app/pdf/render.py` exists

It did not before. `renderer_version` was the literal string `"dev —
unpinned"`, and the archived artifact rule 9 describes had never been
produced by anything.

- **The page number is Chromium's, and only the page number.** `counter(page)`
  resolves only inside an `@page` margin box, which Chromium does not
  implement, so it needs Playwright's `footer_template`. Measured: turning
  `display_header_footer` on costs **nothing** — the content box stays 1017px
  and the page count is identical with it on or off, because the templates
  are drawn in a page-anchored box rather than out of the flow. Margins stay
  a uniform 14mm; 14mm through 18mm produce identical pagination.
- **The running head and foot stay ours.** They repeat from a real
  `<thead>`/`<tfoot>` (R1's finding). Chromium's templates get no page CSS at
  all, so anything richer than "page N of M" belongs in the document.
- **`renderer_version` is now both halves of a render**: the Vite build hash
  from the manifest `vite.config.ts` already writes for this, plus the
  Chromium build. Either alone is decoration — a Vite hash does not survive a
  Chromium bump and a Chromium version does not survive a frontend change.
- **The stamp is written into the DOM at print time, not into the payload.**
  The renderer loads the report's own URL, so it necessarily runs after the
  payload is stored, and the payload is served verbatim. So the archived PDF
  carries the real stamp while the payload says what is true of it — that
  nothing has been archived yet.

### The artifact has somewhere to live

Migration **0013** adds `report_pdfs`: bytes, renderer version, page count
read back from the bytes, size, timestamp. Insert-only by database rule, on
the same line `reports` already holds — a demo may be re-rendered, a customer
report never, because re-rendering on a later Chromium produces different
bytes and would quietly replace the evidence.

**Its own table, not columns on `reports`,** for two reasons. `reports`
refuses `UPDATE` outright and the PDF can only be attached afterwards, so
sharing the row would mean relaxing that rule — and a rule with an exception
in it has to be re-read every time it matters. And a payload read on every
request should not drag half a megabyte of artifact with it.

`scripts/archive_report_pdf.py` is the path: dry by default, `--write` to
archive. **The migration has not been applied and nothing has been archived**
— both are writes to the live database and are the owner's call.

### The page waste, and what it actually was

R10 handed R11 a measurement: 4.5–6.1 pages per document are not content.
R11's answer is that the membership test for "hold this section whole" was
wrong. It was *taller than one page*, which only catches the rule after it
has already failed silently (R8's inert-`break-inside` trap). The real
threshold is about **a third of a page**: a held section costs, on average,
half its own height in blank paper every time it does not happen to fit.

Measured at 688px: `change` 769px, `disclosure` 647px, `provenance` 568px —
each buying a whole-section guarantee at the cost of most of a sheet. All
three now break freely; `competitors` at 375px is the only section still
worth holding. **Sections 11 and 12 share a closing sheet again** as a
result, which R10 had lost.

What is left is structural and honest: the section head must travel with its
first block (R6 found what happens otherwise), rows and figures and callouts
cannot split, and an SVG chart is atomic by nature. Chasing the rest would
mean re-introducing defects each of those rules was adopted to fix.

### Verified

Table widths under 688px on all four documents, no overflow at 1440 / 1100 /
900 / 640 / 390px, running head and foot on every page, page number on every
page, and 12/12 section heads travelling whole with their headings — all at
the true, fonts-loaded page counts.

## R12 — The console record — **SHIPPED 2026-09-09**

`/console/report`, in the shape of `/console/operators`: a hand-kept record
above a live one.

### The hand-kept half

The twelve sections — what each **became**, what each **still needs**, which
component renders it and which part rebuilt it. Then what measuring the paper
turned up, which decisions are closed, and the parts in the order they were
built. It is the engineering record; `/console/concept` keeps the product
argument, and the two are deliberately not merged — the day the anatomy list
starts carrying page heights is the day nobody reads either.

**This is where the 37 kB string went.** What stays on the `5 + 6` milestone
is what the PIPELINE still owes the document: the other 18 site facts,
`cpo_terms`, PLAN 2.5's operator thresholds. A test now fails if
that field grows past 2 kB again.

### The live half, and why it earns its place

`GET /api/internal/document` reports what the **stored payload** can actually
fill, section by section (`domain/report/coverage.py`), and whether the render
has been archived. Every field the rebuild added is optional — a payload from
an older economics version renders a complete-looking page while quietly
showing less. That is correct behaviour, and it is invisible, so it is
measured rather than asserted.

Run against the live database it immediately says something the panel could
never have claimed on its own: **the stored demo was written by economics
0.1.0** and the engine is at 0.5.0. Nine of its twelve sections are printing
less than they can — no plain money, no breakdowns, no full-cost rule, no
WHAT IT MEANS column, no engine ledger, no date. The 17-page "stored" render
R11 measured is short for that reason and not because of print CSS. The panel
says so in those words, because *this report is old* and *this was never
built* read identically on the page and have opposite fixes.

### Two things it will not let drift

- **The section list is pinned to the document.** `ReportBuild.test.tsx`
  renders `<Report/>`, collects its `data-report-section` ids in order, and
  asserts both console lists match — including the numbers and names the
  document gives itself. Concept's list HAD described a report the customer
  was not receiving, for three days between the rebuild and 2026-09-06, and
  nothing caught it.
- **The assembler is pinned to the coverage rules.** A new gap in any section
  other than 04, 06 or 07 fails `test_report_pipeline.py` — so the readout
  stays worth reading, because anything on it is either known or news.

### One defect, found by writing the test

`inspect(session.get_bind()).has_table(...)` takes a **second connection** from
the engine and returns it with a rollback. On a shared connection that discards
whatever the session had pending — the archived row disappeared, and so did the
report it was attached to. Both callers now inspect `session.connection()`, so
the question is asked inside the session's own transaction.

---

## Part R — order of work

```
R0 fixtures ──▶ R1 chrome ──▶ R2 section head + parts ──┬──▶ R3 verdict  ✔
                                                        ├──▶ R4 the site ✔
                          R5 vocabulary DECIDED ✔ ──────┼──▶ R6 money ✔
                                                        ├──▶ R7 chart ✔
                                                        ├──▶ R8 rules + plot ✔
                                                        ├──▶ R9 operators ✔
                                                        └──▶ R10 tail ✔
everything ─────────────────▶ R11 print pass + renderer ✔ ──▶ R12 console ✔
```

**R0 → R8 (2026-09-07) → R9 → R10 (2026-09-08) → R11 → R12 (2026-09-09) are
done. TRACK B IS COMPLETE:** all twelve sections are rebuilt, the renderer
exists, no decision is left open, and the record is in the console at
`/console/report` — which is what lets this file be deleted.

### The order to run the rest

**Nothing in Part R is left, and rule 9 is closed.** On 2026-09-09 the owner
took all three live-database steps and asked for the report to be filled out
now with defaults where no feed exists:

- migration **0013** applied — `report_pdfs` exists;
- the demo **regenerated** — economics 0.1.0 → **0.5.0**, dated, 16 site
  checks → **39**, and nine sections that were printing less than they could
  now print in full;
- the render **archived** — 26 pages, 848,180 bytes, stamped
  `vite Cmyt9u8S · chromium 151.0.7922.34`, read back out of Neon and
  verified byte-for-byte against the render.

Section 04 was filled out to its promised length in the same pass, including
the fifth group (`Site and amenities`) the chapter map had always expected and
the assembler had never put a row into. **Every defaulted check prints
UNVERIFIED instead of a direction** — the fourth state section 04 has had since
R4 — so the document is full-length without one guess dressed as a
measurement. `/console/report` lists all 26 and what would close each.

**One thing was deliberately NOT defaulted**: section 06's repair-target and
tie-in columns. `CpoRow` has no per-cell unverified flag, so an invented
service term would print beside a real company name with nothing marking it —
and section 06 *ranks* operators, so it would change what the report
recommends rather than only what it shows. Those columns stay dropped until
`cpo_terms` exists.

| # | Do | Whose |
|---|---|---|
| 1 | A source for **26 of section 04's 39 checks** | Code, and still the largest single piece of backend work left. Now a list of named gaps rather than a missing half-section. |
| 2 | `cpo_terms` (PLAN 2.3), PLAN 2.5's operator thresholds | Code and a human respectively — sections 03, 06 and 07 are already shaped to receive both. |

**This file can now be folded into `PLAN.md` Part 6 and deleted.** Everything
in it that outlives the work is on `/console/report`, `/console/concept` and
the `5 + 6` milestones — which was the whole point of R12.

**Five decisions were open and are not the code's to make. All five are
now answered.**

- ~~**R5 · IRR**~~ — kept everywhere, as before (2026-09-07).
- ~~**R5 · Full-cost breakeven**~~ — a second number in the engine
  (2026-09-07).
- ~~**R5 · The verdict word**~~ — `conditional` keeps its name (2026-09-07).
- ~~**R8 · Map or schematic**~~ — **keep both**: the drawn schematic goes into
  03, both Mapbox images stay in 04 (2026-09-07).
- ~~**R9 · 3 km or 5 km**~~ — **3 km and 10 km, both as columns, no 5 km**
  (2026-09-08). 3 km is the ring the demand model already deducts volume for,
  so a 5 km column would have put a second meaning of "near" in the same
  document.

**Backend needed anywhere in Track B:** one field (`SiteFact.means`, R4), and
optionally full-cost breakeven in the engine (R5). Everything else is frontend.

**Revised after R0 — two more, both found by building the fixtures:**

- **The other 18 site facts — now the largest single piece of backend work in
  the track, and R4 did not close it.** `_site_facts` emits 16 across four
  groups; the product promises 34 across five, and the fixtures render all 34.
  `SiteFact.means` shipped with R4, so a new check needs only its row and its
  sentence — but there are eighteen of them, each needing a real source, and
  there is no "Site and amenities" group in the assembler at all. Until this
  lands, a customer's section 04 is less than half the length of the sample
  the design was taken from.
- ~~**Full-cost breakeven is a new number, not a new label.**~~ **Shipped
  2026-09-07 with R5.** `engine.py` gained two outputs, `economics_version`
  went to 0.2.0, and the definition is discounted rather than straight-line
  because the straight-line one disagreed with the NPV four pages away.

**And a print-path finding, for R11.** `app/pdf/render.py` does not exist.
There is no Playwright PDF path in the repo — STACK.md §6 specifies it and
nothing implements it. Until it does, `renderer_version` cannot be real, the
archived artifact behind Rule 1 does not exist, and the page number in the
running foot has nowhere to come from.
