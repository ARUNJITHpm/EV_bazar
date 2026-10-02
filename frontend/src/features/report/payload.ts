import type { components } from "../../api/schema";
import { api } from "../../api/client";
import type { Paise } from "../../lib/money";

/**
 * The report payload, as `GET /api/internal/reports/{id}` serves it — the
 * stored JSONB data of record (AGENTS.md rule 9), shaped by
 * `app/domain/report/payload.py`. These types mirror that pydantic model
 * field for field; the generated `api/schema.d.ts` carries the same shape
 * from the OpenAPI contract and CI fails if the two drift apart.
 *
 * Money is integer paise (lib/money.ts renders it). Utilisation is a fraction
 * of rated capacity. Every uncertain number is a P10/P50/P90 band, never a
 * point (AGENTS.md rule 6).
 */

export type Verdict = "build" | "conditional" | "dont";

/** Which side of the argument a fact lands on. Rendered as a sign AND a
 *  word, never colour alone — a bank file gets photocopied. */
export type Direction = "favours" | "against" | "neutral";

export interface UtilisationBand {
  p10: number;
  p50: number;
  p90: number;
  /** Which model produced the band. "synthetic_v0" is the labelled stopgap. */
  model_version: string;
  /** True until the band comes from measured occupancy. Drives the ⚠ state. */
  modelled_not_measured: boolean;
}

/**
 * The same case again, in money an owner can check against a bank statement
 * (Track B · R6). NPV, IRR and payback all still sit above this — R5 kept
 * them — but none of them is a figure a landowner has been handed before.
 *
 * The annual figures are the STEADY year, the last year of the demand ramp,
 * which is the same year `Scenario.kwh_year` reports. `cumulative_paise` is
 * where the ramp shows: it is the engine's own year-by-year running total
 * from year 0 (the build, always negative) to the end of the horizon.
 */
export interface PlainMoney {
  revenue_paise_year: Paise;
  /** Electricity, the operator's cut and the gateway — everything that
   *  scales with what is sold. */
  running_cost_paise_year: Paise;
  fixed_cost_paise_year: Paise;
  cash_paise_year: Paise;
  revenue_paise_month: Paise;
  cash_paise_month: Paise;
  /** Year 0 through the horizon inclusive. Negative means the setup money
   *  is not back yet. */
  cumulative_paise: Paise[];
}

export interface Scenario {
  label: string;
  utilisation: number;
  kwh_year: number;
  npv_paise: Paise;
  irr_pct: number | null;
  payback_years: number | null;
  /** Absent on payloads stored by economics 0.2.0 — sections 02 and 05 then
   *  omit their plain-money blocks rather than invent the numbers. */
  plain?: PlainMoney | null;
}

/** One line of a breakdown: per year in `fixed_costs`, one-off in
 *  `capex_lines`, per unit in `unit_economics`. */
export interface CostLine {
  label: string;
  paise: Paise;
}

/**
 * One unit's price and everyone who takes a piece before the site does.
 * `selling_paise_kwh` minus every deduction is EXACTLY `margin_paise_kwh` —
 * the engine guarantees it, which is what lets section 05 print the chain as
 * a sentence the reader can check in their head.
 */
export interface UnitEconomics {
  selling_paise_kwh: Paise;
  deductions: CostLine[];
  margin_paise_kwh: Paise;
}

/** The monthly bills, itemised. The lines sum to the total; zero lines are
 *  omitted rather than printed as ₹0 rows. */
export interface FixedCosts {
  lines: CostLine[];
  total_paise_year: Paise;
  total_paise_month: Paise;
}

export interface SiteFact {
  label: string;
  value: string;
  source: string;
  /** Unverified or modelled — rendered in the single warn accent. */
  unverified: boolean;
  /** The heading the fact sits under. Absent on payloads stored before the
   *  factors table grew its markers; the page then renders one flat group. */
  group?: string | null;
  direction?: Direction | null;
  /** Why this check is on the list at all, in one plain sentence — a property
   *  of the FACTOR, not of this site's value. Absent on payloads stored
   *  before the column existed; section 04 then omits the line. */
  means?: string | null;
}

