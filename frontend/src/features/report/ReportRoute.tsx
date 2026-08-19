import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { Report } from "./Report";
import { fetchReport } from "./payload";

/**
 * `/report/:id` — fetch the stored payload and render it. The payload is the
 * data of record served verbatim (AGENTS.md rule 9): nothing here recomputes,
 * and `staleTime: Infinity` is correct because a stored report never changes
 * out from under its reader.
 *
 * `<Report>` mounts (and with it `data-report-ready`, the flag the Playwright
 * PDF path waits on) only once the payload is on screen — never race the
 * render (STACK.md §6).
 */
export function ReportRoute() {
  const { id = "" } = useParams();
  const q = useQuery({
    queryKey: ["report", id],
    queryFn: () => fetchReport(id),
    staleTime: Infinity,
    retry: false,
  });

  if (q.isPending) {
    return (
      <p className="mx-auto max-w-[52rem] px-6 py-12 font-data text-[13px] text-ink-faint">…</p>
    );
  }
  if (q.isError) {
    return (
      <div className="mx-auto max-w-[52rem] px-6 py-12">
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          {String(q.error.message) === "no such report"
            ? `No report ${id} exists. A report link is issued, not guessed.`
            : "Could not read the report."}
        </p>
      </div>
    );
  }
  return <Report payload={q.data} />;
}
