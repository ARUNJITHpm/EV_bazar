import type {
  CostLine,
  CpoRow,
  Direction,
  FixedCosts,
  LedgerRow,
  PlainMoney,
  ReportPayload,
  Scenario,
  SiteFact,
  UnitEconomics,
} from "../payload";

/**
 * Three fictional report payloads — one per verdict — for looking at the
 * document while it is being rebuilt (CPO_SELECTION_PLAN.md, Track B · R0).
 *
 * WHY THESE EXIST
 *
 * The one real report in the system, KL-TVM-DEMO-001, carries one verdict.
 * A design that reads well on a DON'T BUILD and badly on a BUILD — or, far
 * worse, a DON'T BUILD page that still reads as encouraging — is exactly the
 * failure this document exists to prevent, and you cannot see it on one
 * sample. Regenerating the stored demo is also a write to the live database
 * behind a public page, which is nobody's call to make casually.
 *
 * So: three payloads, no database, no fetch, rendered at /report/sample/:which.
 *
 * WHAT THEY ARE NOT
 *
 * Not engine output. Every figure here was written by hand to be internally
 * consistent with `app/domain/roi/engine.py`'s definitions — the running-bill
 * breakeven is `annual fixed cost / margin per kWh` (build cost excluded),
 * the full-cost breakeven is `(annual fixed + build / annuity) / margin` at
 * 12% over ten years (Track B · R5), NPV discounts ten flat years at 12%,
 * and a payback beyond the ten-year horizon is `null`, never a large number.
 * The two breakevens and the three NPVs agree on every case, which is the
 * point of the second one. They are consistent, and they are invented. Every
 * one carries `demo: true`, so the document renders its own demonstration
 * banner.
 *
 * R6's plain money is DERIVED here, not typed. Each site declares one `econ`
 * — build cost, margin per unit, fixed bills — and `scenarios()` builds the
 * monthly figures and the ten-year running total from it. Those three
 * numbers are not a new invention either: they are what the stored NPVs
 * already imply, recovered from them and checked to the paise on all nine
 * cases. Typing sixty more figures by hand would have been sixty more
 * chances for section 02 to disagree with section 05.
 *
 * They mirror the three sites in `samplereport/` — Palm Junction (BUILD),
 * Market Link (MODERATE), Valley Bypass (DO NOT BUILD) — so the rebuild can
 * be held against the thing it is copying, at all three verdicts.
 *
 * TWO THINGS TO KNOW BEFORE TRUSTING WHAT YOU SEE
 *
 * 1. These carry all 34 checks, grouped 12 / 4 / 8 / 7 / 3 by source, the
 *    grouping `features/animation/data.ts` owns and the landing page
 *    promises. **The live assembler produces 16**, in four groups, with no
 *    "Site and amenities" group at all. Section 04 is therefore LONGER here
 *    than in a real report today. That gap is real and is not R0's to close;
 *    it is written down in `/console/report`.
 * 2. The "what it means" sentence (R4) is NOT written per site. It lives once
 *    per check in `CHECKS` below, and `facts()` attaches it — which is also
 *    what makes the label column a closed type, so all three sites are forced
 *    to carry the same 34 checks under the same names or the build fails.
 *
 * These are typed as `ReportPayload` rather than stored as .json on purpose:
 * a renamed payload field must break the build here too, not go quietly
 * `undefined` where a rupee figure should be (AGENTS.md, the typed-client
 * rule). Kept in one file because reading the three side by side is the
 * whole point.
 */

export const SAMPLE_IDS = ["build", "moderate", "dont"] as const;
export type SampleId = (typeof SAMPLE_IDS)[number];

export function isSampleId(s: string): s is SampleId {
  return (SAMPLE_IDS as readonly string[]).includes(s);
}

/* -------------------------------------------------------------------------
 * Compact writers. 34 facts × 3 sites is 102 objects; as tuples it is 102
 * readable lines, and the three sites can be diffed check against check.
 * ---------------------------------------------------------------------- */

/**
 * The 34 checks, and what each one MEANS — one plain sentence, written once
 * per check rather than once per site (Track B · R4).
 *
 * The sentence explains why the check is on the list at all, never what this
 * particular reading implies: "a divider can force a driver into a U-turn
 * they will not make" stays true whether or not this site has one, so it
 * survives the value changing underneath it. That is also why it can be
 * authored once and shared by all three fixtures — and by every real site,
 * which is how `assemble.py` writes it too.
 *
 * Being the key set, these labels are the closed type the fact rows are
 * checked against: a typo, a rename, or a check missing from one of the
 * three sites is a build error rather than a page that quietly renders 33.
 */
const CHECKS = {
  // Group 1 — access and geometry (12)
  "Road class": "Road type decides who passes the gate at all.",
  "Distance from main road": "A shorter detour is easier for a driver to choose.",
  "Carriageway direction served": "Only traffic that can actually reach the entrance counts.",
  "Sub-road access": "A second approach gives drivers a way in when the first is blocked.",
  "Median or divider": "A divider can force a driver into a U-turn they will not make.",
  "Sight line": "Drivers need to see the entrance in time to slow down for it.",
  "Turning radius": "A vehicle has to turn in without reversing into moving traffic.",
  "Entry and exit width": "The gate must take one car in and another out at the same time.",
  "Frontage width": "Road-facing width is how the site gets noticed at all.",
  "AADT traffic count": "All vehicles pass here — not all of them EVs, fewer still customers.",
  "Dominant flow direction": "Passing traffic only helps on the side that can turn in.",
  "Peak hour timing": "When the site is busy sets both staffing and the power bill.",

  // Group 2 — demand (4)
  "EV registrations, district": "Registrations are the pool of possible drivers, not daily demand.",
  "Registration mix": "Fast charging only serves the vehicles built to take it.",
  "Fleet operators within 10 km": "A nearby fleet is a lead, never guaranteed business.",
  "Distance to nearest city": "Demand is steadier where the site sits inside a daily journey.",

  // Group 3 — power and tariff (8)
  "Tariff order": "What one unit costs to buy, before any of it is sold.",
  "Demand charges": "A fixed power bill that arrives whether or not a car turns up.",
  "Sanctioned load": "The connection has to be sized for the plan, and approved for it.",
  "Transformer distance": "A longer cable run is paid for once, in the setup cost.",
  "Transformer spare capacity": "The electricity board has to confirm there is room on the feeder.",
  "Grid outage hours": "Hours with no supply are hours with no sales.",
  "New connection cost": "A one-time charge that belongs in the setup budget, not the bills.",
  "State subsidy applicability": "A grant changes the setup cost only once it is actually awarded.",

  // Group 4 — the plot and its surroundings (7)
  "Plot area": "The plot has to hold the bays, the turning space and the equipment.",
  "Parking bays": "Bays decide how many cars can charge at once, and how many wait.",
  "Canopy feasibility": "Shade and shelter decide whether drivers wait here or drive on.",
  "Amenities within walking distance":
    "Somewhere to go while charging is what makes a wait tolerable.",
  "Mobile network coverage": "No signal means no payment taken and no fault reported.",
  "Night lighting": "Half the charging day is after dark, and drivers avoid unlit sites.",
  "Land or lease cost": "Rent is a fixed monthly bill the site must cover before it earns.",

  // Group 5 — competition (3)
  "Nearest competitor": "The closest alternative this site’s drivers already have.",
  "Competitor density at 3 / 5 / 10 km": "How many other options sit inside the same detour.",
  "Announced stations": "A station not yet built still changes the picture within a year.",
} as const satisfies Record<string, string>;

