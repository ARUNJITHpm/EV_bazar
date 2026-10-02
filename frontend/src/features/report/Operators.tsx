import { formatRupeesCompact, formatRupeesCompactSigned } from "../../lib/money";
import { formatPercentagePoints } from "../../lib/units";
import type { CpoRow, ReportPayload } from "./payload";
import { Callout, Chip, NUM, Note, Section, TD, TH, Table } from "./parts";

/**
 * 06 — the engine re-run once per operator (OVERVIEW.md §8), in two tables.
 *
 * TWO, because the two halves are never blended into one score (PLAN 6,
 * AGENTS.md constraint 1) and a single table invites exactly that: the
 * sample document puts money and service in one grid and then has to write
 * "There is no combined score" underneath to undo the impression the grid
 * just made. Splitting them says it structurally, and it is also what keeps
 * the section printable — nine attributes across one table means either
 * fourteen columns or operators as columns, and a table that grows a column
 * per operator is cut off on paper the day a fifth one appears. As rows,
 * every operator costs a row and no width.
 *
 * WHAT EACH TABLE IS FOR
 *
 * The money table is the same engine run once per operator at the SAME
 * volume, so it isolates what the terms cost and claims nothing about which
 * network brings more drivers. Rows are in rank order; the rank is financial
 * only, and the footnote says so rather than a column asserting it — the
 * order already carries it (Track B · R9).
 *
 * The network table answers what section 07 structurally cannot: 07 counts
 * neighbouring chargers once, operator-blind, which is the right count for
 * "how crowded is this place". Here the SAME neighbour is counted again per
 * operator, because a rival's station is competition while a station run by
 * the operator you sign with is competition AND a split — their app has two
 * places to send the same drivers (domain/cpo/presence.py). Both radii are
 * columns: 3 km is the split you feel, 10 km the one you feel later, and 3 km
 * is also the ring `domain/demand/synthetic.py` actually deducts volume for,
 * so the report never carries two meanings of "near".
 *
 * A dash is not a zero. It marks a row whose footprint we cannot state: an
 * operator name not matched to our charger inventory, or self-operation,
 * which is not a network at all. Those rows — and only those — keep their
 * sentence under the table, because a dash is the one cell that cannot
 * explain itself. The rest had their sentence deleted when the counts became
 * columns: R6's rule is that a document says a thing once.
 *
 * Repair target and tie-in period wait on `cpo_terms` (PLAN 2.3). Until that
 * table exists every operator carries null and both columns disappear, which
 * is the rule `uptime` has lived under since this section was written: a
 * column of one repeated placeholder is furniture.
 *
 * A payload stored before any of this carries none of it, and by Rule 9 it is
 * served verbatim rather than recomputed against today's data. Each piece
 * disappears on its own instead of printing empty cells: an old report is
 * allowed to be an old report, and must not look like a broken new one.
 */
