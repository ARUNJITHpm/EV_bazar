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
  district_boundaries: "data.topojson",
  highways: "data.geojson",
};

export const metadataSchema = z
  .object({
    id: z.enum([
      "district_reference",
      "rto_to_district",
      "ev_registrations",
      "public_chargers",
      "ev_tariffs",
      "district_boundaries",
      "highways",
    ]),
    title: text,
    description: text,
    source_name: text,
    source_url: url,
    retrieved_on: date,
    licence: text,
    geography_level: z.enum(["district", "state", "rto", "station", "corridor"]),
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
  })
  .strict();
export type DatasetMetadata = z.infer<typeof metadataSchema>;
export const publicDataVersions = {
  model_version: "not_applicable:observed_public_data",
  economics_version: "not_applicable:no_economics_computation",
  schema_version: "public_analytics_v1",
  archetype_version: "not_applicable:public_data",
  tariff_effective_date: "per_row:effective_from_for_tariffs;not_applicable_otherwise",
  renderer_version: "public_data_export_v1",
} as const;
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
