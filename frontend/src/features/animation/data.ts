/**
 * The illustrative content behind the three animations.
 *
 * ONE rule governs this file: every value here is example content for a
 * fictional site, not a measurement. Landing.tsx's working rule applies -
 * numbers the repo does not have render BRACKETED, and un-bracketing one is
 * a human step with evidence, never an edit. `BRACKET_ILLUSTRATIVE` below is
 * the single switch; flipping it to false is that human step, and it should
 * be taken deliberately, for a site whose numbers someone has actually
 * sourced.
 *
 * The factor names and the grouping are NOT illustrative. The names are
 * Landing.tsx's FACTORS verbatim; the grouping is by SOURCE, 12 / 4 / 8 / 7
 * / 3 = 34, and it is the product's only one - the landing page, the
 * /animation surface and the live assessment screen all read it from here.
 * If a factor is added to FACTORS, add it to the group whose source fetches
 * it.
 *
 * Deliberately absent: a 0-100 "site fit" score. The report payload has no
 * such field (app/domain/report/payload.py), and marketing a headline metric
 * the product does not produce would sell a report that cannot be delivered.
 * The verdict below is real vocabulary - VerdictPayload is
 * Literal["build", "conditional", "dont"].
 */

/** Wrap illustrative figures in brackets. See the module note before changing. */
const BRACKET_ILLUSTRATIVE = true;

/** Bracket a value unless it is already an honest state word like "unverified". */
export function illustrative(value: string): string {
  return BRACKET_ILLUSTRATIVE ? `[${value}]` : value;
}

export type Check = {
  /** Verbatim from Landing.tsx's FACTORS. */
  readonly source?: string;
  readonly label: string;
  /** Illustrative. Rendered through `illustrative()` at the point of use. */
  readonly value: string;
  /** Copper, and only copper, marks a factor the assessment could not source. */
  readonly unverified?: boolean;
};

export type Group = {
  readonly key: string;
  /** Shown in the category strip - short enough to sit in five columns. */
  readonly short: string;
  readonly name: string;
  /** What is read for this group - a source, never a result. Grouping is owner-approved; this does not assert one live fetch per group. */
  readonly source: string;
  readonly checks: readonly Check[];
};

/**
 * The 34, grouped 12 / 4 / 8 / 7 / 3 BY SOURCE.
 *
 * This is the only grouping in the product. An earlier version of this file
 * grouped them 9 / 7 / 8 / 6 / 4 by subject, which read better on a
 * marketing page and was wrong everywhere else: a visitor met one taxonomy
 * on the landing page and a different one ten seconds into their own
 * assessment. Owner's call - the source grouping wins, because one group is
 * a walkthrough; individual checks can have pending or manual sources.
 *
 * flow/Working.tsx imports these rather than declaring its own, so the two
 * cannot drift apart again.
 */
