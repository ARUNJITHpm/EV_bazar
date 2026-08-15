import { useQuery } from "@tanstack/react-query";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — the competitor inventory (PLAN 2.3).
 *
 * How much competition exists, and whose. This is the denominator for every
 * "competitors within 3 km" feature, and the surface the poller's observed
 * occupancy attaches to later. Existence + specs here; free/busy is the
 * poller's job, never this.
 */

type OperatorRow = { operator: string; stations: number; dc_fast: number };
type StateRow = { lgd_state_code: number; state: string; stations: number };
type CompetitorsOut = {
  checked_at: string;
  total: number;
  unplaced: number;
  fetched_from: string[];
  by_state: StateRow[];
  top_operators: OperatorRow[];
};

export function Competitors() {
  const q = useQuery({
    queryKey: ["competitors"],
    queryFn: async () => {
      const res = await fetch("/api/internal/competitors", { credentials: "include" });
      if (!res.ok) throw new Error(`competitors returned ${res.status}`);
      return (await res.json()) as CompetitorsOut;
    },
  });

  return (
    <>
      <PanelHeader
        title="Competitors"
        note="Every charging station we know about that is not a customer's site — who runs it, where, how powerful. The denominator for 'how much competition is near this site'. Existence and specs only; how BUSY each one is comes from the poller, not here."
      />
      <Glossary terms={["CPO", "Connector", "Occupancy", "LGD"]} />

      {q.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read competitors.
        </p>
      )}

      {q.data && q.data.total === 0 && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Nothing fetched yet. Run{" "}
          <code>uv run python -m scripts.fetch_competitors --state kerala --write</code>.
        </p>
      )}

      {q.data && q.data.total > 0 && (
        <>
          <section className="mb-8 flex max-w-3xl flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
            <Figure label="Stations" value={q.data.total.toLocaleString()} />
            <Figure label="Sources" value={q.data.fetched_from.join(", ")} />
            <Figure
              label="Unplaced"
              value={q.data.unplaced.toLocaleString()}
              warn={q.data.unplaced > 0}
            />
          </section>

          <section className="mb-8 max-w-3xl">
            <SectionTitle>By state</SectionTitle>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">State</th>
                  <th className="py-1 text-right font-medium">Stations</th>
                </tr>
              </thead>
              <tbody>
                {q.data.by_state.map((s) => (
                  <tr key={s.lgd_state_code} className="border-t border-rule">
                    <td className="py-1.5 text-[13px]">{s.state}</td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.stations.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="max-w-3xl">
            <SectionTitle>Top networks</SectionTitle>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">Operator</th>
                  <th className="py-1 text-right font-medium">Stations</th>
                  <th
                    className="py-1 text-right font-medium"
                    title="Stations with a connector rated 50 kW or higher"
                  >
                    DC-fast
                  </th>
                </tr>
              </thead>
              <tbody>
                {q.data.top_operators.map((o) => (
                  <tr key={o.operator} className="border-t border-rule">
                    <td className="py-1.5 font-data text-[13px]">{o.operator}</td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {o.stations.toLocaleString()}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] text-ink-muted tabular-nums">
                      {o.dc_fast.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              Source: Open Charge Map (crowd-sourced inventory). Our own network appears here on the
              same footing as every other — the comparison is scored by public rules, no
              special-casing (PLAN 6). Duplicates across sources are reconciled downstream, not at
              fetch.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function Figure({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <div className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div
        className={
          warn ? "bg-warn-ground px-1 font-data text-[15px] text-warn" : "font-data text-[15px]"
        }
      >
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}
