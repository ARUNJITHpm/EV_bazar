import {
  formatLakhPlain,
  formatRupees,
  formatRupeesCompact,
  formatRupeesPrecise,
} from "../../lib/money";
import { formatKva, formatUtilisation, kva } from "../../lib/units";
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
import { NUM, Note, SRC, Section, TD, TH, Table } from "./parts";

/**
 * 05 — three cases, one engine. Every number here is rendered from the
 * payload the ROI engine produced (AGENTS.md rule 1); this component does no
 * arithmetic beyond formatting.
 *
 * THE SECTION SHOWS ITS WORKING (Track B · R6), in the order an owner would
 * ask for it: what the build costs, what one unit leaves behind, what
 * arrives every year whether or not anyone charges — then the three cases,
 * then ten years of running total. The first three are the engine's own
 * breakdowns, and each SUMS EXACTLY to a headline printed beside it. That is
 * enforced in `roi/engine.py` rather than trusted here, because a printed
 * sum that does not add up costs more than it explains.
 *
 * The ten-year table is the clearest thing in the sample document and we had
 * nothing like it. Ours differs in one way worth keeping: the sample repeats
 * an identical annual figure for ten years, while this is the engine's real
 * ramp, so the early years are smaller and the row spacing is the ramp.
 *
 * The three India-specific levers the engine models (OVERVIEW.md §3) each
 * keep one plain paragraph at the end: the fleet anchor, the sanctioned-load
 * recommendation, and price sensitivity.
 */

function caseName(s: Scenario): string {
  const id = CASES.find((c) => s.label.startsWith(c));
  return id ? `${CASE_LABEL[id]} (${id})` : s.label;
}

/** A loss reads as "−₹44.27 L", never "₹-44.27 L". */
function signed(paise: number): string {
  return paise < 0 ? `−${formatRupeesCompact(-paise)}` : formatRupeesCompact(paise);
}

/**
 * Whole rupees, for the budget and the bills.
 *
 * Those two tables are money the reader checks against a quotation or a
 * lease, not against a scale — and `formatRupeesCompact` changes unit at one
 * lakh, which put "₹36.0k" in a column of "L" figures. Two units in one
 * column is the reader's problem, not the formatter's. The ₹-lakh grids
 * below declare their unit in the head instead and stay bare.
 */
function signedExact(paise: number): string {
  return paise < 0 ? `−${formatRupees(-paise)}` : formatRupees(paise);
}

function years(n: number | null): string {
  if (n === null) return "beyond horizon";
  return `${Number.isInteger(n) ? n : n.toFixed(1)} yr`;
}

/**
 * The three cases in printing order, only when every one carries plain money
 * — a ten-year table missing a column is worse than none.
 *
 * `span` is how many rows the cumulative table has, and it is returned
 * rather than read off the first case: if the three ever disagreed, the
 * payload was stitched from two runs and the table would silently misalign
 * its years against its labels.
 */
function plainCases(payload: ReportPayload): { rows: [CaseId, PlainMoney][]; span: number } | null {
  const rows: [CaseId, PlainMoney][] = [];
  for (const id of CASES) {
    const plain = scenarioFor(payload, id)?.plain;
    if (!plain) return null;
    rows.push([id, plain]);
  }
  const spans = new Set(rows.map(([, m]) => m.cumulative_paise.length));
  const span = rows[0]?.[1].cumulative_paise.length ?? 0;
  return spans.size === 1 && span > 0 ? { rows, span } : null;
}

/** A money cell in one of the ₹-lakh tables. */
function Lakh({ paise }: { paise: number }) {
  return <td className={`${TD} ${NUM}`}>{formatLakhPlain(paise)}</td>;
}

