import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "../../api/schema";
import { AreaCard, AreaGrid } from "./AreaGrid";
import { clearPrivateGridCache } from "./grid-cache";

const mockApi = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() }));
vi.mock("../../api/client", () => ({ api: mockApi }));
type Grid = components["schemas"]["OwnerGridOut"];
type Area = components["schemas"]["OwnerAreaOut"];
const empty: Grid = {
  version: "owner_grid_v1",
  consent_private: false,
  storage_available: true,
  details: null,
  outages: [],
};
const area: Area = {
  version: "owner_area_v1",
  state: "Kerala",
  district: "Ernakulam",
  snapshot_sha256: null,
  items: Array.from({ length: 6 }, (_, i) => ({
    key: String(i),
    label: `Metric ${i}`,
    value: null,
    source_name: "Source pending",
    note: "Coverage needs review.",
  })),
};
const saved: Grid = {
  ...empty,
  consent_private: true,
  details: {
    id: 1,
    supersedes_id: null,
    effective_on: "2025-07-01",
    recorded_at: "2025-07-01T00:00:00Z",
    sanctioned_load_kva: 100,
    connected_load_kw: 60,
    transformer_ownership: "unknown",
    transformer_rating_kva: null,
  },
};
let client: QueryClient;
beforeEach(() => {
  vi.resetAllMocks();
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  mockApi.GET.mockImplementation(
    async (path) =>
      ({ data: path.endsWith("/area") ? area : empty, response: new Response() }) as never,
  );
});
afterEach(() => {
  cleanup();
  client.clear();
});
function show() {
  return render(
    <QueryClientProvider client={client}>
      <AreaGrid stationId={1} />
    </QueryClientProvider>,
  );
}

describe("owner area and private grid", () => {
  it("shows missing public metrics without turning them into zero", () => {
    render(<AreaCard area={area} />);
    expect(screen.getAllByText("Not available yet")).toHaveLength(6);
  });
  it("blocks collection until ownership evidence is reviewed", async () => {
    mockApi.GET.mockImplementation(async (path) => ({
      data: path.endsWith("/area")
        ? area
        : { ...empty, storage_available: false, storage_reason: "Ownership review pending." },
      response: new Response(),
    }));
    show();
    await screen.findByText("Ownership review pending.");
    expect(screen.queryByText("Add grid details")).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
  it("keeps kVA, kW and null distinct in a typed save", async () => {
    mockApi.POST.mockResolvedValue({ data: saved, response: new Response() } as never);
    show();
    await screen.findByText("No grid details recorded.");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByText("Add grid details"));
    fireEvent.change(screen.getByLabelText("Sanctioned load (kVA)"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Connected load (kW)"), { target: { value: "60" } });
    fireEvent.click(screen.getByText("Save grid revision"));
    await screen.findByText("Grid revision saved privately.");
    expect(mockApi.POST.mock.calls[0]?.[1]?.body).toMatchObject({
      consent_private: true,
      sanctioned_load_kva: 100,
      connected_load_kw: 60,
      transformer_rating_kva: null,
      expected_revision_id: null,
    });
    expect(screen.getByText("100 kVA")).toBeTruthy();
    expect(screen.getByText("60 kW")).toBeTruthy();
  });
  it("retains an unsaved draft after a connection failure", async () => {
    mockApi.POST.mockRejectedValue(new Error("offline"));
    show();
    await screen.findByText("No grid details recorded.");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByText("Add grid details"));
    const input = screen.getByLabelText("Connected load (kW)") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "60" } });
    fireEvent.click(screen.getByText("Save grid revision"));
    await screen.findByRole("alert");
    expect(input.value).toBe("60");
  });
  it("withdraws consent and removes all current private fields from the query cache", async () => {
    mockApi.GET.mockImplementation(
      async (path) =>
        ({ data: path.endsWith("/area") ? area : saved, response: new Response() }) as never,
    );
    mockApi.DELETE.mockResolvedValue({
      response: new Response(null, { status: 204 }),
    } as never);
    show();
    await screen.findByText("100 kVA");
    fireEvent.click(screen.getByText("Withdraw grid consent and delete details"));
    fireEvent.click(screen.getByText("Yes, delete grid details"));
    await screen.findByText(
      "All grid and outage revisions deleted. Private grid consent withdrawn.",
    );
    expect(client.getQueryData(["owner-grid", 1])).toMatchObject(empty);
    expect(screen.queryByText("100 kVA")).toBeNull();
  });
  it("does not restore private data when an outstanding save finishes after logout", async () => {
    let finish!: (value: unknown) => void;
    mockApi.POST.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    show(); await screen.findByText("No grid details recorded.");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByText("Add grid details"));
    fireEvent.click(screen.getByText("Save grid revision"));
    await waitFor(() => expect(mockApi.POST).toHaveBeenCalled());
    await clearPrivateGridCache(client);
    finish({data: saved, response: new Response()});
    await waitFor(() => expect(screen.queryByText("Saving?")).toBeNull());
    expect(client.getQueryData(["owner-grid", 1])).toBeUndefined();
  });
  it("clears grid and area queries on logout without discarding public data", async () => {
    client.setQueryData(["owner-grid", 1], { canary: "PrivateOwnerGridCanary" });
    client.setQueryData(["owner-area", 1], area);
    client.setQueryData(["public-data"], "public");
    await clearPrivateGridCache(client);
    await waitFor(() => expect(client.getQueryData(["owner-grid", 1])).toBeUndefined());
    expect(client.getQueryData(["owner-area", 1])).toBeUndefined();
    expect(client.getQueryData(["public-data"])).toBe("public");
  });
});
