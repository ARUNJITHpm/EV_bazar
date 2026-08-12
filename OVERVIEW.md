# EV Site Intelligence Platform — Project Overview

> **Repo:** `evsite`
> **Status:** Pre-Part-0
> **Read this before touching any code.** Every architectural rule below is load-bearing.

---

## 1. What this product is

A customer drops a **pin on a map** (or types an address). The system returns a **site assessment report** that answers three questions:

1. **What utilisation will this EV charging site get?** (uncertain — modelled)
2. **What utilisation does it need to break even?** (certain — arithmetic)
3. **Which CPO partner makes the economics work best?** (arithmetic, run per-operator)

Secondary product: a **Tariff Audit** for operators who already have chargers and a real electricity bill.

**Geography:** India. National schema, tiered data coverage.

---

## 2. The core architecture — three separable layers

```
LOCATION ──▶ [ DEMAND MODEL ] ──▶ utilisation ──▶ [ ROI ENGINE ] ──▶ financials
                    ▲                                    ▲
             the ONLY learned                     pure arithmetic
                  thing                          (no ML, ever)
```

### The single most important rule

**No model ever predicts payback, IRR, or revenue directly.**

A model predicts exactly one thing: `kWh per connector per day`. That number is handed to a deterministic function. This means:

- If a financial number is wrong, it is a **bad tariff PDF or a bad geocode** — findable in minutes.
- The ROI engine can be unit-tested to exhaustion.
- The demand model can be swapped (heuristic → LightGBM → hierarchical) without touching anything downstream.
- Uncertainty lives in exactly one quarantined place.

---

## 3. The headline output

The report's hero number is **breakeven utilisation**, not predicted payback.

```
margin_per_kWh        = selling_price − energy_tariff − cpo_fee − gateway_cost

annual_fixed          = amortised_capex + demand_charges + O&M + rent + fixed_platform_fee

breakeven_kWh_year    = annual_fixed / margin_per_kWh

breakeven_utilisation = breakeven_kWh_year / (rated_kW × connectors × 24 × 365)

margin_of_safety      = predicted_utilisation_P10 − breakeven_utilisation
```

**Why this framing wins:** breakeven utilisation is a *fact about the site's cost structure*. It is true whether or not the demand model is any good. It cannot be "wrong" the way a prediction can. It is sellable on its own, before a demand model exists at all.

**Verdicts are driven by P10, never P50.** If the site doesn't clear breakeven in the pessimistic case, the report says *don't build*. Telling someone their site is bad **is** the product.

### What the ROI engine must also capture — India-specific, in order of how much they move the verdict

| # | Factor | Why it flips verdicts |
|---|---|---|
| 1 | **Fleet anchor contracts** | A minimum-guarantee offtake (e-buses, 3W aggregators, cab fleets) is the single biggest de-risker in Indian charging economics. Model *with/without anchor* as first-class scenarios — an anchor alone can move a site from Don't to Build. |
| 2 | **Utilisation ramp, not a flat rate** | Payback is brutally sensitive to whether P50 arrives in year 1 or year 3. Predict a ramp curve with P10/P50/P90 bands. A static number makes good sites look bad and bad sites look survivable. |
| 3 | **Capital subsidies & tax treatment** | PM E-DRIVE and state EV-policy subsidies, accelerated depreciation, GST input credit — these change amortised capex materially. A per-state **subsidy ledger** lives next to the tariff ledger, same effective-dating discipline. |
| 4 | **Sanctioned load as an *output*** | Don't just take kVA as input — *recommend* it. Battery-buffered chargers or a smaller sanctioned load with managed peaks can cut ₹2–4 lakh/year of fixed cost. That's advice worth paying for, not just assessment. |
| 5 | **Solar co-location scenario** | Rooftop/canopy solar changes `margin_per_kWh` enough to flip verdicts, and site owners ask about it unprompted. |
| 6 | **Selling price as a decision variable** | Price is a choice constrained by nearby competitor pricing (which the poller observes). One sensitivity line — "at ₹19/kWh vs ₹22/kWh your breakeven moves 14% → 18%" — makes the report feel alive. |
| 7 | **2W/3W segment economics** | Indian EV volume is overwhelmingly two- and three-wheelers. AC / swap / low-ticket charging is a different archetype from 4W DC fast. Archetypes that only cover 4W DC miss most of the actual demand in Tier 1 states. |
| 8 | **Financing structure** | IRR without a debt/equity split and interest rate is incomplete for the buyer segment with the deepest pockets: lenders. Optional input block. |

