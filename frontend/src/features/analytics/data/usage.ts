import { z } from "zod";
const scalar = z
  .string()
  .regex(/^\d+(?:\.\d+)?(?:e[+-]?\d+)?$/i)
  .transform(Number)
  .refine(Number.isFinite);
const nullable = <T extends z.ZodTypeAny>(schema: T) =>
  z.union([z.literal("").transform(() => null), schema]);
const count = scalar.refine((value) => Number.isSafeInteger(value));
export const usageBaseSchema = z
  .object({
    lgd_code: count.refine((value) => value > 0),
    month: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/),
    stations_known: nullable(count),
    stations_with_data: nullable(count),
    kwh_per_charger_p10: nullable(scalar),
    kwh_per_charger_p50: nullable(scalar),
    kwh_per_charger_p90: nullable(scalar),
    district_total_p10: nullable(scalar),
    district_total_p50: nullable(scalar),
    district_total_p90: nullable(scalar),
    note: z
      .string()
      .refine(
        (note) =>
          note === "Not enough data yet" ||
          /^(?:Volunteer connector\/road mix differs from the listed inventory; )?(?:Volunteer opening ages differ or age coverage is incomplete; )?Opening age imputed for \d+% of listed stations\. Inventory coverage is incomplete; these estimates are not the entire district's charging energy\.$/.test(
            note,
          ),
      ),
  })
  .strict();
export const usageRowSchema = usageBaseSchema.superRefine((row, context) => {
  const values = [
    row.stations_known,
    row.stations_with_data,
    row.kwh_per_charger_p10,
    row.kwh_per_charger_p50,
    row.kwh_per_charger_p90,
    row.district_total_p10,
    row.district_total_p50,
    row.district_total_p90,
  ];
  if (row.note === "Not enough data yet") {
    if (values.some((value) => value !== null))
      context.addIssue({
        code: "custom",
        message: "Suppressed groups cannot disclose counts or values",
      });
    return;
  }
  if (
    values.some((value) => value == null) ||
    row.stations_with_data! < 10 ||
    row.stations_known! < row.stations_with_data! ||
    row.kwh_per_charger_p10! > row.kwh_per_charger_p50! ||
    row.kwh_per_charger_p50! > row.kwh_per_charger_p90!
  ) {
    context.addIssue({ code: "custom", message: "Invalid published group or range" });
    return;
  }
  for (const [average, total] of [
    [row.kwh_per_charger_p10, row.district_total_p10],
    [row.kwh_per_charger_p50, row.district_total_p50],
    [row.kwh_per_charger_p90, row.district_total_p90],
  ])
    if (Math.abs(average! * row.stations_known! - total!) > Math.max(1e-6, total! * 1e-8))
      context.addIssue({ code: "custom", message: "Totals and per-station averages differ" });
});
export type UsageRow = z.infer<typeof usageRowSchema>;
export const usageMetaSchema = z
  .object({
    versions: z
      .object({
        model_version: z.literal("owner_mixed_v1"),
        economics_version: z.literal("not_applicable"),
        schema_version: z.literal("usage_aggregate_v1"),
        archetype_version: z.string().min(1),
        tariff_effective_date: z.string().min(1),
        renderer_version: z.literal("usage_csv_v1"),
      })
      .strict(),
    run_id: z.string().uuid(),
    source: z.literal(
      "Consented full-calendar-month owner observations and approved source inventory",
    ),
    source_url: z
      .string()
      .url()
      .refine((url) => /^https:\/\//.test(url)),
    retrieved_on: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/)
      .refine((value) => {
        const date = new Date(`${value}T00:00:00Z`);
        return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
      }),
    licence: z.literal("CC BY 4.0"),
    unit: z.literal(
      "kWh per listed physical station per month; legacy kwh_per_charger field names",
    ),
    note: z.literal(
      "Not all chargers in the district; no private report or station record accompanies this artifact.",
    ),
    source_hashes: z
      .object({
        public_chargers: z.string().regex(/^[a-f0-9]{64}$/),
        ev_registrations: z.string().regex(/^[a-f0-9]{64}$/),
      })
      .strict(),
    is_demo: z.literal(false),
    privacy_gates: z.literal("usage_privacy_v1"),
    validation_passed: z.literal(true),
  })
  .strict();
export type UsageMeta = z.infer<typeof usageMetaSchema>;
