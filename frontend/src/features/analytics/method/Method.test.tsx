import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import catalogue from "virtual:analytics-public-data";
import articles from "virtual:analytics-content";
import reviewed from "virtual:analytics-method";
import { Methodology, Sources } from "./Method";
import { Chart } from "../chart/Chart";
import { analyticsMetadata } from "../catalog";
import { renderAnalytics } from "../prerender";
import { publicDataVersions } from "../data/schemas";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  reviewed.validation = null;
  reviewed.corrections = [];
});
it("prerenders exact privacy rules, volunteer bias, pending validation and corrections", () => {
  const html = renderAnalytics("/data/methodology");
  expect(html).toContain("distinct eligible stations");
  expect(html).toContain('class="analytics-number">10</span>');
  expect(html).toContain("one third");
  expect(html).toContain("Volunteer bias");
  expect(html).toContain("No approved real validation summary");
  expect(html).toContain('id="corrections"');
  expect(html).toContain("CC BY 4.0");
  expect(html).toContain("currently has no affiliation with any charge point operator");
  expect(html).toContain("do not own charging stations and do not plan to own them");
  expect(html).toContain("business model is based on site-assessment and operator-matching fees");
  expect(html).not.toContain("awaiting confirmation");
  expect(analyticsMetadata("/data/methodology").noindex).toBe(false);
});
it("generates each source with dates, licence, attribution, downloads and chart links", () => {
  render(
    <MemoryRouter>
      <Sources />
    </MemoryRouter>,
  );
  for (const dataset of catalogue.datasets) {
    const section = document.getElementById(`source-${dataset.id}`)!;
    const source = within(section);
    expect(source.getByRole("heading", { name: dataset.metadata.title })).toBeTruthy();
    expect(source.getByText(dataset.metadata.retrieved_on)).toBeTruthy();
    expect(source.getByText(dataset.metadata.licence)).toBeTruthy();
    expect(source.getByRole("link", { name: "Download source data" }).getAttribute("href")).toBe(
      dataset.data_url,
    );
    expect(
      source.getAllByRole("link").filter((a) => a.getAttribute("href")?.includes("#")),
    ).toHaveLength(dataset.id === "district_reference" ? 3 : 0);
    if (dataset.id === "osm_power") {
      expect(source.getByText("No published article charts use this source yet.")).toBeTruthy();
      expect(source.getByText(/Attribution:.*OpenStreetMap contributors/)).toBeTruthy();
      expect(source.getByText(/All LGD codes unresolved/)).toBeTruthy();
    }
  }
  expect(analyticsMetadata("/data/sources").noindex).toBe(false);
});
it("renders latest aggregate metrics with units and the saved configuration", () => {
  reviewed.validation = {
    approved: true,
    is_demo: false,
    completed_on: "2026-10-01",
    unit: "kwh_per_connector_day",
    median_absolute_percentage_error: 0.42,
    interval_coverage: 0.81,
    stations: 32,
    selected_features: ["log_age"],
    simulation_count: 1000,
    publication_validation_passed: false,
    versions: publicDataVersions,
  };
  render(
    <MemoryRouter>
      <Methodology />
    </MemoryRouter>,
  );
  expect(screen.getByText("42%")).toBeTruthy();
  expect(screen.getByText("81%")).toBeTruthy();
  expect(screen.getByText("32")).toBeTruthy();
  expect(screen.getByText(/did not pass/)).toBeTruthy();
  expect(screen.getByText(/Selected features: log_age/)).toBeTruthy();
});
it("links an affected chart to its dated correction and back", () => {
  const article = articles[0]!;
  const block = article.blocks.find((b) => b.kind === "chart")!;
  if (block.kind !== "chart") throw new Error("chart required");
  reviewed.corrections = [
    {
      id: "label-review",
      date: "2026-10-01",
      changed: "Reviewed label",
      reason: "Checked transcription",
      charts: [block.data.id],
    },
  ];
  render(
    <MemoryRouter>
      <Methodology />
      <Chart data={block.data} />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: /Correction: 2026/ }).getAttribute("href")).toBe(
    "/data/methodology#correction-label-review",
  );
  expect(screen.getByRole("link", { name: /Affected chart:/ }).getAttribute("href")).toContain(
    `#${block.data.id}`,
  );
});
