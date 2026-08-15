import { useQuery } from "@tanstack/react-query";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — VAHAN vehicle counts (PLAN 4.1).
 *
 * How many EVs each state and district holds, how fast that is growing, and the
 * split by vehicle class. Growth is the headline the panel leads with, because
 * PLAN 4.1 weights the year-on-year rate above the absolute count. Everything
 * reflects the latest snapshot; older snapshots live on as the series the growth
 * rate is drawn from.
 */

type StateRow = {
  lgd_state_code: number;
  state: string;
  districts: number;
  ev_total: number;
  growth_pct: number | null;
};
type DistrictRow = {
  lgd_district_code: number | null;
  district: string;
  state: string;
  ev_total: number;
  growth_pct: number | null;
};
type ClassRow = { group: string; ev_total: number };
type VahanOut = {
  checked_at: string;
  snapshot_date: string | null;
  periods: string[];
  display_period: string | null;
  total_rows: number;
  by_state: StateRow[];
  top_districts: DistrictRow[];
  by_class: ClassRow[];
};

function Growth({ pct }: { pct: number | null }) {
  if (pct === null)
    return (
      <span className="text-ink-faint" title="need two calendar years to compute">
        —
      </span>
    );
  const up = pct >= 0;
  return (
    <span className={up ? "text-ok" : "text-warn"}>
      {up ? "+" : ""}
      {(pct * 100).toFixed(0)}%
    </span>
  );
}

export function Vahan() {
  const q = useQuery({
    queryKey: ["vahan"],
    queryFn: async () => {
      const res = await fetch("/api/internal/vahan", { credentials: "include" });
      if (!res.ok) throw new Error(`vahan returned ${res.status}`);
      return (await res.json()) as VahanOut;
    },
  });

  return (
    <>
      <PanelHeader
        title="VAHAN vehicle counts"
        note="How many EVs are registered in each district, split by vehicle class, from the government's VAHAN dashboard. The demand layer's raw material — and the panel leads with GROWTH, not the absolute count, because a site is a bet on where EVs are going, not only where they are. Latest snapshot shown; every reading is kept so the growth rate has a series to stand on."
      />
      <Glossary terms={["VAHAN", "RTO", "Registration growth", "Snapshot", "LGD", "Tier"]} />

      {q.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read VAHAN data.
        </p>
      )}

      {q.data && q.data.total_rows === 0 && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Nothing ingested yet. Run <code>uv sync --extra scrape</code>, then{" "}
          <code>uv run python -m scripts.scrape_vahan --state kerala</code>, then{" "}
          <code>uv run python -m scripts.ingest_vahan --csv &lt;the CSV&gt; --write</code>.
        </p>
      )}

      {q.data && q.data.total_rows > 0 && (
        <>
          <section className="mb-8 flex max-w-3xl flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
            <Figure label="Snapshot" value={q.data.snapshot_date ?? "—"} />
            <Figure label="Showing year" value={q.data.display_period ?? "—"} />
            <Figure label="Years held" value={q.data.periods.join(", ") || "—"} />
            <Figure label="Rows" value={q.data.total_rows.toLocaleString()} />
          </section>

          <section className="mb-8 max-w-3xl">
            <SectionTitle>By state — EV registrations, newest year</SectionTitle>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">State</th>
                  <th className="py-1 text-right font-medium">Districts</th>
                  <th className="py-1 text-right font-medium">EV total</th>
                  <th className="py-1 text-right font-medium" title="year over year">
                    Growth
                  </th>
                </tr>
              </thead>
              <tbody>
                {q.data.by_state.map((s) => (
                  <tr key={s.lgd_state_code} className="border-t border-rule">
                    <td className="py-1.5 text-[13px]">{s.state}</td>
                    <td className="py-1.5 text-right font-data text-[13px] text-ink-muted tabular-nums">
                      {s.districts}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {s.ev_total.toLocaleString()}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      <Growth pct={s.growth_pct} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {q.data.by_class.length > 0 && (
            <section className="mb-8 max-w-3xl">
              <SectionTitle>By vehicle class — {q.data.display_period}</SectionTitle>
              <table className="w-full border-t border-rule text-left">
                <thead>
                  <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                    <th className="py-1 font-medium">Class</th>
                    <th className="py-1 text-right font-medium">EVs</th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.by_class.map((c) => (
                    <tr key={c.group} className="border-t border-rule">
                      <td className="py-1.5 text-[13px]">{c.group}</td>
                      <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                        {c.ev_total.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
                Buses and goods vehicles are kept, not dropped — an e-bus depot or a commercial
                fleet is among the largest charging anchors a district can have.
              </p>
            </section>
          )}

          <section className="max-w-3xl">
            <SectionTitle>Top districts — EV registrations, newest year</SectionTitle>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">District</th>
                  <th className="py-1 font-medium">State</th>
                  <th className="py-1 text-right font-medium">EV total</th>
                  <th className="py-1 text-right font-medium">Growth</th>
                </tr>
              </thead>
              <tbody>
                {q.data.top_districts.map((d) => (
                  <tr key={`${d.lgd_district_code}-${d.district}`} className="border-t border-rule">
                    <td className="py-1.5 text-[13px]">{d.district}</td>
                    <td className="py-1.5 text-[13px] text-ink-muted">{d.state}</td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      {d.ev_total.toLocaleString()}
                    </td>
                    <td className="py-1.5 text-right font-data text-[13px] tabular-nums">
                      <Growth pct={d.growth_pct} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              Source: VAHAN dashboard, scraped by our own fetcher. Counts are per RTO, each RTO's
              office resolved to its district via point-in-polygon. "—" growth means only one
              calendar year is loaded so far.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">{label}</div>
      <div className="font-data text-[15px]">{value}</div>
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