/** The closed set of check names. Every fixture must use exactly these. */
type CheckLabel = keyof typeof CHECKS;

type FactRow = readonly [
  group: string,
  label: CheckLabel,
  value: string,
  source: string,
  direction: Direction,
  unverified?: boolean,
];

function facts(rows: readonly FactRow[]): SiteFact[] {
  return rows.map(([group, label, value, source, direction, unverified = false]) => ({
    group,
    label,
    value,
    source,
    direction,
    unverified,
    means: CHECKS[label],
  }));
}

const ACCESS = "Access and geometry";
const DEMAND = "Demand";
const POWER = "Power and tariff";
const PLOT = "Site and amenities";
const COMPETITION = "Competition";

/* Source strings, written the way `assemble.py` writes them — short enough
 * to sit under the value on one line at A4, which is what keeps 34 checks to
 * three pages rather than five. A source nobody can fit on the page is a
 * source nobody reads. */
const OSM = "OSM · Overpass";
const VAHAN = "VAHAN · district";
const TARIFF = "KSERC order";
const PLACES = "OSM POI · 1 km";
const INVENTORY = "competitor_stations";

type ScenarioRow = readonly [
  label: string,
  utilisation: number,
  kwh_year: number,
  npv_paise: number,
  irr_pct: number | null,
  payback_years: number | null,
];

/**
 * What one site's money is made of. Everything R6 prints comes from these
 * three numbers plus the volume of the case.
 *
 * They are not new inventions: `margin` and `fixed` are what each fixture's
 * stored NPVs already imply, recovered from them and verified to zero paise
 * on all nine cases. `samples.test.ts` re-derives the NPVs from them so the
 * two can never drift apart again.
 */
interface Econ {
  /** Net of subsidy — the same figure as `financials.capex_paise`. */
  capex: number;
  /** Paise one unit is sold to the driver for. */
  selling: number;
  /** Paise left on one unit after electricity and everyone else's cut. */
  margin: number;
  /** Paise a year that arrive whether or not a unit is sold. */
  fixed: number;
}

/** Ten flat years at 12%, which is what these fixtures' NPVs assume. The
 *  engine computes the same factor from `discount_pct` and `horizon_years`. */
const HORIZON = 10;

/** Present value of 1 a year for the horizon at 12% — 5.6502. The same
 *  factor the engine derives from `discount_pct`, written out here because
 *  these fixtures have no engine to ask. */
const ANNUITY = Array.from({ length: HORIZON }, (_, i) => 1 / 1.12 ** (i + 1)).reduce(
  (a, b) => a + b,
);

/** All three fixtures are the same two-gun 60 kW site — only the money and
 *  the ground differ. Written once so `MAX_KWH_YEAR` cannot drift from the
 *  hardware the three payloads actually print. */
const HARDWARE = { connectors: 2, rated_kw_each: 60, sanctioned_kva_full: 133 };

/** Both guns at full power every hour of the year: the denominator every
 *  utilisation in this document is a share of. */
const MAX_KWH_YEAR = HARDWARE.connectors * HARDWARE.rated_kw_each * 24 * 365;

/**
 * The build cost as an annual figure — one term of the full-cost breakeven,
 * which section 09 prints as a division the reader can check (Track B · R7).
 *
 * Derived rather than typed, for the same reason the plain money is: it has
 * to agree with the `full_cost_kwh_year` already stored beside it, and
 * `samples.test.ts` holds it to that.
 */
function recovery({ capex }: Econ): number {
  return Math.round(capex / ANNUITY);
}

/**
 * The plain-money block for one case (Track B · R6).
 *
 * These fixtures are FLAT — one steady annual volume, no ramp — which is
 * exactly why their stored NPV, IRR and payback reproduce from
 * `kwh × margin − fixed` over ten years. A real payload ramps, and its
 * `cumulative_paise` steps unevenly; here every step is the same size, and
 * section 05's footnote about the ramp is the one sentence these fixtures
 * cannot demonstrate.
 */
function plain(kwh: number, { capex, selling, margin, fixed }: Econ): PlainMoney {
  const revenue = Math.round(kwh * selling);
  const cash = Math.round(kwh * margin - fixed);
  const cumulative: number[] = [];
  for (let year = 0; year <= HORIZON; year += 1) cumulative.push(-capex + cash * year);
  return {
    revenue_paise_year: revenue,
    running_cost_paise_year: revenue - fixed - cash,
    fixed_cost_paise_year: fixed,
    cash_paise_year: cash,
    revenue_paise_month: Math.round(revenue / 12),
    cash_paise_month: Math.round(cash / 12),
    cumulative_paise: cumulative,
  };
}

function scenarios(
  rows: readonly [ScenarioRow, ScenarioRow, ScenarioRow],
  econ: Econ,
): [Scenario, Scenario, Scenario] {
  const one = ([label, utilisation, kwh_year, npv_paise, irr_pct, payback_years]: ScenarioRow) => ({
    label,
    utilisation,
    kwh_year,
    npv_paise,
    irr_pct,
    payback_years,
    plain: plain(kwh_year, econ),
  });
  // A tuple rather than an array so `cpo` below can take the downside and
  // central cases by position without first asking whether they exist.
  return [one(rows[0]), one(rows[1]), one(rows[2])];
}

/** The one-time budget and the standing bills, per site. Both sum to the
 *  headline they explain, which is what `samples.test.ts` checks. */
function working(
  capexLines: readonly (readonly [string, number])[],
  billLines: readonly (readonly [string, number])[],
): { capex_lines: CostLine[]; fixed_costs: FixedCosts } {
  const lines = billLines.map(([label, paise]) => ({ label, paise }));
  const total = lines.reduce((sum, line) => sum + line.paise, 0);
  return {
    capex_lines: capexLines.map(([label, paise]) => ({ label, paise })),
    fixed_costs: {
      lines,
      total_paise_year: total,
      total_paise_month: Math.round(total / 12),
    },
  };
}

/** One unit's price, and the single deduction these fixtures actually claim.
 *  Each site's stated effective tariff IS its whole deduction — the invented
 *  economics carry no separate operator cut, and inventing one to make the
 *  chain longer would put a number on the page the CPO table cannot back. */
