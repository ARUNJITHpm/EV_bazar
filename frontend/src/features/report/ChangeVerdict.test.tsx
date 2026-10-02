import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChangeVerdict } from "./ChangeVerdict";
import { SAMPLES } from "./fixtures/samples";
import type { ReportPayload } from "./payload";

/**
 * Section 08 (Track B · R7). What is asserted here is the two things a
 * reader would be misled by if they broke:
 *
 * 1. **The build-cost line is a lever on a BUILD too.** The BUILD fixture's
 *    downside case clears the bills line and is ₹1.94 L short over ten
 *    years. A section 08 that only listed the bills line would leave that as
 *    a surprise in section 05 — which is the failure this rebuild exists to
 *    remove.
 * 2. **The contract row carries its no-double-counting warning.** The row
 *    without the warning is worse than no row: it reads as though any signed
 *    volume helps.
 */

function sectionText(): string {
  const section = document.querySelector('[data-report-section="change"]');
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

describe("the levers", () => {
  it("makes the build-cost line a lever even where the verdict is BUILD", () => {
    render(<ChangeVerdict payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("Demand, against the build-cost line");
    expect(text).toContain("Demand reaches 7.4%");
    expect(text).toContain("about 214 units a day");
    // No rule is measured against this line, so the cell shows the band.
    expect(text).toContain("7.2% – 12.2% likely");
  });

  it("offers a contract on a BUILD whose downside misses the build-cost line", () => {
    render(<ChangeVerdict payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("A fleet or campus contract");
    expect(text).toContain("only helps if its volume is additional");
  });

  it("drops the contract row, and its warning, where nothing is short", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      // A downside case above the build-cost line: nothing left to underwrite.
      predicted: { ...base.predicted, p10: 0.09, p50: 0.11, p90: 0.13 },
    };
    render(<ChangeVerdict payload={payload} />);
    const text = sectionText();
    expect(text).not.toContain("A fleet or campus contract");
    expect(text).not.toContain("only helps if its volume is additional");
  });

  it("asks the central case to reach the bills line only on a DON’T", () => {
    render(<ChangeVerdict payload={SAMPLES.dont} />);
    const text = sectionText();
    expect(text).toContain("The central case reaches 8.1%");
    expect(text).toContain("The same line, at the low end");
  });

  it("omits the build-cost lever on a payload that has no such line", () => {
    const base = SAMPLES.moderate;
    const payload: ReportPayload = {
      ...base,
      breakeven: {
        utilisation: base.breakeven.utilisation,
        kwh_year: base.breakeven.kwh_year,
        kwh_day: base.breakeven.kwh_day,
      },
    };
    render(<ChangeVerdict payload={payload} />);
    expect(sectionText()).not.toContain("build-cost line");
  });
});

describe("what to get in writing", () => {
  it("names what is still open on this site", () => {
    const payload = SAMPLES.moderate;
    const open = payload.site_facts.filter((f) => f.unverified);
    expect(open).toHaveLength(3);
    render(<ChangeVerdict payload={payload} />);
    const text = sectionText();
    expect(text).toContain(`${open.length} of the ${payload.site_facts.length} checks`);
    for (const f of open) expect(text).toContain(f.label.toLowerCase());
    // Three is the whole list, so nothing is being held back.
    expect(text).not.toContain("among them");
  });

  it("names three and says there are more, rather than printing a list nobody acts on", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      site_facts: base.site_facts.map((f, i) => ({ ...f, unverified: i < 5 })),
    };
    render(<ChangeVerdict payload={payload} />);
    const text = sectionText();
    expect(text).toContain(`5 of the ${payload.site_facts.length} checks`);
    expect(text).toContain("among them");
    expect(text).toContain(payload.site_facts[2]!.label.toLowerCase());
    expect(text).not.toContain(payload.site_facts[3]!.label.toLowerCase());
  });

  it("says so rather than inventing a to-do list when nothing is open", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      site_facts: base.site_facts.map((f) => ({ ...f, unverified: false })),
    };
    render(<ChangeVerdict payload={payload} />);
    const text = sectionText();
    expect(text).toContain(`All ${payload.site_facts.length} checks are verified`);
    expect(text).not.toContain("still unverified");
  });
});