---

## 4. Scope rule — national schema, tiered data

Every table is built with LGD district codes as if all ~780 districts exist.

| Tier | States | Behaviour |
|---|---|---|
| **1** | Kerala, Tamil Nadu, Karnataka, Maharashtra, Delhi-NCR, Gujarat | Full report |
| **2** | Partial data | Degraded report, flagged |
| **3** | Everything else | `waitlist` response |

A waitlist response is **not a failure — it is lead capture**. Log every waitlisted pin. Whichever uncovered district accumulates the most pins is the next state whose SERC tariff PDFs get scraped.

---

## 5. The five non-negotiable rules

| # | Rule | Why |
|---|---|---|
| 1 | **Version everything** — `model_version`, `economics_version`, `schema_version`, `tariff_effective_date` on every report | Reports must be byte-regenerable in three years |
| 2 | **Log every prediction with a NULL `actual` column from day one** | In 18 months this table is worth more than the model |
| 3 | **Hunt failed and closed stations** | Selection bias is the thing that silently ruins the model. Surviving stations are a biased sample. |
| 4 | **Ranges and scenarios, never point estimates** | P10 / P50 / P90, always |
| 5 | **Hard quota caps on every paid API key before the first call** | One runaway loop = ₹40,000 |

---

## 6. What actually gets you paid

Not the model.

**a) The polling dataset.** Public charger availability, every 5 minutes, nationwide, starting day one. Nobody else will have three years of national occupancy data. This is the one asset that **cannot be retroactively acquired** — every day you don't poll is a day permanently lost.

**b) The attribution chain.** If you can't prove the lead was yours, nobody pays. Built in Part 7, *before* it feels necessary.

Both are boring infrastructure. Both compound.

### 6.1 The revenue ladder — in this order

The retail report is **marketing, not the business.** Individual site owners in India will not pay ₹15–25k for a PDF at volume; they are low-LTV, high-CAC. The money is:

| Rung | Product | Buyer | Why they pay |
|---|---|---|---|
| **1. Cash now** | **Tariff Audit** | Existing operators | They feel pain *today* — wrong tariff category, oversized sanctioned load, missed ToD. "We found ₹2.8 lakh/year in your bill" sells itself and needs **no demand model**. |
| **2. The business** | **Portfolio screening subscription / API** | CPO expansion teams, lenders & NBFCs, OMC dealer programs, fleet operators | "Rank these 200 candidate sites" annually beats selling reports one at a time. Lenders have **no underwriting standard for chargers** — a P10 margin-of-safety number is exactly what a credit committee wants. One bank partnership > thousands of retail reports. |
| **3. Upside** | **Attribution commissions** | CPOs, per installed lead | Only after the firewall in §6.2 exists. |

The retail report and the **free instant breakeven teaser** (drop a pin → breakeven number in 30 seconds; pure arithmetic, no model needed) sit underneath the ladder as lead capture. The teaser feeds the ⚠️-ledger upsell and the waitlist-by-district expansion signal.

### 6.2 The honesty firewall

Commission-per-installed-lead financially rewards **Build** verdicts. Credibility *is* the product, so this needs a structural answer, not good intentions:

