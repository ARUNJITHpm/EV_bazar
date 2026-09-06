import { COVERAGE, GROUPS, SITE_LABEL, SOURCES, TOTAL_CHECKS, VERDICT } from "./data";
import { useLoopClock } from "./useLoopClock";

/**
 * C - Sources in, report out. Three bands, left to right.
 *
 * Ported from Designv3/sources-to-assessment-report.html: the framed sheet,
 * the source plates wired into the matrix, the matrix shell with its
 * per-group nodes, and the paper sliding in on the right. Public sources
 * connect; the 34 checks resolve against them, group by group; a report
 * comes out. It is the product's whole shape in one frame, and the only
 * claim it makes is a claim about traceability - every figure in the sheet
 * on the right came from a plate on the left.
 *
 * The wires are the argument, which is why they are drawn rather than
 * implied by proximity. They are also the first thing to go when the bands
 * stack, because a wire that runs off the side of a column into nothing
 * asserts a connection that is not on screen.
 *
 * The plates are derived from GROUPS, not typed out. The reference listed
 * FIELD SURVEY and LAND · POLICY among its sources; the pipeline fetches
 * neither, and a source plate is a claim about capability, not decoration.
 *
 * The paper band uses the report's own palette (--cw-paper / --cw-ink), so
 * what the animation promises and what /report/:id actually renders are the
 * same document. Copper - here --cw-caution, its paper-side value - falls on
 * one line only: the outage history nobody could source.
 */

/** sources, then one step per group, then the sheet, then the verdict. */
const DURATIONS = [1600, 1900, 1100, 1600, 1500, 1000, 2600, 3200] as const;
const FIRST_GROUP = 1;
const PAPER = 6;
const VERDICT_STEP = 7;

