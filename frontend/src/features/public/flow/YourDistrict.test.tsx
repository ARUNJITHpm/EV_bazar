import { cleanup, render, screen, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { YourDistrict } from "./YourDistrict";
import { Working } from "./Working";
import { Result } from "./Result";
import type { AssessOut } from "./state";

vi.mock("virtual:analytics-atlas", () => ({
  default: { registrations: [], chargers: [], tariffs: [], shapes: [] },
}));
vi.mock("virtual:analytics-expansion", () => ({
  default: { asOf: "2026-10-02", performance: [], supply: [], policies: [], amenities: [] },
}));
vi.mock("virtual:analytics-public-data", () => ({
  default: {
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
  },
}));
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
const out: AssessOut = {
  lgd_district_code: 555,
  district: "Ernakulam",
  state: "Kerala",
  site_id: "00000000-0000-0000-0000-000000000001",
  requests: 1,
  confidence: "high",
  boundary_ambiguous: false,
  tier: 3,
  tier_why: "Source pending",
  waitlisted: true,
  waitlist_reason: "Verified tariff pending",
  teaser: null,
};
const show = (element: React.ReactNode) => render(<MemoryRouter>{element}</MemoryRouter>);
it("keeps old saved assessments without an LGD code usable", () => {
  const { container } = show(<YourDistrict out={{ ...out, lgd_district_code: undefined }} />);
  expect(container.textContent).toBe("");
});
it("shows the same four facts and district link on a waitlisted result", () => {
  show(<Result out={out} onRestart={() => {}} />);
  expect(screen.getByRole("heading", { name: /Your district/ })).toBeTruthy();
  expect(screen.getByText("EV registrations and growth")).toBeTruthy();
  expect(screen.getByText("EVs per public charger")).toBeTruthy();
  expect(screen.getByText("Serving DISCOM")).toBeTruthy();
  expect(screen.getByText("Policy in force")).toBeTruthy();
  expect(screen.getByRole("link", { name: /Explore this district/ }).getAttribute("href")).toBe(
    "/data/district/ernakulam-555",
  );
});
it("shows district facts while keeping the fourteen-second walkthrough and final hold", async () => {
  vi.useFakeTimers();
  const done = vi.fn();
  const run = vi.fn().mockResolvedValue(true);
  show(<Working out={out} run={run} onDone={done} />);
  await act(async () => {
    await Promise.resolve();
  });
  expect(run).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("heading", { name: /Your district/ })).toBeTruthy();
  expect(done).not.toHaveBeenCalled();
  await act(async () => {
    vi.advanceTimersByTime(13_500);
  });
  expect(done).not.toHaveBeenCalled();
  await act(async () => {
    vi.advanceTimersByTime(700);
  });
  expect(done).not.toHaveBeenCalled();
  await act(async () => {
    vi.advanceTimersByTime(750);
  });
  expect(done).toHaveBeenCalledTimes(1);
});