export const GROUPS: readonly Group[] = [
  {
    key: "access",
    short: "Access",
    name: "Access and geometry",
    source: "OSM roads; geometry and traffic survey pending",
    checks: [
      { source: "OpenStreetMap road layer", label: "Road class", value: "NH arterial" },
      { source: "OpenStreetMap road layer", label: "Distance from main road", value: "0.4 km" },
      {
        source: "Site survey; direction matching pending",
        label: "Carriageway direction served",
        value: "Eastbound",
      },
      {
        source: "OpenStreetMap roads; access survey confirms",
        label: "Sub-road access",
        value: "2 points",
      },
      {
        source: "OpenStreetMap roads; median access survey confirms",
        label: "Median or divider",
        value: "Divided",
      },
      { source: "Site survey pending", label: "Sight line", value: "180 m" },
      { source: "Site survey pending", label: "Turning radius", value: "12.5 m" },
      { source: "Site survey pending", label: "Entry and exit width", value: "8.2 m" },
      { source: "Site survey pending", label: "Frontage width", value: "46 m" },
      {
        source: "No verified AADT count; traffic survey pending",
        label: "AADT traffic count",
        value: "18,400 /day",
      },
      { source: "Traffic survey pending", label: "Dominant flow direction", value: "Inbound AM" },
      { source: "Traffic survey pending", label: "Peak hour timing", value: "08:00–10:00" },
    ],
  },
  {
    key: "demand",
    short: "Demand",
    name: "Demand",
    source: "VAHAN records where loaded; fleet inventory pending",
    checks: [
      {
        source: "VAHAN district records where loaded; otherwise pending",
        label: "EV registrations",
        value: "12,540",
      },
      {
        source: "VAHAN vehicle classes where loaded; otherwise pending",
        label: "Registration mix",
        value: "68% 4W",
      },
      {
        source: "Verified fleet inventory pending",
        label: "Fleet operators within 10 km",
        value: "14",
      },
      {
        source: "OpenStreetMap places; reviewed distance pending",
        label: "Distance to nearest city",
        value: "6.8 km",
      },
    ],
  },
  {
    key: "power",
    short: "Power",
    name: "Power and tariff",
    source: "Verified tariff where available; OSM power; confirmations pending",
    checks: [
      {
        source: "Human-verified SERC EV tariff order where available; otherwise pending",
        label: "Tariff order",
        value: "TOU C&I",
      },
      {
        source: "Human-verified SERC EV tariff order where available; otherwise pending",
        label: "Demand charges",
        value: "₹390 /kVA",
      },
      {
        source: "Customer input or labelled archetype assumption",
        label: "Sanctioned load",
        value: "75 kVA",
      },
      {
        source: "Geofabrik / OpenStreetMap power; site survey confirms",
        label: "Transformer distance",
        value: "140 m",
      },
      {
        source: "Serving DISCOM confirmation pending",
        label: "Transformer spare capacity",
        value: "180 kVA",
      },
      /* The one copper value on the whole surface. Its meaning is the
         product's argument: a gap is reported, never quietly filled. */
      {
        source: "NFMS / NPP area supply context pending; not site outage measurements",
        label: "Grid outage hours",
        value: "unverified",
        unverified: true,
      },
      { source: "DISCOM quotation pending", label: "New connection cost", value: "₹8.4 lakh" },
      {
        source: "Reviewed policy register pending; site eligibility unverified",
        label: "State subsidy applicability",
        value: "Applicable",
      },
    ],
  },
  {
    key: "site",
    short: "Site",
    name: "Site and amenities",
    source: "OSM places; site survey and owner documents pending",
    checks: [
      {
        source: "Customer documents or site survey pending",
        label: "Plot area",
        value: "3,420 m²",
      },
      { source: "Site survey pending", label: "Parking bays", value: "12" },
      { source: "Site survey pending", label: "Canopy feasibility", value: "680 m²" },
      {
        source: "OpenStreetMap places within 1 km; walking access unverified",
        label: "Amenities within walking distance",
        value: "6",
      },
      { source: "Site measurement pending", label: "Mobile network coverage", value: "−79 dBm" },
      { source: "Site measurement pending", label: "Night lighting", value: "18 lux" },
      { source: "Customer agreement pending", label: "Land or lease cost", value: "₹1.8 lakh/mo" },
    ],
  },
  {
    key: "competition",
    short: "Competition",
    name: "Competition",
    source: "Dated inventory; announced-charger evidence pending",
    checks: [
      {
        source: "Dated competitor inventory; geodesic distance",
        label: "Competitor distance",
        value: "2.4 km",
      },
      {
        source: "Dated competitor inventory; radius counts",
        label: "Competitor density at 3 / 5 / 10 km",
        value: "1 / 3 / 5",
      },
      {
        source:
          "Dated charging inventory / NHAI WSA evidence pending; amenities are not open chargers",
        label: "Announced stations",
        value: "2",
      },
    ],
  },
];

export const TOTAL_CHECKS = GROUPS.reduce((n, g) => n + g.checks.length, 0);

