import type { ReportPayload, Verdict as VerdictValue } from "./payload";

/**
 * The verdict sits UNDER the hero number, small, as confirmation — not above
 * it as instruction. A client putting real money in reaches the conclusion
 * from the figure in two seconds; this line confirms they read it right and
 * states why. Driven by P10, never P50 (OVERVIEW.md §3).
 *
 * Ink weights, not status chips (tokens.css): the word carries the colour,
 * the sentence carries the argument.
 */

const LABEL: Record<VerdictValue, string> = {
  build: "Build",
  conditional: "Conditional",
  dont: "Don't build",
};

const INK: Record<VerdictValue, string> = {
  build: "text-verdict-build",
  conditional: "text-verdict-condition",
  dont: "text-verdict-dont",
};

export function Verdict({ payload }: { payload: ReportPayload }) {
  const { verdict } = payload;
  return (
    <section data-report-section="verdict" className="border-b border-rule py-5">
      <p className="font-ui text-[11px] tracking-[0.08em] uppercase">
        <span className="text-ink-muted">Verdict · from P10 </span>
        <span className={`font-bold ${INK[verdict.value]}`}>{LABEL[verdict.value]}</span>
      </p>
      <p className="mt-2 max-w-[34rem] text-[0.9375rem] text-ink-muted">{verdict.reason}</p>
    </section>
  );
}
