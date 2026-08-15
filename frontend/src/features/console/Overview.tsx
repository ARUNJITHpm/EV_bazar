import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { cn } from "@/lib/utils";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/** PART C.0 — health, spend, and the poller heartbeat. */
export function Overview() {
  const ready = useQuery({
    queryKey: ["readyz"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/internal/readyz");
      if (error) throw new Error("readiness check failed");
      return data;
    },
    refetchInterval: 30_000,
  });

  const poller = useQuery({
    queryKey: ["poller-health"],
    // A 503 here is meaningful data (the poller is silent), not a failure to
    // fetch — so it must not be thrown away as an error.
    queryFn: async () => {
      const res = await fetch("/api/internal/poller/health", { credentials: "include" });
      return (await res.json()) as {
        alive: boolean;
        never_run: boolean;
        threshold_minutes: number;
        stale_sources: string[];
        sources: {
          source: string;
          pollable: boolean;
          blocking_reason: string | null;
          last_success_at: string | null;
          last_error: string | null;
          events_last_run: number;
          connectors_last_run: number;
          raw_pages_last_run: number;
          silent_for_seconds: number | null;
          stale: boolean;
        }[];
      };
    },
    refetchInterval: 60_000,
  });

  return (
    <>
      <PanelHeader
        title="Overview"
        note="Is the system alive, is it recording, and what has it spent. The poller heartbeat is shown even when nothing is wrong, because for a recorder the failure mode is silence rather than errors — a poller that died quietly loses history that cannot be re-acquired."
      />
      <Glossary
        terms={["Poller", "CPO", "Connector", "Archive", "Change log", "Dead-man's switch"]}
      />

      <section className="max-w-3xl">
        <SectionTitle>Poller</SectionTitle>
        {poller.isPending ? (
          <p className="font-data text-[13px] text-ink-faint">…</p>
        ) : poller.isError || !poller.data ? (
          <p className="bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
            Could not reach the poller health endpoint.
          </p>
        ) : (
          <>
            <dl className="border-t border-rule">
              <Row
                label="Recording"
                value={
                  poller.data.never_run
                    ? "never run"
                    : poller.data.alive
                      ? "alive"
                      : `silent > ${poller.data.threshold_minutes} min`
                }
                warn={!poller.data.alive}
              />
              <Row label="Dead-man threshold" value={`${poller.data.threshold_minutes} min`} />
            </dl>

            <table className="mt-4 w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">Source</th>
                  <th className="py-1 font-medium">State</th>
                  <th className="py-1 text-right font-medium" title="Pages archived losslessly">
                    Pages
                  </th>
                  <th
                    className="py-1 text-right font-medium"
                    title="Connectors the source reported in its last successful poll"
                  >
                    Connectors
                  </th>
                  <th
                    className="py-1 text-right font-medium"
                    title="Status changes recorded. Zero is normal — this is a change log."
                  >
                    Changes
                  </th>
                  <th className="py-1 text-right font-medium">Silent for</th>
                </tr>
              </thead>
              <tbody>
                {poller.data.sources.map((s) => (
                  <tr key={s.source} className="border-t border-rule align-top">
                    <td className="py-1.5 font-data text-[13px]">{s.source}</td>
                    <td className="py-1.5 text-[13px]">
                      {s.pollable ? (
                        <span className="font-data">{s.stale ? "stalled" : "polling"}</span>
                      ) : (
                        <span
                          className="font-data text-ink-faint"
                          title={s.blocking_reason ?? undefined}
                        >
                          not authorised
                        </span>
                      )}
                    </td>
                    {/* Pages is the one that must never be zero on a live
                        source: the archive is the only unrecoverable table. */}
                    <td
                      className={cn(
                        "py-1.5 text-right font-data text-[13px] tabular-nums",
                        s.pollable && s.raw_pages_last_run === 0 && "bg-warn-ground text-warn",
                      )}
                    >
                      {s.pollable ? s.raw_pages_last_run : "—"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 text-right font-data text-[13px] tabular-nums",
                        s.pollable && s.connectors_last_run === 0 && "bg-warn-ground text-warn",
                      )}
                    >
                      {s.pollable ? s.connectors_last_run : "—"}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] text-ink-muted tabular-nums">
                      {s.pollable ? s.events_last_run : "—"}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.silent_for_seconds === null
                        ? "—"
                        : `${Math.round(s.silent_for_seconds / 60)}m`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              A source reads “not authorised” until its terms, rate limit and authorisation are
              recorded in <code>app/domain/polling/sources.py</code>. That is deliberate — traffic
              requires a reviewed change, never a default.
            </p>
            <p className="mt-1 max-w-prose font-data text-[11px] text-ink-faint">
              <strong>Changes of zero is healthy.</strong> We store one row per status transition,
              not one per observation, so a quiet five minutes writes nothing. The numbers that must
              not be zero on a live source are <em>pages</em> — the lossless archive — and{" "}
              <em>connectors</em>, which reads zero when an endpoint answers 200 with an empty feed.
            </p>
          </>
        )}
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Backend</SectionTitle>
        <dl className="border-t border-rule">
          <Row label="Database" value={fmt(ready.isPending, ready.isError, ready.data?.database)} />
          <Row label="PostGIS" value={fmt(ready.isPending, ready.isError, ready.data?.postgis)} />
          <Row label="Environment" value={fmt(ready.isPending, ready.isError, ready.data?.env)} />
          <Row
            label="Paid providers enabled"
            value={
              ready.isPending || ready.isError
                ? "…"
                : ready.data.paid_providers_enabled.length
                  ? ready.data.paid_providers_enabled.join(", ")
                  : "none"
            }
          />
        </dl>
      </section>

      <section className="mt-8 max-w-3xl">
        <SectionTitle>Awaiting their Part</SectionTitle>
        <dl className="border-t border-rule">
          <Row label="Spend today" value="not built — PLAN C.2" warn />
          <Row label="Stale data layers" value="not built — PLAN C.5" warn />
        </dl>
      </section>
    </>
  );
}

function fmt(pending: boolean, error: boolean, value?: string): string {
  if (pending) return "…";
  if (error || value === undefined) return "unknown";
  return value;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}

function Row({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-rule py-1.5">
      <dt className="font-ui text-[13px] text-ink-muted">{label}</dt>
      <dd
        className={
          warn
            ? "bg-warn-ground px-1 font-data text-[13px] text-warn"
            : "font-data text-[13px] tabular-nums"
        }
      >
        {value}
      </dd>
    </div>
  );
}