- Price the report and the lead **separately** — a *Don't build* verdict still earns.
- **Publish the verdict distribution** (Build / Conditional / Don't) publicly. A shop that says "Build" 95% of the time is a funnel, and everyone can see it.
- Verdict logic stays in the pure ROI engine, versioned — a commission cannot touch a number.

### 6.3 The operator-affiliation decision — resolve before selling anything

We are ourselves affiliated with an operating CPO. A CPO-owned assessment platform that ranks CPO partners will be read — fairly or not — as a funnel for our own network. Two coherent positions exist:

1. **Internal expansion weapon** — screen our own pipeline, sell nothing externally. Valuable, different business.
2. **Neutral brand** — visible independence, our own network listed and scored by the same public rules as everyone else's.

**The middle is where trust dies.** Pick one before the first external sale. Until then, the affiliation is an asset: our own session data is ground truth for the demand model, and our Tier 1 footprint matches where the model needs calibrating first.

### 6.4 Publish the data

A quarterly *State of EV Charger Utilisation* note (Kerala / TN / Karnataka) built from the polling data would be the only report of its kind in India. Cheap PR, inbound institutional interest — and it advertises the moat itself.

---

## 7. Product shape

**Input from customer:** one pin + five optional taps
- Existing electricity connection?
- Sanctioned load (kVA)?
- Transformer on site?
- Land owned or leased?
- Budget band?

**Everything else is archetype defaults.** Every default appears in an **assumption ledger** at the end of the report. Unverified ones carry ⚠️.

Each ⚠️ is simultaneously:
- an honesty mechanism
- a re-engagement hook ("resolve this to sharpen your report")
- a lead-qualification signal (someone who resolves five ⚠️ is serious)

### Two products, never merged

| | Site Assessment | Tariff Audit |
|---|---|---|
| Input | Location only | A real electricity bill |
| Customer | Greenfield / prospecting | Existing operator |
| Function | **Acquisition** | **Door-opener & cash now** |
| Needs demand model? | Yes (for the prediction band) | **No — pure arithmetic, sellable first** |

The audit sells *this quarter*, before any model exists. Every audit customer is a warm prospect for expansion assessments — it earns trust with a number the customer can verify against their own bill.

---

## 8. Report anatomy

```
1. VERDICT                Build / Conditional / Don't
2. THE NUMBER             Breakeven utilisation    ██ 18.4%
                          Predicted P10–P90        ██ 11% – 27%
                          Margin of safety         −7.4 pp  ⚠️
3. SITE PROFILE           Archetype, comparables, competitor occupancy
4. FINANCIALS             3 scenarios · NPV · IRR · payback · 10-yr cashflow
5. CPO COMPARISON         Ranked table, IRR recomputed per operator
6. ASSUMPTION LEDGER      Every default, ⚠️ on unverified
7. PROVENANCE             All version stamps + data vintages
```

CPO ranking runs the ROI engine **once per operator**, because each one changes `margin_per_kWh` (revenue share / ₹ per kWh fee), `annual_fixed` (platform fee, AMC) and capex (bundled hardware or BYO). Financial rank and qualitative score are displayed **side by side, never blended** — the site owner's weighting is not ours.

---

## 9. Sequencing philosophy

Three things start **immediately and in parallel**, because they have zero dependencies and one of them is time-critical:

1. **Status poller** — day one, non-negotiable
2. **SERC tariff PDF collection** — one state per evening, pure manual labour
3. **CPO conversations** — their fee terms determine what the attribution chain must log

Everything else is sequenced in `PLAN.md`.

---

## 10. Glossary

| Short | Full form |
|---|---|
| LGD | Local Government Directory (Ministry of Panchayati Raj) |
| SERC | State Electricity Regulatory Commission |
| DISCOM | Distribution Company (KSEB, TANGEDCO, BESCOM…) |
| CPO | Charge Point Operator |
| EMSP | E-Mobility Service Provider |
| VAHAN | MoRTH national vehicle registration database |
| OSM | OpenStreetMap |
| OCPI | Open Charge Point Interface (roaming) |
| OCPP | Open Charge Point Protocol (charger ↔ backend) |
| PostGIS | PostgreSQL + Geographic Information System extension |
| kVA | Kilovolt-ampere — **sanctioned load is billed in kVA, not kW** |
| ToD | Time of Day tariff slabs |
| P10/P50/P90 | 10th / 50th / 90th percentile |
| pp | Percentage points |
| NPV / IRR | Net Present Value / Internal Rate of Return |
| LODO-CV | Leave-One-District-Out Cross-Validation |
| AMC | Annual Maintenance Contract |
| BYO | Bring Your Own (hardware) |

### The two that matter most

**kVA vs kW.** A 60 kW charger at 0.9 power factor needs ~67 kVA sanctioned. Demand charges of ₹300–500/kVA/month = ₹2.4–4 lakh/year **before selling a single unit**. Get this wrong and every financial number in the report is wrong.

**P10 vs P50.** Selling on P50 is how you get a refund request.

