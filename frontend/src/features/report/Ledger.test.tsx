import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Disclosure } from "./Disclosure";
import { SAMPLES } from "./fixtures/samples";
import { Ledger } from "./Ledger";
import type { ReportPayload } from "./payload";
import { Provenance } from "./Provenance";

/**
 * Sections 10, 11 and 12 (Track B · R10). What is worth holding:
 *
 * 1. **Two ledgers, and both on the page.** `engine.py` has written every
 *    default into `RoiResult.assumptions` since it was built and claimed in
 *    its own docstring that the report consumed them verbatim. Nothing
 *    printed them until R10. If they stop reaching the page, that claim goes
 *    back to being false quietly.
 * 2. **Neither ledger repeats the other.** They are different things — the
 *    model's choices against where each input came from — and the moment the
 *    same fact appears in both, the section is teaching the reader that its
 *    two halves are not about different things.
 * 3. **The document has a date.** Until R10 it had none anywhere, which is a
 *    strange thing for the section whose whole job is letting an old report
 *    defend itself.
 * 4. **Every piece degrades alone.** A payload stored before R10 has no
 *    engine ledger and no date, and must still render a complete section.
 */

function sectionText(id: string): string {
  const section = document.querySelector(`[data-report-section="${id}"]`);
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

/** A payload from before R10: no engine ledger, no date. */
function stripped(base: ReportPayload): ReportPayload {
  return { ...base, model_assumptions: undefined, generated_at: undefined };
}

describe("10 · the assumptions ledger", () => {
  it("prints the engine's own ledger, not only the assembler's", () => {
    render(<Ledger payload={SAMPLES.build} />);
    const text = sectionText("ledger");
    expect(text).toContain("What the model assumed");
    expect(text).toContain("discount rate 12% for NPV");
    expect(text).toContain("utilisation ceiling assumes every plug at full rated power");
  });

  it("carries the full-cost line R6 left behind, with R7's figure in it", () => {
    // Section 09 prints `(bills + recovery) / margin` and calls the recovery
    // term the whole difference between the two rules. The ledger is where
    // that term is stated as an assumption rather than as arithmetic, and
    // the number has to be the same one.
    render(<Ledger payload={SAMPLES.build} />);
    const text = sectionText("ledger");
    expect(text).toContain("full-cost breakeven spreads the 24.00 lakh build cost");
    expect(text).toContain("which is 4.25 lakh a year");
    expect(text).toContain("agrees with the NPV above rather than offering a second opinion");
  });

  it("does not say the same thing in both ledgers", () => {
    // The discount rate and the horizon were rows in the input table AND
    // lines in the engine's list. One page, one statement (R6).
    render(<Ledger payload={SAMPLES.build} />);
    const rows = document.querySelectorAll('[data-report-section="ledger"] tbody tr');
    const items = [...rows].map((r) => r.querySelector("td")?.textContent ?? "");
    expect(items).not.toContain("Discount rate");
    expect(items).not.toContain("Horizon");
    expect(sectionText("ledger")).toContain("discount rate 12% for NPV");
  });

  it("does not call an unconfirmed recommendation verified", () => {
    // "engine recommendation" beside the word "Verified" is the page
    // contradicting itself inside one row.
    render(<Ledger payload={SAMPLES.build} />);
    const row = [...document.querySelectorAll('[data-report-section="ledger"] tbody tr')].find(
      (r) => r.querySelector("td")?.textContent === "Sanctioned load",
    );
    expect(row?.textContent).toContain("not confirmed with the DISCOM");
    expect(row?.textContent).toContain("unverified");
  });

  it("keeps the value and its basis in one cell", () => {
    render(<Ledger payload={SAMPLES.build} />);
    const row = [...document.querySelectorAll('[data-report-section="ledger"] tbody tr')].find(
      (r) => r.querySelector("td")?.textContent === "Selling price",
    );
    const cells = row?.querySelectorAll("td") ?? [];
    expect(cells).toHaveLength(3);
    expect(cells[1]?.textContent).toContain("₹22.00/kWh to the driver");
    expect(cells[1]?.textContent).toContain("invented for this fixture");
  });

  it("drops the engine block whole on a payload stored without it", () => {
    render(<Ledger payload={stripped(SAMPLES.build)} />);
    const text = sectionText("ledger");
    expect(text).not.toContain("What the model assumed");
    expect(text).toContain("Every input the arithmetic used");
    expect(text).toContain("Selling price");
  });
});

describe("11 · provenance", () => {
  it("gives the document a record with a date on it", () => {
    render(<Provenance payload={SAMPLES.build} />);
    const text = sectionText("provenance");
    expect(text).toContain("Document record");
    expect(text).toContain("CW-SAMPLE-BUILD · 2026-09-08 · 34 checks · economics 0.5.0");
  });

  it("says what the report was not built from", () => {
    render(<Provenance payload={SAMPLES.build} />);
    const text = sectionText("provenance");
    expect(text).toContain("What this was not built from");
    expect(text).toContain("None of it is a site visit");
    expect(text).toContain("a map cannot see a transformer with no spare capacity");
  });

  it("leaves the date out rather than inventing one", () => {
    // The date is a payload field, never the clock: a payload is served
    // verbatim, so a date filled in at render time is the date of the
    // reading, not of the report.
    render(<Provenance payload={stripped(SAMPLES.build)} />);
    const text = sectionText("provenance");
    expect(text).toContain("CW-SAMPLE-BUILD · 34 checks");
    expect(text).not.toContain("2026-09-08");
    expect(text).not.toContain("undefined");
  });
});

describe("12 · disclosure", () => {
  it("states the actual business model and absence of CPO affiliation", () => {
    render(<Disclosure />);
    const text = sectionText("disclosure");
    expect(text).toContain("operator-matching fees are our income sources");
    expect(text).toContain("not affiliated with any charge point operator");
    expect(text).toContain("do not own or operate charging stations");
  });

  it("does not present invented assessment counts as a track record", () => {
    render(<Disclosure />);
    const text = sectionText("disclosure");
    expect(text).toContain("No verified assessment counts or rejection rate");
    expect(text).not.toContain("340");
    expect(text).not.toContain("129");
  });

  it("lists what must be disclosed before a real client sees it", () => {
    render(<Disclosure />);
    const text = sectionText("disclosure");
    expect(text).toContain("Disclose before this is used with a real client");
    expect(text).toContain("every referral or success fee attached to the site");
    expect(text).toContain("No actual fees or operator agreements");
  });
});