function unitEconomics({ selling, margin }: Econ): UnitEconomics {
  return {
    selling_paise_kwh: selling,
    deductions: [{ label: "Electricity, all-in", paise: selling - margin }],
    margin_paise_kwh: margin,
  };
}

/**
 * One operator's TERMS and footprint. Nothing about the money is typed here.
 *
 * Cash, return and margin at downside are DERIVED from these terms and the
 * site's `Econ`, for the reason R6 derived the plain money and R7 derived
 * the recovery figure — the hand-typed table this replaces had Operator A
 * returning 28.8% on a 13.6% revenue share while Self-operate returned 24.1%
 * on nothing at all, printed in the same row as the terms that make it
 * impossible (Track B · R9).
 *
 * `Econ.margin` carries NO operator cut — `unitEconomics` deducts the
 * effective tariff and nothing else — so every stored figure on these sites
 * is the ZERO-TERMS case. That is why Self-operate is the row sections 02
 * and 05 are about, and why its derived return and margin reproduce the P50
 * scenario's IRR and the payload's own `margin_of_safety_pp` to the decimal
 * on all three sites. `samples.test.ts` holds them to it.
 */
type CpoTuple = readonly [
  operator: string,
  ours: boolean,
  /** Share of the driver's payment. Comes off the unit, so it cuts margin. */
  revenue_share_pct: number,
  /** Owed whether or not a unit is sold, so it joins the bills instead. */
  platform_fee_paise_year: number,
  ocpi_roaming: boolean,
  stations_district: number | null,
  stations_state: number | null,
  own_within_3km: number | null,
  own_within_10km: number | null,
  /** Signed service terms — null where there is nobody to sign with. Real
   *  payloads carry null on every row until `cpo_terms` exists (PLAN 2.3). */
  repair_hours: number | null,
  tie_in_years: number | null,
  presence_note: string,
];

/** Uptime is one repeated placeholder until the poller runs (PLAN 0.1), so
 *  it is written once here rather than three times per site. */
const NO_UPTIME = "not measured";

/**
 * Ten flat years of `cash` against `capex`, solved for the rate at which
 * they meet.
 *
 * `null` where the capital never comes back — the same fact the engine
 * reports as `irr_pct is None`, and never a large negative number dressed as
 * a return. Bisection is enough because these fixtures do not ramp; a real
 * cashflow is the engine's problem, not this file's.
 */
function flatIrr(capex: number, cash: number): number | null {
  if (cash <= 0 || cash * HORIZON <= capex) return null;
  let lo = 0;
  let hi = 10;
  for (let step = 0; step < 200; step += 1) {
    const mid = (lo + hi) / 2;
    let npv = -capex;
    for (let year = 1; year <= HORIZON; year += 1) npv += cash / (1 + mid) ** year;
    if (npv > 0) lo = mid;
    else hi = mid;
  }
  return Math.round(((lo + hi) / 2) * 1000) / 10;
}

/**
 * Section 06, priced from the terms.
 *
 * Every row is run at the SAME volume — the central case's — so the table
 * isolates what the terms cost and claims nothing about which operator
 * brings more drivers. That is the engine's behaviour too: `assemble.py`
 * hands every option the same `kwh_year_ramp_p50`.
 */
function cpo(
  rows: readonly CpoTuple[],
  econ: Econ,
  cases: readonly [Scenario, Scenario, Scenario],
): CpoRow[] {
  const kwhP50 = cases[1].kwh_year;
  const p10 = cases[0].utilisation;
  return rows
    .map(
      ([
        operator,
        ours,
        revenue_share_pct,
        platform_fee_paise_year,
        ocpi_roaming,
        stations_district,
        stations_state,
        own_within_3km,
        own_within_10km,
        repair_hours,
        tie_in_years,
        presence_note,
      ]) => {
        const margin = econ.margin - Math.round((econ.selling * revenue_share_pct) / 100);
        const fixed = econ.fixed + platform_fee_paise_year;
        const cash = Math.round(kwhP50 * margin) - fixed;
        return {
          operator,
          ours,
          revenue_share_pct,
          platform_fee_paise_year,
          irr_p50_pct: flatIrr(econ.capex, cash),
          // Bills over margin is the breakeven; how far the downside case
          // sits above it is the margin of safety. Both under THIS
          // operator's terms, which is the whole point of the column.
          margin_of_safety_pp: Math.round((p10 - fixed / margin / MAX_KWH_YEAR) * 1000) / 10,
          cash_p50_paise_year: cash,
          uptime: NO_UPTIME,
          ocpi_roaming,
          stations_district,
          stations_state,
          own_within_3km,
          own_within_10km,
          repair_hours,
          tie_in_years,
          presence_note,
        };
      },
    )
    .sort((a, b) => {
      // The assembler's own order: any return beats none, then the larger
      // return, then the wider margin. Sorted rather than typed, because a
      // hand-typed order is exactly what ranked a 13.6% deal above a free
      // one before R9.
      const rank = (r: CpoRow): [number, number, number] => [
        r.irr_p50_pct === null ? 0 : 1,
        r.irr_p50_pct ?? 0,
        r.margin_of_safety_pp,
      ];
      const [ax, ay, az] = rank(a);
      const [bx, by, bz] = rank(b);
      return bx - ax || by - ay || bz - az;
    });
}

function ledger(rows: readonly (readonly [string, string, string, boolean])[]): LedgerRow[] {
  return rows.map(([item, value, source, unverified]) => ({ item, value, source, unverified }));
}

/** Every fixture stamps itself. `renderer_version` says "fixture" so a
 *  screenshot of one of these can never be mistaken for engine output. */
/** The day these three were last rebuilt. Fixed, not `new Date()`: a fixture
 *  whose document record changes every time it is opened is not a record. */
const FIXTURE_DATE = "2026-09-08";

/**
 * The engine's own assumption ledger — for payloads that have no engine
 * (Track B · R10).
 *
 * A real report prints `RoiResult.assumptions`, generated as the run
 * happened. These fixtures cannot, so the list says what is true of THEM
 * rather than repeating the engine's defaults: no O&M share, no gateway cut
 * and no operator cut are modelled here, because `unitEconomics` deducts the
 * stated effective tariff and nothing else. Copying the engine's wording
 * would have put six assumptions on the page that these numbers do not obey,
 * which is the failure the whole rebuild exists to remove.
 *
 * The full-cost line is derived from `recovery()`, so the lakh-a-year figure
 * here is the same one section 09 prints in its formula.
 */
