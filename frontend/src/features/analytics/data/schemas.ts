import { publicDataVersions } from "./versions.ts";
import { z } from "zod";

const text = z.string().trim().min(1);
const url = text
  .url()
  .refine((value) => /^https?:\/\//.test(value), "must be an HTTP(S) source URL");
const integer = z
  .string()
  .regex(/^\d+$/, "must be a non-negative integer")
  .transform(Number)
  .refine(Number.isSafeInteger, "integer is too large");
const code = integer.refine((value) => value > 0, "LGD code must be positive");
const number = z
  .string()
  .regex(/^-?\d+(?:\.\d+)?$/, "must be a finite number")
  .transform(Number)
  .refine(Number.isFinite);
const nullable = <T extends z.ZodTypeAny>(schema: T) =>
  z.union([z.literal("").transform(() => null), schema]);
const date = text.regex(/^\d{4}-\d{2}-\d{2}$/, "use YYYY-MM-DD").refine((value) => {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}, "invalid calendar date");
const month = text.regex(/^\d{4}-(?:0[1-9]|1[0-2])$/, "use YYYY-MM");
const boolean = z.enum(["true", "false"]).transform((value) => value === "true");
const stringArray = z.string().transform((value, context): string[] => {
  try {
    const result: unknown = JSON.parse(value);
    return z.array(text).parse(result);
  } catch {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "must be a JSON array of names" });
    return z.NEVER;
  }
});

export const expansionDatasetIds = [
  "discom_performance",
  "supply_hours",
  "state_ev_policies",
  "nhai_wayside_amenities",
  "osm_power",
  "cea_ev_consumption",
] as const;

