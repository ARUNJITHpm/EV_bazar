import { describe, expect, it } from "vitest";
import type { PublicCatalogue } from "../data/schemas";
import { publicDataVersions } from "../data/versions";
import {
  consumptionCharts,
  monthLabel,
  monthRange,
  type Consumption,
  type Expansion,
} from "./model";

const sha = "a".repeat(64);
const row = (over: Partial<Consumption>): Consumption => ({
  state: "KERALA",
  cea_state_name: "Kerala",
  report_month: "2024-04",
  span: "month",
  span_start: "2024-04-01",
  pcs_kwh: null,
  heavy_duty_pcs_kwh: null,
  other_kwh: null,
  total_kwh: 1_000_000,
  source_url: "https://cea.nic.in/report.pdf",
  source_sha256: sha,
  notes: "",
  ...over,
});
const catalogue = {
  versions: publicDataVersions,
  districts: [],
  pending: [],
  datasets: [
    {
      id: "cea_ev_consumption",
      rows: 0,
      data_url: "/analytics-data/cea_ev_consumption/data.csv",
      sha256: sha,
      metadata: {
        source_name: "Central Electricity Authority",
        source_url: "https://cea.nic.in/electric-vehicle-charging-reports/",
        licence: "Reproduced with attribution",
        retrieved_on: "2026-10-03",
      },
    },
  ],
} as unknown as PublicCatalogue;
const expansion = (consumption: Consumption[]): Expansion => ({
  asOf: "2026-10-03",
  performance: [],
  supply: [],
  policies: [],
  amenities: [],
  consumption,
});

describe("CEA EV charging electricity charts", () => {
  it("formats and spans months", () => {
    expect(monthLabel("2025-12")).toBe("Dec 2025");
    expect(monthRange("2025-11", "2026-02")).toEqual(["2025-11", "2025-12", "2026-01", "2026-02"]);
  });

  it("shows unpublished months as gaps, never zero", () => {
    const [india] = consumptionCharts(
      expansion([
        row({ state: "India", cea_state_name: "India", total_kwh: 52_860_000 }),
        row({
          state: "India",
          cea_state_name: "India",
          report_month: "2024-07",
          span_start: "2024-07-01",
          total_kwh: 64_140_000,
        }),
      ]),
      catalogue,
    );
    expect(india!.rows.map((r) => [r.label, r.value, r.status])).toEqual([
      ["Apr 2024", 52.86, "observed"],
      ["May 2024", null, "missing"],
      ["Jun 2024", null, "missing"],
      ["Jul 2024", 64.14, "observed"],
    ]);
    expect(india!.sources[0]!.licence).toBe("Reproduced with attribution");
  });

  it("ranks states for the latest year to date and leaves out unreported ones", () => {
    const fy = { span: "fy_to_date" as const, report_month: "2026-03", span_start: "2025-04-01" };
    const charts = consumptionCharts(
      expansion([
        row({ ...fy, total_kwh: 25_860_000 }),
        row({ ...fy, state: "DELHI", cea_state_name: "Delhi", total_kwh: 435_310_000 }),
        row({ ...fy, state: "GOA", cea_state_name: "Goa", total_kwh: null }),
      ]),
      catalogue,
    );
    const states = charts.find((c) => c.id === "ev-charging-electricity-states")!;
    expect(states.title).toBe("EV charging electricity by state, Apr 2025 to Mar 2026");
    expect(states.rows.map((r) => [r.label, r.value])).toEqual([
      ["Delhi", 435.31],
      ["Kerala", 25.86],
    ]);
  });

  it("renders nothing without data", () => {
    expect(consumptionCharts(expansion([]), catalogue)).toEqual([]);
  });
});
