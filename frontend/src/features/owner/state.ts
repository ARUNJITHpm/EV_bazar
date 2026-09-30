import type { components } from "../../api/schema";
import { rupeesToPaise } from "../../lib/money";

export type BillIn = components["schemas"]["BillIn"];
export type ConnectorIn = components["schemas"]["ConnectorIn"];
export type StationHome = components["schemas"]["StationHome"];
export type PortfolioRow = components["schemas"]["PortfolioRow"];
export type MeterAnswer = NonNullable<components["schemas"]["OnboardIn"]["meter_answer"]>;
export type Standard = ConnectorIn["standard"];

/** Months are "YYYY-MM" strings end to end: that is what the API takes, and
 *  there is no date arithmetic here beyond stepping a month at a time. */
export type Month = string;

export interface DraftConnector {
  standard: Standard;
  power_kw: number;
  count: number;
}

/** Common connectors, one tap each. */
export const PRESETS: { label: string; standard: Standard; power_kw: number }[] = [
  { label: "CCS2 60 kW", standard: "CCS2", power_kw: 60 },
  { label: "CCS2 30 kW", standard: "CCS2", power_kw: 30 },
  { label: "Type 2 AC 7.4 kW", standard: "Type 2 AC", power_kw: 7.4 },
];

export interface OwnerDraft {
  /** Whether this visitor is creating an account or logging in. */
  mode: "new" | "returning" | null;
  /** Never the password: that lives only in the password screen's own state. */
  phone: string;
  /** Text as typed, so a half-typed number survives a reload. */
  bill: {
    period: Month | null;
    kwh: string;
    imageId: string | null;
    imageType: string | null;
    history: Record<Month, string>;
    tariff: string;
    contractDemand: string;
    recordedDemand: string;
    demandUnit: "kVA" | "kW";
    powerFactor: string;
    pfEffect: "penalty" | "incentive" | null;
    pfAmountRupees: string;
    todPeak: string;
    todNormal: string;
    todOffPeak: string;
    board: string;
    consumerNumber: string;
    confirmed: boolean;
  };
  name: string;
  address: string;
  pin: { lat: number; lng: number } | null;
  connectors: DraftConnector[];
  wentLive: Month | null;
  meter: MeterAnswer | null;
  consent: boolean;
}

export const blankBill = (): OwnerDraft["bill"] => ({
  period: null,
  kwh: "",
  imageId: null,
  imageType: null,
  history: {},
  tariff: "",
  contractDemand: "",
  recordedDemand: "",
  demandUnit: "kVA",
  powerFactor: "",
  pfEffect: null,
  pfAmountRupees: "",
  todPeak: "",
  todNormal: "",
  todOffPeak: "",
  board: "",
  consumerNumber: "",
  confirmed: false,
});

export const blankDraft = (): OwnerDraft => ({
  mode: null,
  phone: "",
  bill: blankBill(),
  name: "",
  address: "",
  pin: null,
  connectors: [],
  wentLive: null,
  meter: null,
  consent: false,
});

// The draft holds no station id or connector id any more; bumped so an older
// draft (which did) is dropped rather than misread.
const KEY = "cw-owner-draft-3";

export function loadDraft(): OwnerDraft {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Partial<OwnerDraft>;
      return { ...blankDraft(), ...saved, bill: { ...blankBill(), ...saved.bill } };
    }
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

/** "2026-03-01" from the API -> "2026-03". */
export const toMonth = (isoDate: string): Month => isoDate.slice(0, 7);

/** The latest month an owner can hold a full bill for: last calendar month. */
export function lastFullMonth(now = new Date()): Month {
  return monthFromIndex(now.getFullYear() * 12 + now.getMonth() - 1);
}

/** The twelve months before ``period``, oldest first: what a bill's history covers. */
export const historyMonths = (period: Month): Month[] =>
  Array.from({ length: 12 }, (_, k) => monthFromIndex(monthIndex(period) - 12 + k));

const num = (s: string): number | null => {
  const n = Number(s.replace(/,/g, "").trim());
  return s.trim() !== "" && Number.isFinite(n) ? n : null;
};

export const totalKw = (connectors: DraftConnector[]): number =>
  connectors.reduce((sum, c) => sum + c.power_kw * c.count, 0);

/** Every connector on its own row, as the API takes them. */
export const expandConnectors = (connectors: DraftConnector[]): ConnectorIn[] =>
  connectors.flatMap((c) =>
    Array.from({ length: c.count }, () => ({ standard: c.standard, power_kw: c.power_kw })),
  );

/** Mirrors the server's tariff rule only to skip a question; the server decides. */
export const tariffImpliesOwnMeter = (tariff: string): boolean =>
  /\b(ev|electric vehicle|charging)\b/i.test(tariff);

/** The bill as the API takes it. Blank optional fields are left out. */
export function toBillIn(b: OwnerDraft["bill"]): BillIn | null {
  const kwh = num(b.kwh);
  if (!b.period || kwh === null) return null;
  const demand = num(b.contractDemand) !== null || num(b.recordedDemand) !== null;
  const pfAmount = num(b.pfAmountRupees);
  return {
    confirmed: b.confirmed,
    period: b.period,
    kwh,
    image_id: b.imageId,
    history: Object.entries(b.history).flatMap(([period, v]) => {
      const n = num(v);
      return n === null ? [] : [{ period, kwh: n }];
    }),
    tariff_category: b.tariff.trim() || null,
    contract_demand: num(b.contractDemand),
    recorded_demand: num(b.recordedDemand),
    demand_unit: demand ? b.demandUnit : null,
    power_factor: num(b.powerFactor),
    pf_effect: b.pfEffect,
    pf_amount_paise: pfAmount === null ? null : rupeesToPaise(pfAmount),
    tod_peak_kwh: num(b.todPeak),
    tod_normal_kwh: num(b.todNormal),
    tod_offpeak_kwh: num(b.todOffPeak),
    board: b.board.trim() || null,
    consumer_number: b.consumerNumber.trim() || null,
  };
}

/** A message from the API's ``detail``, or ``fallback``. */
export function detailOf(err: unknown, fallback: string): string {
  const detail = (err as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}
