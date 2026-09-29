import type { components } from "../../api/schema";

export type OwnerStation = components["schemas"]["OwnerStation"];
export type SubmissionOut = components["schemas"]["SubmissionOut"];
export type MeterType = components["schemas"]["SubmissionIn"]["meter_type"];

/** Months are "YYYY-MM" strings end to end: that is what the API takes, and
 *  there is no date arithmetic here beyond stepping a month at a time. */
export type Month = string;

export interface OwnerDraft {
  station: OwnerStation | null;
  connectors: number[];
  installMonth: Month | null;
  meter: MeterType | null;
  /** kWh typed per month, kept as text so a half-typed number survives. */
  readings: Record<Month, string>;
  consentAggregate: boolean;
  consentPublic: boolean;
  result: SubmissionOut | null;
}

export const blankDraft = (): OwnerDraft => ({
  station: null,
  connectors: [],
  installMonth: null,
  meter: null,
  readings: {},
  consentAggregate: false,
  consentPublic: false,
  result: null,
});

const KEY = "cw-owner-draft";

export function loadDraft(): OwnerDraft {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return { ...blankDraft(), ...(JSON.parse(raw) as Partial<OwnerDraft>) };
  } catch {
    /* private window or corrupt draft: start clean */
  }
  return blankDraft();
}

export function saveDraft(d: OwnerDraft): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(d));
  } catch {
    /* the flow still works without persistence */
  }
}

export function clearDraft(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}

export const monthIndex = (m: Month): number => {
  const [y = 0, mo = 1] = m.split("-").map(Number);
  return y * 12 + mo - 1;
};

export const monthFromIndex = (i: number): Month =>
  `${String(Math.floor(i / 12)).padStart(4, "0")}-${String((i % 12) + 1).padStart(2, "0")}`;

const NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const monthLabel = (m: Month): string => {
  const i = monthIndex(m);
  return `${NAMES[i % 12]} ${Math.floor(i / 12)}`;
};

/** The most recent whole months ending at ``latest``, oldest first. */
export const billMonths = (latest: Month, count = 6): Month[] =>
  Array.from({ length: count }, (_, k) => monthFromIndex(monthIndex(latest) - count + 1 + k));

/** Only readings on or after the install month are asked for or sent. */
export function toReadings(d: OwnerDraft): { month: Month; kwh: number }[] {
  return Object.entries(d.readings)
    .map(([month, v]) => ({ month, kwh: Number(v.replace(/,/g, "")) }))
    .filter((r) => Number.isFinite(r.kwh) && r.kwh > 0)
    .filter((r) => !d.installMonth || monthIndex(r.month) >= monthIndex(d.installMonth))
    .sort((a, b) => a.month.localeCompare(b.month));
}