export interface CompetitorRow {
  name: string;
  operator: string;
  distance_m: number;
  max_power_kw: number;
  points: number;
}

export interface CpoRow {
  operator: string;
  ours: boolean;
  revenue_share_pct: number;
  platform_fee_paise_year: Paise;
  /** null when the central case never returns the capital — a fact, not 0%. */
  irr_p50_pct: number | null;
  margin_of_safety_pp: number;
  /** The steady-year cash THIS operator's terms leave. A return is comparable
   *  but abstract; this is the number the owner feels, and it is what makes
   *  the revenue share beside it mean something. Absent on payloads stored
   *  before the column existed — the column then disappears. */
  cash_p50_paise_year?: Paise | null;
  uptime: string;
  ocpi_roaming: boolean;
  /** Hours to attend a fault, and the years the owner is locked in. Both wait
   *  on `cpo_terms` (PLAN 2.3); until then every operator carries null and
   *  section 06 drops both columns rather than printing a column of dashes. */
  repair_hours?: number | null;
  tie_in_years?: number | null;
  /** How much of THIS operator's own network already sits around the site.
   *  null where the name is not matched to a network we inventory, or is not
   *  a network at all — unknown, which must never render as zero. */
  stations_district?: number | null;
  stations_state?: number | null;
  own_within_3km?: number | null;
  own_within_10km?: number | null;
  /** One plain sentence: what their own nearby stations do to your volume. */
  presence_note?: string;
}

export interface LedgerRow {
  item: string;
  value: string;
  source: string;
  unverified: boolean;
}

export interface ReportPayload {
  public_context?: components["schemas"]["PublicContextPayload"] | null;
  report_id: string;
  demo: boolean;
  site: {
    name: string;
    line: string;
    district: string;
    lgd_district_code: number;
    lat: number;
    lng: number;
    archetype: string;
    data_tier: 1 | 2 | 3;
  };
  hardware: {
    connectors: number;
    rated_kw_each: number;
    sanctioned_kva_full: number;
  };
  /**
   * Two thresholds. The first three are the RUNNING-BILL breakeven — how busy
   * the site must be to stop losing money month to month, build cost
   * excluded. The `full_cost_*` trio adds the build cost spread over ten
   * years: how busy it must be to have been worth building at all.
   *
   * Separate numbers, not one relabelled: a site can clear the first, earn a
   * BUILD verdict, and still be short over ten years. Absent on payloads
   * stored by economics 0.1.0.
   */
  breakeven: {
    utilisation: number;
    kwh_year: number;
    kwh_day: number;
    full_cost_utilisation?: number | null;
    full_cost_kwh_year?: number | null;
    full_cost_kwh_day?: number | null;
    /** The build-cost half of the full-cost line, per year (Track B · R7).
     *  Section 09 prints the division rather than asserting its answer, and a
     *  sum the reader is invited to check has to show every term in it. */
    full_cost_recovery_paise_year?: Paise | null;
  };
  predicted: UtilisationBand;
  margin_of_safety_pp: number;
  verdict: { value: Verdict; reason: string };
  demand: {
    district_ev_2025: number;
    district_growth_yoy_pct: number;
    two_wheeler_share_pct: number;
    vahan_snapshot: string;
  };
  site_facts: SiteFact[];
  competitors: {
    within_3km: number;
    nearest: CompetitorRow[];
    source: string;
    within_5km?: number | null;
    dc_fast_within_3km?: number | null;
  };
  financials: {
    capex_paise: Paise;
    selling_price_paise_kwh: Paise;
    energy_tariff_paise_kwh: Paise;
    scenarios: Scenario[];
    anchor_note: {
      kwh_year: number;
      npv_paise: Paise;
      irr_pct: number;
    };
    sanctioned_load: {
      full_kva: number;
      recommended_kva: number;
      recommended_label: string;
      saving_paise_year: Paise;
      buffered_kva: number;
    };
    price_sensitivity: { price_paise_kwh: Paise; breakeven_utilisation: number }[];
    /** The working behind the headline (Track B · R6): the one-time budget
     *  summing to `capex_paise`, the per-unit chain, and the monthly bills.
     *  All absent on payloads stored by economics 0.2.0. */
    capex_lines?: CostLine[] | null;
    unit_economics?: UnitEconomics | null;
    fixed_costs?: FixedCosts | null;
  };
  cpo: CpoRow[];
  ledger: LedgerRow[];
  /** The ENGINE's own assumption ledger, verbatim — the model's choices
   *  (discount rate, O&M share, what the utilisation ceiling means), as
   *  distinct from `ledger`, which is where each INPUT came from and whether
   *  anyone has confirmed it. engine.py has always written these and nothing
   *  ever printed them (Track B · R10). Absent on payloads stored before
   *  then; section 10 prints the input table alone. */
  model_assumptions?: string[];
  provenance: { label: string; value: string; unverified?: boolean }[];
  /** The day this payload was assembled, ISO. A document with no date on it
   *  cannot defend itself, which is section 11's whole job. Absent on
   *  payloads stored before R10. */
  generated_at?: string | null;
}

