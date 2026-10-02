import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsApp } from "./AnalyticsApp";
import { analyticsMetadata, verticals } from "./catalog";

// Shell behavior is independent of network chunk timing. The production
// Playwright launch audit exercises real lazy loading and SSR hydration.
vi.mock("./route-components", async () => ({
  ...(await import("./content/Content")),
  ...(await import("./expansion/Expansion")),
  ...(await import("./expansion/StateRegistrations")),
  ...(await import("./districts/DistrictDetails")),
}));
vi.mock("./chart/ProgressiveChart", async () => ({
  ProgressiveChart: (await import("./chart/Chart")).Chart,
}));

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/data/*" element={<AnalyticsApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("public analytics shell", () => {
  it("lets visitors find and open a topic without an API or fabricated data", () => {
    at("/data");
    fireEvent.change(screen.getByLabelText("Search Chargeworthy Data"), {
      target: { value: "electri" },
    });
    expect(
      document.querySelector("#data-search-results")?.previousElementSibling?.textContent,
    ).toBe("1 result found");
    const matches = document.querySelector("#data-search-results")!;
    fireEvent.click(within(matches as HTMLElement).getByRole("link", { name: "Electricity" }));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Electricity");
    expect(screen.getByText(/Rates will appear with their effective dates/)).toBeTruthy();
    fireEvent.click(
      within(screen.getByRole("navigation", { name: "Breadcrumb" })).getByRole("link", {
        name: "Data",
      }),
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Chargeworthy Data");
  });

  it.each(verticals)("renders $title with an honest preparation state", ({ slug, title }) => {
    at(`/data/${slug}`);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(title);
    if (slug === "corridors")
      expect(screen.getByText(/No corridor coverage or gap length is claimed/)).toBeTruthy();
    else expect(screen.getByText("Being prepared")).toBeTruthy();
    if (["vehicles", "charging-network", "usage"].includes(slug)) {
      expect(screen.queryByRole("table")).toBeNull();
      expect(
        screen.getByText(/The interactive map loads when this section is in view/),
      ).toBeTruthy();
    } else expect(screen.queryByRole("table")).toBeNull();
  });

  it("handles unknown districts and invalid topics without inventing an indicator", () => {
    at("/data/district/unknown-district");
    expect(screen.getByText(/No district indicators have been published/)).toBeTruthy();
    expect(document.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe(
      "noindex, follow",
    );
    cleanup();
    at("/data/not-a-vertical");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Data page unavailable");
    expect(analyticsMetadata("/data/not-a-vertical").noindex).toBe(true);
  });

  it("searches sourced districts and returns an honest empty topic search result", () => {
    at("/data");
    expect((screen.getByLabelText("District name") as HTMLInputElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText("District name"), { target: { value: "Ernakulam" } });
    expect(
      within(document.querySelector("#district-search-results") as HTMLElement).getByRole("link", {
        name: "Ernakulam",
      }),
    ).toBeTruthy();
    fireEvent.change(screen.getByLabelText("District name"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Search Chargeworthy Data"), {
      target: { value: "unknown" },
    });
    expect(
      document.querySelector("#data-search-results")?.previousElementSibling?.textContent,
    ).toContain("No matching titles");
    expect(document.querySelector("#data-search-results")?.children.length).toBe(0);
  });
});
