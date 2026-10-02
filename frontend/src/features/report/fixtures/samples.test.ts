import { describe, expect, it } from "vitest";

import { CASES, scenarioFor, type ReportPayload } from "../payload";
import { SAMPLE_IDS, SAMPLES } from "./samples";

/**
 * These fixtures are invented. That is the point of them — but "invented"
 * has to mean "one consistent site", not "numbers that look plausible side
 * by side", because the whole reason the sample document is being copied is
 * that our report used to print two figures that disagreed about the same
 * site four pages apart (CPO_SELECTION_PLAN.md, Track B · R0 and R5).
 *
 * R6 added sixty more figures per site. They are DERIVED from each site's
 * `Econ` rather than typed, and this file is what holds that derivation to
 * the NPV, IRR and payback that were typed by hand long before it — if the
 * two ever part company, one of them is lying to the reader.
 */

/** Ten flat years at 12%: what the fixtures' NPVs assume, and what the
 *  engine computes from `discount_pct` and `horizon_years`. */
const ANNUITY = Array.from({ length: 10 }, (_, i) => 1 / 1.12 ** (i + 1)).reduce((a, b) => a + b);

describe.each(SAMPLE_IDS)("the %s fixture", (id) => {
  const payload: ReportPayload = SAMPLES[id];
  const f = payload.financials;

  it("carries plain money on every case", () => {
    for (const c of CASES) expect(scenarioFor(payload, c)?.plain).toBeTruthy();
  });

  it("derives a cash figure the stored NPV agrees with", () => {
    for (const s of f.scenarios) {
      const cash = s.plain!.cash_paise_year;
      // Ten flat years of that cash, less the build: the stored NPV, to the
      // rupee. These fixtures do not ramp, which is why this is exact.
      expect(Math.round(-f.capex_paise + cash * ANNUITY)).toBe(s.npv_paise);
    }
  });

  it("derives a running total the stored payback agrees with", () => {
    for (const s of f.scenarios) {
      const cumulative = s.plain!.cumulative_paise;
      expect(cumulative).toHaveLength(11);
      expect(cumulative[0]).toBe(-f.capex_paise);
      const turns = cumulative.some((c) => c >= 0);
      expect(turns).toBe(s.payback_years !== null);
      if (s.payback_years !== null) {
        // The year the running total crosses zero is the payback year,
        // rounded up — the same crossing, said two ways.
        const crossing = cumulative.findIndex((c) => c >= 0);
        expect(crossing).toBe(Math.ceil(s.payback_years));
      }
    }
  });

  it("balances what comes in against what goes out", () => {
    for (const s of f.scenarios) {
      const m = s.plain!;
      expect(m.revenue_paise_year - m.running_cost_paise_year - m.fixed_cost_paise_year).toBe(
        m.cash_paise_year,
      );
    }
  });

  it("sums its one-time budget to the setup cost it prints", () => {
    expect(f.capex_lines!.reduce((sum, line) => sum + line.paise, 0)).toBe(f.capex_paise);
  });

  it("sums its bills to the fixed cost every case carries", () => {
    const bills = f.fixed_costs!;
    expect(bills.lines.reduce((sum, line) => sum + line.paise, 0)).toBe(bills.total_paise_year);
    for (const s of f.scenarios) {
      expect(s.plain!.fixed_cost_paise_year).toBe(bills.total_paise_year);
    }
  });

  it("leaves exactly the margin its breakeven divides by", () => {
    const u = f.unit_economics!;
    expect(u.selling_paise_kwh).toBe(f.selling_price_paise_kwh);
    expect(u.selling_paise_kwh - u.deductions.reduce((sum, d) => sum + d.paise, 0)).toBe(
      u.margin_paise_kwh,
    );
    // The site's stated effective tariff IS its whole deduction here.
    expect(u.deductions[0]!.paise).toBe(f.energy_tariff_paise_kwh);
    // Bills over margin is the running-bill breakeven in section 03.
    expect(Math.round(f.fixed_costs!.total_paise_year / u.margin_paise_kwh)).toBe(
      Math.round(payload.breakeven.kwh_year),
    );
  });

  it("differs between its two thresholds by exactly the term section 09 prints", () => {
    // Section 09 prints both divisions and says one extra term is the whole
    // difference between the two rules. If that stops being true of these
    // fixtures, the page is doing arithmetic the reader cannot reproduce.
    const be = payload.breakeven;
    const margin = f.unit_economics!.margin_paise_kwh;
    const bills = f.fixed_costs!.total_paise_year;
    const recovery = be.full_cost_recovery_paise_year!;

    expect(Math.round(bills / margin)).toBe(Math.round(be.kwh_year));
    expect(Math.round((bills + recovery) / margin)).toBe(Math.round(be.full_cost_kwh_year!));
    expect(recovery).toBeGreaterThan(f.capex_paise / 10); // discounted, not divided
  });

  it("prices its zero-terms operator at the figures the rest of the document uses", () => {
    // `Econ.margin` deducts the effective tariff and nothing else, so every
    // stored figure on these sites is the NO-OPERATOR-CUT case. The row with
    // no terms is therefore the row sections 02 and 05 are about, and has to
    // agree with them to the decimal.
    //
    // This is exactly what the hand-typed table before R9 got wrong: it gave
    // the P50 scenario's own IRR to an operator taking 13.6% of revenue, and
    // put the free arrangement third — a ranking the terms printed in the
    // same row make arithmetically impossible (Track B · R9).
    const free = payload.cpo.find(
      (c) => c.revenue_share_pct === 0 && c.platform_fee_paise_year === 0,
    );
    expect(free).toBeTruthy();
    const central = scenarioFor(payload, "P50")!;
    expect(free!.irr_p50_pct).toBe(central.irr_pct);
    expect(free!.margin_of_safety_pp).toBe(payload.margin_of_safety_pp);
    expect(free!.cash_p50_paise_year).toBe(central.plain!.cash_paise_year);
  });

  it("leaves less to the owner as the operator takes more", () => {
    // Not a ranking claim — an arithmetic one. If one operator's cut is at
    // least as large on both terms and larger on one, the owner cannot end
    // up with more. A table that says otherwise is printing the terms that
    // contradict it two columns away.
    for (const a of payload.cpo) {
      for (const b of payload.cpo) {
        const dearer =
          a.revenue_share_pct >= b.revenue_share_pct &&
          a.platform_fee_paise_year >= b.platform_fee_paise_year &&
          (a.revenue_share_pct > b.revenue_share_pct ||
            a.platform_fee_paise_year > b.platform_fee_paise_year);
        if (!dearer) continue;
        expect(a.cash_p50_paise_year!).toBeLessThan(b.cash_p50_paise_year!);
        expect(a.margin_of_safety_pp).toBeLessThan(b.margin_of_safety_pp);
      }
    }
  });

  it("orders section 06 the way the assembler orders it", () => {
    // assemble.py: any return beats none, then the larger return, then the
    // wider margin. The fixture sorts rather than trusting the order it was
    // typed in, and this is what says the two agree.
    const key = (c: (typeof payload.cpo)[number]) =>
      [c.irr_p50_pct === null ? 0 : 1, c.irr_p50_pct ?? 0, c.margin_of_safety_pp] as const;
    for (let i = 1; i < payload.cpo.length; i += 1) {
      const above = key(payload.cpo[i - 1]!);
      const below = key(payload.cpo[i]!);
      // Lexicographic and descending: at the first key the two differ on,
      // the row above must be the larger. Rows equal on all three may sit
      // either way round, and the assembler does not order them either.
      const first = above.findIndex((v, n) => v !== below[n]);
      if (first !== -1) expect(above[first]!).toBeGreaterThan(below[first]!);
    }
  });

  it("never counts more stations at 3 km than at 10 km", () => {
    // A station inside the near ring is inside the wide one. The two are
    // separate columns now, so the report shows the pair rather than
    // implying it.
    for (const c of payload.cpo) {
      if (c.own_within_3km == null || c.own_within_10km == null) continue;
      expect(c.own_within_3km).toBeLessThanOrEqual(c.own_within_10km);
    }
  });
});
