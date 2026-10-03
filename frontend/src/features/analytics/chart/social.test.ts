import { describe, expect, it } from "vitest";
import { publicDataVersions } from "../data/schemas";
import {
  assertSocialSvgLegibility,
  socialFormats,
  socialSvg,
  wrapSocialText,
  socialImagePath,
  type SocialPalette,
} from "./social";
import { pngWithProvenance } from "./social-png";
import { CW_MARK_BOX, CW_MARK_PATH } from "../../public/cwMarkGlyphs";
import type { ChartData, ChartType } from "./model";
// Test-only colours never enter the public bundle.
const palette: SocialPalette = {
  paper: "#faf8f4",
  ink: "#12171a",
  muted: "#5c5852",
  slate: "#1c3a4f",
  rule: "#d6d2c8",
  highlight: "#b5651d",
};
const data: ChartData = {
  id: "social-test",
  title: "Test energy",
  subtitle: "January 2026",
  summary: "Test only",
  type: "bar",
  unit: "kWh",
  updated: "2026-10-01",
  sources: [{ name: "Test source", url: "https://example.invalid/social-test", licence: "CC0" }],
  notes: [],
  versions: publicDataVersions,
  rows: [
    {
      region: "North",
      period: "2026-01",
      indicator: "Energy",
      series: "Energy",
      label: "North",
      status: "observed",
      value: 783,
    },
  ],
};
const input = {
  data,
  rows: data.rows,
  question: "How much energy?",
  pageUrl: "https://example.invalid/data/test",
  palette,
};
describe("shared social exports", () => {
  for (const format of Object.keys(socialFormats) as (keyof typeof socialFormats)[])
    it(`enforces ${format} dimensions, minimum fonts and provenance`, () => {
      const svg = socialSvg({ ...input, format });
      const f = socialFormats[format];
      expect(svg).toContain(`width="${f.width}" height="${f.height}"`);
      assertSocialSvgLegibility(svg, format);
      expect(() =>
        assertSocialSvgLegibility(svg.replace(/font-size="[0-9]+"/, 'font-size="8"'), format),
      ).toThrow(/minimum/);
      for (const key of Object.keys(publicDataVersions)) expect(svg).toContain(key);
      expect(svg).toContain("CC BY 4.0");
      expect(svg).toContain("CC0");
      expect(svg).toContain("783");
    });
  for (const type of ["bar", "horizontal-bar", "line", "range", "small-multiples"] as ChartType[])
    it(`retains ${type} observations in a labelled comparison`, () => {
      const chart = { ...data, type };
      const svg = socialSvg({ ...input, data: chart, rows: chart.rows, format: "portrait" });
      expect(svg).toContain("783");
      expect(svg).toContain("North");
    });
  it("keeps estimate ranges and never exposes suppressed values", () => {
    const chart: ChartData = {
      ...data,
      rows: [
        { ...data.rows[0]!, status: "estimate", value: 20, p10: 10, p90: 30 },
        { ...data.rows[0]!, label: "South", status: "suppressed", value: null },
      ],
    };
    const svg = socialSvg({ ...input, data: chart, rows: chart.rows, format: "portrait" });
    expect(svg).toContain("P50 estimate");
    expect(svg).toContain("P10 10");
    expect(svg).toContain("P90 30");
    expect(svg).toContain("Not enough data yet");
    expect(svg).toContain('stroke-width="12"');
  });
  it("refuses dense selections and overflowing text instead of shrinking", () => {
    const chart = {
      ...data,
      rows: Array.from({ length: 7 }, (_, i) => ({ ...data.rows[0]!, label: `Row ${i}` })),
    };
    expect(() =>
      socialSvg({ ...input, data: chart, rows: chart.rows, format: "portrait" }),
    ).toThrow(/at most/);
    expect(() => wrapSocialText("long ".repeat(30), 200, 40, 1)).toThrow(/readable/);
    expect(() => socialSvg({ ...input, rows: [], format: "square" })).toThrow(/No data/);
    expect(() => socialSvg({ ...input, question: "Not a question", format: "square" })).toThrow(
      /question/,
    );
    expect(() => socialImagePath("../private", "og")).toThrow(/Unsafe/);
  });
  it("carries the Cw mark beside the brand line in every format", () => {
    for (const format of Object.keys(socialFormats) as (keyof typeof socialFormats)[]) {
      const svg = socialSvg({ ...input, format });
      expect(svg).toContain(`d="${CW_MARK_PATH}"`);
      const [, x, y, s] = /<g transform="translate\(([\d.]+) ([\d.]+)\) scale\(([\d.]+)\)">/
        .exec(svg)!
        .map(Number);
      // Inside the image, and clear of the brand text that follows it.
      expect(y).toBeGreaterThan(0);
      const brandX = Number(/<text x="([\d.]+)"[^>]*>Chargeworthy Data/.exec(svg)![1]);
      expect(x! + CW_MARK_BOX * s!).toBeLessThan(brandX);
    }
  });
  it("adds UTF-8 PNG provenance with the full six version stamps", () => {
    const png = new Uint8Array([
      137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
    ]);
    const svg = socialSvg({ ...input, format: "portrait" });
    const annotated = pngWithProvenance(png, svg);
    const text = new TextDecoder().decode(annotated);
    expect(text).toContain("iTXt");
    expect(text).toContain("analytics_social_v2");
    for (const key of Object.keys(publicDataVersions)) expect(text).toContain(key);
    expect(text).toContain('"value":783');
    expect(text).toContain('"sources"');
    expect(() => pngWithProvenance(png, "no metadata")).toThrow(/provenance/);
  });
});
