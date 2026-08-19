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

export interface UtilisationBand {
  p10: number;
  p50: number;
  p90: number;
  /** Which model produced the band. "synthetic_v0" is the labelled stopgap. */
  model_version: string;
  /** True until the band comes from measured occupancy. Drives the ⚠ state. */
  modelled_not_measured: boolean;
}

export interface Scenario {
  label: string;
  utilisation: number;
  kwh_year: number;
  npv_paise: Paise;
  irr_pct: number | null;
  payback_years: number | null;
}

export interface SiteFact {
  label: string;
  value: string;
  source: string;
  /** Unverified or modelled — rendered in the single warn accent. */
  unverified: boolean;
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
  irr_p50_pct: number;
  margin_of_safety_pp: number;
  uptime: string;
  ocpi_roaming: boolean;
}

export interface LedgerRow {
  item: string;
  value: string;
  source: string;
  unverified: boolean;
}

export interface ReportPayload {
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
  breakeven: {
    utilisation: number;
    kwh_year: number;
    kwh_day: number;
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
  competitors: { within_3km: number; nearest: CompetitorRow[]; source: string };
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
  };
  cpo: CpoRow[];
  ledger: LedgerRow[];
  provenance: { label: string; value: string; unverified?: boolean }[];
}

/** The one report that exists before the assess pipeline does. */
export const DEMO_REPORT_ID = "KL-TVM-DEMO-001";

export async function fetchReport(reportId: string): Promise<ReportPayload> {
  const res = await fetch(`/api/internal/reports/${encodeURIComponent(reportId)}`);
  if (res.status === 404) throw new Error("no such report");
  if (!res.ok) throw new Error(`reports returned ${res.status}`);
  return (await res.json()) as ReportPayload;
}
