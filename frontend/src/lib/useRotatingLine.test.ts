import { describe, expect, it } from "vitest";

import { LOADING_LINES, type LoadingLine } from "../content/loadingLines";
import { dateIst, dayPartIst, pickLines } from "./useRotatingLine";

const LINES: LoadingLine[] = [
  { text: "general a" },
  { text: "general b" },
  { text: "morning", when: "morning" },
  { text: "night", when: "night" },
  { text: "kerala", states: ["KERALA"] },
  { text: "tamil", states: ["TAMIL NADU"] },
  { text: "diwali", between: ["2026-11-05", "2026-11-10"] },
  { text: "onam", states: ["KERALA"], between: ["2027-09-02", "2027-09-13"] },
];

/** 03:00 UTC is 08:30 IST - a morning. */
const MORNING = new Date("2026-10-03T03:00:00Z");

describe("dayPartIst", () => {
  it("reads the hour in IST, not the viewer's zone", () => {
    // 20:00 UTC is 01:30 IST.
    expect(dayPartIst(new Date("2026-10-03T20:00:00Z"))).toBe("night");
    expect(dayPartIst(MORNING)).toBe("morning");
    expect(dayPartIst(new Date("2026-10-03T08:00:00Z"))).toBe("afternoon");
    expect(dayPartIst(new Date("2026-10-03T13:00:00Z"))).toBe("evening");
  });
});

describe("dateIst", () => {
  it("rolls over at IST midnight, not UTC midnight", () => {
    // 19:00 UTC on the 4th is 00:30 IST on the 5th.
    expect(dateIst(new Date("2026-11-04T19:00:00Z"))).toBe("2026-11-05");
  });
});

describe("pickLines", () => {
  it("leads with the site's state, then the time of day, and drops the rest", () => {
    const out = pickLines(LINES, "KERALA", MORNING, () => 0);
    expect(out[0]).toBe("kerala");
    expect(out[1]).toBe("morning");
    expect(out).not.toContain("tamil");
    expect(out).not.toContain("night");
    expect(out).toHaveLength(4);
  });

  it("matches the state whatever its casing", () => {
    expect(pickLines(LINES, " Tamil Nadu ", MORNING)[0]).toBe("tamil");
  });

  it("falls back to general lines when the state is unknown", () => {
    const out = pickLines(LINES, null, new Date("2026-10-03T08:00:00Z"));
    expect(out.sort()).toEqual(["general a", "general b"]);
  });

  it("puts a festival first inside its window, and drops it outside", () => {
    expect(pickLines(LINES, null, new Date("2026-11-08T06:00:00Z"))[0]).toBe("diwali");
    expect(pickLines(LINES, null, new Date("2026-11-11T06:00:00Z"))).not.toContain("diwali");
  });

  it("keeps a state's festival to that state", () => {
    const onam = new Date("2027-09-12T06:00:00Z");
    expect(pickLines(LINES, "KERALA", onam)[0]).toBe("onam");
    expect(pickLines(LINES, "TAMIL NADU", onam)).not.toContain("onam");
  });
});

describe("LOADING_LINES", () => {
  it("carries no digits - a joke must never smuggle in an unsourced figure", () => {
    for (const line of LOADING_LINES) expect(line.text).not.toMatch(/\d/);
  });

  it("has well-formed festival windows", () => {
    for (const line of LOADING_LINES) {
      if (!line.between) continue;
      const [from, to] = line.between;
      expect(from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(from <= to).toBe(true);
    }
  });
});
