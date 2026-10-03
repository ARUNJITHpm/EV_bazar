import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { DistrictMap } from "./DistrictMap";
import type { District } from "../data/schemas";
import {
  decodeTopology,
  districtValue,
  neighbourCodes,
  registrationTotal,
  stateLabel,
  type Atlas,
} from "./model";

const districts: District[] = [
  {
    lgd_code: 1,
    district_name: "Test North",
    state_name: "Test State",
    slug: "test-north",
    former_names: [],
  },
  {
    lgd_code: 2,
    district_name: "Test South",
    state_name: "Test State",
    slug: "test-south",
    former_names: [],
  },
];
const atlas: Atlas = {
  registrations: [],
  chargers: [],
  tariffs: [],
  shapes: [
    {
      lgd_code: 1,
      rings: [
        [
          [75, 10],
          [76, 10],
          [76, 11],
          [75, 11],
          [75, 10],
        ],
      ],
    },
    {
      lgd_code: 2,
      rings: [
        [
          [76, 10],
          [77, 10],
          [77, 11],
          [76, 11],
          [76, 10],
        ],
      ],
    },
  ],
};
afterEach(cleanup);
describe("district atlas", () => {
  it("hatches missing districts without zero and offers keyboard list selection", () => {
    render(
      <MemoryRouter>
        <DistrictMap atlas={atlas} districts={districts} />
      </MemoryRouter>,
    );
    const shapes = document.querySelectorAll(".analytics-map-district");
    expect(shapes).toHaveLength(2);
    expect(shapes[0]!.getAttribute("fill")).toContain("missing");
    expect(document.querySelectorAll(".analytics-map-step-0.analytics-map-district")).toHaveLength(
      0,
    );
    fireEvent.change(screen.getByLabelText("Find a district on this map"), {
      target: { value: "south" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Test South · Test State" }));
    expect(screen.getByRole("status").textContent).toContain(
      "Test South, Test State: Not enough data yet",
    );
    expect(screen.getByRole("link", { name: "Open district page" }).getAttribute("href")).toBe(
      "/data/district/test-south",
    );
    expect(document.querySelector(".analytics-map-selected")).toBeTruthy();
  });
  it("marks wide uncertainty separately, shows ranges/sample sizes, and sorts with nulls last", () => {
    render(
      <MemoryRouter>
        <DistrictMap
          atlas={atlas}
          districts={districts}
          initialIndicator="usage"
          values={{
            usage: { 1: { value: 100, p10: 10, p90: 250, sample_size: 12 }, 2: { value: null } },
          }}
        />
      </MemoryRouter>,
    );
    expect(document.querySelectorAll(".analytics-map-wide.analytics-map-district")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Test North · Test State" }));
    expect(screen.getByRole("status").textContent).toContain("P10 10–P90 250");
    expect(screen.getByRole("status").textContent).toContain("12 stations");
    fireEvent.click(screen.getByRole("button", { name: "Value and range" }));
    expect(document.querySelector("tbody tr")?.textContent).toContain("Test North");
  });
  it("decodes quantised deltas and reversed arcs", () => {
    const shapes = decodeTopology({
      transform: { scale: [0.1, 0.1], translate: [75, 10] },
      arcs: [
        [
          [0, 0],
          [10, 0],
          [0, 10],
          [-10, 0],
          [0, -10],
        ],
      ],
      objects: {
        districts: { geometries: [{ type: "Polygon", properties: { lgd_code: 1 }, arcs: [[-1]] }] },
      },
    });
    expect(shapes[0]!.rings[0]).toEqual([
      [75, 10],
      [75, 11],
      [76, 11],
      [76, 10],
      [75, 10],
    ]);
  });
  it("counts neighbours by shared edges and handles absent geometry", () => {
    expect(neighbourCodes(atlas.shapes, 1)).toEqual([2]);
    expect(neighbourCodes([], 1)).toEqual([]);
  });
  it("requires explicit monthly vehicle-class coverage and preserves observed zero", () => {
    const registrations = Array.from({ length: 12 }, (_, index) =>
      ["2W", "3W", "4W", "bus", "goods"].map((vehicle_class) => ({
        month: `2026-${String(index + 1).padStart(2, "0")}`,
        state: "Test State",
        rto_code: "XX01",
        lgd_code: 1,
        vehicle_class,
        fuel: "PURE EV",
        count: 0,
      })),
    ) as unknown as Atlas["registrations"][];
    const complete = { ...atlas, registrations: registrations.flat() };
    expect(registrationTotal(complete, 1, "2026-12")).toBe(0);
    expect(
      registrationTotal(
        { ...complete, registrations: complete.registrations.slice(1) },
        1,
        "2026-12",
      ),
    ).toBeNull();
    expect(districtValue(atlas, 1, "chargers").value).toBeNull();
    expect(districtValue(complete, 1, "ratio").value).toBeNull();
  });
});

describe("stateLabel", () => {
  it("turns capitalised LGD state names into readable labels", () => {
    expect(stateLabel("KERALA")).toBe("Kerala");
    expect(stateLabel("JAMMU & KASHMIR")).toBe("Jammu & Kashmir");
    expect(stateLabel("DADRA,NAGAR HAVELI,DAMAN & DIU")).toBe("Dadra, Nagar Haveli, Daman & Diu");
    expect(stateLabel("ANDAMAN AND NICOBAR ISLANDS")).toBe("Andaman and Nicobar Islands");
  });
});
