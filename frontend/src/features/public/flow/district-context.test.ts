import { expect, it } from "vitest";
import type { DatasetDescriptor, PublicCatalogue } from "../../analytics/data/schemas";
import { publicDataVersions } from "../../analytics/data/schemas";
import { monthOffset, type Atlas } from "../../analytics/districts/model";
import type { Expansion, Policy } from "../../analytics/expansion/model";
import { expansionLinks } from "../../analytics/expansion/home-links";
import { districtContext } from "./district-context";
import { factCoverage } from "../../report/FactCoverage";
import { COVERAGE, GROUPS, TOTAL_CHECKS } from "../../animation/data";

const catalogue: PublicCatalogue = {
  versions: publicDataVersions,
  pending: [],
  datasets: [],
  districts: [
    {
      lgd_code: 555,
      district_name: "Ernakulam",
      state_name: "Kerala",
      slug: "ernakulam-555",
      former_names: [],
    },
  ],
};
const atlas: Atlas = { registrations: [], chargers: [], tariffs: [], shapes: [] };
const expansion: Expansion = {
  asOf: "2026-10-02",
  policies: [],
  supply: [],
  performance: [],
  amenities: [],
};
const descriptor = (id: DatasetDescriptor["id"]): DatasetDescriptor => ({
  id,
  rows: 1,
  data_url: "test.csv",
  sha256: "a".repeat(64),
  metadata: {
    source_name: "Test reviewed source",
    source_url: "https://example.invalid/source",
    retrieved_on: "2026-09-30",
  } as DatasetDescriptor["metadata"],
});
const reviewed = {
  ...catalogue,
  datasets: [descriptor("ev_registrations"), descriptor("state_ev_policies")],
};
function registrations(count = 1): Atlas {
  return {
    ...atlas,
    registrations: Array.from({ length: 24 }, (_, i) =>
      ["2W", "3W", "4W", "bus", "goods"].map((vehicle_class) => ({
        month: monthOffset("2026-09", -i),
        state: "Kerala",
        rto_code: "KL01",
        lgd_code: 555,
        fuel: "PURE EV" as const,
        vehicle_class: vehicle_class as Atlas["registrations"][number]["vehicle_class"],
        count: i < 12 ? count * 2 : count,
      })),
    ).flat(),
  };
}
const policy: Policy = {
  state: "Kerala",
  policy_name: "Test policy",
  notification_ref: "TEST",
  clause_ref: "1",
  notified_on: "2024-01-01",
  valid_from: "2024-01-01",
  valid_to: "2026-10-02",
  incentive_type: "other",
  vehicle_scope: "all",
  amount_text: null,
  eligibility: "Test only",
  supersedes_ref: null,
  source_url: "https://example.invalid/policy",
  recorded_on: "2026-09-30",
  notes: "fixture",
};

it("uses exact LGD identity, never names or a guessed slug", () => {
  expect(districtContext(undefined, catalogue, atlas, expansion)).toBeNull();
  expect(districtContext(999, catalogue, atlas, expansion)).toBeNull();
  expect(districtContext(555, catalogue, atlas, expansion)?.district.slug).toBe("ernakulam-555");
});
it("exposes four honest gaps and six version stamps", () => {
  const context = districtContext(555, catalogue, atlas, expansion)!;
  expect(context.facts).toHaveLength(4);
  expect(context.facts.map((f) => f.value)).toEqual([
    "Not available yet",
    "Not available yet",
    "Not confirmed",
    "Not confirmed",
  ]);
  expect(Object.keys(context.versions)).toHaveLength(6);
});
it("requires a validated source and complete two-year cells for growth", () => {
  expect(districtContext(555, catalogue, registrations(), expansion)!.facts[0]!.value).toBe(
    "Not available yet",
  );
  const context = districtContext(555, reviewed, registrations(), expansion)!;
  expect(context.facts[0]!.value).toContain("120 new registrations");
  expect(context.facts[0]!.value).toContain("+100.0%");
  expect(context.facts[1]!.value).toBe("Not available yet");
  const partial = registrations();
  partial.registrations.pop();
  expect(districtContext(555, reviewed, partial, expansion)!.facts[0]!.value).toContain(
    "growth unavailable",
  );
});
it("does not turn missing months, zero prior counts or future data into growth", () => {
  const partial = registrations();
  partial.registrations.shift();
  expect(districtContext(555, reviewed, partial, expansion)!.facts[0]!.value).toBe(
    "Not available yet",
  );
  expect(districtContext(555, reviewed, registrations(0), expansion)!.facts[0]!.value).toContain(
    "growth unavailable",
  );
  const future = registrations();
  future.registrations = future.registrations.map((row) => ({
    ...row,
    month: monthOffset(row.month, 24),
  }));
  expect(districtContext(555, reviewed, future, expansion)!.facts[0]!.value).toBe(
    "Not available yet",
  );
});
it("requires a confirmed policy interval and handles inclusive expiry, supersession and future dates", () => {
  const summary = (rows: Policy[], asOf = expansion.asOf) =>
    districtContext(555, reviewed, atlas, { ...expansion, asOf, policies: rows })!.facts[3]!.value;
  expect(summary([policy])).toBe("Test policy");
  expect(summary([policy], "2026-10-03")).toBe("Not confirmed");
  expect(summary([{ ...policy, valid_to: null }])).toBe("Not confirmed");
  expect(summary([{ ...policy, notified_on: "2027-01-01" }])).toBe("Not confirmed");
  expect(
    summary([
      policy,
      { ...policy, notification_ref: "NEXT", supersedes_ref: "TEST", policy_name: "Replacement" },
    ]),
  ).toBe("Replacement");
});
it("does not promote pending, empty or future-only electricity datasets", () => {
  expect(expansionLinks(expansion, catalogue)).toEqual([]);
  expect(expansionLinks(expansion, reviewed)).toEqual([]);
  expect(expansionLinks({ ...expansion, policies: [policy] }, reviewed)[0]!.to).toBe(
    "/data/electricity",
  );
  expect(
    expansionLinks(
      { ...expansion, policies: [{ ...policy, notified_on: "2027-01-01" }] },
      reviewed,
    ),
  ).toEqual([]);
});
it("keeps the owner-approved 34 checks and records a source for every check", () => {
  expect(TOTAL_CHECKS).toBe(34);
  expect(GROUPS.map((g) => g.checks.length)).toEqual([12, 4, 8, 7, 3]);
  expect(GROUPS.flatMap((g) => g.checks).every((c) => c.source)).toBe(true);
  expect(COVERAGE.every((c) => c.count === "—")).toBe(true);
});
it("counts only stored facts, including zero and all-unverified reports", () => {
  expect(factCoverage([])).toEqual({ measured: 0, sourced: 0, unverified: 0, total: 0 });
  expect(
    factCoverage([
      { source: "OSM", unverified: false },
      { source: "survey pending", unverified: true },
    ]),
  ).toEqual({ measured: 0, sourced: 1, unverified: 1, total: 2 });
  expect(factCoverage([{ source: "OSM survey confirms", unverified: true }]).sourced).toBe(0);
});
