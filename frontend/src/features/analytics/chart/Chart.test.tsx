import { cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseCsv } from "../../../../scripts/csv";
import { publicDataVersions } from "../data/schemas";
import { Chart } from "./Chart";
import {
  chartCsv,
  chartFilters,
  selectRows,
  validateChart,
  valueDomain,
  type ChartData,
  type ChartType,
} from "./model";

const data: ChartData = {
  id: "test-chart",
  title: "Energy by period",
  subtitle: "Energy in kWh",
  summary: "Energy estimates with a suppressed observation.",
  type: "line",
  unit: "kWh",
  updated: "2026-09-30",
  sources: [
    {
      name: "Test source",
      url: "https://example.invalid/test",
      licence: "Test licence",
      attribution: "Test source attribution",
    },
  ],
  notes: ["Test notes"],
  versions: { ...publicDataVersions, renderer_version: "analytics_svg_v1" },
  rows: [
    {
      region: "North",
      period: "2026-01",
      indicator: "Energy",
      series: "AC",
      label: "January",
      value: 125000,
      p10: 100000,
      p90: 150000,
      status: "estimate",
      sample_size: 12,
    },
    {
      region: "North",
      period: "2026-02",
      indicator: "Energy",
      series: "AC",
      label: "February",
      value: null,
      status: "suppressed",
    },
    {
      region: "South",
      period: "2026-03",
      indicator: "Energy",
      series: "AC",
      label: "March",
      value: 200000,
      p10: 150000,
      p90: 250000,
      status: "estimate",
      sample_size: 15,
    },
  ],
};
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function Harness() {
  const location = useLocation(),
    navigate = useNavigate();
  return (
    <>
      <output data-testid="url">{location.search}</output>
      <button onClick={() => navigate(-1)}>Back</button>
      <Chart data={data} />
    </>
  );
}
function at(query = "") {
  return render(
    <MemoryRouter initialEntries={[`/data/test${query}`]}>
      <Harness />
    </MemoryRouter>,
  );
}
describe("shared analytics charts", () => {
  it.each<ChartType>(["line", "bar", "horizontal-bar", "range", "small-multiples"])(
    "renders %s as named SVG with labelled ranges and gaps",
    (type) => {
      render(
        <MemoryRouter>
          <Chart data={{ ...data, type }} />
        </MemoryRouter>,
      );
      expect(screen.getByRole("img").getAttribute("aria-label")).toContain("suppressed");
      expect(document.querySelectorAll(".analytics-whisker").length).toBe(2);
      expect(screen.getByText(/Gaps: Not enough data yet/)).toBeTruthy();
      expect(screen.getByText(/Estimates: markers show P50/)).toBeTruthy();
    },
  );
  it("does not bridge a missing value with a line or band", () => {
    at();
    expect(document.querySelectorAll(".analytics-range-band").length).toBe(0);
    expect(document.querySelectorAll(".analytics-series > g > path[fill='none']").length).toBe(0);
  });
  it("renders an SVG and full table in static HTML without browser APIs", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <Chart data={data} />
      </MemoryRouter>,
    );
    expect(html).toContain("<svg");
    expect(html).not.toContain("<noscript>");
    expect(html).toContain("<table");
    expect(html).toContain("1,25,000");
  });
  it("persists all filters and view, preserves other query keys and supports back and reload", () => {
    at("?other=keep");
    fireEvent.change(screen.getByLabelText("Region (state or district)"), {
      target: { value: "north" },
    });
    fireEvent.change(screen.getByLabelText("Time period"), { target: { value: "2026-01" } });
    fireEvent.change(screen.getByLabelText("Indicator"), { target: { value: "Energy" } });
    fireEvent.click(screen.getByRole("button", { name: /^Table$/ }));
    const query = screen.getByTestId("url").textContent!;
    expect(query).toContain("other=keep");
    expect(within(screen.getByRole("table")).getAllByRole("row").length).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.queryByRole("table")).toBeNull();
    cleanup();
    at(query);
    expect((screen.getByLabelText("Region (state or district)") as HTMLInputElement).value).toBe(
      "north",
    );
    expect((screen.getByLabelText("Time period") as HTMLSelectElement).value).toBe("2026-01");
    expect((screen.getByLabelText("Indicator") as HTMLSelectElement).value).toBe("Energy");
    expect(screen.getByRole("table")).toBeTruthy();
  });
  it("sorts numeric columns numerically, formats en-IN and leaves missing values last", () => {
    at("?test-chart.view=table");
    fireEvent.click(screen.getByRole("button", { name: "Value / P50" }));
    fireEvent.click(screen.getByRole("button", { name: "Value / P50 ↑" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows[1]!.textContent).toContain("2,00,000");
    expect(rows[3]!.textContent).toContain("Not enough data yet");
  });
  it("both CSVs retain exact numbers, missing cells, ranges, licences and versions", () => {
    const selected = selectRows(
      data.rows,
      chartFilters("?test-chart.region=north&test-chart.period=2026-01", data.id),
    );
    const selection = parseCsv(
      chartCsv(data, selected, "https://example.invalid/view", "2026-09-30"),
      "selection",
    );
    const all = parseCsv(
      chartCsv(data, data.rows, "https://example.invalid/view", "2026-09-30"),
      "all",
    );
    expect(selection).toHaveLength(2);
    expect(all).toHaveLength(4);
    expect(selection[1]!.values[5]).toBe("125000");
    expect(all[2]!.values[5]).toBe("");
    expect(selection[1]!.values[6]).toBe("100000");
    expect(selection[1]!.values).toContain("Test source: Test licence");
    expect(selection[0]!.values).toContain("renderer_version");
    expect(selection[1]!.values).toContain("analytics_svg_v1");
  });
  it("wires both download buttons to the same selection as the table", () => {
    const blobs: Blob[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      blobs.push(blob as Blob);
      return "blob:test";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    at("?test-chart.region=North&test-chart.view=table");
    fireEvent.click(screen.getByRole("button", { name: "Download CSV (current selection)" }));
    fireEvent.click(screen.getByRole("button", { name: "Download CSV (all data)" }));
    expect(blobs).toHaveLength(2);
    expect(blobs[0]!.size).toBeLessThan(blobs[1]!.size);
    expect(
      screen.getByText("3 rows downloaded with source licences and version stamps."),
    ).toBeTruthy();
  });
  it("offers a manual citation when clipboard access fails", async () => {
    at("?test-chart.period=2026-01");
    fireEvent.click(screen.getByRole("button", { name: "Copy citation" }));
    await waitFor(() => expect(screen.getByLabelText("Copy citation text")).toBeTruthy());
    const citation = (screen.getByLabelText("Copy citation text") as HTMLTextAreaElement).value;
    expect(citation).toContain("test-chart.period=2026-01#test-chart");
    expect(citation).toContain("Test licence");
    expect(citation).toContain("Test source attribution");
  });
  it("shows an empty selection and disables its CSV without disabling the all-data download", () => {
    at("?test-chart.region=absent");
    expect(screen.getByText("No data matches this selection.")).toBeTruthy();
    expect(
      (
        screen.getByRole("button", {
          name: "Download CSV (current selection)",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(
      (screen.getByRole("button", { name: "Download CSV (all data)" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });
  it("rejects estimates without bounds and suppressed records with leaked fields", () => {
    expect(() => validateChart({ ...data, rows: [{ ...data.rows[0]!, p10: undefined }] })).toThrow(
      "P10/P50/P90",
    );
    expect(() => validateChart({ ...data, rows: [{ ...data.rows[1]!, sample_size: 9 }] })).toThrow(
      "must not disclose",
    );
    expect(() => validateChart({ ...data, rows: [{ ...data.rows[0]!, value: Infinity }] })).toThrow(
      "finite",
    );
  });
  it("handles negative and all-zero domains without clipping or division by zero", () => {
    expect(valueDomain([{ ...data.rows[0]!, value: -5, p10: -10, p90: -2 }])).toEqual([-10, 0]);
    expect(valueDomain([{ ...data.rows[0]!, value: 0, p10: 0, p90: 0 }])).toEqual([0, 1]);
  });
  it("refuses ambiguous categories and series that cannot be distinguished by markers", () => {
    expect(() => validateChart({ ...data, rows: [data.rows[0]!, data.rows[0]!] })).toThrow(
      "unique",
    );
    expect(() =>
      validateChart({
        ...data,
        rows: ["a", "b", "c", "d"].map((series) => ({ ...data.rows[0]!, series })),
      }),
    ).toThrow("small multiples");
  });
  it("escapes quoted CSV text and neutralises formula text without altering negative numbers", () => {
    const rows = [{ ...data.rows[0]!, region: '=HYPERLINK("x")', value: -4, p10: -5, p90: -3 }];
    const parsed = parseCsv(chartCsv(data, rows, "https://example.invalid", "2026-09-30"), "csv");
    expect(parsed[1]!.values[0]).toBe('\'=HYPERLINK("x")');
    expect(parsed[1]!.values[5]).toBe("-4");
  });
});
