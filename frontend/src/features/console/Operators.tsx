import { useQuery } from "@tanstack/react-query";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C.4b — operator selection. The other half of the CPO panel next door.
 *
 * `/console/cpo` answers *are we allowed to poll this network*: governance and
 * poll health, a source registry. This answers *whose chargers do we actually
 * hold, can we name them, and what still has to be built before the report can
 * recommend one operator over another*.
 *
 * It carries its own status block on purpose. Operator selection is half-built
 * — the counting works, the judging does not — and a panel that showed only
 * the working half would read as a finished feature. The standing record of
 * what is left is `CPO_SELECTION_PLAN.md` at the repo root; this panel is how
 * you find your way back to it.
 */

type OperatorRow = {
  canonical: string;
  ours: boolean;
  stations: number;
  raw_rows: number;
  dc_fast: number;
  districts: number;
  states: number;
};
type UnresolvedRow = { raw: string; rows: number };
type OperatorsOut = {
  checked_at: string;
  total_rows: number;
  resolved_rows: number;
  unattributed_rows: number;
  coverage_pct: number;
  canonical_known: number;
  operators: OperatorRow[];
  unresolved: UnresolvedRow[];
};

/** What is built, what is not, and where the rest is written down. Hand-kept:
 *  it is a note to a human, and it should be edited when a part lands. */
const STATE: { part: string; what: string; state: "live" | "open" | "blocked" }[] = [
  {
    part: "2.1 identity",
    what: "Raw feed names → one canonical network. app/domain/cpo/identity.py. No fuzzy tier: an unmatched name reports as unknown rather than being guessed onto a neighbour.",
    state: "live",
  },
  {
    part: "2.2 presence",
    what: "Per-site footprint per network — district, state, own within 3 km and 10 km. app/domain/cpo/presence.py. Source duplicates folded within ~55 m before counting.",
    state: "live",
  },
  {
    part: "6 · report 06",
    what: "Operator comparison carries the near count and one plain sentence per operator. The stored demo was regenerated on 2026-09-09 and carries them for real; what section 06 still drops is the repair-target and tie-in columns, which wait on 2.3 below.",
    state: "live",
  },
  {
    part: "2.3 cpo_terms",
    what: "Revenue share, platform fee, AMC, tenure, effective-dated. Until this exists every terms figure on the report is a placeholder and says so.",
    state: "blocked",
  },
  {
    part: "2.5 thresholds",
    what: "favours / neutral / against for the operator factors, printed in report section 03 BEFORE the site data. Needs numbers signed off; deliberately not invented.",
    state: "open",
  },
  {
    part: "7 · 8 uptime",
    what: "Measured uptime and observed occupancy at an operator's nearby stations. Blocked on the poller (PLAN 0.1) — no source is authorised with an endpoint, so it has never run.",
    state: "blocked",
  },
  {
    part: "4 · 5 public",
    what: "The landing section naming what decides the operator, and the fourth animation. Illustrative only; nothing there reads live data.",
    state: "live",
  },
];

const BADGE: Record<string, string> = {
  live: "bg-ok-ground text-ok",
  open: "bg-info-ground text-info",
  blocked: "bg-warn-ground text-warn",
};