function modelAssumptions(econ: Econ): string[] {
  const lakh = (paise: number) => (paise / 10_000_000).toFixed(2);
  return [
    "economics_version 0.5.0",
    "discount rate 12% for NPV",
    `ten flat years at ${lakh(econ.fixed)} lakh of fixed bills — no ramp, growth, ` +
      "replacement or residual value; a real payload ramps, and section 05 prints every year",
    "utilisation ceiling assumes every plug at full rated power all 8,760 hours",
    `the stated effective tariff is the WHOLE deduction on a unit: ${(econ.selling / 100).toFixed(
      2,
    )} sold less ${((econ.selling - econ.margin) / 100).toFixed(2)} leaves ${(
      econ.margin / 100
    ).toFixed(2)} — no separate O&M share, gateway cut or operator cut is modelled`,
    `full-cost breakeven spreads the ${lakh(econ.capex)} lakh build cost over 10 years at 12%, ` +
      `which is ${lakh(recovery(econ))} lakh a year — it is the steady-state volume at which ` +
      "NPV is zero, so it agrees with the NPV above rather than offering a second opinion",
    "every figure on this document is invented: no site was visited, no model was run, " +
      "and no operator was asked for terms",
  ];
}

function provenance(reportId: string): ReportPayload["provenance"] {
  return [
    // The version that could actually have produced these fields. It said
    // 0.1.0 until R7 looked at it, by which point the payloads carried R5's
    // second breakeven, R6's three breakdowns and R7's recovery figure —
    // none of which 0.1.0 computes. A provenance row that contradicts the
    // payload it stamps is worse than no provenance row. 0.5.0 is the first
    // version whose assumptions are printed, and these fixtures print them.
    { label: "economics_version", value: "0.5.0" },
    { label: "model_version", value: "none — hand-written fixture", unverified: true },
    { label: "schema_version", value: "0012" },
    // A fixture is never rendered to an archived PDF, so it has no renderer
    // version to report. app/pdf/render.py stamps this cell in the DOM at
    // print time; on screen it says what is true, which is that nothing has
    // been archived (Track B · R11).
    { label: "renderer_version", value: `fixture ${reportId} — not archived`, unverified: true },
    { label: "archetype_version", value: "2026.09" },
    { label: "tariff_effective_date", value: "2026-04-01" },
    { label: "vahan_snapshot", value: "2026-08-18" },
    { label: "competitor_fetch", value: "not fetched — invented", unverified: true },
  ];
}

/* =========================================================================
 * 1 · PALM JUNCTION — BUILD
 *
 *   capex ₹24.00 L · sells at ₹22.00/kWh · buys at ₹8.50 · margin ₹13.50
 *   fixed running cost ₹6.30 L/yr → breakeven 46,667 kWh/yr = 4.44%
 *   downside 7.19% clears it by 2.8 points, so: BUILD.
 *
 * Look at what section 02 does with this one. The verdict is BUILD, and the
 * downside case is still ₹1.94 L SHORT over ten years — because breakeven
 * covers the running bills and not the build cost. Both statements are true
 * and the document currently puts them four inches apart without reconciling
 * them. That is R5's second question, seen rather than argued about.
 * ====================================================================== */

const PALM_ECON: Econ = {
  capex: 240000000,
  selling: 2200,
  margin: 1350,
  fixed: 63000000,
};
const PALM_WORKING = working(
  [
    ["Chargers, installation and commissioning", 140000000],
    ["Civil work and site preparation", 40000000],
    ["Power connection and cabling", 40000000],
    ["Canopy, signage and lighting", 30000000],
    ["Less subsidy", -10000000],
  ],
  [
    ["Demand charge on the sanctioned connection", 22320000],
    ["Rent", 18000000],
    ["Maintenance and repair reserve", 22680000],
  ],
);

/** Hoisted out of `financials` so section 06 is priced at the same central
 *  volume section 05 prints, rather than at a second copy of the number. */
const PALM_CASES = scenarios(
  [
    ["P10 · downside", 0.0719, 75581, -19447217, 10.0, 6.15],
    ["P50 · central", 0.0973, 102282, 184222700, 28.8, 3.2],
    ["P90 · upside", 0.1219, 128141, 381470008, 44.7, 2.18],
  ],
  PALM_ECON,
);

