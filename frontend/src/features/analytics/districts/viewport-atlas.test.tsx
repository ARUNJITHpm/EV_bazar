import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Atlas } from "./model";
import { useViewportAtlas } from "./viewport-atlas";

const source = vi.hoisted(() => ({ datasets: [] as { id: string; data_url: string }[] }));
vi.mock("virtual:analytics-public-data", () => ({ default: source }));
const base: Atlas = { registrations: [], chargers: [], tariffs: [], shapes: [] };
afterEach(() => {
  source.datasets = [];
  vi.unstubAllGlobals();
});

it("does not fetch missing boundary data or change unknown observations", async () => {
  vi.stubGlobal("IntersectionObserver", undefined);
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const { result } = renderHook(() => useViewportAtlas(base));
  expect(result.current.atlas).toBe(base);
  expect(fetch).not.toHaveBeenCalled();
});

it("waits until the section is visible, then reports a failed fetch and allows retry", async () => {
  let enter: (entries: { isIntersecting: boolean }[]) => void = () => {};
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: typeof enter) {
        enter = callback;
      }
      observe() {}
      disconnect() {}
    },
  );
  source.datasets = [
    { id: "district_boundaries", data_url: "/analytics-data/district_boundaries/data.topojson" },
  ];
  const fetch = vi.fn().mockRejectedValue(new Error("offline"));
  vi.stubGlobal("fetch", fetch);
  const { result } = renderHook(() => {
    const value = useViewportAtlas(base);
    // A real component attaches this before effects run.
    value.ref.current = document.createElement("div");
    return value;
  });
  expect(fetch).not.toHaveBeenCalled();
  act(() => enter([{ isIntersecting: true }]));
  await waitFor(() => expect(result.current.error).toBe(true));
  expect(result.current.atlas.shapes).toEqual([]);
  act(() => result.current.retry());
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});
