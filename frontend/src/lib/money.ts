/**
 * The only place paise become rupees.
 *
 * AGENTS.md: money is integer paise everywhere - backend, wire, and client.
 * Floating-point rupees are how a report ends up asserting a payback period
 * that is off by a rounding error, so the conversion happens once, here, at
 * the render boundary.
 */

/** Integer paise. 100 paise = 1 rupee. Never a float. */
export type Paise = number;

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const INR_PRECISE = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function assertInteger(paise: Paise): void {
  if (!Number.isInteger(paise)) {
    throw new Error(
      `money: expected integer paise, got ${paise}. ` +
        "A fractional value here means a rupee amount leaked in somewhere upstream.",
    );
  }
}

/** Whole rupees, Indian digit grouping. `formatRupees(1234567800)` -> "₹1,23,45,678". */
export function formatRupees(paise: Paise): string {
  assertInteger(paise);
  return INR.format(paise / 100);
}

/** Rupees and paise, for per-kWh margins where the paise genuinely matter. */
export function formatRupeesPrecise(paise: Paise): string {
  assertInteger(paise);
  return INR_PRECISE.format(paise / 100);
}

/**
 * Lakh / crore for capex and annual figures.
 *
 * Indian financial readers parse "₹42.5 L" far faster than "₹42,50,000",
 * and capex is always discussed in these units in this market.
 */
export function formatRupeesCompact(paise: Paise): string {
  assertInteger(paise);
  const rupees = paise / 100;
  const abs = Math.abs(rupees);
  if (abs >= 1_00_00_000) return `₹${(rupees / 1_00_00_000).toFixed(2)} Cr`;
  if (abs >= 1_00_000) return `₹${(rupees / 1_00_000).toFixed(2)} L`;
  if (abs >= 1_000) return `₹${(rupees / 1_000).toFixed(1)}k`;
  return INR.format(rupees);
}

/** Rupees in, paise out. For form input only - never for arithmetic on API values. */
export function rupeesToPaise(rupees: number): Paise {
  return Math.round(rupees * 100);
}
