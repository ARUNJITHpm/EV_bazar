import { describe, expect, it } from "vitest";

import {
  formatKva,
  formatKw,
  formatPercentagePoints,
  formatUtilisation,
  kva,
  kw,
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
