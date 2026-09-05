import { COVERAGE, GROUPS, SITE_LABEL, SOURCES, TOTAL_CHECKS, VERDICT } from "./data";
import { useLoopClock } from "./useLoopClock";

/**
 * C - Sources in, report out. Three bands, left to right, 14s loop.
 *
 * Public sources connect; the 34 checks resolve against them, category by
 * category; a report comes out on paper. It is the product's whole shape in
 * one frame, and the only claim it makes is a claim about traceability -
 * every figure in the sheet on the right came from a plate on the left.
 *
 * The middle band is a ledger, not a neural network. A network lattice was
 * specified for this slot and is still open - it would sit here, between the
 * source plates and the paper, without disturbing either. It is not built
 * yet because a decorative topology and a real audit trail want the same
 * piece of screen, and the ledger is the one that survives a customer
 * asking "where did that number come from?".
 *
 * The paper band uses the report's own palette (--cw-paper / --cw-ink), so
 * what the animation promises and what /report/:id actually renders are the
 * same document. Copper - here --cw-caution, its paper-side value - falls on
 * one line only: the outage history nobody could source.
 */

/** sources, then one step per category, then the sheet, then the verdict. */
const DURATIONS = [1600, 1500, 1400, 1600, 1300, 1200, 2600, 3200] as const;
const FIRST_GROUP = 1;
const PAPER = 6;
const VERDICT_STEP = 7;

