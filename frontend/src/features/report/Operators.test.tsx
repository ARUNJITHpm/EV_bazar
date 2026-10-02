import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SAMPLES } from "./fixtures/samples";
import { Operators } from "./Operators";
import type { CpoRow, ReportPayload } from "./payload";

/**
 * Section 06 (Track B · R9). Four things are worth holding:
 *
 * 1. **The two halves stay apart.** Money in one table, network and service
 *    in another, because they are never blended into a score — and a single
 *    grid is what invites the blend.
 * 2. **Prose is counted, never asserted.** "3 of the 4 arrangements return
 *    the build cost" has to be read off the rows, the way R6, R7 and R8 read
 *    theirs, or it becomes a sentence that survives its own data changing.
 * 3. **Every optional piece degrades on its own.** The live payload has no
 *    signed service terms and an old one has no cash column; each disappears
 *    without taking the section with it.
 * 4. **A dash keeps its sentence and a count loses one.** The counts moved
 *    into columns, so repeating them in prose underneath would be the
 *    duplication R6 removed — but a dash is the one cell that cannot explain
 *    itself.
 */

function sectionText(): string {
  const section = document.querySelector('[data-report-section="operators"]');
  return (section?.textContent ?? "").replace(/\s+/g, " ");
}

function withCpo(base: ReportPayload, cpo: CpoRow[]): ReportPayload {
  return { ...base, cpo };
}

/** A payload from before R9: no cash, no service terms. */
function stripped(base: ReportPayload): ReportPayload {
  return withCpo(
    base,
    base.cpo.map((c) => ({
      ...c,
      cash_p50_paise_year: undefined,
      repair_hours: undefined,
      tie_in_years: undefined,
    })),
  );
}

describe("the money table", () => {
  it("prints cash beside the terms that produce it", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("Cash left a year, central");
    // The free arrangement leads, and leads on rupees the reader can check
    // against section 02 — the fixtures derive both from one `Econ`.
    expect(text).toContain("Self-operate");
    expect(text).toContain("₹7.51 L");
  });

  it("signs a loss the way section 02 signs one", () => {
    // Every arrangement on the DON'T BUILD site loses money. A minus sign
    // that differs between two sections is the drift R9 moved the formatter
    // into lib/money to stop.
    render(<Operators payload={SAMPLES.dont} />);
    expect(sectionText()).toContain("−₹2.82 L");
  });

  it("drops the cash column whole on a payload stored without it", () => {
    render(<Operators payload={stripped(SAMPLES.build)} />);
    const text = sectionText();
    expect(text).not.toContain("Cash left a year");
    // and the section still stands
    expect(text).toContain("Revenue share");
    expect(text).toContain("Margin at downside");
  });

  it("says the rank is financial only rather than printing a rank column", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("the rank is financial only");
    expect(text).toContain("no combined score");
  });
});

describe("what the table says when it is read", () => {
  it("counts the arrangements that return the capital", () => {
    // build: every row returns it.
    render(<Operators payload={SAMPLES.build} />);
    expect(sectionText()).toContain("All of these arrangements return the build cost");
  });

  it("counts them again when only some do", () => {
    // moderate: only the free arrangement returns the capital.
    render(<Operators payload={SAMPLES.moderate} />);
    // The verb follows the count, not the set.
    expect(sectionText()).toContain("1 of the 4 arrangements returns the build cost");
  });

  it("says none rather than counting to zero", () => {
    render(<Operators payload={SAMPLES.dont} />);
    const text = sectionText();
    expect(text).toContain("No arrangement here returns the build cost");
    expect(text).not.toContain("0 of the");
  });

  it("names the work nobody is being paid for", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("prices no operator cut for Self-operate");
    expect(text).toContain("prices none of the work either");
  });

  it("says it on a site where nothing returns the capital too", () => {
    // The sentence is about the row, not about the ranking. "Leads" is a
    // word the table does not support when every row reads "no return", and
    // the caveat is true wherever the free row lands.
    render(<Operators payload={SAMPLES.dont} />);
    const text = sectionText();
    expect(text).toContain("No arrangement here returns the build cost");
    expect(text).toContain("prices none of the work either");
    expect(text).not.toContain("leads");
  });

  it("says nothing about unpaid work when every arrangement has a counterparty", () => {
    const paid = SAMPLES.build.cpo.filter(
      (c) => c.revenue_share_pct > 0 || c.platform_fee_paise_year > 0,
    );
    expect(paid).toHaveLength(3);
    render(<Operators payload={withCpo(SAMPLES.build, paid)} />);
    expect(sectionText()).not.toContain("prices none of the work");
  });
});