const PALM_JUNCTION: ReportPayload = {
  report_id: "CW-SAMPLE-BUILD",
  demo: true,
  site: {
    name: "Palm Junction",
    line: "Roadside food court · NH-66, Kollam · fictional site",
    district: "Kollam",
    lgd_district_code: 588,
    lat: 8.8932,
    lng: 76.6141,
    archetype: "highway_food_court",
    data_tier: 2,
  },
  hardware: HARDWARE,
  breakeven: {
    utilisation: 0.0444,
    kwh_year: 46667,
    kwh_day: 128,
    // (6.30 L bills + 240 L build / 5.6502) / 13.50 per unit. The downside
    // case (7.19%) clears the running-bill line and MISSES this one - which
    // is the same fact as the -1.94 L NPV at P10, said as a threshold.
    full_cost_utilisation: 0.0743,
    full_cost_kwh_year: 78131,
    full_cost_kwh_day: 214,
    full_cost_recovery_paise_year: recovery(PALM_ECON),
  },
  predicted: {
    p10: 0.0719,
    p50: 0.0973,
    p90: 0.1219,
    model_version: "synthetic_v0",
    modelled_not_measured: true,
  },
  margin_of_safety_pp: 2.8,
  verdict: {
    value: "build",
    reason:
      "The downside case clears breakeven by 2.8 points. Even a poor year covers the running bills, and the central case returns the build cost inside four years.",
  },
  demand: {
    district_ev_2025: 11240,
    district_growth_yoy_pct: 18.4,
    two_wheeler_share_pct: 71.0,
    vahan_snapshot: "2026-08-18",
  },
  site_facts: facts([
    [ACCESS, "Road class", "NH service lane, one side", OSM, "favours"],
    [ACCESS, "Distance from main road", "60 m", OSM, "favours"],
    [ACCESS, "Carriageway direction served", "Southbound + local access", OSM, "neutral"],
    [ACCESS, "Sub-road access", "2 points, 6 m service road", OSM, "favours"],
    [ACCESS, "Median or divider", "No divider on the access lane", OSM, "favours"],
    [ACCESS, "Sight line", "180 m clear", OSM, "favours"],
    [ACCESS, "Turning radius", "9 m at the gate", OSM, "favours"],
    [ACCESS, "Entry and exit width", "6 m in · 6 m out", OSM, "favours"],
    [ACCESS, "Frontage width", "30 m", OSM, "favours"],
    [ACCESS, "AADT traffic count", "18,400 vehicles/day", "NHAI count point", "favours"],
    [
      ACCESS,
      "Dominant flow direction",
      "62% on the served approach",
      "NHAI count point",
      "favours",
    ],
    [ACCESS, "Peak hour timing", "17:00–20:00", "NHAI count point", "neutral"],

    [DEMAND, "EV registrations, district", "11,240 (2025)", VAHAN, "favours"],
    [DEMAND, "Registration mix", "71% two-wheeler · 24% 4W", VAHAN, "against"],
    [DEMAND, "Fleet operators within 10 km", "9", "MSME + fleet register", "favours"],
    [DEMAND, "Distance to nearest city", "8.2 km", OSM, "neutral"],

    [POWER, "Tariff order", "LT-VII EV charging, TOU", TARIFF, "favours"],
    [POWER, "Demand charges", "₹200/kVA/month", TARIFF, "favours"],
    [POWER, "Sanctioned load", "93 kVA managed-peak", TARIFF, "neutral"],
    [POWER, "Transformer distance", "110 m", "KSEB feeder map", "favours"],
    [POWER, "Transformer spare capacity", "160 kVA", "KSEB feeder map", "favours"],
    [POWER, "Grid outage hours", "unverified", "no record obtained", "neutral", true],
    [POWER, "New connection cost", "₹4.00 lakh allowance", "KSEB schedule of rates", "neutral"],
    [
      POWER,
      "State subsidy applicability",
      "Applicable — capex shown net",
      "Kerala EV policy",
      "favours",
    ],

    [PLOT, "Plot area", "900 m²", PLACES, "favours"],
    [PLOT, "Parking bays", "2 charging + 2 waiting", PLACES, "favours"],
    [PLOT, "Canopy feasibility", "Room for a 120 m² canopy", PLACES, "favours"],
    [PLOT, "Amenities within walking distance", "Café and toilet within 80 m", PLACES, "favours"],
    [PLOT, "Mobile network coverage", "−78 dBm · 2 carriers", "field estimate", "favours", true],
    [PLOT, "Night lighting", "Gate and bays lit", PLACES, "favours"],
    [PLOT, "Land or lease cost", "₹15,000/month", "owner-stated", "favours"],

    [COMPETITION, "Nearest competitor", "4.2 km", INVENTORY, "favours"],
    [
      COMPETITION,
      "Competitor density at 3 / 5 / 10 km",
      "0 / 1 / 3 stations",
      INVENTORY,
      "favours",
    ],
    [COMPETITION, "Announced stations", "None in inventory", INVENTORY, "neutral"],
  ]),
  competitors: {
    within_3km: 0,
    within_5km: 1,
    dc_fast_within_3km: 0,
    source: INVENTORY,
    nearest: [
      {
        name: "Nearby site 1",
        operator: "Operator B",
        distance_m: 4200,
        max_power_kw: 60,
        points: 2,
      },
      {
        name: "Nearby site 2",
        operator: "Operator A",
        distance_m: 6800,
        max_power_kw: 30,
        points: 2,
      },
      {
        name: "Nearby site 3",
        operator: "(unattributed)",
        distance_m: 9100,
        max_power_kw: 22,
        points: 1,
      },
    ],
  },
  financials: {
    capex_paise: PALM_ECON.capex,
    selling_price_paise_kwh: PALM_ECON.selling,
    energy_tariff_paise_kwh: 850,
    scenarios: PALM_CASES,
    anchor_note: { kwh_year: 150000, npv_paise: 548206112, irr_pct: 57.5 },
    sanctioned_load: {
      full_kva: 133,
      recommended_kva: 93,
      recommended_label: "managed-peak",
      saving_paise_year: 9600000,
      buffered_kva: 67,
    },
    price_sensitivity: [
      { price_paise_kwh: 2000, breakeven_utilisation: 0.0521 },
      { price_paise_kwh: 2200, breakeven_utilisation: 0.0444 },
      { price_paise_kwh: 2400, breakeven_utilisation: 0.0387 },
    ],
    ...PALM_WORKING,
    unit_economics: unitEconomics(PALM_ECON),
  },
  cpo: cpo(
    [
      [
        "Operator C",
        false,
        11.4,
        2400000,
        false,
        6,
        42,
        0,
        1,
        24,
        2,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 6 in this district and 42 in the state.",
      ],
      [
        "Operator A",
        false,
        13.6,
        0,
        true,
        18,
        120,
        0,
        2,
        8,
        3,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 18 in this district and 120 in the state.",
      ],
      [
        "Self-operate",
        true,
        0,
        0,
        false,
        null,
        null,
        null,
        null,
        null,
        null,
        "You would run the station yourself, so no operator’s app is dividing these drivers between your plug and another — and none is bringing them either.",
      ],
      [
        "Operator B",
        false,
        18.2,
        1200000,
        true,
        30,
        180,
        1,
        4,
        12,
        5,
        "1 station of their own within 3 km (4 within 10 km) — their app can send the same drivers there instead of to you. 30 in this district and 180 in the state.",
      ],
    ],
    PALM_ECON,
    PALM_CASES,
  ),
  ledger: ledger([
    ["Utilisation band", "hand-written fixture — no model was run", "not measured", true],
    ["Build cost", "₹24.00 lakh, net of state subsidy", "invented for this fixture", true],
    ["Selling price", "₹22.00/kWh to the driver", "invented for this fixture", true],
    ["Energy tariff", "₹8.50/kWh effective, LT-VII TOU", "KSERC order 2026-04-01", true],
    [
      "Fixed running cost",
      "₹6.30 lakh/year — power charge, rent, maintenance, overhead",
      "archetype default",
      true,
    ],
    [
      "Sanctioned load",
      "93 kVA managed-peak, from 133 kVA full",
      "engine recommendation — not confirmed with the DISCOM",
      true,
    ],
    ["Operator terms", "invented — no signed terms on file", "no cpo_terms row", true],
    [
      "Operator footprint",
      "3 of 4 arrangements matched to a network we inventory",
      "competitor_stations",
      true,
    ],
    ["Grid outage history", "not obtained", "no record", true],
  ]),
  model_assumptions: modelAssumptions(PALM_ECON),
  provenance: provenance("CW-SAMPLE-BUILD"),
  generated_at: FIXTURE_DATE,
};

/* =========================================================================
 * 2 · MARKET LINK — BUILD, CONDITIONAL
 *
 *   capex ₹26.00 L · sells at ₹21.00/kWh · buys at ₹9.50 · margin ₹11.50
 *   fixed running cost ₹7.40 L/yr → breakeven 64,348 kWh/yr = 6.12%
 *   central 8.88% clears it, downside 5.73% does not: CONDITIONAL.
 *
 * The hardest of the three to write and the most useful to look at: it must
 * not read as a soft yes. The downside case loses money outright — no return
 * and no payback inside the horizon — while the central case pays back in
 * 7.8 years. Whether the page makes that tension legible is the test.
 * ====================================================================== */

const MARKET_ECON: Econ = {
  capex: 260000000,
  selling: 2100,
  margin: 1150,
  fixed: 74000000,
};
const MARKET_WORKING = working(
  [
    ["Chargers, installation and commissioning", 150000000],
    ["Civil work and site preparation", 50000000],
    ["Transformer", 30000000],
    ["Power connection and cabling", 40000000],
    ["Canopy, signage and lighting", 20000000],
    ["Less subsidy", -30000000],
  ],
  [
    ["Demand charge on the sanctioned connection", 22320000],
    ["DISCOM fixed charge", 3600000],
    ["Rent", 24000000],
    ["Maintenance and repair reserve", 24080000],
  ],
);

