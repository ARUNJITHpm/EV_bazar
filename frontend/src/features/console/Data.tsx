import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — what the database actually holds, and what follows from it.
 *
 * Two questions, one screen:
 *
 *   1. Which tables exist, how full are they, and what is each one FOR?
 *      An empty table here is normally a Part that has not shipped, so the row
 *      says which Part rather than reading as a fault.
 *   2. What can we honestly claim per state? The tier is derived live from the
 *      evidence that exists — never hardcoded, because a console that agrees
 *      with the plan instead of with the database is worse than no console.
 */

type TableRow = {
  table: string;
  group: string;
  rows: number;
  what: string;
  filled_by: string;
  empty_means: string | null;
};

type StateRow = {
  lgd_state_code: number;
  state: string;
  focus: boolean;
  districts: number;
  has_tariff_data: boolean;
  has_competitor_poll: boolean;
  has_vahan_data: boolean;
  has_osm_road_quality: boolean;
  tier: number;
  why: string;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return (await res.json()) as T;
}

export function Data() {
  const tables = useQuery({
    queryKey: ["lookup-tables"],
    queryFn: () =>
      get<{
        checked_at: string;
        tables: TableRow[];
        undocumented: string[];
        extension_tables: string[];
      }>("/api/internal/lookup/tables"),
  });

  const coverage = useQuery({
    queryKey: ["lookup-coverage"],
    queryFn: () =>
      get<{ rule: string; note: string; states: StateRow[] }>("/api/internal/lookup/coverage"),
  });

  const groups = [...new Set((tables.data?.tables ?? []).map((t) => t.group))];

  return (
    <>
      <PanelHeader
        title="Data"
        note="Every table in the database, how full it is, and what it is for in plain words. An empty table here is usually a Part that has not shipped yet, not a fault — the row says which one. Underneath: what all of that adds up to per state, as a tier derived from the evidence rather than declared."
      />
      <Glossary
        terms={[
          "Archive",
          "Change log",
          "Append-only",
          "Price card",
          "LGD",
          "Manual queue",
          "Tier",
        ]}
      />

      {/* --- tables -------------------------------------------------------- */}
      <section className="max-w-4xl">
        <SectionTitle>Tables</SectionTitle>

        {tables.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
        {tables.isError && (
          <p className="bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
            Could not read the table inventory.
          </p>
        )}

        {groups.map((group) => (
          <div key={group} className="mb-6">
            <h3 className="mb-1 font-ui text-[11px] text-ink-muted">{group}</h3>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">Table</th>
                  <th className="w-20 py-1 text-right font-medium">Rows</th>
                  <th className="py-1 font-medium">What it holds</th>
                  <th className="py-1 font-medium">Filled by</th>
                </tr>
              </thead>
              <tbody>
                {(tables.data?.tables ?? [])
                  .filter((t) => t.group === group)
                  .map((t) => (
                    <tr key={t.table} className="border-t border-rule align-top">
                      <td className="py-2 pr-3 font-data text-[12px]">{t.table}</td>
                      <td
                        className={cn(
                          "py-2 pr-3 text-right font-data text-[12px] tabular-nums",
                          t.rows === 0 && "text-ink-faint",
                        )}
                      >
                        {t.rows.toLocaleString()}
                      </td>
                      <td className="py-2 pr-3 text-[12px] text-ink-muted">
                        {t.what}
                        {t.empty_means && (
                          <span className="mt-1 block font-data text-[11px] text-ink-faint">
                            Empty: {t.empty_means}
                          </span>
                        )}
                      </td>
                      <td className="py-2 font-data text-[11px] text-ink-faint">{t.filled_by}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ))}

        {tables.data && tables.data.undocumented.length > 0 && (
          <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">
            In the database but not described above: {tables.data.undocumented.join(", ")}. Add it
            to <code>_TABLES</code> in <code>app/api/internal/lookup.py</code> — this list exists so
            that “every table is on this screen” stays true.
          </p>
        )}

        {tables.data && (
          <p className="max-w-prose font-data text-[11px] text-ink-faint">
            Also present: {tables.data.extension_tables.join(", ")} — owned by the PostGIS
            extension, not by us. Monthly partition children (
            <code>charger_status_events_2026_08</code> and friends) are folded into their parent
            above rather than listed separately.
          </p>
        )}
      </section>

      {/* --- tiers --------------------------------------------------------- */}
      <section className="mt-4 max-w-4xl">
        <SectionTitle>What we can honestly claim, per state</SectionTitle>

        {coverage.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
        {coverage.isError && (
          <p className="bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
            Could not read coverage.
          </p>
        )}

        {coverage.data && (
          <>
            <p className="mb-3 max-w-prose text-[13px] text-ink-muted">{coverage.data.rule}</p>
            <p className="mb-4 max-w-prose bg-warn-ground px-2 py-1 font-data text-[12px] text-warn">
              {coverage.data.note}
            </p>

            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">State / UT</th>
                  <th className="w-16 py-1 text-right font-medium">Districts</th>
                  <th className="w-16 py-1 text-center font-medium" title="PLAN 0.2">
                    Tariff
                  </th>
                  <th className="w-16 py-1 text-center font-medium" title="PLAN 0.1 — the poller">
                    Occupancy
                  </th>
                  <th className="w-16 py-1 text-center font-medium" title="PLAN 4.1">
                    VAHAN
                  </th>
                  <th className="w-16 py-1 text-center font-medium" title="PLAN 2.1">
                    Roads
                  </th>
                  <th className="w-14 py-1 text-center font-medium">Tier</th>
                </tr>
              </thead>
              <tbody>
                {coverage.data.states.map((s) => (
                  <tr
                    key={s.lgd_state_code}
                    className={cn("border-t border-rule", s.focus && "bg-info-ground")}
                  >
                    <td className="py-1.5 text-[13px]" title={s.why}>
                      {s.state}
                      {s.focus && (
                        <span className="ml-2 bg-info-ground px-1 font-ui text-[9px] tracking-[0.08em] text-info uppercase">
                          focus market
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 text-right font-data text-[12px] tabular-nums">
                      {s.districts}
                    </td>
                    <Flag on={s.has_tariff_data} />
                    <Flag on={s.has_competitor_poll} />
                    <Flag on={s.has_vahan_data} />
                    <Flag on={s.has_osm_road_quality} />
                    <td className="py-1.5 text-center">
                      <span
                        className={cn(
                          "px-1.5 font-data text-[12px]",
                          s.tier === 1
                            ? "bg-ok-ground text-ok"
                            : s.tier === 2
                              ? "bg-info-ground text-info"
                              : "bg-ground-sunk text-ink-faint",
                        )}
                      >
                        {s.tier}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              <span className="bg-ok-ground px-1 text-ok">1</span> full report ·{" "}
              <span className="bg-info-ground px-1 text-info">2</span> breakeven number and tariff
              audit only · <span className="bg-ground-sunk px-1">3</span> waitlist. A tier is OUR
              data coverage, not a city-size ranking — a state moves up when we load data for it,
              and all loading effort goes to the focus markets (Kerala, Tamil Nadu) first.
            </p>
            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              Tier 3 everywhere is the correct answer today, not a bug: three of the four evidence
              sources have no table yet. A Tier 2/3 customer is still logged as a site, and the
              count of pins per uncovered district is the expansion roadmap.
            </p>
          </>
        )}
      </section>
    </>
  );
}

function Flag({ on }: { on: boolean }) {
  return (
    <td className="py-1.5 text-center font-data text-[12px]">
      {on ? <span className="text-ok">yes</span> : <span className="text-ink-faint">—</span>}
    </td>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-2 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
      {children}
    </h2>
  );
}
