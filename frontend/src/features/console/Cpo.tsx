import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

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
  /** Researched route to availability without OCPI/app-capture (2026-08-15). */
  public_route: string | null;
  last_success_at: string | null;
  last_error: string | null;
  stations_last_run: number;
  connectors_last_run: number;
  /** Status transitions, not observations. Zero is the healthy quiet case. */
  events_last_run: number;
};

function stateLabel(s: CpoSource): { label: string; cls: string } {
  if (s.pollable) return { label: "polling", cls: "bg-ok-ground text-ok" };
  if (!s.authorised) return { label: "not authorised", cls: "bg-ground-sunk text-ink-faint" };
  if (!s.configured) return { label: "authorised · no endpoint", cls: "bg-info-ground text-info" };
  return { label: "blocked", cls: "bg-warn-ground text-warn" };
}

/** One row of the state legend — what a word in the State column means. */
function Legend({ term, cls, children }: { term: string; cls: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-rule py-1.5">
      <dt>
        <span className={cn("px-1 font-data text-[12px]", cls)}>{term}</span>
      </dt>
      <dd className="mt-0.5 text-[12px] text-ink-muted">{children}</dd>
    </div>
  );
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
        note="Every charging network we watch, and whether we are allowed to watch it yet. A network is polled only when BOTH locks are open: a human read its terms and marked it authorised in the code, and an endpoint is configured. Everything on the right is measured by our own poller, never the operator's claim."
      />
      <Glossary
        terms={["CPO", "Scrape", "OCPI", "Two locks", "Connector", "Change log", "Occupancy"]}
      />

      <section className="mb-6 max-w-3xl border border-rule bg-ground-sunk px-3 py-2">
        <p className="font-ui text-[10px] font-bold tracking-[0.08em] text-ink-muted uppercase">
          Public-web availability — research 2026-08-15
        </p>
        <p className="mt-1 max-w-prose text-[12px] text-ink-muted">
          The small note under each network is the researched route to its <em>live</em>{" "}
          availability <strong>without OCPI and without capturing an app</strong> (full detail in{" "}
          <code>CPO_SOURCES.md</code>). The honest picture: only a <strong>few</strong> networks
          expose free/busy on the public web — <strong>Tata Power</strong> (clean JSON with status)
          and <strong>Statiq</strong> (status in page HTML). Most keep occupancy inside their app,
          and Google's API has it but its ToS forbids storing it. chargeMOD is ours — read our own
          backend, never the app.
        </p>
        <p className="mt-2 max-w-prose text-[12px] text-ink-muted">
          <strong>Can we poll every CPO in India every 10 minutes?</strong> On cadence, yes —
          trivially: each network is <em>one</em> bulk request per cycle, so even all of India is a
          few dozen calls per 10 min, and the change-log only grows when a status actually flips.
          The real limit is <strong>coverage, not compute</strong>: you can only poll the handful
          that expose availability (start with KL+TN, then widen). Be a polite client — per-source
          rate limit, jitter, honest User-Agent, back off on blocks — and run it on an always-on
          VPS, because a sleeping laptop is a permanent hole in the record.
        </p>
      </section>

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
                    <td className="py-1.5 font-data text-[13px]">
                      {s.source}
                      {s.public_route && (
                        <span className="mt-0.5 block max-w-[22rem] font-data text-[10px] leading-snug text-ink-faint">
                          {s.public_route}
                        </span>
                      )}
                      {s.terms_note && (
                        <details className="mt-1 max-w-[22rem]">
                          <summary className="cursor-pointer font-data text-[10px] text-ink-faint">
                            terms &amp; status ▾
                          </summary>
                          <p className="mt-0.5 font-data text-[10px] leading-snug text-ink-muted">
                            {s.terms_note}
                          </p>
                          {s.terms_url && (
                            <a
                              href={s.terms_url}
                              target="_blank"
                              rel="noreferrer"
                              className="font-data text-[10px] text-info underline"
                            >
                              read the terms ↗
                            </a>
                          )}
                        </details>
                      )}
                    </td>
                    <td className="py-1.5 font-data text-[12px] text-ink-muted">{s.kind}</td>
                    <td className="py-1.5 text-[13px]">
                      <span
                        className={cn("px-1 font-data", st.cls)}
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

          <dl className="mt-4 max-w-prose border-t border-rule">
            <Legend term="not authorised" cls="bg-ground-sunk text-ink-faint">
              Nobody has read this network's app terms and switched it on in the code yet, so we
              send it ZERO requests. Not an error — this is where every network starts, and only a
              deliberate human decision moves it forward. Grey because it is waiting on us, not
              broken.
            </Legend>
            <Legend term="authorised · no endpoint" cls="bg-info-ground text-info">
              A human approved it, but we have not yet found the web address its app calls. That
              discovery is hand work — a few hours per app with a traffic inspector — then one line
              in .env.
            </Legend>
            <Legend term="polling" cls="bg-ok-ground text-ok">
              Both locks open. We are recording this network right now.
            </Legend>
            <Legend term="blocked" cls="bg-warn-ground text-warn">
              Authorised and configured, but something is stopping it. Hover the label for the
              reason.
            </Legend>
          </dl>

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
