import type { ReportPayload } from "./payload";
import { Chip, Footnote, Note, SRC, Section, TD, TH, Table } from "./parts";

/**
 * 10 — every default that shaped the answer, in two blocks, because there
 * are two kinds of assumption and they were never the same thing.
 *
 * THE INPUTS come first: what each figure was, where it came from, and
 * whether anyone has confirmed it. Unverified rows carry the caution chip,
 * which makes them the loudest thing on the page after the verdict — that is
 * the point: each one is an honesty mechanism, a re-engagement hook and a
 * qualification signal at once (OVERVIEW.md §7).
 *
 * Value and source share a cell (Track B · R10, following the sample's
 * "value and basis"). They were two columns, and the basis is the half that
 * makes a row worth reading — "₹22.00/kWh" says nothing, "₹22.00/kWh
 * assumed, a decision variable rather than an observation" says everything.
 * Splitting them gave the sentence a third of the width and the two words
 * "archetype default" a column of their own.
 *
 * WHAT THE MODEL ASSUMED comes second, and is the engine's own ledger
 * printed verbatim. `engine.py` has written every default that shapes the
 * answer into `RoiResult.assumptions` since it was built, and its docstring
 * has always claimed "the report's assumption ledger consumes it verbatim".
 * It did not. Two ledgers existed — one generated from the inputs actually
 * used and invisible, one hand-written here and printed — and only the
 * invisible one could go stale without anyone noticing. Now the generated
 * one is on the page, which is also why its wording is version-stamped from
 * `economics_version` 0.5.0 onward.
 *
 * A payload stored before R10 has no engine ledger, and the second block
 * disappears rather than printing an empty heading.
 */
export function Ledger({ payload }: { payload: ReportPayload }) {
  const assumed = payload.model_assumptions ?? [];

  return (
    <Section
      num="10"
      title="Assumptions ledger"
      heading="Every assumption, with its basis."
      id="ledger"
    >
      <Note className="mb-4">
        Every input the arithmetic used. A verified row was read from a record; an unverified row is
        an archetype default or a pending fetch, shown here rather than buried.
      </Note>
      <Table minWidth="36rem">
        <thead>
          <tr>
            <th className={TH}>Assumption or input</th>
            <th className={TH}>Value and basis</th>
            <th className={TH}>Status</th>
          </tr>
        </thead>
        <tbody>
          {payload.ledger.map((row) => (
            <tr key={row.item}>
              <td className={`${TD} w-[11rem]`}>{row.item}</td>
              <td className={`${TD} text-[16px]`}>
                {row.value}
                <span className={`mt-1 block ${SRC}`}>{row.source}</span>
              </td>
              <td className={`${TD} w-[7.5rem]`}>
                {row.unverified ? (
                  <Chip>unverified</Chip>
                ) : (
                  <span className="text-[15px] text-cw-paper-muted">Verified</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <Footnote>
        Resolving an unverified row sharpens the report: your own figures for the grid connection,
        sanctioned load, transformer, land and budget replace the archetype defaults.
      </Footnote>

      {assumed.length > 0 && (
        <>
          <h3 className="mt-8 mb-3.5 font-cw-mono text-[13px] font-normal tracking-[0.14em] text-cw-paper-slate uppercase">
            What the model assumed
          </h3>
          <Note className="mb-3">
            The table above is where each input came from. These are the choices the arithmetic
            itself made, written by the engine as it ran — so they describe the run that produced
            this document and no other, at the version stamped in section 11.
          </Note>
          <ul className="m-0 grid list-none gap-0 p-0 border-t border-cw-rule">
            {assumed.map((line) => (
              <li
                key={line}
                className="border-b border-cw-rule py-2 pl-5 text-[15px] leading-[1.55] text-cw-paper-slate before:-ml-5 before:inline-block before:w-5 before:text-cw-paper-muted before:content-['—']"
              >
                {line}
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}
