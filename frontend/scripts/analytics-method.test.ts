// @vitest-environment node
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { loadAnalyticsMethod } from "./analytics-method";
import { validationSummarySchema } from "../src/features/analytics/method/reviewed";
import { publicDataVersions } from "../src/features/analytics/data/schemas";
import type { Article } from "../src/features/analytics/content/model";
const temporary: string[] = [];
async function file(name: string, data: unknown) {
  const root = await mkdtemp(resolve(tmpdir(), "chargeworthy-method-"));
  temporary.push(root);
  await writeFile(resolve(root, name), JSON.stringify(data));
  return root;
}
afterEach(async () => {
  for (const root of temporary.splice(0)) await rm(root, { recursive: true, force: true });
});
// Synthetic summary is confined to this test; it never populates reviewed production content.
const summary = {
  approved: true,
  is_demo: false,
  completed_on: "2026-10-01",
  unit: "kwh_per_connector_day",
  median_absolute_percentage_error: 0.4,
  interval_coverage: 0.8,
  stations: 30,
  selected_features: ["log_age"],
  simulation_count: 1000,
  publication_validation_passed: true,
  versions: publicDataVersions,
};
describe("reviewed public method inputs", () => {
  it("refuses explicit null summaries instead of silently treating them as missing", async () => {
    const root = await file("validation-summary.json", null);
    await expect(loadAnalyticsMethod(root, [])).rejects.toThrow();
  });
  it("keeps missing real validation pending, without manufacturing metrics", async () => {
    const root = await file("corrections.json", []);
    expect(await loadAnalyticsMethod(root, [])).toEqual({ validation: null, corrections: [] });
  });
  it("loads only the approved aggregate summary and all output versions", async () => {
    const root = await file("validation-summary.json", summary);
    const loaded = await loadAnalyticsMethod(root, []);
    expect(loaded.validation?.stations).toBe(30);
    expect(loaded.validation?.versions).toEqual(publicDataVersions);
  });
  it.each([
    { is_demo: true },
    { approved: false },
    { station_id: "private" },
    { loo: [{ station_id: "private" }] },
    { stations: 9 },
    { completed_on: "2026-02-30" },
    { interval_coverage: 1.01 },
    { median_absolute_percentage_error: -1 },
    { versions: { model_version: "x" } },
  ])("refuses demo, private, incomplete or invalid summaries %j", (patch) => {
    expect(() => validationSummarySchema.parse({ ...summary, ...patch })).toThrow();
  });
  it("rejects corrections referring to unpublished charts", async () => {
    const root = await file("corrections.json", [
      {
        id: "fix",
        date: "2026-10-01",
        changed: "Corrected a label",
        reason: "Transcription review",
        charts: ["unknown"],
      },
    ]);
    await expect(loadAnalyticsMethod(root, [])).rejects.toThrow("unknown chart");
  });
  it("loads dated corrections and checks their chart references", async () => {
    const root = await file("corrections.json", [
      {
        id: "fix",
        date: "2026-10-01",
        changed: "Corrected a label",
        reason: "Transcription review",
        charts: ["known"],
      },
    ]);
    const articles = [{ blocks: [{ kind: "chart", data: { id: "known" } }] }] as Article[];
    expect((await loadAnalyticsMethod(root, articles)).corrections[0]?.id).toBe("fix");
  });
});
