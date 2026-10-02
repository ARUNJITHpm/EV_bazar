import { expect, it } from "vitest";
import { formatLakhPlain, formatRupeesSigned, formatRupeesCompactSigned } from "./money";

it("keeps losses signed consistently in the report's rupee and lakh tables", () => {
  expect(formatLakhPlain(-24_00_00_000)).toBe("−24.00");
  expect(formatRupeesSigned(-100)).toBe("−₹1");
  expect(formatRupeesCompactSigned(-24_00_00_000)).toBe("−₹24.00 L");
});

it("rejects fractional paise rather than formatting rupees as paise", () => {
  expect(() => formatLakhPlain(12.5)).toThrow(/integer paise/);
  expect(() => formatRupeesSigned(-12.5)).toThrow(/integer paise/);
  expect(() => formatRupeesCompactSigned(-12.5)).toThrow(/integer paise/);
});