export function Financials({ payload }: { payload: ReportPayload }) {
  const f = payload.financials;
  const sl = f.sanctioned_load;
  const cases = plainCases(payload);
  const budget = f.capex_lines;
  const unit = f.unit_economics;
  const bills = f.fixed_costs;

  return (
    <Section
      num="05"
      title="Financial working"
      heading="Every rupee has a calculation."
      standfirst="All amounts are before tax and financing. One unit means one kWh sold to a customer."
      id="financials"
    >
      {budget && budget.length > 0 ? (
        <Table minWidth="30rem" zebra={false}>
          <thead>
            <tr>
              <th className={TH}>One-time budget</th>
              <th className={`${TH} text-right`}>Amount</th>
            </tr>
          </thead>
          <tbody>
            {budget.map((line) => (
              <tr key={line.label}>
                <td className={TD}>{line.label}</td>
                <td className={`${TD} ${NUM}`}>{signedExact(line.paise)}</td>
              </tr>
            ))}
            <tr>
              <td className={`${TD} border-t-2 border-cw-ink font-medium`}>Total setup cost</td>
              <td className={`${TD} ${NUM} border-t-2 border-cw-ink font-medium`}>
                {formatRupees(f.capex_paise)}
              </td>
            </tr>
          </tbody>
        </Table>
      ) : (
        <Note className="mb-4">
          Build cost{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">
            {formatRupees(f.capex_paise)}
          </span>{" "}
          · price to the driver{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">
            {formatRupeesPrecise(f.selling_price_paise_kwh)}/kWh
          </span>{" "}
          · energy bought at{" "}
          <span className="font-cw-mono text-cw-ink tabular-nums">
            {formatRupeesPrecise(f.energy_tariff_paise_kwh)}/kWh
          </span>
          .
        </Note>
      )}

      {unit && (
        <p className="mt-5 mb-0 max-w-[74ch] text-[17px] leading-[1.6]">
          <span className="font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
            Per unit
          </span>
          <br />
          <span className="font-cw-mono tabular-nums">
            {formatRupeesPrecise(unit.selling_paise_kwh)}
          </span>{" "}
          from the driver
          {unit.deductions.map((d) => (
            <span key={d.label}>
              {" − "}
              <span className="font-cw-mono tabular-nums">{formatRupeesPrecise(d.paise)}</span>{" "}
              {d.label.toLowerCase()}
            </span>
          ))}{" "}
          ={" "}
          <span className="font-cw-mono font-medium tabular-nums">
            {formatRupeesPrecise(unit.margin_paise_kwh)}
          </span>{" "}
          left toward the fixed bills.
        </p>
      )}

      {bills && bills.lines.length > 0 && (
        <div className="mt-6">
          <Table minWidth="30rem" zebra={false}>
            <thead>
              <tr>
                <th className={TH}>Arrives every year, sold or not</th>
                <th className={`${TH} text-right`}>Per year</th>
              </tr>
            </thead>
            <tbody>
              {bills.lines.map((line) => (
                <tr key={line.label}>
                  <td className={TD}>{line.label}</td>
                  <td className={`${TD} ${NUM}`}>{signedExact(line.paise)}</td>
                </tr>
              ))}
              <tr>
                <td className={`${TD} border-t-2 border-cw-ink font-medium`}>
                  Total fixed running cost
                  <span className="ml-2 text-[15px] font-normal text-cw-paper-muted">
                    {formatRupees(bills.total_paise_month)} a month
                  </span>
                </td>
                <td className={`${TD} ${NUM} border-t-2 border-cw-ink font-medium`}>
                  {signedExact(bills.total_paise_year)}
                </td>
              </tr>
            </tbody>
          </Table>
          {unit && (
            <Note className="mt-2.5">
              These bills divided by the{" "}
              <span className="font-cw-mono text-cw-ink tabular-nums">
                {formatRupeesPrecise(unit.margin_paise_kwh)}
              </span>{" "}
              left on each unit are the running-bill breakeven in section 03 — the volume at which
              the site stops losing money month to month.
            </Note>
          )}
        </div>
      )}

      {cases && (
        <>
          <div className="mt-7">
            <Table minWidth="34rem" zebra={false}>
              <thead>
                <tr>
                  <th className={TH}>A steady year (₹ lakh)</th>
                  {cases.rows.map(([id]) => (
                    <th key={id} className={`${TH} text-right`}>
                      {CASE_LABEL[id]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className={TD}>Customer receipts</td>
                  {cases.rows.map(([id, m]) => (
                    <Lakh key={id} paise={m.revenue_paise_year} />
                  ))}
                </tr>
                <tr>
                  <td className={TD}>Electricity and other per-unit costs</td>
                  {cases.rows.map(([id, m]) => (
                    <Lakh key={id} paise={m.running_cost_paise_year} />
                  ))}
                </tr>
                <tr>
                  <td className={TD}>Fixed running costs</td>
                  {cases.rows.map(([id, m]) => (
                    <Lakh key={id} paise={m.fixed_cost_paise_year} />
                  ))}
                </tr>
                <tr>
                  <td className={`${TD} font-medium`}>Cash after running costs</td>
                  {cases.rows.map(([id, m]) => (
                    <Lakh key={id} paise={m.cash_paise_year} />
                  ))}
                </tr>
              </tbody>
            </Table>
          </div>

          <div className="mt-7">
            <Table minWidth="34rem">
              <thead>
                <tr>
                  <th className={TH}>Cumulative cash after setup (₹ lakh)</th>
                  {cases.rows.map(([id]) => (
                    <th key={id} className={`${TH} text-right`}>
                      {CASE_LABEL[id]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: cases.span }, (_, year) => (
                  <tr key={year}>
                    <td className={TD}>{year === 0 ? "Year 0 — the build" : `Year ${year}`}</td>
                    {cases.rows.map(([id, m]) => (
                      <Lakh key={id} paise={m.cumulative_paise[year] ?? 0} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </Table>
            <Note className="mt-2.5">
              A negative total means the setup money is not back yet.{" "}
              {ramps(cases.rows[1]?.[1] ?? cases.rows[0]![1])
                ? "The years are not identical: demand ramps, so each year sells more than the last until it settles."
                : "Every year carries the same cash figure — no ramp-up is modelled here, so the running total moves by one step a year."}{" "}
              No inflation, major replacement, salvage value or discounting is applied here — a
              maintenance reserve is included above, and any replacement beyond it comes out of this
              cash. The discounted view of the same flows is the value column above.
            </Note>
          </div>
        </>
      )}

      <div className="mt-7">
        <Table minWidth="40rem">
          <thead>
            <tr>
              <th className={TH}>Case</th>
              <th className={`${TH} ${NUM}`}>Utilisation</th>
              <th className={`${TH} ${NUM}`}>Units sold, year {HORIZON_YEARS}</th>
              <th className={`${TH} ${NUM}`}>Value, {HORIZON_YEARS} yr</th>
              <th className={`${TH} ${NUM}`}>Return</th>
              <th className={`${TH} ${NUM}`}>Payback</th>
            </tr>
          </thead>
          <tbody>
            {f.scenarios.map((s) => (
              <tr key={s.label}>
                <td className={TD}>{caseName(s)}</td>
                <td className={`${TD} ${NUM}`}>{formatUtilisation(s.utilisation)}</td>
                <td className={`${TD} ${NUM}`}>{Math.round(s.kwh_year).toLocaleString("en-IN")}</td>
                <td className={`${TD} ${NUM}`}>{signed(s.npv_paise)}</td>
                <td className={`${TD} ${NUM}`}>
                  {s.irr_pct === null ? "no return" : `${s.irr_pct.toFixed(1)}%`}
                </td>
                <td className={`${TD} ${NUM}`}>{years(s.payback_years)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
        <Note className="mt-2.5">
          Value is the net present value of {HORIZON_YEARS} years of cash flows; return is the
          annual rate those flows earn on the capital.
        </Note>
      </div>

      <dl className="mt-8 flex max-w-[70ch] flex-col gap-5">
        <div>
          <dt className="font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
            A fleet or campus contract
          </dt>
          <dd className="mt-1.5 ml-0 text-[17px]">
            If a fleet, campus or depot commits to{" "}
            <span className="font-cw-mono tabular-nums">
              {f.anchor_note.kwh_year.toLocaleString("en-IN")}
            </span>{" "}
            units a year on a take-or-pay basis, the central case becomes worth{" "}
            <span className="font-cw-mono tabular-nums">{signed(f.anchor_note.npv_paise)}</span>{" "}
            with a return of{" "}
            <span className="font-cw-mono tabular-nums">{f.anchor_note.irr_pct}%</span>. A contract
            de-risks the return; it does not change breakeven, which asks how busy walk-in trade
            must be.
          </dd>
        </div>
        <div>
          <dt className="font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
            Sanctioned load
          </dt>
          <dd className="mt-1.5 ml-0 text-[17px]">
            Running every charger flat out needs{" "}
            <span className="font-cw-mono tabular-nums">{formatKva(kva(sl.full_kva))}</span> from
            the grid. Managing the peak so chargers share the load runs on{" "}
            <span className="font-cw-mono tabular-nums">{formatKva(kva(sl.recommended_kva))}</span>
            {sl.saving_paise_year > 0 ? (
              <>
                {" "}
                and saves about{" "}
                <span className="font-cw-mono tabular-nums">
                  {formatRupeesCompact(sl.saving_paise_year)}
                </span>{" "}
                a year in demand charges
              </>
            ) : (
              <>
                ; this tariff carries no demand charge, so the smaller connection costs less to
                obtain rather than less to run
              </>
            )}{" "}
            — this is what the figures above assume. A battery buffer could bring the connection
            down to{" "}
            <span className="font-cw-mono tabular-nums">{formatKva(kva(sl.buffered_kva))}</span> if
            the grid connection is the constraint.
          </dd>
        </div>
        <div>
          <dt className="font-cw-mono text-[13px] tracking-[0.12em] text-cw-paper-slate uppercase">
            If the selling price moves
          </dt>
          <dd className="mt-1.5 ml-0">
            <Table>
              <tbody>
                {f.price_sensitivity.map((p) => (
                  <tr key={p.price_paise_kwh}>
                    <td className={`${TD} ${NUM} w-[9rem] text-left`}>
                      {formatRupeesPrecise(p.price_paise_kwh)}/unit
                    </td>
                    <td className={`${TD} ${SRC}`}>
                      breakeven at{" "}
                      <span className="font-cw-mono text-cw-ink tabular-nums">
                        {formatUtilisation(p.breakeven_utilisation)}
                      </span>
                      {p.price_paise_kwh === f.selling_price_paise_kwh && " — the price assumed"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </dd>
        </div>
      </dl>
    </Section>
  );
}