/**
 * The source plates, derived so they can never name something the checks do
 * not actually read. An earlier hand-written list carried "Field survey" and
 * "Land & policy", neither of which the pipeline fetches - a claim about
 * capability, not decoration, and worse than an illustrative number.
 */
export const SOURCES: readonly { readonly name: string; readonly stamp: string }[] = GROUPS.map(
  (g) => ({ name: g.source, stamp: g.name }),
);

/** Counts require a stored report. The illustrative walkthrough has no verification counts. */
export const COVERAGE = [
  { count: "—", label: "Measured" },
  { count: "—", label: "Sourced" },
  { count: "—", label: "Unverified", unverified: true },
] as const;

/** Real vocabulary - see VerdictPayload. The band is illustrative. */
export const VERDICT = {
  word: "Conditional build",
  copy: "Strong access and viable grid proximity. Verify outage history before capital commitment.",
  p10: "19%",
  breakeven: "26%",
  p90: "34%",
} as const;

/**
 * An unnamed candidate site - and it must stay unnamed.
 *
 * This deliberately is NOT DEMO_REPORT_ID. The stored report under that id
 * returns DON'T BUILD on a 0.9-2.4% band against a 4.3% breakeven, and
 * ReportPaper renders it twice on the landing page. An animation labelled
 * with that id while ending on "conditional build" would contradict the
 * document sitting a few hundred pixels below it. The verdict here is
 * illustrative, so the site it describes has to be illustrative too.
 */
export const SITE_LABEL = "Candidate site";

/** Find a check by its exact label. Undefined means FACTORS moved under the
 *  caller, which is its cue to render nothing rather than a stale number. */
export function checkByLabel(label: string): Check | undefined {
  for (const group of GROUPS) {
    const hit = group.checks.find((c) => c.label === label);
    if (hit) return hit;
  }
  return undefined;
}

/**
 * The three figures on the hero card, named by the check they are read from
 * rather than typed out. The card cannot carry a number that is not one of
 * the 34, and if a factor is renamed the row disappears instead of lying.
 */
export const HERO_METRICS: readonly { readonly label: string; readonly value: string }[] = (
  [
    { label: "Traffic", from: "AADT traffic count" },
    { label: "Grid distance", from: "Transformer distance" },
    { label: "Competition", from: "Competitor density at 3 / 5 / 10 km" },
  ] as const
).flatMap((m) => {
  const check = checkByLabel(m.from);
  return check ? [{ label: m.label, value: check.value }] : [];
});

/* ------------------------------------------------------------------ *
 * The operator question - a different question from the 34.
 *
 * The 34 above decide whether anything should be built here. Every one of
 * them is a property of the LAND and is identical whichever operator signs.
 * These twelve decide WHO runs it, and they are site-conditional: the same
 * operator scores differently at two sites five kilometres apart.
 *
 * Same rules as everything else in this file. Grouped BY SOURCE, one group
 * one fetch. Names are illustrative content for a fictional site; the
 * operators below are deliberately UNNAMED, because Landing.tsx promises
 * that partner operators appear named only with written permission, and an
 * animation is not an exception to that.
 *
 * Backend state as of 2026-09-07: groups 1 and 2 are computed for real
 * (app/domain/cpo/presence.py); groups 3 to 5 are not. See
 * CPO_SELECTION_PLAN.md and /console/operators.
 * ------------------------------------------------------------------ */

export type OperatorFactor = {
  readonly label: string;
  /** What it does to the answer, in one clause. Never a score. */
  readonly effect: string;
};

export type OperatorGroup = {
  readonly key: string;
  readonly name: string;
  readonly source: string;
  readonly factors: readonly OperatorFactor[];
};

