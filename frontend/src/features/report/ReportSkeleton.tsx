import { Wordmark } from "../public/Wordmark";

/**
 * The report's shape while the stored payload is on its way: the sheet, the
 * running head, and the twelve section eyebrows with soft bars where the
 * text will land. Only the section names are real - they are fixed by the
 * document, not by the payload - so nothing here can be mistaken for a
 * finding. ReportSkeleton.test.tsx pins the outline against the console's
 * record of the sections, so a renamed section cannot leave this behind.
 *
 * No `data-report-ready` here, ever: the PDF path waits on that flag, and a
 * skeleton must never be printed as the report.
 */
export const REPORT_OUTLINE: readonly { n: string; title: string }[] = [
  { n: "01", title: "Verdict" },
  { n: "02", title: "What this means for your money" },
  { n: "03", title: "How this site was judged" },
  { n: "04", title: "The site" },
  { n: "05", title: "Financial working" },
  { n: "06", title: "Operator comparison" },
  { n: "07", title: "Competitors" },
  { n: "08", title: "What would change this verdict" },
  { n: "09", title: "Statistical basis" },
  { n: "10", title: "Assumptions ledger" },
  { n: "11", title: "Provenance" },
  { n: "12", title: "Disclosure and independence" },
];

/** Bar widths, so the outline reads as text rather than a grid. */
const WIDTHS = ["w-[72%]", "w-[54%]", "w-[63%]"];

function Bar({ className }: { className: string }) {
  return <div className={`cw-shimmer h-3.5 rounded-[2px] ${className}`} />;
}

export function ReportSkeleton({ line }: { line?: string }) {
  return (
    <div
      role="status"
      className="mx-auto max-w-[960px] bg-cw-paper px-[clamp(24px,6vw,64px)] pt-[clamp(20px,3vw,32px)] pb-14 font-cw-serif text-cw-ink"
    >
      <div className="flex items-baseline justify-between gap-6 border-b border-cw-ink pb-2.5">
        <Wordmark className="text-[19px] text-cw-paper-slate" />
        <span className="font-cw-mono text-[13px] text-cw-paper-muted">
          Fetching the stored report…
        </span>
      </div>
      {/* aria-hidden: the status above is what a screen reader needs. Gone
          the moment the report mounts - no joke ever sits on the paper. */}
      {line && (
        <p
          key={line}
          aria-hidden="true"
          className="cw-rise no-print m-0 mt-5 font-cw-sans text-[16px] text-cw-ink"
        >
          {line}
        </p>
      )}
      <div aria-hidden="true">
        {REPORT_OUTLINE.map((s, i) => (
          <section key={s.n} className="mt-10">
            <div className="border-t border-cw-ink pt-3">
              <p className="m-0 font-cw-mono text-[13px] tracking-[0.1em] text-cw-paper-slate uppercase">
                <span>{s.n}</span>
                <span className="mx-2 text-cw-rule">/</span>
                <span>{s.title}</span>
              </p>
            </div>
            <div className="mt-4 flex flex-col gap-2.5">
              <Bar className="h-6 w-[46%]" />
              <Bar className={WIDTHS[i % WIDTHS.length]!} />
              <Bar className={WIDTHS[(i + 1) % WIDTHS.length]!} />
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