export function SourcesToReport() {
  const [ref, step] = useLoopClock<HTMLDivElement>(DURATIONS);
  const active = step - FIRST_GROUP;
  const feeding = step >= FIRST_GROUP && step < PAPER;

  return (
    <div ref={ref}>
      <div
        className="grid items-start gap-[clamp(24px,3vw,44px)]"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))" }}
      >
        {/* 01 - where the factors come from. */}
        <section>
          <BandLabel n="01" text="Sources" />
          <ul className="mt-4 flex flex-col gap-px bg-cw-line">
            {SOURCES.map((s, i) => (
              <li
                key={s.name}
                data-state={feeding ? "feeding" : "idle"}
                className="cwa-source flex items-center gap-3 bg-cw-ground px-3.5 py-3"
                style={{ animationDelay: `${i * 110}ms` }}
              >
                <span className="cwa-source__dot h-1.5 w-1.5 shrink-0 bg-cw-slate" />
                <span className="min-w-0 flex-auto">
                  <span className="block truncate font-cw-mono text-[12px] tracking-[0.08em] uppercase">
                    {s.name}
                  </span>
                  <span className="mt-0.5 block truncate text-[13px] text-cw-muted">{s.stamp}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        {/* 02 - the 34, grouped as the assessment groups them. */}
        <section>
          <BandLabel n="02" text={`${TOTAL_CHECKS} checks`} />
          <ul className="mt-4 flex flex-col gap-px bg-cw-line">
            {GROUPS.map((g, i) => {
              const state =
                step > i + FIRST_GROUP || step >= PAPER
                  ? "done"
                  : i === active
                    ? "live"
                    : "waiting";
              const unresolved = g.checks.filter((c) => c.unverified).length;
              return (
                <li key={g.key} data-state={state} className="cwa-group bg-cw-ground px-3.5 py-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate font-cw-mono text-[12px] tracking-[0.08em] uppercase">
                      {g.short}
                    </span>
                    {/* Mid-flight the numerator is deliberately unreadable
                        rather than wrong: the dots below carry the progress,
                        and "08 / 08 · Measuring…" would contradict itself. */}
                    <span className="shrink-0 font-cw-mono text-[12px] text-cw-muted tabular-nums">
                      {state === "done"
                        ? String(g.checks.length).padStart(2, "0")
                        : state === "live"
                          ? "··"
                          : "00"}{" "}
                      / {String(g.checks.length).padStart(2, "0")}
                    </span>
                  </div>
                  {/* One mark per real check. The count is the taxonomy, not a
                    decoration - 9 / 7 / 8 / 6 / 4 across the five groups. */}
                  <div className="mt-2.5 flex flex-wrap gap-1">
                    {g.checks.map((c, j) => (
                      <span
                        key={c.label}
                        title={c.label}
                        data-unverified={c.unverified ? "" : undefined}
                        className="cwa-node h-[7px] w-[7px]"
                        style={{ animationDelay: `${j * 55}ms` }}
                      />
                    ))}
                  </div>
                  <div className="mt-2 font-cw-mono text-[11px] tracking-[0.08em] text-cw-muted">
                    {state === "waiting"
                      ? "Awaiting source data"
                      : state === "live"
                        ? "Measuring…"
                        : unresolved
                          ? `${unresolved} unresolved input surfaced`
                          : "All checks resolved"}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        {/* 03 - the document, on the report's own paper. */}
        <section>
          <BandLabel n="03" text="Report" />
          <article
            data-state={step >= PAPER ? "in" : "out"}
            className="cwa-paper mt-4 bg-cw-paper px-[clamp(16px,2vw,24px)] py-[clamp(18px,2.2vw,26px)] text-cw-ink"
          >
            <div className="font-cw-mono text-[10px] tracking-[0.16em] text-cw-paper-muted uppercase">
              Site assessment · Illustrative
            </div>
            <div className="mt-3 border-b border-cw-rule pb-2.5 font-cw-serif text-[19px] leading-tight">
              {SITE_LABEL}, assessed
            </div>

            <dl className="m-0">
              {reportLines().map((line, i) => (
                <div
                  key={line.label}
                  data-state={step >= PAPER ? "in" : "out"}
                  className="cwa-line flex items-baseline gap-3 border-b border-cw-rule py-[7px]"
                  style={{ animationDelay: `${i * 130}ms` }}
                >
                  <dt className="min-w-0 flex-auto truncate font-cw-serif text-[14px]">
                    {line.label}
                  </dt>
                  <dd
                    className={`m-0 shrink-0 font-cw-mono text-[12px] tabular-nums ${
                      line.caution ? "text-cw-caution" : "text-cw-paper-muted"
                    }`}
                  >
                    {line.value}
                  </dd>
                </div>
              ))}
            </dl>

            <div
              data-state={step >= VERDICT_STEP ? "in" : "out"}
              className="cwa-summary mt-4 flex gap-5"
            >
              {COVERAGE.map((c) => (
                <div key={c.label}>
                  <div
                    className={`font-cw-mono text-[19px] leading-none font-medium tabular-nums ${
                      "unverified" in c && c.unverified ? "text-cw-caution" : "text-cw-ink"
                    }`}
                  >
                    {String(c.count).padStart(2, "0")}
                  </div>
                  <div className="mt-1 font-cw-mono text-[9px] tracking-[0.12em] text-cw-paper-muted uppercase">
                    {c.label}
                  </div>
                </div>
              ))}
            </div>

            {/* Last, always. */}
            <div
              data-state={step >= VERDICT_STEP ? "in" : "out"}
              className="cwa-summary mt-4 border-t-2 border-cw-ink pt-3"
            >
              <div className="font-cw-mono text-[clamp(15px,1.6vw,19px)] font-medium tracking-[0.04em] text-cw-verdict-positive uppercase">
                {VERDICT.word}
              </div>
              <p className="mt-1.5 font-cw-serif text-[13px] leading-snug text-cw-paper-muted">
                {VERDICT.copy}
              </p>
            </div>
          </article>
        </section>
      </div>

      <p className="mt-7 border-t border-cw-line pt-4 font-cw-mono text-[12px] tracking-[0.08em] text-cw-muted">
        Sources stay traceable. Missing evidence stays visible.
      </p>
    </div>
  );
}

/** Derived from GROUPS so the sheet can never disagree with the ledger. */
function reportLines() {
  const lines = [
    { label: "Assessment coverage", value: `${TOTAL_CHECKS} / ${TOTAL_CHECKS}`, caution: false },
    ...GROUPS.map((g) => {
      const open = g.checks.filter((c) => c.unverified).length;
      const verified = g.checks.length - open;
      return {
        label: g.name,
        value: open
          ? `${String(verified).padStart(2, "0")} + ${String(open).padStart(2, "0")} review`
          : `${String(verified).padStart(2, "0")} verified`,
        caution: false,
      };
    }),
  ];
  GROUPS.forEach((g) =>
    g.checks
      .filter((c) => c.unverified)
      .forEach((c) => lines.push({ label: c.label, value: "Unverified", caution: true })),
  );
  return lines;
}

function BandLabel({ n, text }: { n: string; text: string }) {
  return (
    <div className="flex items-baseline gap-2.5 border-b border-cw-line pb-2">
      <span className="font-cw-mono text-[11px] text-cw-slate tabular-nums">{n}</span>
      <span className="font-cw-mono text-[11px] tracking-[0.16em] text-cw-muted uppercase">
        {text}
      </span>
    </div>
  );
}

export default SourcesToReport;
