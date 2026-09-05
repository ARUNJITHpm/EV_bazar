import { COVERAGE, TOTAL_CHECKS } from "./data";

/**
 * The report sheet, assembling - animation C's third band, driven by the
 * real assessment instead of a clock.
 *
 * C on /animation runs a fixed 14.4s loop and ends on a verdict. Neither of
 * those can come to the working screen. The loop would be a lie about
 * progress on the one screen where the customer is watching real work, and
 * the verdict would be far worse: this component paints a document that the
 * router replaces seconds later with the actual report, and an animation
 * that guessed CONDITIONAL BUILD ahead of a stored DON'T BUILD would be
 * caught by the very next screen.
 *
 * So the verdict block here is a PENDING slot and stays one. It never
 * resolves, because the thing that resolves it is the real report. That is
 * also the better ending: the sheet fills, the last line lands, and the
 * page cuts to the document it was assembling.
 *
 * Grouping comes from the caller - Working.tsx groups the 34 by source
 * (12/4/8/7/3), which is not how data.ts groups them (9/7/8/6/4 by
 * subject). This takes what it is given.
 */
export function AssemblingReport({
  groups,
  done,
  settled,
}: {
  /** In order, with the running total each one completes at. */
  readonly groups: readonly { readonly name: string; readonly count: number }[];
  /** Factors resolved so far, 0..TOTAL_CHECKS. */
  readonly done: number;
  /** The stored answer has landed; the router is about to move. */
  readonly settled: boolean;
}) {
  let offset = 0;
  const lines = groups.map((g) => {
    offset += g.count;
    return { name: g.name, count: g.count, at: offset };
  });
  const complete = done >= TOTAL_CHECKS;

  return (
    <article
      aria-hidden="true"
      className="cwa-paper bg-cw-paper px-[clamp(18px,2.4vw,26px)] py-[clamp(20px,2.6vw,28px)] text-cw-ink"
      data-state="in"
    >
      <div className="flex items-baseline justify-between gap-3 font-cw-mono text-[10px] tracking-[0.16em] text-cw-paper-muted uppercase">
        <span>Site assessment</span>
        <span>{complete ? "Complete" : "Assembling"}</span>
      </div>
      <div className="mt-3 border-b border-cw-rule pb-2.5 font-cw-serif text-[19px] leading-tight">
        Your site, assessed
      </div>

      <dl className="m-0">
        {lines.map((line) => {
          const filled = done >= line.at;
          return (
            <div
              key={line.name}
              data-state={filled ? "in" : "out"}
              className="cwa-line flex items-baseline gap-3 border-b border-cw-rule py-[7px]"
            >
              <dt className="min-w-0 flex-auto truncate font-cw-serif text-[14px]">{line.name}</dt>
              <dd className="m-0 shrink-0 font-cw-mono text-[12px] text-cw-paper-muted tabular-nums">
                {String(line.count).padStart(2, "0")} checked
              </dd>
            </div>
          );
        })}
      </dl>

      {/* The split is only true once all 34 are in, so the counts read "··"
          until then. Holding the row rather than hiding it keeps the sheet
          from jumping when the last line lands - and an empty reserved gap
          looked like a rendering fault. */}
      <div className="mt-4 flex gap-5">
        {COVERAGE.map((c) => (
          <div key={c.label}>
            <div
              className={`font-cw-mono text-[19px] leading-none font-medium tabular-nums transition-colors duration-300 ${
                !complete
                  ? "text-cw-rule"
                  : "unverified" in c && c.unverified
                    ? "text-cw-caution"
                    : "text-cw-ink"
              }`}
            >
              {complete ? String(c.count).padStart(2, "0") : "··"}
            </div>
            <div className="mt-1 font-cw-mono text-[9px] tracking-[0.12em] text-cw-paper-muted uppercase">
              {c.label}
            </div>
          </div>
        ))}
      </div>

      {/* The slot that never fills. See the module note. */}
      <div className="mt-4 border-t-2 border-cw-ink pt-3">
        <div className="font-cw-mono text-[10px] tracking-[0.16em] text-cw-paper-muted uppercase">
          Verdict
        </div>
        <div className="mt-1.5 flex items-center gap-2.5">
          <span
            className="font-cw-mono text-[clamp(16px,1.8vw,20px)] font-medium tracking-[0.18em] text-cw-rule"
            aria-hidden="true"
          >
            ————
          </span>
          <span className="font-cw-serif text-[13px] text-cw-paper-muted">
            {settled ? "Opening your report." : "Held until every check is in."}
          </span>
        </div>
      </div>
    </article>
  );
}

export default AssemblingReport;