const MARKET_CASES = scenarios(
  [
    ["P10 · downside", 0.0573, 60234, -286730640, null, null],
    ["P50 · central", 0.0888, 93347, -71570430, 4.8, 7.8],
    ["P90 · upside", 0.1201, 126249, 142218754, 24.3, 3.65],
  ],
  MARKET_ECON,
);

const MARKET_LINK: ReportPayload = {
  report_id: "CW-SAMPLE-MODERATE",
  demo: true,
  site: {
    name: "Market Link",
    line: "Town-edge retail plot · Thrissur · fictional site",
    district: "Thrissur",
    lgd_district_code: 583,
    lat: 10.5276,
    lng: 76.2144,
    archetype: "town_retail_edge",
    data_tier: 2,
  },
  hardware: HARDWARE,
  breakeven: {
    utilisation: 0.0612,
    kwh_year: 64348,
    kwh_day: 176,
    // (7.40 L bills + 260 L build / 5.6502) / 11.50 per unit. Only the
    // upside case (12.01%) clears it; the central case does not, which is
    // the -71.6 L central NPV in the same document.
    full_cost_utilisation: 0.0993,
    full_cost_kwh_year: 104362,
    full_cost_kwh_day: 286,
    full_cost_recovery_paise_year: recovery(MARKET_ECON),
  },
  predicted: {
    p10: 0.0573,
    p50: 0.0888,
    p90: 0.1201,
    model_version: "synthetic_v0",
    modelled_not_measured: true,
  },
  margin_of_safety_pp: -0.4,
  verdict: {
    value: "conditional",
    reason:
      "The central case clears breakeven, the downside case misses it by 0.4 points. The site pays if demand lands where we expect and loses money if it does not.",
  },
  demand: {
    district_ev_2025: 8460,
    district_growth_yoy_pct: 9.2,
    two_wheeler_share_pct: 76.0,
    vahan_snapshot: "2026-08-18",
  },
  site_facts: facts([
    [ACCESS, "Road class", "State highway, divided", OSM, "neutral"],
    [ACCESS, "Distance from main road", "220 m", OSM, "against"],
    [ACCESS, "Carriageway direction served", "Northbound only", OSM, "against"],
    [ACCESS, "Sub-road access", "1 point, 4 m lane", OSM, "neutral"],
    [ACCESS, "Median or divider", "Divider — U-turn 400 m away", OSM, "against"],
    [ACCESS, "Sight line", "95 m", OSM, "neutral"],
    [ACCESS, "Turning radius", "7.5 m at the gate", OSM, "neutral"],
    [ACCESS, "Entry and exit width", "5 m shared in/out", OSM, "against"],
    [ACCESS, "Frontage width", "22 m", OSM, "neutral"],
    [ACCESS, "AADT traffic count", "11,900 vehicles/day", "PWD count point", "neutral"],
    [ACCESS, "Dominant flow direction", "54% on the served approach", "PWD count point", "neutral"],
    [ACCESS, "Peak hour timing", "18:00–21:00", "PWD count point", "neutral"],

    [DEMAND, "EV registrations, district", "8,460 (2025)", VAHAN, "neutral"],
    [DEMAND, "Registration mix", "76% two-wheeler · 19% 4W", VAHAN, "against"],
    [
      DEMAND,
      "Fleet operators within 10 km",
      "4 · one in discussion",
      "MSME + fleet register",
      "neutral",
    ],
    [DEMAND, "Distance to nearest city", "3.1 km", OSM, "favours"],

    [POWER, "Tariff order", "LT-VII EV charging, TOU", TARIFF, "favours"],
    [POWER, "Demand charges", "₹200/kVA/month", TARIFF, "favours"],
    [POWER, "Sanctioned load", "93 kVA managed-peak", TARIFF, "neutral"],
    [POWER, "Transformer distance", "340 m", "KSEB feeder map", "against"],
    [POWER, "Transformer spare capacity", "unverified", "no record obtained", "neutral", true],
    [POWER, "Grid outage hours", "unverified", "no record obtained", "neutral", true],
    [POWER, "New connection cost", "₹6.00 lakh allowance", "KSEB schedule of rates", "against"],
    [
      POWER,
      "State subsidy applicability",
      "Applicable — capex shown net",
      "Kerala EV policy",
      "favours",
    ],

    [PLOT, "Plot area", "1,150 m²", PLACES, "favours"],
    [PLOT, "Parking bays", "2 charging + 3 waiting", PLACES, "favours"],
    [PLOT, "Canopy feasibility", "Room for a 90 m² canopy", PLACES, "neutral"],
    [PLOT, "Amenities within walking distance", "Shops within 150 m, no toilet", PLACES, "neutral"],
    [PLOT, "Mobile network coverage", "−86 dBm · 1 carrier", "field estimate", "neutral", true],
    [PLOT, "Night lighting", "Street lighting only", PLACES, "against"],
    [PLOT, "Land or lease cost", "₹28,000/month", "owner-stated", "against"],

    [COMPETITION, "Nearest competitor", "1.6 km", INVENTORY, "against"],
    [
      COMPETITION,
      "Competitor density at 3 / 5 / 10 km",
      "2 / 4 / 7 stations",
      INVENTORY,
      "against",
    ],
    [COMPETITION, "Announced stations", "1 announced within 5 km", INVENTORY, "against"],
  ]),
  competitors: {
    within_3km: 2,
    within_5km: 4,
    dc_fast_within_3km: 1,
    source: INVENTORY,
    nearest: [
      {
        name: "Nearby site 1",
        operator: "Operator B",
        distance_m: 1600,
        max_power_kw: 60,
        points: 2,
      },
      {
        name: "Nearby site 2",
        operator: "Operator A",
        distance_m: 2400,
        max_power_kw: 30,
        points: 1,
      },
      {
        name: "Nearby site 3",
        operator: "Operator B",
        distance_m: 3900,
        max_power_kw: 30,
        points: 2,
      },
    ],
  },
  financials: {
    capex_paise: MARKET_ECON.capex,
    selling_price_paise_kwh: MARKET_ECON.selling,
    energy_tariff_paise_kwh: 950,
    scenarios: MARKET_CASES,
    anchor_note: { kwh_year: 140000, npv_paise: 231569403, irr_pct: 31.3 },
    sanctioned_load: {
      full_kva: 133,
      recommended_kva: 93,
      recommended_label: "managed-peak",
      saving_paise_year: 9600000,
      buffered_kva: 67,
    },
    price_sensitivity: [
      { price_paise_kwh: 1900, breakeven_utilisation: 0.0741 },
      { price_paise_kwh: 2100, breakeven_utilisation: 0.0612 },
      { price_paise_kwh: 2300, breakeven_utilisation: 0.0521 },
    ],
    ...MARKET_WORKING,
    unit_economics: unitEconomics(MARKET_ECON),
  },
  cpo: cpo(
    [
      [
        "Operator C",
        false,
        11.4,
        2400000,
        false,
        4,
        42,
        0,
        1,
        24,
        2,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 4 in this district and 42 in the state.",
      ],
      [
        "Operator A",
        false,
        13.6,
        0,
        true,
        14,
        120,
        1,
        2,
        8,
        3,
        "1 station of their own within 3 km (2 within 10 km) — their app can send the same drivers there instead of to you. 14 in this district and 120 in the state.",
      ],
      [
        "Self-operate",
        true,
        0,
        0,
        false,
        null,
        null,
        null,
        null,
        null,
        null,
        "You would run the station yourself, so no operator’s app is dividing these drivers between your plug and another — and none is bringing them either.",
      ],
      [
        "Operator B",
        false,
        18.2,
        1200000,
        true,
        26,
        180,
        2,
        5,
        12,
        5,
        "2 stations of their own within 3 km (5 within 10 km) — their app can send the same drivers there instead of to you. 26 in this district and 180 in the state.",
      ],
    ],
    MARKET_ECON,
    MARKET_CASES,
  ),
  ledger: ledger([
    ["Utilisation band", "hand-written fixture — no model was run", "not measured", true],
    ["Build cost", "₹26.00 lakh, net of state subsidy", "invented for this fixture", true],
    ["Selling price", "₹21.00/kWh to the driver", "invented for this fixture", true],
    ["Energy tariff", "₹9.50/kWh effective, LT-VII TOU", "KSERC order 2026-04-01", true],
    [
      "Fixed running cost",
      "₹7.40 lakh/year — power charge, rent, maintenance, overhead",
      "archetype default",
      true,
    ],
    [
      "Sanctioned load",
      "93 kVA managed-peak, from 133 kVA full",
      "engine recommendation — not confirmed with the DISCOM",
      true,
    ],
    ["Fleet conversation", "one operator in discussion — no contract", "not a commitment", true],
    ["Operator terms", "invented — no signed terms on file", "no cpo_terms row", true],
    [
      "Operator footprint",
      "3 of 4 arrangements matched to a network we inventory",
      "competitor_stations",
      true,
    ],
    ["Transformer spare capacity", "not obtained", "no record", true],
  ]),
  model_assumptions: modelAssumptions(MARKET_ECON),
  provenance: provenance("CW-SAMPLE-MODERATE"),
  generated_at: FIXTURE_DATE,
};

