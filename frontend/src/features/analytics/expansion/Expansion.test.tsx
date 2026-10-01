import { cleanup, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { publicDataVersions, type DatasetDescriptor, type PublicCatalogue } from "../data/schemas";
import { Chart } from "../chart/Chart";
import { chartCsv, validateChart } from "../chart/model";
import { Plot } from "../chart/Plot";
import { CorridorsContext, DistrictGrid, ElectricityContext, Policies } from "./Expansion";
import {
  latestPerformance,
  latestSupply,
  outageNote,
  performanceCharts,
  plannedAmenities,
  policyMarkers,
  policyStatus,
  type Amenity,
  type Expansion,
  type Performance,
  type Policy,
  type Supply,
} from "./model";

const data = vi.hoisted(
  () =>
    ({ asOf: "2026-10-02", performance: [], supply: [], policies: [], amenities: [] }) as Expansion,
);
vi.mock("virtual:analytics-expansion", () => ({ default: data }));
afterEach(() => {
  cleanup();
  data.performance = [];
  data.supply = [];
  data.policies = [];
  data.amenities = [];
});
const policy: Policy = {
  state: "Kerala",
  policy_name: "Test reviewed policy",
  notification_ref: "TEST-1",
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
  notes: "Test fixture",
};
const supply: Supply = {
  state: "Kerala",
  discom_id: null,
  discom: null,
  lgd_code: null,
  period_type: "month",
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  published_period_label: "August 2026",
  area_type: "rural",
  avg_supply_hours_per_day: 0,
  supply_definition: "Test definition",
  source_name: "Test source",
  source_url: "https://example.invalid/supply",
  retrieved_on: "2026-09-30",
  notes: "Test fixture",
};
const perf: Performance = {
  state: "Kerala",
  discom_id: "test-utility",
  discom: "Test electricity utility",
  fiscal_year: "2024-25",
  atc_loss_pct: 12,
  acs_arr_gap_paise_per_kwh: null,
  metric_basis: "test-comparable",
  source_edition: "Test 2025 edition",
  source_table_ref: "Table 1",
  notes: "Test fixture",
};
const amenity: Amenity = {
  wsa_id: "test-amenity",
  nh_ref: "NH66",
  state: "Kerala",
  lgd_code: null,
  chainage_km: 100,
  lat: null,
  lon: null,
  status: "planned",
  status_as_of: "2026-09-01",
  ev_charging_listed: "true",
  source_doc_date: "2026-09-01",
  source_page: "1",
  notes: "Test fixture",
};
const source = {
  id: "discom_performance",
  metadata: {
    source_name: "Test PFC edition",
    source_url: "https://example.invalid/pfc",
    licence: "Test licence",
    retrieved_on: "2026-09-30",
  },
} as DatasetDescriptor;
const catalogue: PublicCatalogue = {
  datasets: [source],
  pending: [],
  districts: [],
  versions: publicDataVersions,
};

it("renders every missing context without invented zeroes or serving utilities", () => {
  render(
    <MemoryRouter>
      <ElectricityContext />
      <DistrictGrid
        district={{
          lgd_code: 594,
          district_name: "Ernakulam",
          state_name: "Kerala",
          slug: "ernakulam",
          former_names: [],
        }}
      />
      <CorridorsContext />
    </MemoryRouter>,
  );
  expect(screen.getByText(/verified district-to-utility mapping/)).toBeTruthy();
  expect(screen.getByText(/not the total EV fleet/)).toBeTruthy();
  expect(screen.getAllByText(/Not available yet/).length).toBeGreaterThan(5);
  expect(screen.queryByText("0")).toBeNull();
});
it("uses the inclusive policy end date, unknown validity and supersession explicitly", () => {
  expect(policyStatus(policy, data.asOf)).toBe("In force through 2026-10-02");
  expect(policyStatus(policy, "2026-10-03")).toBe("Expired 2026-10-02");
  expect(policyStatus({ ...policy, valid_to: null }, data.asOf)).toBe("End date not published");
  expect(
    policyStatus(policy, data.asOf, [
      { ...policy, notification_ref: "TEST-2", supersedes_ref: "TEST-1", valid_from: "2026-01-01" },
    ]),
  ).toBe("Superseded from 2026-01-01");
});
it("retains expired policies with notification links and excludes future notifications", () => {
  data.policies = [
    { ...policy, valid_to: "2025-01-01" },
    { ...policy, notification_ref: "FUTURE", notified_on: "2027-01-01" },
  ];
  render(<Policies />);
  expect(screen.getByText("Expired 2025-01-01")).toBeTruthy();
  expect(screen.getByRole("link", { name: "TEST-1" }).getAttribute("href")).toBe(policy.source_url);
  expect(screen.queryByText("FUTURE")).toBeNull();
});
it("preserves explicit zero supply, rural/urban scope, future and ambiguous periods", () => {
  const urban = { ...supply, area_type: "urban" as const, avg_supply_hours_per_day: 23 };
  expect(latestSupply([supply, urban], data.asOf)).toEqual([supply, urban]);
  expect(latestSupply([supply, { ...supply }], data.asOf)).toEqual([]);
  expect(latestSupply([{ ...supply, period_end: "2027-01-01" }], data.asOf)).toEqual([]);
  expect(latestSupply([supply], data.asOf, "Unknown")).toEqual([]);
});
it("does not assign statewide supply or utility observations to a district", () => {
  data.supply = [supply];
  data.performance = [perf];
  render(
    <DistrictGrid
      district={{
        lgd_code: 594,
        district_name: "Ernakulam",
        state_name: "Kerala",
        slug: "ernakulam",
        former_names: [],
      }}
    />,
  );
  expect(screen.getByText(/statewide context, not district supply/)).toBeTruthy();
  expect(screen.getByText("0")).toBeTruthy();
  expect(screen.queryByText(perf.discom)).toBeNull();
});
it("uses an explicit national reference from the same edition, year and basis", () => {
  const national = {
    ...perf,
    state: "India",
    discom_id: "national",
    discom: "India",
    atc_loss_pct: 17,
  };
  const charts = performanceCharts({ ...data, performance: [perf, national] }, catalogue);
  expect(charts[0]!.reference?.value).toBe(17);
  expect(charts.every((c) => c.notes.includes(outageNote))).toBe(true);
  charts.forEach(validateChart);
  expect(
    chartCsv(charts[0]!, charts[0]!.rows, "https://example.invalid/page", data.asOf),
  ).toContain(outageNote);
  expect(
    performanceCharts(
      { ...data, performance: [perf, { ...national, metric_basis: "other" }] },
      catalogue,
    )[0]!.reference,
  ).toBeUndefined();
  expect(
    latestPerformance([perf, { ...national, source_edition: "Other edition" }], data.asOf),
  ).toEqual([]);
});
it("refuses future years and conflicting utility observations", () => {
  expect(latestPerformance([{ ...perf, fiscal_year: "2026-27" }], data.asOf)).toEqual([]);
  expect(latestPerformance([perf, { ...perf, metric_basis: "other" }], data.asOf)).toEqual([]);
});
it("plots policy markers only inside selected months and keeps accessible date evidence", () => {
  const chart = performanceCharts({ ...data, performance: [perf] }, catalogue)[0]!;
  const markers = policyMarkers([policy, { ...policy, clause_ref: "2" }], "Kerala", data.asOf);
  expect(markers).toHaveLength(2);
  const rows = [{ ...chart.rows[0]!, label: "2024-01", period: "2024-01" }];
  const html = renderToStaticMarkup(
    <Plot rows={rows} type="line" summary="Test registrations" annotations={markers} />,
  );
  expect(html).toContain("2024-01-01: Test reviewed policy: start");
  expect(html).not.toContain("2026-10-02: Test reviewed policy: last valid day");
  render(
    <MemoryRouter>
      <Chart data={{ ...chart, type: "line", rows, annotations: markers }} />
    </MemoryRouter>,
  );
  expect(screen.getByText("Policy dates shown on this chart")).toBeTruthy();
  expect(
    chartCsv({ ...chart, annotations: markers }, rows, "https://example.invalid/page", data.asOf),
  ).toContain("policy_markers");
});
it("refuses invalid marker dates and reference values", () => {
  const chart = performanceCharts({ ...data, performance: [perf] }, catalogue)[0]!;
  expect(() =>
    validateChart({
      ...chart,
      annotations: [{ date: "2026-02-30", label: "Invalid", source_url: policy.source_url }],
    }),
  ).toThrow(/marker/);
  expect(() =>
    validateChart({ ...chart, reference: { value: Infinity, label: "Invalid" } }),
  ).toThrow(/Reference/);
});
it("planned amenities never establish or shorten a gap", () => {
  data.amenities = [amenity];
  render(<CorridorsContext />);
  expect(screen.getByRole("img", { name: "Planned, not a verified charger" })).toBeTruthy();
  expect(screen.getByText(/No corridor coverage or gap length is claimed/)).toBeTruthy();
  expect(
    plannedAmenities(
      [amenity, { ...amenity, status: "open", status_as_of: "2026-10-01" }],
      data.asOf,
    ),
  ).toEqual([]);
  expect(plannedAmenities([{ ...amenity, ev_charging_listed: "unknown" }], data.asOf)).toEqual([]);
  expect(plannedAmenities([{ ...amenity, status_as_of: null }], data.asOf)).toEqual([]);
});
