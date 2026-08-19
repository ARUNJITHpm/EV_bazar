import { formatRupeesCompact } from "../../lib/money";
import { formatPercentagePoints } from "../../lib/units";
import type { ReportPayload } from "./payload";

/**
 * Section 5 — the ROI engine re-run once per operator (OVERVIEW.md §8).
 * Financial rank and qualitative signals sit side by side and are never
 * blended into one score (PLAN 6). Our own network appears under the same
 * public rules as every other operator — the affiliation decision (OVERVIEW
 * §6.3) is surfaced, not hidden.
 */
export function CpoTable({ payload }: { payload: ReportPayload }) {
  return (
    <section data-report-section="cpo" className="border-b border-rule py-8">
      <h2 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        5 · Operator comparison
      </h2>
      <div className="overflow-x-auto">
        <table className="mt-4 w-full min-w-[38rem] border-t border-rule text-[13px]">
          <thead>
            <tr className="border-b border-rule text-left font-ui text-[11px] tracking-[0.08em] text-ink-muted uppercase">
              <th className="py-1.5 pr-4 font-bold">Operator</th>
              <th className="py-1.5 pr-4 text-right font-bold">Rev. share</th>
              <th className="py-1.5 pr-4 text-right font-bold">Platform fee</th>
              <th className="py-1.5 pr-4 text-right font-bold">IRR @ P50</th>
              <th className="py-1.5 pr-4 text-right font-bold">Margin @ P10</th>
              <th className="py-1.5 pr-4 font-bold">Uptime</th>
              <th className="py-1.5 font-bold">OCPI</th>
            </tr>
          </thead>
          <tbody>
            {payload.cpo.map((c) => (
              <tr key={c.operator} className="border-b border-rule">
                <td className="py-1.5 pr-4 font-text">
                  {c.operator}
                  {c.ours && (
                    <span className="ml-2 font-data text-[11px] text-ink-faint">(our network)</span>
                  )}
                </td>
                <td className="py-1.5 pr-4 text-right">{c.revenue_share_pct}%</td>
                <td className="py-1.5 pr-4 text-right">
                  {c.platform_fee_paise_year === 0
                    ? "₹0"
                    : `${formatRupeesCompact(c.platform_fee_paise_year)}/yr`}
                </td>
                <td className="py-1.5 pr-4 text-right">{c.irr_p50_pct}%</td>
                <td className="py-1.5 pr-4 text-right">
                  {formatPercentagePoints(c.margin_of_safety_pp)}
                </td>
                <td className="py-1.5 pr-4 font-data text-[12px] text-ink-faint">{c.uptime}</td>
                <td className="py-1.5 font-data text-[12px]">{c.ocpi_roaming ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1.5 max-w-[34rem] font-data text-[11px] text-ink-faint">
        financial rank and qualitative signals are shown side by side, never blended. our own
        network is scored by the same rules as every other operator. measured uptime fills in when
        the poller runs.{" "}
        <span className="bg-warn-ground px-1 text-warn">terms are placeholders — Part 6</span>
      </p>
    </section>
  );
}