/* =========================================================================
 * 3 · VALLEY BYPASS — DON'T BUILD
 *
 *   capex ₹30.00 L · sells at ₹20.00/kWh · buys at ₹10.50 · margin ₹9.50
 *   fixed running cost ₹8.10 L/yr → breakeven 85,263 kWh/yr = 8.11%
 *   even the upside, 7.33%, is below it: DON'T BUILD.
 *
 * All three cases lose money every year — the upside case included — so
 * there is no IRR and no payback anywhere on the page, and section 05 must
 * say "no return" three times without softening it.
 *
 * This is the page to check hardest. Twelve of its 34 checks argue FOR the
 * site, and they are shown at full weight, because suppressing them is the
 * bias section 04 exists to disprove. The document has to hold both: the
 * plot is fine, and the money does not work.
 * ====================================================================== */

const VALLEY_ECON: Econ = {
  capex: 300000000,
  selling: 2000,
  margin: 950,
  fixed: 81000000,
};
const VALLEY_WORKING = working(
  [
    ["Chargers, installation and commissioning", 160000000],
    ["Civil work and site preparation", 70000000],
    ["Power connection and cabling", 50000000],
    ["Canopy, signage and lighting", 20000000],
  ],
  [
    ["Demand charge on the sanctioned connection", 22320000],
    ["Rent", 30000000],
    ["Maintenance and repair reserve", 28680000],
  ],
);

const VALLEY_CASES = scenarios(
  [
    ["P10 · downside", 0.0353, 37107, -558488381, null, null],
    ["P50 · central", 0.0529, 55608, -459180343, null, null],
    ["P90 · upside", 0.0733, 77053, -344069762, null, null],
  ],
  VALLEY_ECON,
);

