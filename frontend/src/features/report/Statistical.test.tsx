import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLES } from "./fixtures/samples";
import type { ReportPayload } from "./payload";
import { Statistical } from "./Statistical";

/**
 * Section 09 (Track B · R7). Two things are worth a test here and the rest
 * is the chart, which is looked at rather than asserted:
 *
 * 1. **The formula prints all of itself or none of it.** A reader invited to
 *    check a division has to be able to finish it, and three payload fields
 *    can independently be missing on an older stored report.
 * 2. **The build-cost sentence is chosen from the data, not the verdict.**
 *    No verdict is measured against that line, so a sentence keyed on the
 *    verdict would be asserting a rule the engine does not apply — and the
 *    three fixtures happen to exercise only two of its four branches.
 */

function sectionText(): string {
  const section = document.querySelector('[data-report-section="statistical"]');
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

function withBand(p10: number, p50: number, p90: number): ReportPayload {
  const base = SAMPLES.build;
  return { ...base, predicted: { ...base.predicted, p10, p50, p90 } };
}

describe("the two lines", () => {
  it("prints both divisions, and the term that separates them", () => {
    render(<Statistical payload={SAMPLES.build} />);
    const text = sectionText();
    // ₹6.30 L of bills ÷ ₹13.50 a unit = 46,667 units a year.
    expect(text).toContain("₹6.30 L of bills a year ÷ ₹13.50 left on each unit = 46,667");
    // Add ₹4.25 L of build cost a year and the same division moves to 78,131.
    expect(text).toContain("₹4.25 L a year");
    expect(text).toContain("78,131");
    expect(text).toContain("One extra term is the whole difference between the two rules.");
  });

  it("labels both rules on the chart, and only one of them as the verdict's", () => {
    const { container } = render(<Statistical payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("covers the bills 4.4%");
    expect(text).toContain("build cost back 7.4%");
    // Dashed is the harder line, and it is the one no verdict applies to.
    const dashed = container.querySelectorAll("line[stroke-dasharray]");
    expect(dashed).toHaveLength(1);
  });

  it("keeps every axis tick in one format", () => {
    // 0.75 × 0.2 is 0.15000000000000002, which printed "15.0%" beside "10%".
    render(<Statistical payload={SAMPLES.build} />);
    expect(sectionText()).toContain("0%5%10%15%20%");
  });

  it("omits the formula whole when a term of it is missing", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      financials: { ...base.financials, fixed_costs: null },
    };
    render(<Statistical payload={payload} />);
    const text = sectionText();
    expect(text).not.toContain("Where the two lines come from");
    // The thresholds themselves survive: they are not part of the sum.
    expect(text).toContain("covers the bills 4.4%");
    expect(text).toContain("build cost back 7.4%");
  });

  it("drops the second line entirely on a payload that has none", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      breakeven: {
        utilisation: base.breakeven.utilisation,
        kwh_year: base.breakeven.kwh_year,
        kwh_day: base.breakeven.kwh_day,
      },
    };
    const { container } = render(<Statistical payload={payload} />);
    const text = sectionText();
    expect(text).toContain("covers the bills 4.4%");
    expect(text).not.toContain("build cost back");
    expect(text).not.toContain("Where the two lines come from");
    expect(container.querySelectorAll("line[stroke-dasharray]")).toHaveLength(0);
    // …and the prose counts what is drawn, rather than what usually is.
    expect(text).toContain("The line holds the price and the fees fixed");
    expect(text).not.toContain("Both lines");
  });
});

describe("where the band sits against the build-cost line", () => {
  // The fixture's build-cost line is 7.43%.
  it("says every case clears it when the downside does", () => {
    render(<Statistical payload={withBand(0.08, 0.1, 0.13)} />);
    expect(sectionText()).toContain("Every case pictured also clears the build-cost line");
  });

  it("says the line falls inside the band when only the centre clears it", () => {
    render(<Statistical payload={withBand(0.06, 0.1, 0.13)} />);
    expect(sectionText()).toContain("The build-cost line falls inside the band");
  });

  it("names the upside as the only one that clears it", () => {
    render(<Statistical payload={withBand(0.05, 0.07, 0.13)} />);
    expect(sectionText()).toContain("Only the upside case clears the build-cost line");
  });

  it("says so plainly when nothing pictured clears it", () => {
    render(<Statistical payload={withBand(0.02, 0.04, 0.06)} />);
    expect(sectionText()).toContain("No case pictured clears the build-cost line");
  });
});