export function Operators({ payload }: { payload: ReportPayload }) {
  const rows = payload.cpo;
  const cash = rows.some((c) => c.cash_p50_paise_year != null);
  const repair = rows.some((c) => c.repair_hours != null);
  const tieIn = rows.some((c) => c.tie_in_years != null);
  const footprint = rows.some((c) => c.stations_district != null || c.own_within_3km != null);
  const unstated = rows.filter((c) => c.own_within_3km == null && c.presence_note);
  // Roaming is always known, so on a payload carrying nothing else the
  // second table would be one yes/no column under a heading promising four.
  // One sentence says the same thing and does not pretend to be a comparison.
  const compares = footprint || repair || tieIn;

  return (
    <Section
      num="06"
      title="Operator comparison"
      heading="The operator changes your deal."
      id="operators"
    >
      <Note className="mb-4">
        A charging station is built and run by an operator; the owner’s return depends on the terms,
        and on how many drivers that operator’s network can send here. The same engine is run once
        per operator below, ranked by the central-case return. Chargeworthy is not affiliated with a
        CPO and owns no charging network. Demonstration arrangements are illustrative.
      </Note>

      {rows.length === 0 ? (
        <Note>No operator terms are on file for this site yet.</Note>
      ) : (
        <>
          <Table minWidth="42rem">
            <thead>
              <tr>
                <th className={TH}>Operator</th>
                <th className={`${TH} ${NUM}`}>Revenue share</th>
                <th className={`${TH} ${NUM}`}>Platform fee</th>
                {cash && <th className={`${TH} ${NUM}`}>Cash left a year, central</th>}
                <th className={`${TH} ${NUM}`}>Return, central</th>
                <th className={`${TH} ${NUM}`}>Margin at downside</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.operator}>
                  <td className={`${TD} whitespace-nowrap`}>
                    {c.operator}
                    {/* Its own line, not a trailing tag: in a six-column
                        table the tag wrapped under a half-width name and
                        read as a second operator. */}
                    {payload.demo && c.ours && (
                      <span className="mt-0.5 block font-cw-mono text-[12px] text-cw-paper-muted">
                        illustrative arrangement
                      </span>
                    )}
                  </td>
                  <td className={`${TD} ${NUM}`}>{c.revenue_share_pct}%</td>
                  <td className={`${TD} ${NUM}`}>
                    {c.platform_fee_paise_year === 0
                      ? "₹0"
                      : `${formatRupeesCompact(c.platform_fee_paise_year)}/yr`}
                  </td>
                  {cash && (
                    <td className={`${TD} ${NUM}`}>
                      {c.cash_p50_paise_year == null
                        ? "—"
                        : formatRupeesCompactSigned(c.cash_p50_paise_year)}
                    </td>
                  )}
                  <td className={`${TD} ${NUM}`}>
                    {c.irr_p50_pct === null ? "no return" : `${c.irr_p50_pct}%`}
                  </td>
                  <td className={`${TD} ${NUM}`}>
                    {formatPercentagePoints(c.margin_of_safety_pp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <Note className="mt-2.5">
            {returns(rows)} Rows are in rank order and the rank is financial only — there is no
            combined score. Every row is priced at the same central-case volume, so the table
            isolates what the terms cost and forecasts nothing about which network brings more
            drivers. Margin at downside is how far the low-demand case sits above (or below) that
            operator’s own breakeven, in percentage points. {unpaidWork(rows)}
          </Note>

          {!compares ? (
            // Roaming is always known, but one yes/no column is not a
            // comparison. Said in a sentence, it is the same fact without a
            // table implying there is more of it.
            <Note className="mt-2.5">{roaming(rows)}</Note>
          ) : (
            <>
              <h3 className="mt-8 mb-3.5 font-cw-mono text-[13px] font-normal tracking-[0.14em] text-cw-paper-slate uppercase">
                What each network brings, and what it promises
              </h3>
              <Table minWidth="40rem">
                <thead>
                  <tr>
                    <th className={TH}>Operator</th>
                    {footprint && (
                      <>
                        <th className={`${TH} ${NUM}`}>District / state</th>
                        <th className={`${TH} ${NUM}`}>Own within 3 km</th>
                        <th className={`${TH} ${NUM}`}>Own within 10 km</th>
                      </>
                    )}
                    <th className={TH}>Roaming</th>
                    {repair && <th className={`${TH} ${NUM}`}>Repair target</th>}
                    {tieIn && <th className={`${TH} ${NUM}`}>Tie-in</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.operator}>
                      <td className={`${TD} whitespace-nowrap`}>{c.operator}</td>
                      {footprint && (
                        <>
                          <td className={`${TD} ${NUM}`}>
                            {c.stations_district == null || c.stations_state == null
                              ? "—"
                              : `${c.stations_district} / ${c.stations_state}`}
                          </td>
                          <td className={`${TD} ${NUM}`}>{countOrDash(c.own_within_3km)}</td>
                          <td className={`${TD} ${NUM}`}>{countOrDash(c.own_within_10km)}</td>
                        </>
                      )}
                      <td className={`${TD} text-[15px]`}>{c.ocpi_roaming ? "yes" : "no"}</td>
                      {repair && (
                        <td className={`${TD} ${NUM}`}>
                          {c.repair_hours == null ? "—" : `${c.repair_hours} h`}
                        </td>
                      )}
                      {tieIn && (
                        <td className={`${TD} ${NUM}`}>
                          {c.tie_in_years == null ? "—" : `${c.tie_in_years} yr`}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Note className="mt-2.5">
                {footprint && (
                  <>
                    A station of their own near you is competition twice over: it competes for the
                    same drivers, and the app you have signed with can route those drivers to it.
                    Within 3 km is the split you feel — it is the ring the demand forecast already
                    deducts volume for — and 10 km is the same effect, wider and weaker. Counts come
                    from our own charger inventory, so a dash means we cannot state a figure, never
                    that there are none, and no count proves uptime.{" "}
                  </>
                )}
                Roaming is whether a driver arriving on another operator’s app can charge here at
                all.
                {repair && " A repair target is a promise, not a measurement."}
              </Note>
            </>
          )}

          {unstated.length > 0 && (
            <div className="mt-6 flex flex-col gap-3">
              {unstated.map((c) => (
                <div key={c.operator} className="flex flex-col gap-1 sm:flex-row sm:gap-4">
                  <span className="font-cw-mono text-[13px] tracking-[0.06em] text-cw-paper-slate sm:w-[10rem] sm:shrink-0">
                    {c.operator}
                  </span>
                  <Note className="flex-1">{c.presence_note}</Note>
                </div>
              ))}
            </div>
          )}

          {trade(rows, cash, repair) && (
            <div className="mt-6">
              <Callout label="The trade this section does not make for you">
                <p>{trade(rows, cash, repair)}</p>
              </Callout>
            </div>
          )}
        </>
      )}

      <Note className="mt-5">
        How reliably each operator’s chargers work is not measured in this version.{" "}
        <Chip>terms are placeholders</Chip>
      </Note>
    </Section>
  );
}

/** A dash where a count is unknown. Never a zero — "we cannot say" and "none"
 *  are different findings and must not print the same. */
function countOrDash(n: number | null | undefined) {
  return n == null ? "—" : String(n);
}

/**
 * How many of these arrangements return the capital at all, counted rather
 * than assumed.
 *
 * On a strong site every row returns it and the sentence is unremarkable. On
 * a marginal one the answer is often "one of four", and that is the single
 * most useful line in the section — but only if it is read off the table
 * instead of asserted above it (Track B · R6, R7, R8).
 */
function returns(rows: CpoRow[]): string {
  const yes = rows.filter((c) => c.irr_p50_pct !== null).length;
  if (yes === 0) {
    return "No arrangement here returns the build cost in the central case.";
  }
  if (yes === rows.length) {
    return rows.length === 1
      ? "This arrangement returns the build cost in the central case."
      : "All of these arrangements return the build cost in the central case.";
  }
  // "1 of the 4 arrangements RETURNS" - the verb follows the count, not the
  // set. A counted sentence that reads as a typo undoes the reason for
  // counting it.
  return `${yes} of the ${rows.length} arrangements ${yes === 1 ? "returns" : "return"} the build cost in the central case; the rest do not, at this volume.`;
}

/**
 * Roaming, said in a sentence — for the payload that knows nothing else
 * about these networks.
 *
 * Counted rather than asserted, like every other sentence in this section:
 * all, none, or a split naming the ones that do not. A list is only worth
 * printing while it is shorter than the table it replaces, so past three
 * names it says how many instead.
 */
function roaming(rows: CpoRow[]): string {
  const open = rows.filter((c) => c.ocpi_roaming);
  const shut = rows.filter((c) => !c.ocpi_roaming);
  const what =
    "Roaming is whether a driver arriving on another operator’s app can charge here at all";
  if (shut.length === 0) return `${what}. Every arrangement here accepts them.`;
  if (open.length === 0) return `${what}. None of these accepts them.`;
  const named =
    shut.length <= 3
      ? shut.map((c) => c.operator).join(", ")
      : `${shut.length} of the ${rows.length}`;
  return `${what} — and ${named} ${shut.length === 1 ? "does" : "do"} not.`;
}

/**
 * The one thing the table cannot show about the arrangement with no
 * counterparty: the engine prices no operator cut for it, and prices none of
 * the running either.
 *
 * Said whenever such a row exists rather than only when it ranks first — it
 * is true wherever the row lands, and where the row does lead it is the
 * reason. Deliberately not a claim about the ranking: on a site where
 * nothing returns the capital, "leads" is a word the table does not support.
 */
function unpaidWork(rows: CpoRow[]): string {
  const free = rows.find((c) => c.revenue_share_pct === 0 && c.platform_fee_paise_year === 0);
  if (!free) return "";
  return `The model prices no operator cut for ${free.operator}, and prices none of the work either: running a station is a job somebody has to be paid for, and no figure above carries it.`;
}

/**
 * The one sentence the table is not allowed to resolve.
 *
 * When the arrangement leaving the most cash is not the one promising the
 * fastest repair, that is a real trade and it is the owner's to make — so it
 * is named, with both figures, and no recommendation. When one arrangement
 * leads on both there is nothing to trade and the callout does not appear.
 */
function trade(rows: CpoRow[], cash: boolean, repair: boolean): string | null {
  if (!cash || !repair || rows.length < 2) return null;
  const paid = rows.filter((c) => c.cash_p50_paise_year != null);
  const served = rows.filter((c) => c.repair_hours != null);
  const best = paid.reduce<CpoRow | null>(
    (a, b) => (a === null || (b.cash_p50_paise_year ?? 0) > (a.cash_p50_paise_year ?? 0) ? b : a),
    null,
  );
  const quickest = served.reduce<CpoRow | null>(
    (a, b) => (a === null || (b.repair_hours ?? Infinity) < (a.repair_hours ?? Infinity) ? b : a),
    null,
  );
  if (!best || !quickest) return null;

  // "Leaves the most cash, −₹2.82 L a year" is a sentence about a site where
  // every arrangement LOSES money, and it reads as good news. The best of a
  // set of losses loses the LEAST, and the words have to change with the
  // sign or the callout congratulates the reader on a loss.
  const top = best.cash_p50_paise_year ?? 0;
  const lead =
    top >= 0
      ? `leaves the most cash, ${formatRupeesCompact(top)} a year`
      : `loses the least, ${formatRupeesCompact(-top)} a year`;

  if (best.operator === quickest.operator) {
    return `${best.operator} ${lead}, and promises the fastest repair at ${quickest.repair_hours} hours. Nothing here has to be traded off — which is worth confirming in writing before it stops being true.`;
  }

  const behind = quickest.cash_p50_paise_year ?? 0;
  const gap = formatRupeesCompact(Math.abs(top - behind));
  const cost = behind < 0 ? `loses ${gap} a year more` : `leaves ${gap} a year less`;
  return `${best.operator} ${lead}. ${quickest.operator} promises to attend a fault in ${quickest.repair_hours} hours and ${cost}. Days lost to a charger nobody came to fix are not in either figure, so what that promise is worth is yours to judge.`;
}
