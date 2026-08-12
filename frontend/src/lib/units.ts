/**
 * Energy and power units.
 *
 * OVERVIEW.md glossary, "the two that matter most":
 *
 *   A 60 kW charger at 0.9 power factor needs ~67 kVA sanctioned. Demand
 *   charges of Rs 300-500/kVA/month = Rs 2.4-4 lakh/year before selling a
 *   single unit. Get this wrong and every financial number is wrong.
 *
 * So kW and kVA are branded types. Passing one where the other is expected
 * is a compile error, not a silent 11% error in the demand-charge line.
 */

declare const brand: unique symbol;
type Brand<T, B> = T & { readonly [brand]: B };

/** Real power. What a charger delivers to a vehicle. */
export type Kw = Brand<number, "kW">;
/** Apparent power. What the DISCOM sanctions and bills. */
export type Kva = Brand<number, "kVA">;
/** Energy. */
export type Kwh = Brand<number, "kWh">;

export const kw = (n: number): Kw => n as Kw;
export const kva = (n: number): Kva => n as Kva;
export const kwh = (n: number): Kwh => n as Kwh;

/**
 * The only sanctioned conversion, and it requires an explicit power factor.
 *
 * There is no default. A caller that does not know the power factor does not
 * know the demand charge either, and should not be quietly given a number.
 */
export function kwToKva(power: Kw, powerFactor: number): Kva {
  if (powerFactor <= 0 || powerFactor > 1) {
    throw new Error(`units: power factor must be in (0, 1], got ${powerFactor}`);
  }
  return kva(power / powerFactor);
}

export const formatKw = (v: Kw): string => `${trim(v)} kW`;
export const formatKva = (v: Kva): string => `${trim(v)} kVA`;
export const formatKwh = (v: Kwh): string => `${trim(v)} kWh`;

/** Utilisation as a percentage. Always a range in user-facing output (Rule 4). */
export function formatUtilisation(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`;
}

/** Percentage points - for margin of safety, which is a difference, not a ratio. */
export function formatPercentagePoints(pp: number): string {
  const sign = pp > 0 ? "+" : "";
  return `${sign}${pp.toFixed(1)} pp`;
}

function trim(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
