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
 * The factor names are NOT illustrative. They are Landing.tsx's FACTORS
 * array verbatim, in order, grouped into the five categories the flat list
 * implies (9 / 7 / 8 / 6 / 4 = 34). If a factor is added there, add it here.
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
  readonly checks: readonly Check[];
};

export const GROUPS: readonly Group[] = [
  {
    key: "road",
    short: "Road",
    name: "Road access & geometry",
    checks: [
      { label: "Road class", value: "NH arterial" },
      { label: "Distance from main road", value: "0.4 km" },
      { label: "Carriageway direction served", value: "Eastbound" },
      { label: "Sub-road access", value: "2 points" },
      { label: "Median or divider", value: "Divided" },
      { label: "Sight line", value: "180 m" },
      { label: "Turning radius", value: "12.5 m" },
      { label: "Entry and exit width", value: "8.2 m" },
      { label: "Frontage width", value: "46 m" },
    ],
  },
  {
    key: "demand",
    short: "Demand",
    name: "Demand & mobility",
    checks: [
      { label: "AADT traffic count", value: "18,400 /day" },
      { label: "Dominant flow direction", value: "Inbound AM" },
      { label: "Peak hour timing", value: "08:00–10:00" },
      { label: "EV registrations", value: "12,540" },
      { label: "Registration mix", value: "68% 4W" },
      { label: "Fleet operators within 10 km", value: "14" },
      { label: "Distance to nearest city", value: "6.8 km" },
    ],
  },
  {
    key: "grid",
    short: "Grid",
    name: "Grid, tariff & policy",
    checks: [
      { label: "Tariff order", value: "TOU C&I" },
      { label: "Demand charges", value: "₹390 /kVA" },
      { label: "Sanctioned load", value: "75 kVA" },
      { label: "Transformer distance", value: "140 m" },
      { label: "Transformer spare capacity", value: "180 kVA" },
      /* The one copper value on the whole surface. Its meaning is the
         product's argument: a gap is reported, never quietly filled. */
      { label: "Grid outage hours", value: "unverified", unverified: true },
      { label: "New connection cost", value: "₹8.4 lakh" },
      { label: "State subsidy applicability", value: "Applicable" },
    ],
  },
  {
    key: "plot",
    short: "Plot",
    name: "Plot readiness",
    checks: [
      { label: "Plot area", value: "3,420 m²" },
      { label: "Parking bays", value: "12" },
      { label: "Canopy feasibility", value: "680 m²" },
      { label: "Amenities within walking distance", value: "6" },
      { label: "Mobile network coverage", value: "−79 dBm" },
      { label: "Night lighting", value: "18 lux" },
    ],
  },
  {
    key: "commercial",
    short: "Market",
    name: "Commercial landscape",
    checks: [
      { label: "Land or lease cost", value: "₹1.8 lakh/mo" },
      { label: "Competitor distance", value: "2.4 km" },
      { label: "Competitor density at 3 / 5 / 10 km", value: "1 / 3 / 5" },
      { label: "Announced stations", value: "2" },
    ],
  },
];

export const TOTAL_CHECKS = GROUPS.reduce((n, g) => n + g.checks.length, 0);

/** Every check, keyed by the factor name Landing.tsx and Working.tsx share. */
const BY_LABEL = new Map(GROUPS.flatMap((g) => g.checks.map((c) => [c.label, c] as const)));

/**
 * The illustrative value for a factor, for callers that hold the 34 names in
 * a DIFFERENT grouping - flow/Working.tsx groups them 12/4/8/7/3 by source
 * where this file groups them 9/7/8/6/4 by subject. The names are identical
 * in both (they come from Landing.tsx's FACTORS), so a label lookup crosses
 * between them safely; the counts do not.
 *
 * Returns undefined for an unknown label rather than inventing something -
 * a factor added in one place and not the other should render blank, not
 * wrong.
 */
export function checkFor(label: string): Check | undefined {
  return BY_LABEL.get(label);
}

/** Where the factors come from. Names are public data sources, not partners. */
export const SOURCES: readonly { readonly name: string; readonly stamp: string }[] = [
  { name: "VAHAN · Parivahan", stamp: "Registrations · mix" },
  { name: "OpenStreetMap", stamp: "Roads · POIs · access" },
  { name: "DISCOM tariff orders", stamp: "Load · cost · policy" },
  { name: "Field survey", stamp: "Geometry · amenities" },
  { name: "Competitor census", stamp: "3 · 5 · 10 km" },
  { name: "Land & policy", stamp: "Lease · subsidy" },
];

/** Counts across the 34. measured + sourced + unverified must equal TOTAL_CHECKS. */
export const COVERAGE = [
  { count: 27, label: "Measured" },
  { count: 6, label: "Sourced" },
  { count: 1, label: "Unverified", unverified: true },
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
