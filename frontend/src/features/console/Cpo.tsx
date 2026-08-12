import { useQuery } from "@tanstack/react-query";

import { PanelHeader } from "./ConsoleLayout";

/**
 * PART C.4 — CPO / scraped-source panel.
 *
 * Every CPO network we poll, shown with governance and measured status side by
 * side: is it authorised (has someone read its terms?), is an endpoint
 * configured, and what did our OWN poller last see from it. Uptime here is
 * measured, never the operator's claim.
 *
 * Read-only. Enabling a source is a reviewed code change in
 * app/domain/polling/sources.py, never a button here (PLAN C.0).
 */

type CpoSource = {
  source: string;
  kind: string;
  authorised: boolean;
  configured: boolean;
  pollable: boolean;
  blocking_reason: string | null;
  terms_url: string | null;
  terms_note: string | null;
  rate_limit_per_minute: number | null;
  last_success_at: string | null;
  last_error: string | null;
  stations_last_run: number;
  connectors_last_run: number;
  /** Status transitions, not observations. Zero is the healthy quiet case. */
  events_last_run: number;
};

function stateLabel(s: CpoSource): { label: string; warn: boolean } {
  if (s.pollable) return { label: "polling", warn: false };
  if (!s.authorised) return { label: "not authorised", warn: false };
  if (!s.configured) return { label: "authorised · no endpoint", warn: true };
  return { label: "blocked", warn: true };
}

export function Cpo() {
  const q = useQuery({
    queryKey: ["cpo-sources"],
    queryFn: async () => {
      const res = await fetch("/api/internal/sources", { credentials: "include" });
      if (!res.ok) throw new Error("could not load sources");
      return (await res.json()) as { checked_at: string; sources: CpoSource[] };
    },
    refetchInterval: 60_000,
  });

  return (
    <>
      <PanelHeader
        title="CPO"
        note="Every network we scrape or roam, with governance and measured status side by side. A source polls only when it is BOTH authorised in sources.py AND given an endpoint in settings — config alone is not consent."
      />

      {q.isPending ? (
        <p className="font-data text-[13px] text-ink-faint">…</p>
      ) : q.isError || !q.data ? (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not reach the sources endpoint.
        </p>
      ) : (
        <section className="max-w-4xl">
          <table className="w-full border-t border-rule text-left">
            <thead>
              <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                <th className="py-1 font-medium">Network</th>
                <th className="py-1 font-medium">Kind</th>
                <th className="py-1 font-medium">State</th>
                <th className="py-1 text-right font-medium">Rate/min</th>
                <th className="py-1 text-right font-medium">Stations</th>
                <th className="py-1 text-right font-medium">Connectors</th>
                <th
                  className="py-1 text-right font-medium"
                  title="Status changes recorded in the last successful poll. Zero is normal."
                >
                  Changes
                </th>
                <th className="py-1 font-medium">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {q.data.sources.map((s) => {
                const st = stateLabel(s);
                return (
                  <tr key={s.source} className="border-t border-rule align-top">
                    <td className="py-1.5 font-data text-[13px]">{s.source}</td>
                    <td className="py-1.5 font-data text-[12px] text-ink-muted">{s.kind}</td>
                    <td className="py-1.5 text-[13px]">
                      <span
                        className={
                          st.warn
                            ? "bg-warn-ground px-1 font-data text-warn"
                            : "font-data text-ink-muted"
                        }
                        title={s.blocking_reason ?? undefined}
                      >
                        {st.label}
                      </span>
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.rate_limit_per_minute ?? "—"}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.pollable ? s.stations_last_run : "—"}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.pollable ? s.connectors_last_run : "—"}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] text-ink-muted tabular-nums">
                      {s.pollable ? s.events_last_run : "—"}
                    </td>
                    <td className="py-1.5 font-data text-[12px] text-ink-muted">
                      {s.last_success_at
                        ? new Date(s.last_success_at).toLocaleString()
                        : s.last_error
                          ? "error"
                          : "never"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <p className="mt-3 max-w-prose font-data text-[11px] text-ink-faint">
            Many chargers recur across these networks because they roam over OCPI — the same
            physical unit appears under several networks. That overlap is kept on purpose (it maps
            the roaming graph and cross-checks occupancy) and deduped downstream at analysis time,
            never at poll time.
          </p>
          <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
            <strong>Connectors</strong> is what the network reported; <strong>changes</strong> is
            what we wrote down. Every response is archived losslessly either way, and only status
            transitions become rows in the queryable log — so a busy network with nothing changing
            shows a healthy connector count against zero changes.
          </p>
          <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
            To start a source: read its terms, record them + a rate limit and flip{" "}
            <code>authorised</code> in <code>app/domain/polling/sources.py</code>, then set its
            endpoint in settings. Validate the mapping with no database via{" "}
            <code>uv run python -m workers.poller --dry-run</code>.
          </p>
        </section>
      )}
    </>
  );
}