export function SourcesToReport() {
  const [ref, step] = useLoopClock<HTMLDivElement>(DURATIONS);
  const active = step - FIRST_GROUP;
  const feeding = step >= FIRST_GROUP && step < PAPER;

  return (
    <div ref={ref} className="cwa-flow cwa-frame p-[clamp(22px,3.2vw,52px)]">
      <div
        className="grid grid-cols-1 items-center min-[1100px]:grid-cols-[minmax(190px,225px)_minmax(0,1fr)_minmax(300px,350px)]"
        style={{ gap: "var(--cwa-gap)" }}
      >
        {/* 01 - where the factors come from. */}
        <section className="min-w-0">
          <BandLabel n="01" text="Source layer" />
          <ul className="mt-4 grid grid-cols-2 gap-2.5 min-[1100px]:grid-cols-1">
            {SOURCES.map((s, i) => (
              <li
                key={s.name}
                data-state={feeding ? "feeding" : "idle"}
                className="cwa-source min-h-[78px] border border-cw-line bg-cw-surface/88 py-3 pr-[30px] pl-3.5"
                style={{ animationDelay: `${i * 110}ms` }}
              >
                {/* The reference's plates were two-word brands (VAHAN ·
                    PARIVAHAN) and could truncate. These name the actual
                    fetch - "VAHAN registrations, this district" - and a
                    plate reading "VAHAN REGISTRATIONS, TH..." claims less
                    than the pipeline does, so the name wraps instead. */}
                <span className="block font-cw-mono text-[11px] leading-tight font-semibold tracking-[0.07em] text-cw-text uppercase">
                  {s.name}
                </span>
                <span className="mt-1.5 block truncate font-cw-mono text-[9px] leading-tight tracking-[0.08em] text-cw-muted uppercase">
                  {s.stamp}
                </span>
                <span
                  className={`absolute top-[11px] right-2.5 h-1.5 w-1.5 rounded-full ${
                    feeding ? "bg-cw-slate" : "bg-cw-line"
                  }`}
                />
              </li>
            ))}
          </ul>
        </section>

        {/* 02 - the 34, grouped as the assessment groups them. */}
        <section className="min-w-0">
          <BandLabel n="02" text="Assessment matrix" />
          <div
            data-state={feeding ? "feeding" : "idle"}
            className="cwa-matrix relative mt-4 border border-cw-line bg-cw-ground/90 p-[17px]"
          >
            <div className="mb-3.5 flex items-baseline justify-between gap-4 border-b border-cw-line pb-3">
              <span className="min-w-0 truncate text-[clamp(16px,1.9vw,23px)] leading-tight font-medium tracking-[-0.02em]">
                Full-site assessment
              </span>
              <span className="shrink-0 font-cw-mono text-[11px] tracking-[0.1em] text-cw-slate uppercase">
                {TOTAL_CHECKS} factors
              </span>
            </div>

            <ul className="flex flex-col gap-[7px]">
              {GROUPS.map((g, i) => {
                const state =
                  step > i + FIRST_GROUP || step >= PAPER
                    ? "done"
                    : i === active
                      ? "live"
                      : "waiting";
                const unresolved = g.checks.filter((c) => c.unverified).length;
                return (
                  <li
                    key={g.key}
                    data-state={state}
                    className="cwa-group min-h-[81px] bg-cw-surface/72 px-3 py-2.5"
                  >
                    <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2.5">
                      <span className="truncate font-cw-mono text-[10px] font-semibold tracking-[0.08em] text-cw-muted uppercase">
                        {g.name}
                      </span>
                      {/* Mid-flight the numerator is deliberately unreadable
                          rather than wrong: the nodes below carry the
                          progress, and "08 / 08 · Measuring" would
                          contradict itself. */}
                      <span className="font-cw-mono text-[10px] text-cw-text tabular-nums">
                        {state === "done"
                          ? String(g.checks.length).padStart(2, "0")
                          : state === "live"
                            ? "··"
                            : "00"}{" "}
                        / {String(g.checks.length).padStart(2, "0")}
                      </span>
                      <span
                        className={`min-w-[62px] text-right font-cw-mono text-[10px] tracking-[0.06em] uppercase ${
                          state === "live"
                            ? "text-cw-slate"
                            : state === "done"
                              ? "text-cw-text"
                              : "text-cw-muted"
                        }`}
                      >
                        {state === "waiting"
                          ? "Waiting"
                          : state === "live"
                            ? "Measuring"
                            : unresolved
                              ? "Review"
                              : "Complete"}
                      </span>
                    </div>

                    {/* One mark per real check. The count is the taxonomy,
                        not a decoration - 12 / 4 / 8 / 7 / 3 across the five
                        groups.

                        Each mark fills in turn, spread across THIS group's
                        own beat, so twelve checks take longer to resolve
                        than three do. The clock only reports which step it
                        is on, so the within-step pacing is a CSS stagger
                        computed from the same DURATIONS the clock runs on. */}
                    <div className="mt-2.5 flex flex-wrap gap-[5px]">
                      {g.checks.map((c, j) => (
                        <span
                          key={c.label}
                          title={c.label}
                          data-unverified={c.unverified ? "" : undefined}
                          className="cwa-node h-[9px] w-[9px]"
                          style={{
                            animationDelay: `${
                              (j * (DURATIONS[i + FIRST_GROUP] ?? 1500) * 0.7) / g.checks.length
                            }ms`,
                          }}
                        />
                      ))}
                    </div>

                    <div
                      className={`mt-2 truncate font-cw-mono text-[9px] tracking-[0.06em] ${
                        state === "live" ? "text-cw-slate" : "text-cw-muted"
                      }`}
                    >
                      {state === "waiting"
                        ? "Awaiting source data"
                        : state === "live"
                          ? `Reading ${g.source}`
                          : unresolved
                            ? `${unresolved} unresolved input surfaced`
                            : "All checks resolved"}
                    </div>
                  </li>
                );
              })}
            </ul>

            <span className="cwa-matrix-out" aria-hidden="true" />
          </div>
        </section>

        {/* 03 - the document, on the report's own paper. */}
        <section className="min-w-0">
          <BandLabel n="03" text="Report output" />
          <article
            data-state={step >= PAPER ? "in" : "out"}
            className="cwa-paper mt-4 min-h-[560px] bg-cw-paper px-[25px] pt-[26px] pb-[24px] text-cw-ink"
          >
            <div className="font-cw-mono text-[9px] font-semibold tracking-[0.14em] text-cw-paper-slate uppercase">
              EV charging · site intelligence
            </div>
            <h4 className="mt-2 mb-1 font-cw-serif text-[25px] leading-tight font-semibold tracking-[-0.02em]">
              Site assessment
            </h4>
            <div className="mb-5 flex justify-between gap-3 font-cw-mono text-[9px] tracking-[0.07em] text-cw-paper-muted uppercase">
              <span>{SITE_LABEL}</span>
              <span>Illustrative</span>
            </div>

            <dl className="m-0 border-t border-cw-rule">
              {reportLines().map((line, i) => (
                <div
                  key={line.label}
                  data-state={step >= PAPER ? "in" : "out"}
                  className="cwa-line grid min-h-[38px] grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-2 border-b border-cw-rule"
                  style={{ animationDelay: `${i * 130}ms` }}
                >
                  <dt className="font-cw-mono text-[9px] text-cw-paper-muted tabular-nums">
                    {String(i + 1).padStart(2, "0")}
                  </dt>
                  <dd className="m-0 min-w-0 truncate font-cw-serif text-[12px] text-cw-paper-muted">
                    {line.label}
                  </dd>
                  <dd
                    className={`m-0 flex shrink-0 items-center gap-1.5 font-cw-mono text-[10px] font-semibold whitespace-nowrap tabular-nums ${
                      line.caution ? "text-cw-caution" : "text-cw-ink"
                    }`}
                  >
                    {line.caution && (
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-cw-caution" />
                    )}
                    {line.value}
                  </dd>
                </div>
              ))}
            </dl>

            <div
              data-state={step >= VERDICT_STEP ? "in" : "out"}
              className="cwa-summary mt-4 grid grid-cols-3 gap-1.5"
            >
              {COVERAGE.map((c) => {
                const open = "unverified" in c && c.unverified;
                return (
                  <div key={c.label} className="border border-cw-rule px-[7px] py-2.5">
                    <div
                      className={`font-cw-mono text-[17px] leading-none font-medium tabular-nums ${
                        open ? "text-cw-caution" : "text-cw-ink"
                      }`}
                    >
                      {String(c.count).padStart(2, "0")}
                    </div>
                    <div
                      className={`mt-1 font-cw-mono text-[8px] tracking-[0.08em] uppercase ${
                        open ? "text-cw-caution" : "text-cw-paper-muted"
                      }`}
                    >
                      {c.label}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Last, always. */}
            <div
              data-state={step >= VERDICT_STEP ? "in" : "out"}
              className="cwa-summary mt-4 border-t-2 border-cw-paper-slate pt-3.5"
            >
              <div className="font-cw-mono text-[clamp(15px,1.6vw,20px)] leading-none font-bold tracking-[0.025em] text-cw-verdict-positive uppercase">
                {VERDICT.word}
              </div>
              <p className="mt-2 font-cw-serif text-[11px] leading-snug text-cw-paper-muted">
                {VERDICT.copy}
              </p>
            </div>
          </article>
        </section>
      </div>

      <p className="mt-7 font-cw-mono text-[10px] tracking-[0.1em] text-cw-muted uppercase">
        Sources stay traceable · missing evidence stays visible
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
    <div className="flex items-baseline gap-2 font-cw-mono text-[11px] font-semibold text-cw-slate">
      <span className="tabular-nums">{n}</span>
      <span aria-hidden="true">·</span>
      <span className="tracking-[0.15em] uppercase">{text}</span>
    </div>
  );
}

export default SourcesToReport;
