import type { ReportPayload } from "./payload";

/**
 * Section 7 — version stamps and data vintages (AGENTS.md rule 4). This is
 * what makes the report regenerable and a wrong number traceable to a bad
 * PDF or a bad geocode within minutes. Unpinned or stopgap entries carry the
 * warn accent so a demo can never pass as a customer deliverable.
 */
export function Provenance({ payload }: { payload: ReportPayload }) {
  return (
    <section data-report-section="provenance" data-provenance className="py-8">
      <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        7 · Provenance
      </h2>
      <dl className="mt-4 grid border-t border-rule sm:grid-cols-2">
        {payload.provenance.map((p) => (
          <div
            key={p.label}
            className="flex justify-between gap-4 border-b border-rule py-1.5 sm:odd:pr-6"
          >
            <dt className="font-data text-[12px] text-ink-muted">{p.label}</dt>
            <dd
              className={
                p.unverified
                  ? "bg-warn-ground px-1 text-right font-data text-[12px] text-warn"
                  : "text-right font-data text-[12px]"
              }
            >
              {p.value}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 font-data text-[11px] text-ink-faint">
        report {payload.report_id} · payload is the data of record; the archived PDF answers "this
        is not what your report said"
      </p>
    </section>
  );
}
