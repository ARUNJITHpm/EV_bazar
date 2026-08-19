import type { ReportPayload } from "./payload";

/**
 * Section 6 — every default that shaped the answer, verbatim. Unverified rows
 * carry the single warn accent, which makes them the loudest thing on the
 * page after the verdict (STACK.md §7) — that is the point: each ⚠ is an
 * honesty mechanism, a re-engagement hook, and a qualification signal at
 * once (OVERVIEW.md §7).
 */
export function Ledger({ payload }: { payload: ReportPayload }) {
  return (
    <section id="ledger" data-report-section="ledger" className="border-b border-rule py-8">
      <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        6 · Assumption ledger
      </h2>
      <dl className="mt-4 border-t border-rule">
        {payload.ledger.map((row) => (
          <div
            key={row.item}
            className="grid gap-x-4 gap-y-0.5 border-b border-rule py-2 md:grid-cols-[11rem_1fr_auto]"
          >
            <dt className="font-ui text-[13px] text-ink-muted">
              {row.item}
              {row.unverified && <span className="ml-1 text-warn">⚠</span>}
            </dt>
            <dd className="text-[0.9375rem]">{row.value}</dd>
            <dd
              className={
                row.unverified
                  ? "self-start justify-self-start bg-warn-ground px-1 font-data text-[11px] text-warn md:justify-self-end"
                  : "self-start justify-self-start font-data text-[11px] text-ink-faint md:justify-self-end"
              }
            >
              {row.source}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 max-w-[34rem] text-[13px] text-ink-muted">
        Resolving a ⚠ sharpens the report — the five customer inputs (connection, sanctioned load,
        transformer, land, budget) replace archetype defaults with your numbers.
      </p>
    </section>
  );
}
