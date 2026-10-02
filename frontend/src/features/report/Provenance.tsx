import type { ReportPayload } from "./payload";
import { Chip, Footnote, Note, Section } from "./parts";

/**
 * 11 — version stamps and data vintages (AGENTS.md rule 4). This is what
 * makes the report regenerable and a wrong number traceable to a bad PDF or
 * a bad geocode within minutes. Unpinned or stopgap entries carry the chip
 * so a demo can never pass as a customer deliverable. Starts a new page in
 * print, so this and the disclosure close the document on their own sheets —
 * two of them since R10, not one, because both sections grew.
 *
 * THE DOCUMENT RECORD (Track B · R10) is the one line that makes this a
 * record rather than a printout: which report, on what day, over how many
 * checks, at which economics version. Until R10 the document carried no date
 * anywhere — not on the cover, not in the chrome, nowhere — and a document
 * with no date on it cannot defend itself, which is the only thing this
 * section exists to do. The date is read from the payload, never from the
 * clock: the payload is the data of record and is served verbatim, so a date
 * generated at render time would be the date of the READING.
 *
 * WHAT THIS IS NOT BUILT FROM matters as much as the table. Most of section
 * 04 is measured off a map, and a map cannot see a supply, a lease or a
 * power cut. Saying which classes of evidence a live assessment needs — and
 * that this one did not have them — is the difference between a report that
 * admits its limits and one that has to be caught out.
 */
export function Provenance({ payload }: { payload: ReportPayload }) {
  const record = [
    payload.report_id,
    payload.generated_at,
    `${payload.site_facts.length} checks`,
    version(payload, "economics_version") && `economics ${version(payload, "economics_version")}`,
  ].filter(Boolean);

  return (
    <Section num="11" title="Provenance" heading="Where each number came from." id="provenance">
      <dl
        className="m-0 grid gap-x-8 border-t border-cw-rule"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))" }}
        data-provenance
      >
        {payload.provenance.map((p) => (
          <div
            key={p.label}
            className="flex justify-between gap-4 border-b border-cw-rule py-1.5 font-cw-mono text-[12px] leading-[1.9]"
          >
            <dt className="shrink-0 text-cw-paper-muted">{p.label}</dt>
            {/* The renderer stamps its own version into this cell just
                before printing (app/pdf/render.py). It cannot come from the
                payload: the PDF is rendered AFTER the payload is stored, and
                the payload is served verbatim (Rule 9). So the web page
                shows what the payload says and the archived artifact shows
                what actually produced it — which is the honest answer in
                both places. */}
            <dd
              className="m-0 min-w-0 break-words text-right"
              {...(p.label === "renderer_version" ? { "data-renderer-version": "" } : {})}
            >
              {p.unverified ? <Chip wrap>{p.value}</Chip> : p.value}
            </dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-8 mb-2.5 font-cw-mono text-[13px] font-normal tracking-[0.14em] text-cw-paper-slate uppercase">
        Document record
      </h3>
      <p className="m-0 font-cw-mono text-[13px] leading-[1.9]">{record.join(" · ")}</p>
      <Footnote>
        The stored payload is the data of record; the archived PDF answers “this is not what your
        report said”. Figures are frozen at the date above and are not refreshed by reopening this
        page.
      </Footnote>

      <h3 className="mt-8 mb-2.5 font-cw-mono text-[13px] font-normal tracking-[0.14em] text-cw-paper-slate uppercase">
        What this was not built from
      </h3>
      <Note>
        Everything above is a public or licensed record, and every one is dated. None of it is a
        site visit, a measured survey, an electricity bill, a lease, a supply quotation, an outage
        log or signed operator terms. Most of section 04 is measured off a map, and a map cannot see
        a transformer with no spare capacity, a lease that forbids a canopy, or four hours of power
        cuts a day. Those are the documents a decision should rest on; section 08 names the ones
        that would move this verdict.
      </Note>
    </Section>
  );
}

/** A provenance value by label, or undefined — the row set differs between
 *  payload vintages and the record line must not print "undefined". */
function version(payload: ReportPayload, label: string): string | undefined {
  return payload.provenance.find((p) => p.label === label)?.value;
}