describe("the network and service table", () => {
  it("gives both radii a column of their own", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    expect(text).toContain("Own within 3 km");
    expect(text).toContain("Own within 10 km");
    expect(text).toContain("District / state");
  });

  it("keeps a sentence only for the rows that print a dash", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    // Self-operate is not a network, so its dashes are explained.
    expect(text).toContain("You would run the station yourself");
    // The matched operators have columns now, so their sentence is gone.
    expect(text).not.toContain("18 in this district and 120 in the state");
  });

  it("drops the service columns rather than printing a dash per operator", () => {
    render(<Operators payload={stripped(SAMPLES.build)} />);
    const text = sectionText();
    expect(text).not.toContain("Repair target");
    expect(text).not.toContain("Tie-in");
    // The footprint columns are unaffected — each piece degrades alone.
    expect(text).toContain("Own within 3 km");
  });

  it("becomes a sentence when roaming is the only thing left to say", () => {
    // The live 0.1.0 payload knows no footprint and no signed terms. One
    // yes/no column under a heading promising four is furniture; the same
    // fact in a sentence is not.
    const bare = withCpo(
      SAMPLES.build,
      SAMPLES.build.cpo.map((c) => ({
        ...c,
        repair_hours: undefined,
        tie_in_years: undefined,
        stations_district: null,
        stations_state: null,
        own_within_3km: null,
        own_within_10km: null,
        presence_note: "",
      })),
    );
    render(<Operators payload={bare} />);
    const text = sectionText();
    expect(text).not.toContain("What each network brings");
    // Counted, not asserted: the two that refuse a roaming driver are named.
    expect(text).toContain("Self-operate, Operator C do not");
  });

  it("still says a dash is not a zero", () => {
    render(<Operators payload={SAMPLES.build} />);
    expect(sectionText()).toContain("a dash means we cannot state a figure");
  });
});

describe("the trade the section refuses to make", () => {
  it("names both sides when cash and service disagree", () => {
    render(<Operators payload={SAMPLES.build} />);
    const text = sectionText();
    // Self-operate leaves the most and promises nothing; Operator A is the
    // quickest to attend a fault at 8 hours.
    expect(text).toContain("Self-operate leaves the most cash");
    expect(text).toContain("Operator A promises to attend a fault in 8 hours");
    expect(text).toContain("yours to judge");
  });

  it("disappears when there is no service term to trade against", () => {
    render(<Operators payload={stripped(SAMPLES.build)} />);
    expect(sectionText()).not.toContain("The trade this section does not make");
  });

  it("does not congratulate the reader on the smallest loss", () => {
    // Every arrangement on the DON'T BUILD site loses money. "Leaves the
    // most cash, −₹2.82 L a year" is a true sentence that reads as good
    // news, which is the failure this whole rebuild exists to remove.
    render(<Operators payload={SAMPLES.dont} />);
    const text = sectionText();
    expect(text).toContain("Self-operate loses the least, ₹2.82 L a year");
    expect(text).not.toContain("leaves the most cash");
    expect(text).toContain("loses ₹1.51 L a year more");
  });

  it("says so plainly when one arrangement leads on both", () => {
    const rows = SAMPLES.build.cpo.map((c) => ({ ...c, repair_hours: c.ours ? 4 : 24 }));
    render(<Operators payload={withCpo(SAMPLES.build, rows)} />);
    expect(sectionText()).toContain("Nothing here has to be traded off");
  });
});

describe("a site with no operator terms at all", () => {
  it("says so instead of rendering two empty tables", () => {
    render(<Operators payload={withCpo(SAMPLES.build, [])} />);
    const text = sectionText();
    expect(text).toContain("No operator terms are on file");
    expect(text).not.toContain("Revenue share");
    expect(text).not.toContain("Own within 3 km");
  });
});
