import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { formatUtilisation } from "../../lib/units";
import { DEMO_REPORT_ID, fetchReport, type Verdict } from "../report/payload";

/**
 * The public teaser (PLAN G.2): drop a pin, get breakeven utilisation in 30
 * seconds. Pure arithmetic — the certain number, sellable before any demand
 * model exists. Number first, verdict word small beneath it, same doctrine as
 * the report hero.
 *
 * This is the demo cut: the pin is fixed on the Kazhakkoottam sample site and
 * its numbers come from the same stored payload the report serves — one data
 * of record, two surfaces. The five customer taps are listed unanswered. The
 * interactive pin drop (Leaflet, lazy-loaded like Geocoding) arrives with
 * POST /assess; a teaser run will then be logged as a lead with its district —
 * outside KL/TN that becomes the waitlist signal, which is capture, not
 * failure (OVERVIEW.md §4).
 */

const VERDICT_LABEL: Record<Verdict, string> = {
  build: "Build",
  conditional: "Conditional",
  dont: "Don't build",
};
const VERDICT_INK: Record<Verdict, string> = {
  build: "text-verdict-build",
  conditional: "text-verdict-condition",
  dont: "text-verdict-dont",
};

export function Assess() {
  const q = useQuery({
    queryKey: ["report", DEMO_REPORT_ID],
    queryFn: () => fetchReport(DEMO_REPORT_ID),
    staleTime: Infinity,
  });

  return (
    <div className="mx-auto max-w-[52rem] px-6 py-12">
      <header className="flex items-baseline justify-between border-b-2 border-rule-strong pb-3">
        <p className="font-ui text-[13px] font-bold tracking-[0.08em] uppercase">
          EV Site Intelligence
        </p>
        <p className="font-data text-[11px] text-ink-faint">breakeven teaser · demo pin</p>
      </header>

      <h1 className="mt-8 max-w-[34rem] text-[1.125rem] leading-tight">
        Drop a pin. The utilisation this site must reach to break even — in 30 seconds, from
        arithmetic, before any model.
      </h1>

      {q.isPending && <p className="mt-8 font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="mt-8 max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          The demo report is not generated yet. Run{" "}
          <code>uv run python -m scripts.generate_demo_report --write</code>.
        </p>
      )}

      {q.data && (
        <div className="mt-8 border-y border-rule py-6">
          <p className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
            {q.data.site.name} · {q.data.site.district}
          </p>
          <p className="num mt-2 text-[2.75rem] leading-none font-bold">
            {formatUtilisation(q.data.breakeven.utilisation)}
          </p>
          <p className="num mt-1 text-[13px] text-ink-muted">
            breakeven utilisation · {q.data.hardware.connectors} × {q.data.hardware.rated_kw_each}{" "}
            kW DC · ≈ {q.data.breakeven.kwh_day} kWh/day
          </p>
          <p className="mt-3 font-ui text-[11px] tracking-[0.08em] uppercase">
            <span className="text-ink-muted">verdict · from P10 </span>
            <span className={`font-bold ${VERDICT_INK[q.data.verdict.value]}`}>
              {VERDICT_LABEL[q.data.verdict.value]}
            </span>
          </p>
        </div>
      )}

      <h2 className="mt-8 mb-3 border-b border-rule pb-2 font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        Five taps sharpen it — all unanswered, so archetype defaults apply
      </h2>
      <dl className="border-t border-rule">
        <TapRow label="Existing electricity connection?" />
        <TapRow label="Sanctioned load (kVA)?" />
        <TapRow label="Transformer on site?" />
        <TapRow label="Land owned or leased?" />
        <TapRow label="Budget band?" />
      </dl>

      <p className="mt-8">
        <Link
          to={`/report/${DEMO_REPORT_ID}`}
          className="font-ui text-[13px] underline underline-offset-4"
        >
          Full assessment for this pin →
        </Link>
      </p>
      <p className="mt-4 max-w-[34rem] font-data text-[11px] text-ink-faint">
        kerala &amp; tamil nadu today. a pin elsewhere joins the district waitlist — the queue
        decides which state's tariffs we load next.
      </p>
    </div>
  );
}

function TapRow({ label }: { label: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-rule py-1.5">
      <dt className="font-ui text-[13px] text-ink-muted">{label}</dt>
      <dd className="bg-warn-ground px-1 font-data text-[13px] text-warn">not provided ⚠</dd>
    </div>
  );
}
