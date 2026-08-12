import { describe, expect, it } from "vitest";

import { formatRupees, formatRupeesCompact, formatRupeesPrecise, rupeesToPaise } from "./money";

//   is the non-breaking space Intl inserts after the currency symbol.
const nb = (s: string) => s.replace(/ /g, " ");

describe("paise -> rupees", () => {
  it("uses Indian digit grouping, not thousands", () => {
    // 1,23,45,678 - lakh/crore grouping, NOT 12,345,678
    expect(nb(formatRupees(1234567800))).toBe("₹ 1,23,45,678".replace(" ", ""));
  });

  it("keeps paise where the margin depends on them", () => {
    expect(nb(formatRupeesPrecise(1250))).toContain("12.50");
  });

  it("rejects fractional paise - that means rupees leaked in upstream", () => {
    expect(() => formatRupees(12.5)).toThrow(/integer paise/);
  });

  it("handles zero and negatives (a negative margin is a real case)", () => {
    expect(nb(formatRupees(0))).toContain("0");
    expect(nb(formatRupees(-50000))).toContain("500");
  });
});

describe("compact lakh/crore", () => {
  it("uses crore above 1,00,00,000", () => {
    expect(formatRupeesCompact(15_00_00_000_00)).toBe("₹15.00 Cr");
  });

  it("uses lakh above 1,00,000", () => {
    expect(formatRupeesCompact(42_50_000_00)).toBe("₹42.50 L");
  });

  it("uses k below a lakh", () => {
    expect(formatRupeesCompact(45_000_00)).toBe("₹45.0k");
  });
});

describe("rupeesToPaise", () => {
  it("rounds to whole paise", () => {
    expect(rupeesToPaise(12.345)).toBe(1235);
    expect(rupeesToPaise(0.1)).toBe(10);
  });
});
