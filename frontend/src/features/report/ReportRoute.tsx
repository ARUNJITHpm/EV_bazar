import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { Report } from "./Report";
import { fetchReport } from "./payload";

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
export function ReportRoute({
  reportId,
  homepage = false,
}: {
  reportId?: string;
  homepage?: boolean;
}) {
  const params = useParams();
  const id = reportId ?? params.id ?? "";
  const q = useQuery({
    queryKey: ["report", id],
    queryFn: () => fetchReport(id),
    staleTime: Infinity,
    retry: false,
  });

  useEffect(() => {
    if (q.data)
      document.title = `Chargeworthy ${homepage ? "sample report" : "report"} — ${q.data.site.name}`;
    return () => {
      document.title = "Chargeworthy — will your land pay for a charger?";
    };
  }, [q.data, homepage]);

  return (
    <div className="cw-report-root min-h-dvh bg-cw-desk antialiased">
      {/* A quiet bar above the sheet; it does not print. */}
      <a
        href="#report-content"
        className="no-print sr-only focus:not-sr-only focus:block focus:bg-cw-paper focus:p-4"
      >
        Skip to report
      </a>
      <nav
        aria-label="Main navigation"
        className="no-print mx-auto flex max-w-[960px] flex-wrap items-center justify-between gap-4 px-[clamp(24px,6vw,64px)] py-4 font-cw-sans text-[15px] text-cw-paper-muted"
      >
        <Link
          to="/"
          aria-current={homepage ? "page" : undefined}
          className="font-semibold text-cw-ink"
        >
          Chargeworthy
        </Link>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <Link to="/about" className="hover:text-cw-ink">
            About
          </Link>
          <Link to="/data" className="hover:text-cw-ink">
            Data
          </Link>
          <Link to="/assess" className="bg-cw-paper-head px-4 py-2 text-cw-paper hover:underline">
            Assess my site
          </Link>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={!q.data}
          className="transition-colors duration-200 hover:text-cw-ink disabled:cursor-wait disabled:opacity-50"
        >
          Print or save as PDF
        </button>
      </nav>

      <main id="report-content">
        {q.isPending && (
          <div
            role="status"
            className="mx-auto max-w-[960px] bg-cw-paper px-[clamp(24px,6vw,64px)] py-14 font-cw-mono text-[13px] text-cw-paper-muted"
          >
            Fetching the stored report…
          </div>
        )}
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
