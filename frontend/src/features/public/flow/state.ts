import type { components } from "../../../api/schema";

/**
 * The assessment flow's state - one object, persisted to sessionStorage so
 * a refresh mid-flow loses nothing (a non-negotiable from design/IMPLEMENT.md).
 *
 * "skip" is a first-class answer, not an absence: the owner said they do not
 * know, and the teaser echoes the archetype default that applied instead.
 */

export type AssessOut = components["schemas"]["AssessOut"];
export type AssessIn = components["schemas"]["AssessIn"];

export type YesNoSkip = "yes" | "no" | "skip";
export type LandAnswer = "own" | "lease" | "skip";
export type IntentAnswer = "income" | "fleet" | "visitors" | "skip";

export interface Answers {
  connection?: YesNoSkip;
  /** Sanctioned load in kVA; "skip" when the owner does not know it. */
  kva?: number | "skip";
  transformer?: YesNoSkip;
  land?: LandAnswer;
  intent?: IntentAnswer;
}

export interface FlowState {
  pin?: { lat: number; lng: number };
  /** The locate step's confirmation - the bare POST /assess response. */
  confirmed?: AssessOut;
  answers: Answers;
  /** The finishing POST's response, shown on the result screen. */
  result?: AssessOut;
}

const STORE = "cw.assessment";

/**
 * State names arrive from the LGD reference layer in caps ("KERALA"). That is
 * right for a database and shouting on a customer's screen, so it is cased
 * here rather than in the payload - the stored value stays what was resolved.
 */
export function placeName(district: string | null, state: string | null): string {
  const cased = state
    ? state
        .toLocaleLowerCase("en-IN")
        .replace(
          /(^|[\s-])(\p{L})/gu,
          (_, sep: string, c: string) => sep + c.toLocaleUpperCase("en-IN"),
        )
    : null;
  return [district, cased].filter(Boolean).join(", ");
}

export function loadState(): FlowState {
  try {
    const raw = sessionStorage.getItem(STORE);
    const parsed = raw ? (JSON.parse(raw) as FlowState) : null;
    if (!parsed || typeof parsed !== "object") return { answers: {} };
    return { ...parsed, answers: parsed.answers ?? {} };
  } catch {
    return { answers: {} };
  }
}

export function saveState(state: FlowState): void {
  try {
    sessionStorage.setItem(STORE, JSON.stringify(state));
  } catch {
    // Private browsing - the flow still works, it just won't survive a refresh.
  }
}

export function clearState(): void {
  try {
    sessionStorage.removeItem(STORE);
  } catch {
    // Nothing stored, nothing lost.
  }
}

/**
 * The answers, translated into the API's taps. "skip" and "unasked" both
 * become null - the backend treats null as "not provided" and echoes the
 * default that applied, which is exactly what a skip means here.
 */
export function toBody(pin: { lat: number; lng: number }, a: Answers): AssessIn {
  const intents: Record<Exclude<IntentAnswer, "skip">, string> = {
    income: "earn from land I own",
    fleet: "serve my own fleet",
    visitors: "serve visitors to my property",
  };
  return {
    lat: pin.lat,
    lng: pin.lng,
    existing_connection: a.connection === "yes" ? true : a.connection === "no" ? false : null,
    sanctioned_kva: typeof a.kva === "number" ? a.kva : null,
    transformer_on_site: a.transformer === "yes" ? true : a.transformer === "no" ? false : null,
    land_owned: a.land === "own" ? true : a.land === "lease" ? false : null,
    budget_band: null,
    intent: a.intent && a.intent !== "skip" ? intents[a.intent] : null,
  };
}
