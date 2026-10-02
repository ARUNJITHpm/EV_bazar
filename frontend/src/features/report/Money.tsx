import {
  formatRupees,
  formatRupeesCompact,
  formatRupeesCompactSigned,
  formatRupeesSigned,
} from "../../lib/money";
import {
  CASE_LABEL,
  CASES,
  HORIZON_YEARS,
  ramps,
  scenarioFor,
  type CaseId,
  type PlainMoney,
  type ReportPayload,
  type Scenario,
} from "./payload";
import {
  Callout,
  Figure,
  Footnote,
  Note,
  Section,
  StatCard,
  StatCards,
  TD,
  TH,
  Table,
} from "./parts";

/**
 * 02 — the section the reader came for.
 *
 * TWO VOCABULARIES, ON PURPOSE (Track B · R6). The table is money: what
 * customers pay, what is left, how long until the setup cost is back. The
 * box under it is finance: the effective annual return set beside a fixed
 * deposit. R5 decided to keep the second rather than replace it — a
 * landowner reads the first and their accountant reads the second, and this
 * is the one page both of them open.
 *
 * The plain figures are the STEADY year, which is the same year
 * `Scenario.kwh_year` reports. That is a real choice: year 1 is smaller
 * because demand ramps. It is not hidden — the footnote says so and section
 * 05 prints every year of it — but a "cash each month" figure that quietly
 * meant year 1 would be a different kind of wrong.
 *
 * Every rupee figure is the engine's (AGENTS.md rule 1); this component
 * formats and compares, it never computes money. The one number that is not
 * the engine's is the deposit rate, and it says so beside itself.
 */

/** Indicative one-year term-deposit rate at a large scheduled commercial
 *  bank. A yardstick, not a quote — the note beside it tells the reader to
 *  check their own bank's current rate.
 *
 *  It stays a PERCENTAGE and is never multiplied out into rupees here. The
 *  sample document prints "₹24.0 lakh would earn ₹1.44 lakh a year"; doing
 *  that would mean this component computing money, and would stamp an
 *  invented bank rate into a figure that reads like the engine's. */
export const FIXED_DEPOSIT_PCT = 6.5;

function years(n: number | null): string {
  if (n === null) return `Beyond ${HORIZON_YEARS} years`;
  const shown = Number.isInteger(n) ? String(n) : n.toFixed(1);
  return `${shown} years`;
}

function pct(n: number | null): string {
  return n === null ? "No return" : `${n.toFixed(1)}%`;
}

function tenYear(s: Scenario | undefined): string {
  if (!s) return "—";
  return s.npv_paise < 0
    ? `${formatRupeesCompact(-s.npv_paise)} short`
    : `${formatRupeesCompact(s.npv_paise)} ahead`;
}

type CaseRow = [CaseId, Scenario, PlainMoney];

/**
 * The three cases in printing order, only when every one of them carries
 * plain money — a table with a case missing is worse than no table.
 *
 * The central row comes back named rather than indexed, because the two
 * stat cards above the table are the central case and `rows[1]` would be a
 * silent assumption about ordering.
 */
function plainCases(payload: ReportPayload): { rows: CaseRow[]; central: CaseRow } | null {
  const rows: CaseRow[] = [];
  let central: CaseRow | null = null;
  for (const id of CASES) {
    const s = scenarioFor(payload, id);
    if (!s?.plain) return null;
    const row: CaseRow = [id, s, s.plain];
    rows.push(row);
    if (id === "P50") central = row;
  }
  return central === null ? null : { rows, central };
}

