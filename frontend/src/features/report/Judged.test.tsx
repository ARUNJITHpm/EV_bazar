import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLES } from "./fixtures/samples";
import { Judged } from "./Judged";
import type { ReportPayload } from "./payload";

/**
 * Section 03 (Track B · R8). Three things are worth holding:
 *
 * 1. **The rule printed is the rule the engine runs.** The sample document
 *    measures all three verdicts against its full-cost line; ours measures
 *    them against the running-bill line and reports the other separately.
 *    A section 03 that drifted to the sample's wording would describe a rule
 *    the code does not run — the exact failure this rebuild exists to remove.
 * 2. **The verdict names match section 01.** They did not for months: this
 *    table said "Build — conditional" after R3 had removed that prefix.
 * 3. **The second threshold degrades whole.** A 0.1.0 payload has no
 *    full-cost line, and the prose around it has to stop claiming there are
 *    two.
 */

function sectionText(): string {
  const section = document.querySelector('[data-report-section="judged"]');
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

/** A payload from before the engine computed a full-cost breakeven. */
function withoutFullCost(base: ReportPayload): ReportPayload {
  return {
    ...base,
    breakeven: {
      utilisation: base.breakeven.utilisation,
      kwh_year: base.breakeven.kwh_year,
      kwh_day: base.breakeven.kwh_day,
    },
  };
}

describe("the rules", () => {
  it("states the running-bill rule the engine actually runs", () => {
    render(<Judged payload={SAMPLES.moderate} />);
    const text = sectionText();
    expect(text).toContain("The downside case covers the running bills on its own");
    expect(text).toContain("The central case covers the running bills and the downside case");
    expect(text).toContain("Even the central case falls short of the running bills");
  });

  it("names the three answers exactly as section 01 does", () => {
    render(<Judged payload={SAMPLES.moderate} />);
    const text = sectionText();
    expect(text).toContain("BUILD");
    expect(text).toContain("CONDITIONAL");
    expect(text).toContain("DON’T BUILD");
    // R3 removed this prefix from the verdict block; the table kept it.
    expect(text).not.toContain("Build — conditional");
  });

  it("marks which of the three this site landed on", () => {
    render(<Judged payload={SAMPLES.dont} />);
    expect(sectionText()).toContain("DON’T BUILDthis site");
  });
});

describe("the two thresholds", () => {
  it("prints both lines and says which one the verdict uses", () => {
    render(<Judged payload={SAMPLES.moderate} />);
    const text = sectionText();
    expect(text).toContain("Two thresholds, and the rules above use the first");
    expect(text).toContain("6.1%, about 176 units a day");
    expect(text).toContain("9.9%, about 286 units a day");
    expect(text).toContain("can clear the first line, earn a BUILD, and still be short");
    expect(text).toContain("Neither line includes tax or financing costs");
  });

  it("stops claiming two when the payload carries one", () => {
    render(<Judged payload={withoutFullCost(SAMPLES.moderate)} />);
    const text = sectionText();
    expect(text).toContain("6.1%, about 176 units a day");
    expect(text).not.toContain("full-cost breakeven");
    expect(text).not.toContain("Neither line");
    expect(text).toContain("This line includes no tax or financing costs");
  });
});

describe("the concept plot", () => {
  it("draws one bay per connector, each with its own charger", () => {
    const { container } = render(<Judged payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("BAY 1");
    expect(text).toContain("BAY 2");
    expect(text).not.toContain("BAY 3");
    expect(container.querySelectorAll("svg")).toHaveLength(1);
  });

  it("shows one connection smaller than the chargers behind it", () => {
    const payload = SAMPLES.build;
    const sl = payload.financials.sanctioned_load;
    expect(sl.recommended_kva).toBeLessThan(sl.full_kva);
    render(<Judged payload={payload} />);
    const text = sectionText();
    expect(text).toContain("93 kVAone connection");
    expect(text).toContain("sized at 93 kVA rather than 133 kVA");
  });

  it("scales to a site with more than two bays", () => {
    const base = SAMPLES.build;
    const payload: ReportPayload = {
      ...base,
      hardware: { ...base.hardware, connectors: 4 },
    };
    render(<Judged payload={payload} />);
    const text = sectionText();
    expect(text).toContain("BAY 4");
    expect(text).not.toContain("BAY 5");
  });

  it("says what it is not, before anything measured on this site", () => {
    render(<Judged payload={SAMPLES.build} />);
    expect(sectionText()).toContain("Not a survey, route map or approved layout");
  });
});
