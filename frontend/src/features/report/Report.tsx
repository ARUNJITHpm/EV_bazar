import { CpoTable } from "./CpoTable";
import { Financials } from "./Financials";
import { HeroNumber } from "./HeroNumber";
import { Ledger } from "./Ledger";
import { Provenance } from "./Provenance";
import { SiteProfile } from "./SiteProfile";
import { Verdict } from "./Verdict";
import type { ReportPayload } from "./payload";

/**
 * The 7-section report (OVERVIEW.md §8), one component per section so "the
 * ledger is wrong" points at one file (STACK.md §5).
 *
 * Order on the page: the hero number leads and the verdict follows it, small.
 * The buyer reaches the conclusion from the figure; the word confirms it.
 * print.css keeps hero + verdict together on page one either way.
 *
 * `data-report-ready` is what the Playwright PDF path waits on (STACK.md §6)
 * — set only once the payload is on screen, never race the render.
 */
export function Report({ payload }: { payload: ReportPayload }) {
  return (
    <div data-report-ready className="mx-auto max-w-[52rem] px-6 py-12">
      {payload.demo && (
        <p className="mb-6 bg-warn-ground px-3 py-2 font-data text-[12px] text-warn">
          demonstration report — sample site, utilisation is synthetic_v0 (modelled). not a customer
          deliverable.
        </p>
      )}

      <header className="border-b-2 border-rule-strong pb-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-ui text-[13px] font-bold tracking-[0.08em] uppercase">
            EV Site Intelligence · Site Assessment
          </p>
          <p className="num text-[11px] text-ink-faint">{payload.report_id}</p>
        </div>
        <p className="mt-2 text-[1.125rem] leading-tight">{payload.site.name}</p>
        <p className="num text-[13px] text-ink-muted">{payload.site.line}</p>
      </header>

      <main className="mt-8">
        <HeroNumber payload={payload} />
        <Verdict payload={payload} />
        <SiteProfile payload={payload} />
        <Financials payload={payload} />
        <CpoTable payload={payload} />
        <Ledger payload={payload} />
        <Provenance payload={payload} />
      </main>
    </div>
  );
}
