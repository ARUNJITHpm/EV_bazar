import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LocationSearch } from "./LocationSearch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("searches only on submission and passes a town as an area preview", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify([
          { display_name: "Kochi, Kerala, India", lat: "9.97", lon: "76.28", addresstype: "city" },
        ]),
      ),
    );
  vi.stubGlobal("fetch", fetcher);
  const onSelect = vi.fn();
  render(<LocationSearch id="test-site" onSelect={onSelect} />);
  fireEvent.change(screen.getByLabelText("Site location"), { target: { value: "Kochi" } });
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Find location" }));
  fireEvent.click(await screen.findByRole("button", { name: "Kochi Kerala, India" }));
  expect(onSelect).toHaveBeenCalledWith({
    lat: 9.97,
    lng: 76.28,
    name: "Kochi, Kerala, India",
    area: true,
  });
});

it("offers recovery instead of accepting missing coordinates", async () => {
  vi.setSystemTime(Date.now() + 2000);
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify([{ display_name: "Bad result", lat: null, lon: "" }])),
      ),
  );
  const onSelect = vi.fn();
  render(<LocationSearch id="test-site" onSelect={onSelect} />);
  fireEvent.change(screen.getByLabelText("Site location"), {
    target: { value: "Missing coordinates" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Find location" }));
  await screen.findByText(/No places found/);
  expect(onSelect).not.toHaveBeenCalled();
});

it("recovers from denied device location without selecting a point", async () => {
  const onSelect = vi.fn();
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: (_success: PositionCallback, failure: PositionErrorCallback) =>
        failure({ code: 1, message: "denied" } as GeolocationPositionError),
    },
  });
  render(<LocationSearch id="test-site" onSelect={onSelect} />);
  fireEvent.click(screen.getByRole("button", { name: "Use my current location" }));
  expect((await screen.findByRole("alert")).textContent).toContain("Allow location access");
  expect(onSelect).not.toHaveBeenCalled();
});