export function Money({ payload }: { payload: ReportPayload }) {
  const f = payload.financials;
  const central = scenarioFor(payload, "P50");
  const down = scenarioFor(payload, "P10");
  const cases = plainCases(payload);

  const centralReturn = central?.irr_pct ?? null;
  const beats = centralReturn !== null && centralReturn > FIXED_DEPOSIT_PCT;

  return (
    <Section
      num="02"
      title="What this means for your money"
      heading="The money, in simple terms."
      standfirst="Owner-funded equipment, operator-run service. You pay the setup cost, the power bill, the rent and the running expenses; the operator runs the service and takes a share of every unit sold."
      id="money"
    >
      {cases ? (
        <StatCards>
          <StatCard
            label="Setup budget"
            value={formatRupees(f.capex_paise)}
            detail="net of subsidy · equipment, civil work and the power connection"
          />
          <StatCard
            label="Cash left each month"
            value={formatRupeesSigned(cases.central[2].cash_paise_month)}
            detail="central case, in a steady year"
          />
          <StatCard
            label="Time to recover the setup cost"
            value={years(cases.central[1].payback_years)}
            detail="central case"
          />
        </StatCards>
      ) : (
        <div className="flex flex-wrap gap-x-10 gap-y-6">
          <Figure
            label="Capital required"
            value={formatRupees(f.capex_paise)}
            detail="net of subsidy · build cost, connection and civil work"
          />
          <Figure
            label="Payback period, central case"
            value={years(central?.payback_years ?? null)}
            small
          />
          <Figure label="Downside case, over ten years" value={tenYear(down)} small />
        </div>
      )}

      {cases && (
        <div className="mt-6">
          <Table minWidth="34rem" zebra={false}>
            <thead>
              <tr>
                <th className={TH}>Your money</th>
                {cases.rows.map(([id]) => (
                  <th key={id} className={`${TH} text-right`}>
                    {CASE_LABEL[id]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className={TD}>Customer spending each month</td>
                {cases.rows.map(([id, , m]) => (
                  <td key={id} className={`${TD} text-right font-cw-mono tabular-nums`}>
                    {formatRupeesSigned(m.revenue_paise_month)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className={TD}>Cash left / lost each month</td>
                {cases.rows.map(([id, , m]) => (
                  <td key={id} className={`${TD} text-right font-cw-mono tabular-nums`}>
                    {formatRupeesSigned(m.cash_paise_month)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className={TD}>Cash left / lost each year</td>
                {cases.rows.map(([id, , m]) => (
                  <td key={id} className={`${TD} text-right font-cw-mono tabular-nums`}>
                    {formatRupeesCompactSigned(m.cash_paise_year)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className={TD}>Time to recover the setup cost</td>
                {cases.rows.map(([id, s]) => (
                  <td key={id} className={`${TD} text-right font-cw-mono tabular-nums`}>
                    {years(s.payback_years)}
                  </td>
                ))}
              </tr>
            </tbody>
          </Table>
          <Footnote>
            Cash left is what customers pay minus electricity, the operator’s share and the fixed
            running costs. It is before loan payments, tax and recovering the setup cost — it is not
            take-home profit.{" "}
            {ramps(cases.central[2])
              ? "These are steady-year figures: demand ramps, so the first years are smaller."
              : "Every year in this report carries the same figure — no ramp-up is modelled."}{" "}
            Section 05 prints all {HORIZON_YEARS}.
          </Footnote>
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-x-10 gap-y-6 border border-cw-ink px-6 py-5">
        <Figure label="This site, return per year (central case)" value={pct(centralReturn)} />
        <Figure
          label="Illustrative fixed-deposit comparison"
          value={`${FIXED_DEPOSIT_PCT.toFixed(1)}%`}
        />
      </div>
      <Note className="mt-2">
        The site’s return is the annual rate the ten-year cash flows earn on the capital, after
        energy, demand charges, rent and the operator’s share. The deposit rate is an illustrative
        assumption, not a current bank offer — check your bank’s current rate. Charging carries
        operating risk and equipment wear; a deposit does not need you to run a site.
      </Note>

      {central && down && (
        <p className="mt-5 mb-0 max-w-[70ch] text-[18px] leading-[1.6]">
          In the central case the chargers sell about{" "}
          <span className="font-cw-mono tabular-nums">
            {Math.round(central.kwh_year).toLocaleString("en-IN")}
          </span>{" "}
          units a year by their tenth year.{" "}
          {centralReturn === null ? (
            <>
              On <span className="font-cw-mono tabular-nums">{formatRupees(f.capex_paise)}</span>{" "}
              that never earns a return: after ten years the site is{" "}
              <span className="font-cw-mono tabular-nums">{tenYear(central)}</span>, while a fixed
              deposit would have paid about{" "}
              <span className="font-cw-mono tabular-nums">{FIXED_DEPOSIT_PCT.toFixed(1)}%</span> a
              year.
            </>
          ) : (
            <>
              On <span className="font-cw-mono tabular-nums">{formatRupees(f.capex_paise)}</span>{" "}
              that is a return of{" "}
              <span className="font-cw-mono tabular-nums">{pct(centralReturn)}</span> a year against
              about{" "}
              <span className="font-cw-mono tabular-nums">{FIXED_DEPOSIT_PCT.toFixed(1)}%</span>{" "}
              from a fixed deposit — {beats ? "the site beats the bank" : "the bank beats the site"}
              .
            </>
          )}{" "}
          In the downside case{" "}
          {down.irr_pct === null
            ? "there is no return at all"
            : `the return falls to ${pct(down.irr_pct)}`}
          , and after ten years the site is{" "}
          <span className="font-cw-mono tabular-nums">{tenYear(down)}</span>.
        </p>
      )}

      <div className="mt-6">
        <Callout label="Read this before signing" tone="caution">
          <p>
            The setup budget covers equipment, civil work and the power connection. It does not
            include the land, the DISCOM security deposit, GST, financing costs, a contingency for
            delays, or a working-capital buffer for the ramp-up months. A live proposal has to price
            every one of those.
          </p>
        </Callout>
      </div>
    </Section>
  );
}
