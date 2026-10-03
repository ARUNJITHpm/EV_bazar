import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { Report } from "./Report";
import { fetchReport } from "./payload";
import { useRotatingLine } from "../../lib/useRotatingLine";
import { ReportSkeleton } from "./ReportSkeleton";
import { PublicHeader } from "../public/PublicHeader";

/**
 * A WhatsApp link carrying the report's address and nothing else: no
 * verdict, no figure. A report forwarded to a lender or a relative should
 * be read whole, in its own pages, not judged from a chat preview.
 */
export function whatsappShareUrl(origin: string, id: string, siteName: string, demo: boolean) {
  const url = `${origin}/report/${encodeURIComponent(id)}`;
  const text = demo
    ? `A sample Chargeworthy site report: ${url}`
    : `My Chargeworthy site report for ${siteName}: ${url}`;
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

/**
 * `/report/:id` — fetch the stored payload and render it on paper. The
 * payload is the data of record served verbatim (AGENTS.md rule 9): nothing
 * here recomputes, and `staleTime: Infinity` is correct because a stored
 * report never changes out from under its reader.
 *
 * `<Report>` mounts (and with it `data-report-ready`, the flag the Playwright
 * PDF path waits on) only once the payload is on screen — never race the
 * render (STACK.md §6).
 */
export function ReportRoute({ reportId }: { reportId?: string }) {
  const params = useParams();
  const id = reportId ?? params.id ?? "";
  const q = useQuery({
    queryKey: ["report", id],
    queryFn: () => fetchReport(id),
    staleTime: Infinity,
    retry: false,
  });

  // The state is in the payload we are still waiting for, so only the
  // time-of-day and general lines apply here.
  const line = useRotatingLine({
    stateName: null,
    running: q.isPending,
    reducedMotion:
      typeof window !== "undefined" &&
      Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches),
  });

  useEffect(() => {
    if (q.data)
      document.title = `Chargeworthy ${q.data.demo ? "sample report" : "report"} — ${q.data.site.name}`;
    return () => {
      document.title = "Chargeworthy — will your land pay for a charger?";
    };
  }, [q.data]);

  return (
    <div className="cw-report-root min-h-dvh bg-cw-desk antialiased">
      {/* A quiet bar above the sheet; it does not print. */}
      <a
        href="#report-content"
        className="no-print sr-only focus:not-sr-only focus:block focus:bg-cw-paper focus:p-4"
      >
        Skip to report
      </a>
      <PublicHeader>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={!q.data}
          className="inline-flex min-h-[44px] items-center transition-colors duration-200 hover:text-cw-text disabled:cursor-wait disabled:opacity-50"
        >
          Print or save as PDF
        </button>
        {q.data && (
          <a
            href={whatsappShareUrl(window.location.origin, id, q.data.site.name, q.data.demo)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-[44px] items-center transition-colors duration-200 hover:text-cw-text"
          >
            Share on WhatsApp
          </a>
        )}
      </PublicHeader>

      <main id="report-content">
        {q.isPending && <ReportSkeleton line={line} />}
        {q.isError && (
          <div className="mx-auto max-w-[960px] bg-cw-paper px-[clamp(24px,6vw,64px)] py-14 font-cw-serif text-[17px]">
            <p
              role="alert"
              className="m-0 inline-block bg-cw-caution-tint px-3 py-1.5 font-cw-mono text-[13px] text-cw-caution-text"
            >
              {String(q.error.message) === "no such report"
                ? `No report ${id} exists. A report link is issued, not guessed.`
                : "Could not read the report."}
            </p>
            <button
              type="button"
              onClick={() => void q.refetch()}
              className="no-print mt-5 block font-cw-sans text-[15px] underline underline-offset-4"
            >
              Try again
            </button>
          </div>
        )}
        {q.data && <Report payload={q.data} />}
      </main>
    </div>
  );
}
