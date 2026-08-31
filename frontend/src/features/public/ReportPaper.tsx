/**
 * The paper preview of the demonstration report - the landing page's most
 * persuasive artifact (design/brand/launch-checklist.md: "the assessment
 * artifact outranks everything visual").
 *
 * Every figure here is the REAL demo report (KL-TVM-DEMO-001, served from
 * the stored payload at /report/…): an honest DON'T BUILD on a crowded
 * corridor. Hand-copied, not fetched - the landing must not block on the
 * API - so if the demo ever regenerates, this preview is the one place to
 * update by hand (the link below it always shows the live document).
 */

const FIGURES: [string, string][] = [
  ["Breakeven this site must clear", "4.3%"],
  ["Projected utilisation, P10–P90", "0.9–2.4%"],
  ["Verdict driven by", "the P10"],
];

export function ReportPaper({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`flex flex-col bg-cw-paper text-cw-ink ${
        compact ? "gap-3 px-8 py-7" : "gap-5 p-8 sm:px-12 sm:py-10"
      }`}
    >
      <div className="flex items-baseline justify-between gap-4 border-b-[3px] border-cw-ink pb-3">
        <span className="font-cw-mono text-[13px] tracking-[0.1em] text-cw-paper-slate uppercase">
          Chargeworthy
        </span>
        <span className="font-cw-mono text-[13px] text-cw-paper-muted">KL-TVM-DEMO-001</span>
      </div>
      <div className={compact ? "text-[20px]" : "text-[25px]"}>
        NH-<span className="font-cw-mono">66</span>, Kazhakkoottam
      </div>
      <div className="flex flex-col gap-2.5 border-t-2 border-cw-ink pt-3.5">
        <div
          className={`tracking-[0.02em] text-cw-verdict-negative ${
            compact ? "text-[26px]" : "text-[34px]"
          }`}
        >
          DON&rsquo;T BUILD
        </div>
        <p className="text-[16px] leading-[1.55]">
          Even in the optimistic case this site runs below the point where it covers its costs.
        </p>
      </div>
      {!compact && (
        <div className="flex flex-wrap gap-8 border-t border-cw-rule pt-4">
          {FIGURES.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-1.5">
              <span className="text-[14px] text-cw-paper-muted">{label}</span>
              <span className="font-cw-mono text-[24px] font-medium tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