export function Operators() {
  const q = useQuery({
    queryKey: ["operators"],
    queryFn: async () => {
      const res = await fetch("/api/internal/operators", { credentials: "include" });
      if (!res.ok) throw new Error(`operators returned ${res.status}`);
      return (await res.json()) as OperatorsOut;
    },
  });

  return (
    <>
      <PanelHeader
        title="Operators"
        note="Which network runs which chargers, and how much of the inventory we can put a name to. This is the input to the report's operator comparison: a station run by the operator you sign with splits your demand, and a rival's does not, so the same neighbour has to be counted once per operator."
      />
      <Glossary terms={["CPO", "OCPI", "Connector", "Occupancy"]} />

      <section className="mb-8 max-w-3xl border border-rule bg-ground-sunk px-3 py-2">
        <SectionTitle>Where operator selection stands</SectionTitle>
        <p className="mb-2 max-w-prose text-[12px] text-ink-muted">
          Half-built by design: the counting is live, the judging is not. The full part-by-part
          record is <code className="font-data">CPO_SELECTION_PLAN.md</code> at the repo root — a
          temporary file, to be folded into <code className="font-data">PLAN.md</code> Part 6 and
          deleted.
        </p>
        <dl>
          {STATE.map((s) => (
            <div key={s.part} className="border-t border-rule py-1.5">
              <dt className="flex items-baseline gap-2">
                <span className={`px-1 font-data text-[11px] ${BADGE[s.state]}`}>{s.state}</span>
                <span className="font-ui text-[13px]">{s.part}</span>
              </dt>
              <dd className="mt-0.5 max-w-prose text-[12px] text-ink-muted">{s.what}</dd>
            </div>
          ))}
        </dl>
      </section>

      {q.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read operators.
        </p>
      )}

      {q.data && (
        <>
          <section className="mb-8 flex max-w-3xl flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-2">
            <Figure label="Inventory rows" value={q.data.total_rows.toLocaleString()} />
            <Figure label="Named" value={`${q.data.coverage_pct}%`} />
            <Figure
              label="Unresolved names"
              value={q.data.unresolved.length.toLocaleString()}
              warn={q.data.unresolved.length > 0}
            />
            <Figure label="Unattributed rows" value={q.data.unattributed_rows.toLocaleString()} />
            <Figure label="Networks in the table" value={String(q.data.canonical_known)} />
          </section>

          <section className="mb-8 max-w-3xl">
            <SectionTitle>Networks we hold</SectionTitle>
            <table className="w-full border-t border-rule text-left">
              <thead>
                <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                  <th className="py-1 font-medium">Network</th>
                  <th className="py-1 text-right font-medium" title="After folding feed duplicates">
                    Stations
                  </th>
                  <th className="py-1 text-right font-medium" title="Rows before that fold">
                    Rows
                  </th>
                  <th className="py-1 text-right font-medium" title="50 kW or higher">
                    DC-fast
                  </th>
                  <th className="py-1 text-right font-medium">Districts</th>
                  <th className="py-1 text-right font-medium">States</th>
                </tr>
              </thead>
              <tbody>
                {q.data.operators.map((o) => (
                  <tr key={o.canonical} className="border-t border-rule">
                    <td className="py-1.5 font-data text-[13px]">
                      {o.canonical}
                      {o.ours && <span className="ml-2 text-[11px] text-ink-faint">ours</span>}
                    </td>
                    <Num v={o.stations} />
                    <Num v={o.raw_rows} muted />
                    <Num v={o.dc_fast} muted />
                    <Num v={o.districts} muted />
                    <Num v={o.states} muted />
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
              Stations is after folding records within ~55 m under one network — the same charger
              seen through Open Charge Map and through the operator&rsquo;s own feed is two rows by
              design. The gap between Stations and Rows is how much the two feeds overlap. Our own
              network sits here on the same footing as every other, in both directions (PLAN 6).
            </p>
          </section>

          <section className="max-w-3xl">
            <SectionTitle>Names we could not place</SectionTitle>
            {q.data.unresolved.length === 0 ? (
              <p className="max-w-prose text-[12px] text-ink-muted">
                None. Every attributed row in the inventory resolves to a known network. The{" "}
                {q.data.unattributed_rows.toLocaleString()} unattributed rows are ones the source
                itself declined to name — a fact about the feed, with nothing to fix here.
              </p>
            ) : (
              <>
                <table className="w-full border-t border-rule text-left">
                  <thead>
                    <tr className="font-ui text-[10px] tracking-[0.08em] text-ink-faint uppercase">
                      <th className="py-1 font-medium">Raw name</th>
                      <th className="py-1 text-right font-medium">Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.unresolved.map((u) => (
                      <tr key={u.raw} className="border-t border-rule">
                        <td className="py-1.5 font-data text-[13px]">{u.raw}</td>
                        <Num v={u.rows} />
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 max-w-prose font-data text-[11px] text-ink-faint">
                  Each of these is one line in <code>OPERATOR_ALIASES</code> (
                  <code>app/domain/cpo/identity.py</code>) once a human confirms which network it
                  is. Until then their stations are counted for nobody — reported as unknown, never
                  as zero. There is no fuzzy matcher here on purpose: nothing reviews an operator
                  name, and a near-miss would silently merge two networks.
                </p>
              </>
            )}
          </section>
        </>
      )}
    </>
  );
}

function Num({ v, muted = false }: { v: number; muted?: boolean }) {
  return (
    <td
      className={`py-1.5 text-right font-data text-[13px] tabular-nums ${
        muted ? "text-ink-muted" : ""
      }`}
    >
      {v.toLocaleString()}
    </td>
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