const VALLEY_BYPASS: ReportPayload = {
  report_id: "CW-SAMPLE-DONT",
  demo: true,
  site: {
    name: "Valley Bypass",
    line: "Outer-bypass plot · Idukki · fictional site",
    district: "Idukki",
    lgd_district_code: 582,
    lat: 9.8497,
    lng: 76.9784,
    archetype: "rural_bypass",
    data_tier: 3,
  },
  hardware: HARDWARE,
  breakeven: {
    utilisation: 0.0811,
    kwh_year: 85263,
    kwh_day: 234,
    // (8.10 L bills + 300 L build / 5.6502) / 9.50 per unit. Nothing in the
    // band comes close - the upside case is 7.33% against 13.43% needed.
    full_cost_utilisation: 0.1343,
    full_cost_kwh_year: 141153,
    full_cost_kwh_day: 387,
    full_cost_recovery_paise_year: recovery(VALLEY_ECON),
  },
  predicted: {
    p10: 0.0353,
    p50: 0.0529,
    p90: 0.0733,
    model_version: "synthetic_v0",
    modelled_not_measured: true,
  },
  margin_of_safety_pp: -4.6,
  verdict: {
    value: "dont",
    reason:
      "Even the upside case sits 0.8 points below breakeven, and the central case 2.8 points below. At this build cost, tariff and price, no plausible level of demand covers the running bills.",
  },
  demand: {
    district_ev_2025: 2180,
    district_growth_yoy_pct: 4.1,
    two_wheeler_share_pct: 83.0,
    vahan_snapshot: "2026-08-18",
  },
  site_facts: facts([
    [ACCESS, "Road class", "District bypass, undivided", OSM, "neutral"],
    [ACCESS, "Distance from main road", "35 m", OSM, "favours"],
    [ACCESS, "Carriageway direction served", "Both directions", OSM, "favours"],
    [ACCESS, "Sub-road access", "None — single approach", OSM, "against"],
    [ACCESS, "Median or divider", "No divider", OSM, "favours"],
    [ACCESS, "Sight line", "60 m — bend before the gate", OSM, "against"],
    [ACCESS, "Turning radius", "5.5 m at the gate", OSM, "against"],
    [ACCESS, "Entry and exit width", "4 m shared in/out", OSM, "against"],
    [ACCESS, "Frontage width", "18 m", OSM, "neutral"],
    [ACCESS, "AADT traffic count", "3,600 vehicles/day", "PWD count point", "against"],
    [ACCESS, "Dominant flow direction", "51% on the served approach", "PWD count point", "neutral"],
    [ACCESS, "Peak hour timing", "08:00–10:00", "PWD count point", "neutral"],

    [DEMAND, "EV registrations, district", "2,180 (2025)", VAHAN, "against"],
    [DEMAND, "Registration mix", "83% two-wheeler · 12% 4W", VAHAN, "against"],
    [DEMAND, "Fleet operators within 10 km", "0", "MSME + fleet register", "against"],
    [DEMAND, "Distance to nearest city", "31 km", OSM, "against"],

    [POWER, "Tariff order", "LT-VII EV charging, TOU", TARIFF, "favours"],
    [POWER, "Demand charges", "₹200/kVA/month", TARIFF, "favours"],
    [POWER, "Sanctioned load", "93 kVA managed-peak", TARIFF, "neutral"],
    [POWER, "Transformer distance", "1,240 m", "KSEB feeder map", "against"],
    [POWER, "Transformer spare capacity", "35 kVA", "KSEB feeder map", "against"],
    [
      POWER,
      "Grid outage hours",
      "unverified — feeder reported unstable",
      "no record obtained",
      "neutral",
      true,
    ],
    [
      POWER,
      "New connection cost",
      "₹9.50 lakh allowance — HT extension",
      "KSEB schedule of rates",
      "against",
    ],
    [
      POWER,
      "State subsidy applicability",
      "Applicable — capex shown net",
      "Kerala EV policy",
      "favours",
    ],

    [PLOT, "Plot area", "2,600 m²", PLACES, "favours"],
    [PLOT, "Parking bays", "2 charging + 6 waiting", PLACES, "favours"],
    [PLOT, "Canopy feasibility", "Room for a 200 m² canopy", PLACES, "favours"],
    [PLOT, "Amenities within walking distance", "None within 1 km", PLACES, "against"],
    [
      PLOT,
      "Mobile network coverage",
      "−98 dBm · 1 carrier, intermittent",
      "field estimate",
      "against",
      true,
    ],
    [PLOT, "Night lighting", "None", PLACES, "against"],
    [PLOT, "Land or lease cost", "₹9,000/month", "owner-stated", "favours"],

    [COMPETITION, "Nearest competitor", "14.8 km", INVENTORY, "favours"],
    [
      COMPETITION,
      "Competitor density at 3 / 5 / 10 km",
      "0 / 0 / 0 stations",
      INVENTORY,
      "favours",
    ],
    [COMPETITION, "Announced stations", "None in inventory", INVENTORY, "neutral"],
  ]),
  competitors: {
    within_3km: 0,
    within_5km: 0,
    dc_fast_within_3km: 0,
    source: INVENTORY,
    nearest: [
      {
        name: "Nearby site 1",
        operator: "Operator A",
        distance_m: 14800,
        max_power_kw: 30,
        points: 1,
      },
      {
        name: "Nearby site 2",
        operator: "(unattributed)",
        distance_m: 21300,
        max_power_kw: 22,
        points: 1,
      },
    ],
  },
  financials: {
    capex_paise: VALLEY_ECON.capex,
    selling_price_paise_kwh: VALLEY_ECON.selling,
    energy_tariff_paise_kwh: 1050,
    scenarios: VALLEY_CASES,
    anchor_note: { kwh_year: 160000, npv_paise: 101165835, irr_pct: 19.8 },
    sanctioned_load: {
      full_kva: 133,
      recommended_kva: 93,
      recommended_label: "managed-peak",
      saving_paise_year: 9600000,
      buffered_kva: 67,
    },
    price_sensitivity: [
      { price_paise_kwh: 1800, breakeven_utilisation: 0.1027 },
      { price_paise_kwh: 2000, breakeven_utilisation: 0.0811 },
      { price_paise_kwh: 2200, breakeven_utilisation: 0.067 },
    ],
    ...VALLEY_WORKING,
    unit_economics: unitEconomics(VALLEY_ECON),
  },
  cpo: cpo(
    [
      [
        "Self-operate",
        true,
        0,
        0,
        false,
        null,
        null,
        null,
        null,
        null,
        null,
        "You would run the station yourself, so no operator’s app is dividing these drivers between your plug and another — and none is bringing them either.",
      ],
      [
        "Operator C",
        false,
        11.4,
        2400000,
        false,
        0,
        42,
        0,
        0,
        24,
        2,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 0 in this district and 42 in the state.",
      ],
      [
        "Operator A",
        false,
        13.6,
        0,
        true,
        2,
        120,
        0,
        0,
        8,
        3,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 2 in this district and 120 in the state.",
      ],
      [
        "Operator B",
        false,
        18.2,
        1200000,
        true,
        0,
        180,
        0,
        0,
        12,
        5,
        "No station of their own within 3 km, so nothing of theirs is dividing these drivers with you. 0 in this district and 180 in the state.",
      ],
    ],
    VALLEY_ECON,
    VALLEY_CASES,
  ),
  ledger: ledger([
    ["Utilisation band", "hand-written fixture — no model was run", "not measured", true],
    [
      "Build cost",
      "₹30.00 lakh, net of state subsidy — includes HT extension",
      "invented for this fixture",
      true,
    ],
    ["Selling price", "₹20.00/kWh to the driver", "invented for this fixture", true],
    ["Energy tariff", "₹10.50/kWh effective, LT-VII TOU", "KSERC order 2026-04-01", true],
    [
      "Fixed running cost",
      "₹8.10 lakh/year — power charge, rent, maintenance, overhead",
      "archetype default",
      true,
    ],
    [
      "Sanctioned load",
      "93 kVA managed-peak, from 133 kVA full",
      "engine recommendation — not confirmed with the DISCOM",
      true,
    ],
    ["Operator terms", "invented — no signed terms on file", "no cpo_terms row", true],
    [
      "Operator footprint",
      "3 of 4 arrangements matched to a network we inventory",
      "competitor_stations",
      true,
    ],
    ["Grid outage history", "not obtained — feeder reported unstable locally", "no record", true],
    ["Data tier", "tier 3 — thin district coverage widened the band", "coverage rule", true],
  ]),
  model_assumptions: modelAssumptions(VALLEY_ECON),
  provenance: provenance("CW-SAMPLE-DONT"),
  generated_at: FIXTURE_DATE,
};

export const SAMPLES: Record<SampleId, ReportPayload> = {
  build: PALM_JUNCTION,
  moderate: MARKET_LINK,
  dont: VALLEY_BYPASS,
};

/** What each sample is for, shown on the picker so nobody has to open all
 *  three to find the one they meant. */
export const SAMPLE_BLURB: Record<SampleId, string> = {
  build:
    "Palm Junction — the downside case clears breakeven. Check that a yes still reads as measured, not as a sales page.",
  moderate:
    "Market Link — the centre clears breakeven, the downside does not. Check that it does not read as a soft yes.",
  dont: "Valley Bypass — no case clears breakeven. Check that its 12 favourable checks do not make a no read as encouraging.",
};
