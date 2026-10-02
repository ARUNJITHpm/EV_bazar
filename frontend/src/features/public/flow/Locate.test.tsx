import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../../api/client";
import { Locate } from "./Locate";
import type { AssessOut } from "./state";

const map = vi.hoisted(() => ({
  events: {} as Record<string, () => void>,
  centre: { lat: 9.98, lng: 76.3 },
  fail: false,
  enablePan: vi.fn(),
}));
vi.mock("../../../api/client", () => ({ api: { POST: vi.fn() } }));
vi.mock("../mapCore", () => ({
  MAPBOX_TOKEN: "test",
  MAP_STYLE: "test-style",
  autoResize: () => () => {},
  mapboxgl: {
    Map: class {
      constructor() {
        if (map.fail) throw new Error("map unavailable");
      }
      on(name: string, callback: () => void) {
        map.events[name] = callback;
      }
      getCenter() {
        return map.centre;
      }
      loaded() {
        return true;
      }
      remove() {}
      dragPan = { enable: map.enablePan, disable() {} };
      keyboard = { enable() {}, disable() {} };
    },
  },
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  map.events = {};
  map.fail = false;
});

function mount() {
  const onContinue = vi.fn();
  const onChecked = vi.fn();
  const onPin = vi.fn();
  render(
    <MemoryRouter>
      <Locate
        pin={{ lat: 9.98, lng: 76.3 }}
        location={{ lat: 9.98, lng: 76.3, name: "My property", area: false }}
        onPin={onPin}
        onSelect={vi.fn()}
        confirmed={null}
        onChecked={onChecked}
        onContinue={onContinue}
      />
    </MemoryRouter>,
  );
  if (!map.fail) act(() => map.events.idle!());
  return { onContinue, onChecked, onPin };
}

it("checks the selected coordinates once and immediately continues", async () => {
  const out = { waitlisted: false } as AssessOut;
  vi.mocked(api.POST).mockResolvedValue({ data: out, response: new Response() });
  const { onChecked, onContinue } = mount();
  expect(api.POST).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Confirm location" }));
  await waitFor(() => expect(onContinue).toHaveBeenCalledWith(out));
  expect(onChecked).toHaveBeenCalledWith(out);
  expect(api.POST).toHaveBeenCalledTimes(1);
  expect(api.POST).toHaveBeenCalledWith("/api/internal/assess", {
    body: {
      lat: 9.98,
      lng: 76.3,
      transformer_kva: null,
      transformer_distance_m: null,
      space: null,
      intent: null,
    },
  });
});

it("keeps the pin and permits retry when confirmation fails", async () => {
  vi.mocked(api.POST).mockRejectedValue(new Error("network failure"));
  const { onContinue, onPin } = mount();
  fireEvent.click(screen.getByRole("button", { name: "Confirm location" }));
  await screen.findByRole("alert");
  expect(onContinue).not.toHaveBeenCalled();
  expect(onPin).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Confirm location" }).hasAttribute("disabled")).toBe(
    false,
  );
});

it("allows immediate adjustment of a property result and blocks confirmation during movement", () => {
  const { onPin } = mount();
  expect(map.enablePan).toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Adjust pin" })).toBeNull();
  act(() => map.events.movestart!());
  expect(screen.getByRole("button", { name: "Confirm location" }).hasAttribute("disabled")).toBe(
    true,
  );
  map.centre = { lat: 10, lng: 76.4 };
  act(() => map.events.moveend!());
  expect(onPin).toHaveBeenCalledWith({ lat: 10, lng: 76.4 });
  expect(api.POST).not.toHaveBeenCalled();
});

it("requires a visible map before a customer can confirm", () => {
  map.fail = true;
  mount();
  expect(screen.getByRole("alert").textContent).toContain("map could not load");
  expect(screen.getByRole("button", { name: "Confirm location" }).hasAttribute("disabled")).toBe(
    true,
  );
  expect(api.POST).not.toHaveBeenCalled();
});
