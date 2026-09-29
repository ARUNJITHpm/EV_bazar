import { describe, expect, it } from "vitest";

import {
  formatKva,
  formatKw,
  formatKwhBound,
  formatPercentagePoints,
  formatUtilisation,
  kva,
  kw,
  kwh,
  kwToKva,
} from "./units";

describe("kW vs kVA", () => {
  it("converts at an explicit power factor - the OVERVIEW.md worked example", () => {
    // "A 60 kW charger at 0.9 power factor needs ~67 kVA sanctioned."
    expect(kwToKva(kw(60), 0.9)).toBeCloseTo(66.67, 1);
  });

  it("refuses a power factor outside (0, 1]", () => {
    expect(() => kwToKva(kw(60), 0)).toThrow(/power factor/);
    expect(() => kwToKva(kw(60), 1.2)).toThrow(/power factor/);
  });

  it("allows unity power factor", () => {
    expect(kwToKva(kw(60), 1)).toBe(60);
  });

  it("formats each unit with its own label", () => {
    expect(formatKw(kw(60))).toBe("60 kW");
    expect(formatKva(kva(66.67))).toBe("66.7 kVA");
  });
});

describe("utilisation", () => {
  it("renders a fraction as a percentage", () => {
    expect(formatUtilisation(0.184)).toBe("18.4%");
  });

  it("signs percentage points, because margin of safety is a difference", () => {
    expect(formatPercentagePoints(-7.4)).toBe("-7.4 pp");
    expect(formatPercentagePoints(3.1)).toBe("+3.1 pp");
  });
});

describe("formatKwhBound", () => {
  it("rounds a range outward, so rounding only ever widens it", () => {
    expect(formatKwhBound(kwh(1210.4), "low")).toBe("1,210 kWh");
    expect(formatKwhBound(kwh(2064.1), "high")).toBe("2,065 kWh");
  });

  it("groups digits the Indian way", () => {
    expect(formatKwhBound(kwh(123456.2), "high")).toBe("1,23,457 kWh");
  });

  it("leaves a whole number alone at either end", () => {
    expect(formatKwhBound(kwh(900), "low")).toBe("900 kWh");
    expect(formatKwhBound(kwh(900), "high")).toBe("900 kWh");
  });
});
