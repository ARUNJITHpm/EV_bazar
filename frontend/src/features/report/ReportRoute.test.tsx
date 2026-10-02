import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ReportRoute } from "./ReportRoute";
import { DEMO_REPORT_ID, fetchReport } from "./payload";
import { SAMPLES } from "./fixtures/samples";
const fixture = SAMPLES.build;

vi.mock("./payload", async (original) => ({
  ...(await original<typeof import("./payload")>()),
  fetchReport: vi.fn(),
}));
afterEach(() => vi.resetAllMocks());

function mount() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <ReportRoute reportId={DEMO_REPORT_ID} homepage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("loads the fixed stored demo at the homepage and renders all twelve sections", async () => {
  vi.mocked(fetchReport).mockResolvedValue(fixture);
  mount();
  await screen.findByRole("heading", { name: fixture.site.name, level: 1 });
  expect(fetchReport).toHaveBeenCalledWith(DEMO_REPORT_ID);
  expect(document.querySelectorAll("[data-report-section]")).toHaveLength(12);
  expect(screen.getByRole("link", { name: "Assess my site" }).getAttribute("href")).toBe("/assess");
  expect(screen.getByRole("link", { name: "About" }).getAttribute("href")).toBe("/about");
  expect(document.title).toContain("sample report");
});

it("shows a recoverable failure and disables printing until the report loads", async () => {
  vi.mocked(fetchReport).mockRejectedValue(new Error("reports returned 500"));
  mount();
  await screen.findByRole("alert");
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Print or save as PDF" }).hasAttribute("disabled"),
    ).toBe(true),
  );
});