export const rowSchemas = {
  district_reference: z
    .object({
      lgd_code: code,
      district_name: text,
      state_name: text,
      slug: text.regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
      former_names: stringArray,
    })
    .strict(),
  rto_to_district: z
    .object({
      state: text,
      rto_code: text.regex(/^[A-Z]{2}\d{1,3}$/),
      lgd_code: code,
      covers_multiple_districts: boolean,
      allocation_note: z.string(),
    })
    .strict(),
  ev_registrations: z
    .object({
      month,
      state: text,
      rto_code: text.regex(/^[A-Z]{2}\d{1,3}$/),
      lgd_code: code,
      vehicle_class: z.enum(["2W", "3W", "4W", "bus", "goods"]),
      fuel: z.enum(["ELECTRIC(BOV)", "PURE EV"]),
      count: integer,
    })
    .strict(),
  public_chargers: z
    .object({
      charger_id: text,
      name: text,
      lat: number.refine((value) => value >= -90 && value <= 90, "latitude outside EPSG:4326"),
      lon: number.refine((value) => value >= -180 && value <= 180, "longitude outside EPSG:4326"),
      lgd_code: code,
      road_class: z.enum(["national_highway", "state_highway", "urban", "rural", "unknown"]),
      connector_type: text,
      power_kw: number.refine((value) => value > 0, "power must be positive kW"),
      ac_or_dc: z.enum(["AC", "DC"]),
      opened_month: nullable(month),
      source_name: text,
      source_url: url,
      recorded_on: date,
    })
    .strict(),
  // Monetary cells are integer paise throughout; display conversion belongs
  // exclusively in lib/money.ts. Never infer a kVA charge from a kW charge.
  ev_tariffs: z
    .object({
      state: text,
      discom: text,
      tariff_order_ref: text,
      effective_from: date,
      category: text,
      energy_charge_paise_per_kwh: integer,
      demand_or_fixed_charge_paise: nullable(integer),
      unit: z.enum(["per_kva_month", "per_kw_month", "per_connection_month", "none", "unknown"]),
      tod_rules: z.string(),
      notes: z.string(),
    })
    .strict(),

  discom_performance: z
    .object({
      state: text,
      discom_id: text,
      discom: text,
      fiscal_year: text
        .regex(/^\d{4}-\d{2}$/)
        .refine(
          (v) => Number(v.slice(5)) === (Number(v.slice(0, 4)) + 1) % 100,
          "invalid fiscal year",
        ),
      atc_loss_pct: number.refine((v) => v >= 0 && v <= 100, "AT&C must be 0-100 percent"),
      acs_arr_gap_paise_per_kwh: nullable(
        z
          .string()
          .regex(/^-?\d+$/)
          .transform(Number)
          .refine(Number.isSafeInteger),
      ),
      metric_basis: text,
      source_edition: text,
      source_table_ref: text,
      notes: z.string(),
    })
    .strict(),
  supply_hours: z
    .object({
      state: text,
      discom_id: nullable(text),
      discom: nullable(text),
      lgd_code: nullable(code),
      period_type: z.enum(["month", "fiscal_year", "calendar_year", "other"]),
      period_start: date,
      period_end: date,
      published_period_label: text,
      area_type: z.enum(["rural", "urban", "all"]),
      avg_supply_hours_per_day: number.refine((v) => v >= 0 && v <= 24, "hours must be 0-24/day"),
      supply_definition: text,
      source_name: text,
      source_url: url,
      retrieved_on: date,
      notes: z.string(),
    })
    .strict(),
  state_ev_policies: z
    .object({
      state: text,
      policy_name: text,
      notification_ref: text,
      clause_ref: text,
      notified_on: date,
      valid_from: date,
      valid_to: nullable(date),
      incentive_type: z.enum([
        "purchase_subsidy",
        "road_tax_waiver",
        "registration_fee_waiver",
        "charging_capex_subsidy",
        "concessional_ev_tariff",
        "land_or_permit",
        "other",
      ]),
      vehicle_scope: z.enum(["2W", "3W", "4W", "bus", "goods", "charging", "all"]),
      amount_text: nullable(text),
      eligibility: text,
      supersedes_ref: nullable(text),
      source_url: url,
      recorded_on: date,
      notes: z.string(),
    })
    .strict(),
  nhai_wayside_amenities: z
    .object({
      wsa_id: text,
      nh_ref: text.regex(/^NH[ -]?\d+[A-Z]?$/),
      state: text,
      lgd_code: nullable(code),
      chainage_km: nullable(number.refine((v) => v >= 0)),
      lat: nullable(number.refine((v) => v >= -90 && v <= 90)),
      lon: nullable(number.refine((v) => v >= -180 && v <= 180)),
      status: text,
      status_as_of: nullable(date),
      ev_charging_listed: z.enum(["true", "false", "unknown"]),
      source_doc_date: nullable(date),
      source_page: text,
      notes: z.string(),
    })
    .strict(),
  osm_power: z
    .object({
      osm_id: text.regex(/^(node|way|relation)\/\d+$/),
      kind: z.enum(["substation", "transformer"]),
      voltage: nullable(text),
      lat: number.refine((v) => v >= -90 && v <= 90),
      lon: number.refine((v) => v >= -180 && v <= 180),
      lgd_code: nullable(code),
      extract_date: date,
      point_derivation: z.enum(["node", "representative_point"]),
    })
    .strict(),
  cea_ev_consumption: z
    .object({
      state: text,
      cea_state_name: text,
      report_month: month,
      span: z.enum(["month", "fy_to_date"]),
      span_start: date,
      pcs_kwh: nullable(integer),
      heavy_duty_pcs_kwh: nullable(integer),
      other_kwh: nullable(integer),
      total_kwh: nullable(integer),
      source_url: url,
      source_sha256: text.regex(/^[a-f0-9]{64}$/),
      notes: z.string(),
    })
    .strict(),
} as const;

export type CsvDatasetId = keyof typeof rowSchemas;
export type DatasetId = CsvDatasetId | "district_boundaries" | "highways";
export type District = z.infer<typeof rowSchemas.district_reference>;
export type Registration = z.infer<typeof rowSchemas.ev_registrations>;
export type PublicCharger = z.infer<typeof rowSchemas.public_chargers>;
export type PublicTariff = z.infer<typeof rowSchemas.ev_tariffs>;