/** Twelve, grouped 4 / 2 / 2 / 2 / 2 by source. */
export const OPERATOR_GROUPS: readonly OperatorGroup[] = [
  {
    key: "reach",
    name: "Network reach",
    source: "Our charger inventory, by operator",
    factors: [
      {
        label: "Their stations in your district",
        effect: "how many drivers nearby already carry their app",
      },
      {
        label: "Their stations in your state",
        effect: "how far the nearest engineer is when a charger fails",
      },
      {
        label: "Their own stations within 3 km",
        effect: "the split — their app can send those drivers there instead",
      },
      { label: "Their own stations within 10 km", effect: "the same split, wider and weaker" },
    ],
  },
  {
    key: "channel",
    name: "Demand channel",
    source: "VAHAN records where loaded; fleet inventory pending",
    factors: [
      {
        label: "Registrations against their presence",
        effect: "how much of the local demand their network plausibly reaches",
      },
      {
        label: "Connector fit against the vehicle mix",
        effect: "a two-wheeler district and a car-only network is a mismatch",
      },
    ],
  },
  {
    key: "reachability",
    name: "Interoperability",
    source: "Roaming and interoperability registers",
    factors: [
      {
        label: "Roaming with other apps",
        effect: "a driver on a rival app can still find and pay at your plug",
      },
      {
        label: "Reservation and in-app routing",
        effect: "whether they send a driver to you or wait to be found",
      },
    ],
  },
  {
    key: "terms",
    name: "Commercial terms",
    source: "Written terms, on file",
    factors: [
      { label: "Revenue share or fee per unit", effect: "what reaches you from each unit sold" },
      {
        label: "Platform fee, maintenance, tenure",
        effect: "the fixed costs and how long you are tied in",
      },
    ],
  },
];

export const TOTAL_OPERATOR_FACTORS = OPERATOR_GROUPS.reduce((n, g) => n + g.factors.length, 0);

/**
 * Three candidate operators at one illustrative site.
 *
 * UNNAMED on purpose - see the block comment above. The shape of the
 * argument is the point: the operator with the widest reach is also the one
 * whose own chargers are nearest, and no single score can settle that trade
 * for the site owner.
 */
export type OperatorCandidate = {
  readonly id: string;
  readonly label: string;
  readonly ours: boolean;
  readonly ownWithin3km: number;
  readonly district: number;
  readonly state: number;
  readonly roaming: boolean;
  /** What their own nearby stations do to this site's volume. */
  readonly note: string;
};

export const OPERATOR_CANDIDATES: readonly OperatorCandidate[] = [
  {
    id: "a",
    label: "Network A",
    ours: true,
    ownWithin3km: 3,
    district: 32,
    state: 281,
    roaming: true,
    note: "The widest reach here, and the nearest chargers of their own. Their app has three other places to send the same drivers.",
  },
  {
    id: "b",
    label: "Network B",
    ours: false,
    ownWithin3km: 1,
    district: 24,
    state: 284,
    roaming: true,
    note: "Comparable reach, one station of their own within 3 km. One place to lose a driver to, not three.",
  },
  {
    id: "c",
    label: "Network C",
    ours: false,
    ownWithin3km: 0,
    district: 3,
    state: 4,
    roaming: false,
    note: "Nothing of theirs nearby to divide the demand — and almost nothing in the state, so no local audience and no engineer close by.",
  },
];

/**
 * Six neighbouring chargers, as they sit around the illustrative site.
 * ``x``/``y`` are percentages of the plane, ``owner`` indexes
 * OPERATOR_CANDIDATES by id, and ``near`` marks the ones inside 3 km.
 */
export const NEIGHBOURS: readonly {
  readonly id: string;
  readonly owner: string;
  readonly x: number;
  readonly y: number;
  readonly near: boolean;
}[] = [
  { id: "n1", owner: "a", x: 34, y: 30, near: true },
  { id: "n2", owner: "a", x: 68, y: 36, near: true },
  { id: "n3", owner: "a", x: 58, y: 70, near: true },
  { id: "n4", owner: "b", x: 30, y: 66, near: true },
  { id: "n5", owner: "b", x: 84, y: 18, near: false },
  { id: "n6", owner: "c", x: 16, y: 84, near: false },
];
