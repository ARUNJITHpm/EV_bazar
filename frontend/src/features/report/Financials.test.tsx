import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLES } from "./fixtures/samples";
import { Financials } from "./Financials";
import type { ReportPayload, UnitEconomics } from "./payload";

/**
 * Section 05's per-unit sentence, and the two ways it can be missing.
 *
 * The three fixtures each claim ONE deduction — their stated effective
 * tariff is their whole margin gap — so none of them renders the chain a
 * real payload produces, where the operator's share and the payment gateway
 * take a cut of their own. A live report always has at least two. This is
 * where that shape gets looked at.
 */

function withUnitEconomics(unit: UnitEconomics | null): ReportPayload {
  const base = SAMPLES.build;
  return { ...base, financials: { ...base.financials, unit_economics: unit } };
}

/** Text nodes are split across <span>s, so match on the flattened section. */
function sectionText(): string {
  const section = document.querySelector('[data-report-section="financials"]');
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

describe("the per-unit chain", () => {
  it("names every cut and lands on the margin", () => {
    render(
      <Financials
        payload={withUnitEconomics({
          selling_paise_kwh: 2200,
          deductions: [
            { label: "Electricity, all-in", paise: 850 },
            { label: "Operator revenue share", paise: 250 },
            { label: "Payment gateway", paise: 40 },
          ],
          margin_paise_kwh: 1060,
        })}
      />,
    );
    const text = sectionText();
    expect(text).toContain("₹22.00 from the driver");
    expect(text).toContain("− ₹8.50 electricity, all-in");
    expect(text).toContain("− ₹2.50 operator revenue share");
    expect(text).toContain("− ₹0.40 payment gateway");
    expect(text).toContain("= ₹10.60 left toward the fixed bills");
  });

  it("still reads as a sentence when there is only one cut", () => {
    render(<Financials payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("₹22.00 from the driver − ₹8.50 electricity, all-in = ₹13.50");
  });

  it("says nothing at all rather than half a sum when it is absent", () => {
    render(<Financials payload={withUnitEconomics(null)} />);
    const text = sectionText();
    expect(text).not.toContain("from the driver");
    // The budget above it is a SEPARATE piece of working and is untouched:
    // one missing breakdown never takes another down with it.
    expect(text).toContain("Total setup cost");
  });

  it("falls back to the one-line summary when the budget is missing too", () => {
    const base = SAMPLES.build;
    render(
      <Financials
        payload={{
          ...base,
          financials: { ...base.financials, capex_lines: null, unit_economics: null },
        }}
      />,
    );
    expect(sectionText()).not.toContain("Total setup cost");
    expect(screen.getByText(/price to the driver/)).toBeTruthy();
  });
});

describe("the ten-year table", () => {
  it("prints one row per year plus the build, in bare lakh", () => {
    render(<Financials payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("Year 0 — the build");
    expect(text).toContain("Year 10");
    // Palm Junction: ₹24.00 L out, and the central case back in front by
    // year 4 — the same crossing the payback of 3.2 years describes.
    expect(text).toContain("−24.00");
  });

  it("is dropped whole when a case has no plain money", () => {
    const base = SAMPLES.build;
    const [first, ...rest] = base.financials.scenarios;
    render(
      <Financials
        payload={{
          ...base,
          financials: {
            ...base.financials,
            scenarios: [{ ...first!, plain: null }, ...rest],
          },
        }}
      />,
    );
    expect(sectionText()).not.toContain("Year 0 — the build");
    // The case table above it is untouched: degrading drops the block that
    // lost its data, never the section.
    expect(sectionText()).toContain("Downside (P10)");
  });
});
