import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ContentArticle, ContentIndex } from "./Content";
import { analyticsMetadata, searchPublicContent, staticAnalyticsPaths } from "../catalog";
import { renderAnalytics } from "../prerender";
// Test synchronous content/SSR markup here. Browser chunk loading is exercised
// against the actual production build in check_analytics_launch.py.
vi.mock("../route-components", async () => ({
  ...(await import("./Content")),
  ...(await import("../expansion/Expansion")),
  ...(await import("../expansion/StateRegistrations")),
  ...(await import("../districts/DistrictDetails")),
}));
vi.mock("../chart/ProgressiveChart", async () => ({
  ProgressiveChart: (await import("../chart/Chart")).Chart,
}));
afterEach(cleanup);
it("renders a sourced insight, its update and changelog", () => {
  render(
    <MemoryRouter initialEntries={["/data/insights/what-does-the-district-reference-cover"]}>
      <Routes>
        <Route path="/data/insights/:slug" element={<ContentArticle format="insights" />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(screen.getByText(/Updated on/)).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Changelog" })).toBeTruthy();
  for (const button of screen.getAllByRole("button", { name: "Table" })) fireEvent.click(button);
  expect(screen.getAllByRole("table")).toHaveLength(2);
});
it("keeps vertical filters in the URL and shows empty topics honestly", () => {
  render(
    <MemoryRouter initialEntries={["/data/weekly?vertical=usage"]}>
      <ContentIndex format="weekly" />
    </MemoryRouter>,
  );
  expect(screen.getByText(/No posts have been published/)).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Method" }));
  expect(screen.getByRole("link", { name: /How many district/ })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Method" }).getAttribute("aria-current")).toBe("page");
});
it("prerenders dates, changelog and chart tables and registers SEO/search", () => {
  const path = "/data/insights/what-does-the-district-reference-cover";
  const html = renderAnalytics(path);
  expect(html).toContain("Updated on");
  expect(html).toContain("Changelog");
  expect(html).toContain("<table");
  expect(html).toContain("783");
  expect(staticAnalyticsPaths).toContain(path);
  expect(analyticsMetadata(path).noindex).toBe(false);
  expect(analyticsMetadata("/data/insights/unknown").noindex).toBe(true);
  expect(searchPublicContent("district reference", "Insight")).toHaveLength(1);
});