export const datasetIds: readonly DatasetId[] = [
  ...(Object.keys(rowSchemas) as CsvDatasetId[]),
  "district_boundaries",
  "highways",
];
export const datasetFiles: Record<DatasetId, string> = {
  district_reference: "data.csv",
  rto_to_district: "data.csv",
  ev_registrations: "data.csv",
  public_chargers: "data.csv",
  ev_tariffs: "data.csv",
  discom_performance: "data.csv",
  supply_hours: "data.csv",
  state_ev_policies: "data.csv",
  nhai_wayside_amenities: "data.csv",
  osm_power: "data.csv",
  cea_ev_consumption: "data.csv",
  district_boundaries: "data.topojson",
  highways: "data.geojson",
};

/** Reader-facing names for datasets that have no published metadata title yet. */
export const datasetLabels: Record<DatasetId, string> = {
  district_reference: "District reference",
  rto_to_district: "RTO-to-district mapping",
  ev_registrations: "EV registrations",
  public_chargers: "Public chargers",
  ev_tariffs: "EV electricity tariffs",
  discom_performance: "Electricity distribution company performance",
  supply_hours: "Electricity supply hours",
  state_ev_policies: "State EV policies",
  nhai_wayside_amenities: "NHAI wayside amenities",
  osm_power: "OpenStreetMap power equipment",
  cea_ev_consumption: "EV charging electricity consumption (CEA)",
  district_boundaries: "District boundaries",
  highways: "National highways",
};

export const metadataSchema = z
  .object({
    id: z.enum([
      "district_reference",
      "rto_to_district",
      "ev_registrations",
      "public_chargers",
      "ev_tariffs",
      ...expansionDatasetIds,
      "district_boundaries",
      "highways",
    ]),
    title: text,
    description: text,
    source_name: text,
    source_url: url,
    retrieved_on: date,
    licence: text,
    geography_level: z.enum(["district", "state", "rto", "station", "corridor", "discom", "mixed"]),
    time_coverage: text,
    update_frequency: text,
    notes: z.string(),
    columns: z
      .array(
        z
          .object({
            name: text,
            type: z.enum(["string", "integer", "number", "date", "month", "boolean", "json"]),
            unit: text,
            description: text,
            nullable: z.boolean().optional(),
          })
          .strict(),
      )
      .min(1),
    fixture: z.boolean().optional(),
    source_sha256: z
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional(),
    licence_url: url.optional(),
    attribution: text.optional(),
    review_ref: text.optional(),
    transformation_version: text.optional(),
  })
  .strict();
export type DatasetMetadata = z.infer<typeof metadataSchema>;
export { publicDataVersions } from "./versions.ts";
export interface DatasetDescriptor {
  id: DatasetId;
  metadata: DatasetMetadata;
  rows: number;
  data_url: string;
  sha256: string;
}
export interface PublicCatalogue {
  versions: typeof publicDataVersions;
  districts: District[];
  datasets: DatasetDescriptor[];
  pending: DatasetId[];
}

export function columnNullable(id: DatasetId, name: string): boolean {
  if (!(id in rowSchemas)) return false;
  const shape = rowSchemas[id as CsvDatasetId].shape as Record<string, z.ZodTypeAny>;
  const result = shape[name]?.safeParse("");
  return Boolean(result?.success && result.data === null);
}
export function columnType(
  name: string,
): "integer" | "number" | "json" | "boolean" | "month" | "date" | "string" {
  if (
    [
      "lgd_code",
      "count",
      "energy_charge_paise_per_kwh",
      "demand_or_fixed_charge_paise",
      "acs_arr_gap_paise_per_kwh",
      "pcs_kwh",
      "heavy_duty_pcs_kwh",
      "other_kwh",
      "total_kwh",
    ].includes(name)
  )
    return "integer";
  if (
    ["lat", "lon", "power_kw", "atc_loss_pct", "avg_supply_hours_per_day", "chainage_km"].includes(
      name,
    )
  )
    return "number";
  if (["geometry", "former_names"].includes(name)) return "json";
  if (name === "covers_multiple_districts") return "boolean";
  if (["month", "opened_month", "report_month"].includes(name)) return "month";
  if (
    [
      "recorded_on",
      "effective_from",
      "notified_on",
      "valid_from",
      "valid_to",
      "period_start",
      "period_end",
      "retrieved_on",
      "status_as_of",
      "source_doc_date",
      "extract_date",
      "span_start",
    ].includes(name)
  )
    return "date";
  return "string";
}