/** The one report that exists before the assess pipeline does. */
export const DEMO_REPORT_ID = "KL-TVM-DEMO-001";

/** The engine's planning horizon — every NPV and payback figure is over
 *  this many years (app/domain/roi/engine.py, RoiInputs.horizon_years). */
export const HORIZON_YEARS = 10;

export type CaseId = "P10" | "P50" | "P90";

/**
 * Does this case's cash actually ramp, or is every year the same size?
 *
 * The engine ramps. The hand-written fixtures do not — they are one flat
 * annual volume, which is what makes their NPVs reproducible by hand. A
 * footnote asserting "the early years are smaller" printed over a column of
 * identical numbers is the document contradicting itself on the same page,
 * which is the failure this whole rebuild exists to remove. So the sentence
 * is chosen from the data instead of assumed (Track B · R6).
 *
 * One rupee of growth across the horizon is the threshold: below that it is
 * rounding, not a ramp.
 */
export function ramps(m: PlainMoney): boolean {
  const c = m.cumulative_paise;
  if (c.length < 4) return false;
  const first = (c[2] ?? 0) - (c[1] ?? 0);
  const last = (c[c.length - 1] ?? 0) - (c[c.length - 2] ?? 0);
  return last - first > 100;
}

/** The three cases in the order they are always printed. */
export const CASES: readonly CaseId[] = ["P10", "P50", "P90"] as const;

/**
 * The one place the cases have plain names.
 *
 * The sample document calls them CAUTIOUS / MIDDLE / OPTIMISTIC and R5's
 * plan copied that. We kept downside / central / upside instead, because
 * five other sections already say "the downside case" in their prose, and a
 * third vocabulary for the same three numbers is exactly the drift R2 built
 * this shared module to prevent. "Cautious" also describes the forecaster
 * rather than the outcome; "downside" describes the outcome.
 */
export const CASE_LABEL: Record<CaseId, string> = {
  P10: "Downside",
  P50: "Central",
  P90: "Upside",
};

/** The scenario rows are labelled "P10 · downside" and so on by the
 *  assembler; the case id is the stable prefix. */
export function scenarioFor(payload: ReportPayload, c: CaseId): Scenario | undefined {
  return payload.financials.scenarios.find((s) => s.label.startsWith(c));
}

export async function fetchReport(reportId: string): Promise<ReportPayload> {
  const { data, response } = await api.GET("/api/internal/reports/{report_id}", {
    params: { path: { report_id: reportId } },
  });
  if (response.status === 404) throw new Error("no such report");
  if (!response.ok || !data) throw new Error(`reports returned ${response.status}`);
  return data;
}
