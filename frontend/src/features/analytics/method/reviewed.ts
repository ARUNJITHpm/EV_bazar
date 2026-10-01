import { z } from "zod";
const date = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine((value) => {
    const parsed = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  }, "Invalid calendar date");
const versions = z
  .object({
    model_version: z.string().min(1),
    economics_version: z.string().min(1),
    schema_version: z.string().min(1),
    archetype_version: z.string().min(1),
    tariff_effective_date: z.string().min(1),
    renderer_version: z.string().min(1),
  })
  .strict();
export const validationSummarySchema = z
  .object({
    approved: z.literal(true),
    is_demo: z.literal(false),
    completed_on: date,
    unit: z.literal("kwh_per_connector_day"),
    median_absolute_percentage_error: z.number().finite().nonnegative(),
    interval_coverage: z.number().finite().min(0).max(1),
    stations: z.number().int().min(10),
    selected_features: z.array(
      z.enum([
        "dc_share",
        "power_class",
        "log_age",
        "highway",
        "urban",
        "rural",
        "log_distance",
        "log_ev",
      ]),
    ),
    simulation_count: z.number().int().min(1000),
    publication_validation_passed: z.boolean(),
    versions,
  })
  .strict();
export const correctionsSchema = z.array(
  z
    .object({
      id: z.string().regex(/^[a-z][a-z0-9-]*$/),
      date,
      changed: z.string().min(1),
      reason: z.string().min(1),
      charts: z.array(z.string().regex(/^[a-z][a-z0-9-]*$/)).min(1),
    })
    .strict(),
);
export interface ReviewedMethod {
  validation: z.infer<typeof validationSummarySchema> | null;
  corrections: z.infer<typeof correctionsSchema>;
}
