import { FactCoverage } from "./FactCoverage";
import { ChangeVerdict } from "./ChangeVerdict";
import { Competitors } from "./Competitors";
import { Disclosure } from "./Disclosure";
import { Financials } from "./Financials";
import { Judged } from "./Judged";
import { Ledger } from "./Ledger";
import { Money } from "./Money";
import { Operators } from "./Operators";
import type { ReportPayload } from "./payload";
import { Provenance } from "./Provenance";
import { Site } from "./Site";
import { Statistical } from "./Statistical";
import { Verdict } from "./Verdict";
import { CwMark } from "../public/CwMark";
import { Wordmark } from "../public/Wordmark";

/**
 * The report — one site's verdict on paper, in the order design/brand/
 * report-spec.md argues for: plain language decides, statistics verify.
 *
 *   01 Verdict                    one word and one sentence, first
 *   02 What this means for money  return beside a fixed deposit
 *   03 How this site was judged   the rules, BEFORE the data
 *   04 The site                   pictures, then every factor with its direction
 *   05 Financials                 three cases, one engine
 *   06 Operator comparison
 *   07 Competitors
 *   08 What would change this     checkable conditions — why a reader trusts a no
 *   09 Statistical basis          the one chart, for the accountant
 *   10 Assumptions ledger         unverified inputs shown, not buried
 *   11 Provenance                 starts a new page in print
 *   12 Disclosure                 the conflict, stated
 *
 * One component per section so "the ledger is wrong" points at one file
 * (STACK.md §5). The payload is rendered verbatim (AGENTS.md rule 9): no
 * section recomputes a number.
 *
 * `data-report-ready` is what the Playwright PDF path waits on (STACK.md §6)
 * — set only once the payload is on screen, never race the render.
 *
 * PAGE CHROME (Track B · R1). The running head and foot repeat on every
 * printed page, and the document is wrapped in a one-column presentation
 * table to make that happen. That is not a style choice — it is the only
 * mechanism current Chromium actually implements. Measured, in this order:
 *
 *   · `@page` margin boxes with `counter(page)` — not implemented at all;
 *   · `position: fixed` — head on 0 pages of 12, foot on 1;
 *   · `display: table-header-group` on a plain div — head on page 1 only;
 *   · a real `<thead>` in a real `<table>` — repeats, which is what ships.
 *
 * Hence `role="presentation"`: this table carries no relationships, and a
 * screen reader must not announce the whole report as a data table. Do not
 * "tidy" it back into divs without re-running that measurement.
 *
 * The head carries no report data on purpose. It has to be identical on
 * every page, and a page-9 header saying "data tier 2" would be read as a
 * fact about page 9.
 *
 * The twelve sections below are the document's order of record: the console
 * describes them at /console/report, and features/console/ReportBuild.test.tsx
 * pins that description against what this component actually renders. Adding,
 * removing or reordering a section here fails that test, which is the only
 * moment anyone would find out the console had started describing a document
 * the customer is not receiving.
 */
export function Report({ payload }: { payload: ReportPayload }) {
  const { site } = payload;
  return (
    <article
      data-report-ready
      className="mx-auto max-w-[960px] bg-cw-paper px-[clamp(24px,6vw,64px)] pt-[clamp(20px,3vw,32px)] pb-[clamp(28px,4vw,44px)] font-cw-serif text-[17px] leading-[1.6] text-cw-ink"
    >
      <table role="presentation" data-report-page className="w-full table-fixed border-collapse">
        <thead data-page-head>
          <tr>
            <td className="p-0">
              <div className="flex items-baseline justify-between gap-6 border-b border-cw-ink pb-2.5">
                <span className="inline-flex items-center gap-2.5 self-center">
                  <CwMark className="size-[22px]" />
                  <Wordmark className="text-[19px] text-cw-paper-slate" />
                </span>
                <span className="font-cw-mono text-[11px] tracking-[0.12em] text-cw-paper-muted uppercase">
                  Right site. Right operator.
                </span>
              </div>
            </td>
          </tr>
        </thead>

        {/*
         * The running foot. Declared before <tbody> because that is where
         * HTML wants <tfoot>; it still renders last, on screen and on paper.
         *
         * The page number the sample carries (`CW-DEMO-001 / 04`) is NOT
         * here, and never will be. `counter(page)` resolves only inside an
         * `@page` margin box, which Chromium does not implement, so the page
         * half is drawn by Playwright's `footer_template` instead
         * (`app/pdf/render.py`, R11) — measured to cost nothing: the content
         * box stays 1017px and the page count is identical with it on or
         * off. This foot carries the half that is a fact about the DOCUMENT
         * rather than about the sheet.
         */}
        <tfoot data-page-foot>
          <tr>
            <td className="p-0 pt-11">
              <div className="flex flex-wrap justify-between gap-x-6 gap-y-1.5 border-t border-cw-ink pt-2.5 font-cw-mono text-[11px] tracking-[0.1em] uppercase">
                <span className={payload.demo ? "text-cw-caution-text" : "text-cw-paper-muted"}>
                  {payload.demo
                    ? "Demonstration only · sample site & figures"
                    : "Chargeworthy · site assessment"}
                </span>
                <span className="text-cw-paper-muted">{payload.report_id}</span>
              </div>
            </td>
          </tr>
        </tfoot>

        <tbody>
          <tr>
            <td className="p-0">
              <header className="mt-6">
                {payload.demo && (
                  <p className="mb-4 inline-block bg-cw-caution-tint px-3 py-1.5 font-cw-mono text-[13px] tracking-[0.06em] text-cw-caution-text">
                    DEMONSTRATION REPORT — a sample site; the demand band uses{" "}
                    {payload.predicted.model_version} (modelled). Not a customer deliverable.
                  </p>
                )}
                <p className="m-0 font-cw-mono text-[12px] tracking-[0.14em] text-cw-paper-muted uppercase">
                  EV charging site assessment
                </p>
                <h1 className="mt-2 mb-0 text-[clamp(30px,5vw,44px)] leading-[1.1] font-normal tracking-[-0.015em]">
                  {site.name}
                </h1>
                <p className="mt-1.5 mb-0 text-[17px] text-cw-paper-muted">{site.line}</p>
                <p className="mt-4 mb-0 font-cw-mono text-[12px] leading-[1.8] tracking-[0.04em] text-cw-paper-muted">
                  {payload.report_id} · data as of {payload.demand.vahan_snapshot} · data tier{" "}
                  {site.data_tier} · {site.district}
                </p>
              </header>

              <Verdict payload={payload} />
              <Money payload={payload} />
              <Judged payload={payload} />
              <FactCoverage facts={payload.site_facts} />
              <Site payload={payload} />
              <Financials payload={payload} />
              <Operators payload={payload} />
              <Competitors payload={payload} />
              <ChangeVerdict payload={payload} />
              <Statistical payload={payload} />
              <Ledger payload={payload} />
              <Provenance payload={payload} />
              <Disclosure />
            </td>
          </tr>
        </tbody>
      </table>
    </article>
  );
}
