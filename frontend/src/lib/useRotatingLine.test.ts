import { describe, expect, it } from "vitest";

import { LOADING_LINES, type LoadingLine } from "../content/loadingLines";
import { dayPartIst, pickLines } from "./useRotatingLine";

const LINES: LoadingLine[] = [
  { text: "general a" },
  { text: "general b" },
  { text: "morning", when: "morning" },
  { text: "night", when: "night" },
  { text: "kerala", states: ["KERALA"] },
  { text: "tamil", states: ["TAMIL NADU"] },
];

describe("dayPartIst", () => {
  it("reads the hour in IST, not the viewer's zone", () => {
    // 20:00 UTC is 01:30 IST.
    expect(dayPartIst(new Date("2026-10-03T20:00:00Z"))).toBe("night");
    // 03:00 UTC is 08:30 IST.
    expect(dayPartIst(new Date("2026-10-03T03:00:00Z"))).toBe("morning");
    expect(dayPartIst(new Date("2026-10-03T08:00:00Z"))).toBe("afternoon");
    expect(dayPartIst(new Date("2026-10-03T13:00:00Z"))).toBe("evening");
  });
});

describe("pickLines", () => {
  it("leads with the site's state, then the time of day, and drops the rest", () => {
    const out = pickLines(LINES, "KERALA", "morning", () => 0);
    expect(out[0]).toBe("kerala");
    expect(out[1]).toBe("morning");
    expect(out).not.toContain("tamil");
    expect(out).not.toContain("night");
    expect(out).toHaveLength(4);
  });

  it("matches the state whatever its casing", () => {
    expect(pickLines(LINES, " Tamil Nadu ", "night")[0]).toBe("tamil");
  });

  it("falls back to general lines when the state is unknown", () => {
    const out = pickLines(LINES, null, "afternoon");
    expect(out.sort()).toEqual(["general a", "general b"]);
  });
});

describe("LOADING_LINES", () => {
  it("carries no digits - a joke must never smuggle in an unsourced figure", () => {
    for (const line of LOADING_LINES) expect(line.text).not.toMatch(/\d/);
  });
});
