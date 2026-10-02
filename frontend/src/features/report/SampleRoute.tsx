import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { Report } from "./Report";
import { SAMPLE_BLURB, SAMPLE_IDS, SAMPLES, isSampleId, type SampleId } from "./fixtures/samples";

/**
 * `/report/sample/:which` — the document rendered from a hand-written
 * fixture instead of a stored payload (CPO_SELECTION_PLAN.md, Track B · R0).
 *
 * Unlinked, like `/animation`, and for the same reason: it is a review
 * surface, not a page. It exists so the report can be looked at AT ALL THREE
 * VERDICTS while it is being rebuilt — the one stored report carries one
 * verdict, and regenerating it is a write to the live database behind a
 * public page.
 *
 * It renders the same `<Report>` the real route does. That is the whole
 * discipline: if the sample looks right and `/report/:id` does not, the
 * difference is the payload, never the component.
 *
 * `data-report-ready` still comes from `<Report>`, so the Playwright PDF
 * path can print these three the same way it prints a real one — which is
 * what R11 needs, and needs without a database.
 */

const LABEL: Record<SampleId, string> = {
  build: "Build",
  moderate: "Conditional",
  dont: "Don’t build",
};

export function SampleRoute() {
  const { which = "build" } = useParams();
  /** Narrowed once, so nothing below has to assert the id back. */
  const id: SampleId | null = isSampleId(which) ? which : null;
  const payload = id === null ? null : SAMPLES[id];

  useEffect(() => {
    if (payload) document.title = `Chargeworthy sample — ${payload.site.name}`;
    return () => {
      document.title = "Chargeworthy — will your land pay for a charger?";
    };
  }, [payload]);

  return (
    <div className="cw-report-root min-h-dvh bg-cw-desk antialiased">
      {/* The picker and the notice are screen-only: what prints is exactly
          what `/report/:id` would print, or the print pass proves nothing. */}
      <div className="no-print mx-auto max-w-[960px] px-[clamp(24px,6vw,64px)] py-4 font-cw-sans text-[15px] text-cw-paper-muted">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link to="/" className="transition-colors duration-200 hover:text-cw-ink">
            ← Chargeworthy
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            {SAMPLE_IDS.map((sample) => (
              <Link
                key={sample}
                to={`/report/sample/${sample}`}
                title={SAMPLE_BLURB[sample]}
                aria-current={sample === id ? "page" : undefined}
                className={`px-2.5 py-1 font-cw-mono text-[13px] tracking-[0.06em] uppercase transition-colors duration-200 ${
                  sample === id
                    ? "bg-cw-ink text-cw-paper"
                    : "text-cw-paper-muted hover:text-cw-ink"
                }`}
              >
                {LABEL[sample]}
              </Link>
            ))}
          </nav>
          <button
            type="button"
            onClick={() => window.print()}
            className="transition-colors duration-200 hover:text-cw-ink"
          >
            Print or save as PDF
          </button>
        </div>
        {id && (
          <p className="mt-3 mb-0 max-w-[70ch] text-[14px] leading-[1.6]">
            <span className="font-cw-mono text-[12px] tracking-[0.08em] uppercase">
              Review surface
            </span>{" "}
            — {SAMPLE_BLURB[id]} Nothing here came from the engine or the database; the figures are
            hand-written and internally consistent, and the page below is the same component{" "}
            <code className="font-cw-mono text-[13px]">/report/:id</code> renders.
          </p>
        )}
      </div>

      {payload ? (
        <Report payload={payload} />
      ) : (
        <div className="mx-auto max-w-[960px] bg-cw-paper px-[clamp(24px,6vw,64px)] py-14 font-cw-serif text-[17px]">
          <p className="m-0 inline-block bg-cw-caution-tint px-3 py-1.5 font-cw-mono text-[13px] text-cw-caution-text">
            No sample “{which}”. The three are {SAMPLE_IDS.join(", ")}.
          </p>
        </div>
      )}
    </div>
  );
}
